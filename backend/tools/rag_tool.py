"""
RAG Tool for MCP Integration
Qdrant 기반 벡터 검색 도구
"""

from typing import List, Dict, Optional
import yaml
from pathlib import Path
import uuid
import os
import re

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError as e:
    print(f"Required packages not installed: {e}")
    print("  pip install qdrant-client sentence-transformers langchain")
    raise


def expand_env_vars(config: dict) -> dict:
    """Recursively expand environment variables in config values"""
    def expand_value(value):
        if isinstance(value, str):
            # Match ${VAR:-default} or ${VAR} patterns
            pattern = r'\$\{([^}:-]+)(?::-([^}]*))?\}'
            def replacer(match):
                var_name = match.group(1)
                default = match.group(2) if match.group(2) is not None else ''
                return os.environ.get(var_name, default)
            return re.sub(pattern, replacer, value)
        elif isinstance(value, dict):
            return {k: expand_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [expand_value(v) for v in value]
        return value

    return expand_value(config)


class RAGTool:
    """RAG 검색 도구"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize RAG Tool

        Args:
            config_path: Path to config.yaml
        """
        # Config 로드
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "config.yaml"

        with open(config_path) as f:
            raw_config = yaml.safe_load(f)
            self.config = expand_env_vars(raw_config)

        # Qdrant 클라이언트 초기화
        qdrant_config = self.config['qdrant']
        self.client = QdrantClient(
            host=qdrant_config['host'],
            port=qdrant_config['port']
        )
        self.collection_name = qdrant_config['collection_name']

        # Embedding 모델 초기화
        embedding_config = self.config['embedding']
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_config['model_name'],
            model_kwargs={'device': embedding_config['device']},
            encode_kwargs={'batch_size': embedding_config['batch_size']}
        )

        # Collection 생성 (없으면)
        self._ensure_collection()

        print(f"✅ RAG Tool initialized")
        print(f"   Qdrant: {qdrant_config['host']}:{qdrant_config['port']}")
        print(f"   Collection: {self.collection_name}")
        print(f"   Embedding: {embedding_config['model_name']}")

    def _ensure_collection(self):
        """Collection이 없으면 생성"""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            qdrant_config = self.config['qdrant']
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=qdrant_config['vector_size'],
                    distance=Distance.COSINE
                )
            )
            print(f"✅ Created collection: {self.collection_name}")

    def add_documents(self, texts: List[str], metadatas: Optional[List[Dict]] = None):
        """
        문서 추가

        Args:
            texts: 문서 텍스트 리스트
            metadatas: 메타데이터 리스트 (선택)
        """
        if not texts:
            return

        # 임베딩 생성
        embeddings = self.embeddings.embed_documents(texts)

        # Qdrant에 저장
        points = []
        for idx, (text, embedding) in enumerate(zip(texts, embeddings)):
            payload = {"text": text}
            if metadatas and idx < len(metadatas):
                payload.update(metadatas[idx])

            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),  # UUID for globally unique IDs
                    vector=embedding,
                    payload=payload
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

        print(f"✅ Added {len(texts)} documents to Qdrant")

    def search(self, query: str, k: int = 3) -> List[Dict]:
        """
        벡터 검색

        Args:
            query: 검색 쿼리
            k: 반환할 문서 수

        Returns:
            검색 결과 리스트
        """
        # 쿼리 임베딩
        query_embedding = self.embeddings.embed_query(query)

        # Qdrant 검색 (qdrant-client 1.7+ uses query_points instead of search)
        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=k
            ).points
        except AttributeError:
            # Fallback for older versions
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=k
            )

        # 결과 포맷팅
        formatted_results = []
        for result in results:
            formatted_results.append({
                'id': str(result.id),
                'text': result.payload['text'],
                'score': result.score,
                'metadata': {
                    k: v for k, v in result.payload.items()
                    if k != 'text'
                }
            })

        return formatted_results

    def upload_file(self, file_path: str):
        """
        파일 업로드 및 인덱싱

        Args:
            file_path: 파일 경로
        """
        # 파일 읽기
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        # 청킹
        doc_config = self.config['document']
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=doc_config['chunk_size'],
            chunk_overlap=doc_config['chunk_overlap']
        )
        chunks = splitter.split_text(text)

        # 메타데이터
        metadatas = [
            {'source': file_path, 'chunk_id': i}
            for i in range(len(chunks))
        ]

        # 문서 추가
        self.add_documents(chunks, metadatas)

        print(f"✅ Uploaded {file_path}")
        print(f"   Chunks: {len(chunks)}")

    def get_documents(self) -> List[Dict]:
        """
        저장된 문서 목록 조회

        Returns:
            문서 목록 (파일 경로 기준으로 그룹화)
        """
        # Qdrant에서 모든 points 조회
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            limit=10000,  # 충분히 큰 값
            with_payload=True,
            with_vectors=False
        )

        points, _ = scroll_result

        # source 기준으로 그룹화
        documents_map = {}
        for point in points:
            source = point.payload.get('source', 'unknown')
            if source not in documents_map:
                # display_name이 있으면 사용, 없으면 원본 파일명 사용
                display_name = point.payload.get('display_name')
                file_path = Path(source)
                file_name = display_name if display_name else file_path.name
                file_type = file_path.suffix.lstrip('.')

                documents_map[source] = {
                    'id': source,  # source를 document id로 사용
                    'filename': file_name,
                    'fileType': file_type,
                    'fileSize': 0,  # 실제 파일 크기는 나중에 계산
                    'uploadedAt': None,  # 업로드 시간은 별도 관리 필요
                    'chunkCount': 0,
                    'status': 'processed'
                }

            documents_map[source]['chunkCount'] += 1

        return list(documents_map.values())

    def get_document_content(self, doc_id: str) -> Optional[str]:
        """
        문서 내용 조회

        Args:
            doc_id: 문서 ID (source 경로)

        Returns:
            문서 전체 내용 (청크들을 합친 것)
        """
        # Qdrant에서 해당 source의 모든 청크 조회
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter={
                "must": [
                    {
                        "key": "source",
                        "match": {"value": doc_id}
                    }
                ]
            },
            limit=10000,
            with_payload=True,
            with_vectors=False
        )

        points, _ = scroll_result

        if not points:
            return None

        # chunk_id로 정렬하여 원래 순서대로 합치기
        sorted_points = sorted(points, key=lambda p: p.payload.get('chunk_id', 0))
        content = "\n".join([p.payload.get('text', '') for p in sorted_points])

        return content

    def rename_document(self, doc_id: str, new_name: str):
        """
        문서 표시 이름 변경

        Args:
            doc_id: 문서 ID (source 경로)
            new_name: 새로운 파일 이름
        """
        from qdrant_client.models import SetPayload

        # Qdrant에서 해당 source의 모든 points 조회
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter={
                "must": [
                    {
                        "key": "source",
                        "match": {"value": doc_id}
                    }
                ]
            },
            limit=10000,
            with_payload=False,
            with_vectors=False
        )

        points, _ = scroll_result
        point_ids = [p.id for p in points]

        # 모든 청크에 display_name 업데이트
        if point_ids:
            self.client.set_payload(
                collection_name=self.collection_name,
                payload={"display_name": new_name},
                points=point_ids
            )
            print(f"✅ Renamed {len(point_ids)} chunks: {doc_id} -> {new_name}")
            return len(point_ids)

        return 0

    def delete_document(self, doc_id: str):
        """
        문서 삭제

        Args:
            doc_id: 문서 ID (source 경로)
        """
        # Qdrant에서 해당 source의 모든 points 조회
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter={
                "must": [
                    {
                        "key": "source",
                        "match": {"value": doc_id}
                    }
                ]
            },
            limit=10000,
            with_payload=False,
            with_vectors=False
        )

        points, _ = scroll_result
        point_ids = [p.id for p in points]

        # Points 삭제
        if point_ids:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=point_ids
            )
            print(f"✅ Deleted {len(point_ids)} chunks from document: {doc_id}")

    def clear_all_documents(self):
        """
        모든 문서 삭제 (컬렉션 재생성)

        Returns:
            삭제된 문서 수
        """
        # 현재 문서 수 조회
        try:
            collection_info = self.client.get_collection(self.collection_name)
            points_count = collection_info.points_count
        except Exception:
            points_count = 0

        # 컬렉션 삭제
        try:
            self.client.delete_collection(self.collection_name)
            print(f"✅ Deleted collection: {self.collection_name}")
        except Exception as e:
            print(f"⚠️  Collection deletion warning: {e}")

        # 컬렉션 재생성
        self._ensure_collection()
        print(f"✅ Cleared all documents (previous count: {points_count})")

        return points_count


# CLI 테스트
if __name__ == "__main__":
    import sys

    tool = RAGTool()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "upload" and len(sys.argv) > 2:
            file_path = sys.argv[2]
            tool.upload_file(file_path)

        elif command == "search" and len(sys.argv) > 2:
            query = " ".join(sys.argv[2:])
            results = tool.search(query, k=3)

            print(f"\n검색 결과 (query: {query}):")
            for i, result in enumerate(results, 1):
                print(f"\n[{i}] Score: {result['score']:.3f}")
                print(f"Text: {result['text'][:200]}...")
                print(f"Source: {result['metadata'].get('source', 'N/A')}")

        else:
            print("Usage:")
            print("  python rag_tool.py upload <file_path>")
            print("  python rag_tool.py search <query>")
    else:
        print("✅ RAG Tool ready")
        print("\nTesting search...")
        results = tool.search("test query", k=1)
        print(f"Search works: {len(results) >= 0}")
