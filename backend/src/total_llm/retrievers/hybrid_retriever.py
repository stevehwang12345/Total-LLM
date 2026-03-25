"""
Hybrid Retriever - BM25 + Vector Search with RRF Fusion
BM25 키워드 검색과 Vector 의미 검색을 결합
"""

from typing import List, Dict, Tuple
from pathlib import Path

# Add parent directory to path

from total_llm.retrievers.bm25_indexer import BM25Indexer
from total_llm.retrievers.cross_encoder_reranker import CrossEncoderReranker
from total_llm.tools.rag_tool import RAGTool


class HybridRetriever:
    """하이브리드 검색기 (BM25 + Vector + Re-ranking)"""

    def __init__(
        self,
        rag_tool: RAGTool,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        k_multiplier: int = 3,
        enable_reranking: bool = True,
        reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ):
        """
        Initialize Hybrid Retriever

        Args:
            rag_tool: RAG 도구 (Vector 검색용)
            vector_weight: Vector 검색 가중치 (기본 0.7)
            bm25_weight: BM25 검색 가중치 (기본 0.3)
            k_multiplier: Over-retrieve 배수 (기본 3x)
            enable_reranking: Re-ranking 활성화 여부
            reranker_model: Cross-encoder 모델 이름
        """
        self.rag_tool = rag_tool
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.k_multiplier = k_multiplier
        self.enable_reranking = enable_reranking

        # BM25 인덱서 초기화
        self.bm25_indexer = BM25Indexer(
            cache_path="data/bm25_index.pkl"
        )

        # Cross-Encoder Re-ranker 초기화
        self.reranker = None
        if enable_reranking:
            try:
                self.reranker = CrossEncoderReranker(
                    model_name=reranker_model,
                    device="cpu"
                )
                print("✅ Cross-Encoder Re-ranker initialized")
            except Exception as e:
                print(f"⚠️ Failed to initialize re-ranker: {e}")
                print("   Continuing without re-ranking...")
                self.enable_reranking = False

        print("✅ Hybrid Retriever initialized")
        print(f"   Vector weight: {vector_weight}")
        print(f"   BM25 weight: {bm25_weight}")
        print(f"   Re-ranking: {'enabled' if self.enable_reranking else 'disabled'}")

    def sync_bm25_index(self):
        """
        Qdrant의 모든 문서로 BM25 인덱스 동기화
        문서 업로드 후 호출 필요
        """
        # Qdrant에서 모든 문서 가져오기
        from qdrant_client.models import Filter

        try:
            # 모든 문서 검색 (limit 크게)
            results = self.rag_tool.client.scroll(
                collection_name=self.rag_tool.collection_name,
                limit=10000  # 최대 10K 문서
            )

            documents = []
            for point in results[0]:
                documents.append({
                    'id': str(point.id),
                    'text': point.payload.get('text', '')
                })

            if documents:
                self.bm25_indexer.build_index(documents)
                print(f"✅ BM25 index synced: {len(documents)} documents")
            else:
                print("⚠️  No documents found in Qdrant")

        except Exception as e:
            print(f"❌ Failed to sync BM25 index: {e}")

    def reciprocal_rank_fusion(
        self,
        vector_results: List[Dict],
        bm25_results: List[Tuple[str, float]],
        k: int
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion (RRF)으로 결과 통합

        Args:
            vector_results: Vector 검색 결과 [{'id': str, 'score': float, 'text': str}, ...]
            bm25_results: BM25 검색 결과 [(doc_id, score), ...]
            k: 최종 반환 개수

        Returns:
            통합된 결과 리스트 (RRF 점수 내림차순)
        """
        # RRF 상수 (일반적으로 60 사용)
        K = 60

        # 문서별 RRF 점수 계산
        rrf_scores = {}
        doc_data = {}  # 문서 메타데이터 저장

        # Vector 검색 결과의 RRF 점수
        for rank, doc in enumerate(vector_results, 1):
            doc_id = str(doc['id'])
            rrf_score = self.vector_weight / (K + rank)
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + rrf_score
            doc_data[doc_id] = doc

        # BM25 검색 결과의 RRF 점수
        for rank, (doc_id, _) in enumerate(bm25_results, 1):
            rrf_score = self.bm25_weight / (K + rank)
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + rrf_score

            # BM25에만 있는 문서는 Qdrant에서 가져오기
            if doc_id not in doc_data:
                try:
                    point = self.rag_tool.client.retrieve(
                        collection_name=self.rag_tool.collection_name,
                        ids=[doc_id]
                    )
                    if point:
                        doc_data[doc_id] = {
                            'id': doc_id,
                            'text': point[0].payload.get('text', ''),
                            'score': 0.0  # BM25 only
                        }
                except:
                    pass

        # RRF 점수로 정렬
        sorted_docs = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Top-k 문서 반환
        final_results = []
        for doc_id, rrf_score in sorted_docs[:k]:
            if doc_id in doc_data:
                doc = doc_data[doc_id].copy()
                doc['rrf_score'] = rrf_score
                final_results.append(doc)

        return final_results

    def search(self, query: str, k: int = 5) -> List[Dict]:
        """
        하이브리드 검색 수행 (Vector + BM25 + RRF + Re-ranking)

        Args:
            query: 검색 쿼리
            k: 최종 반환 문서 수

        Returns:
            검색 결과 리스트 (re-rank 점수 내림차순)
        """
        # Over-retrieve (더 많이 검색 후 re-rank)
        k_retrieve = k * self.k_multiplier

        # 1. Vector 검색
        vector_results = self.rag_tool.search(query, k=k_retrieve)

        # 2. BM25 검색
        bm25_results = self.bm25_indexer.search(query, k=k_retrieve)

        # 3. RRF Fusion
        fused_results = self.reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            k=k_retrieve  # Re-ranking 전에는 더 많이 유지
        )

        # 4. Cross-Encoder Re-ranking (optional)
        if self.enable_reranking and self.reranker:
            final_results = self.reranker.rerank(
                query,
                fused_results,
                top_k=k
            )
        else:
            final_results = fused_results[:k]

        return final_results


# 테스트 코드
if __name__ == "__main__":
    print("=" * 60)
    print("Hybrid Retriever Test")
    print("=" * 60)

    # RAG Tool 초기화
    from total_llm.tools.rag_tool import RAGTool

    try:
        rag_tool = RAGTool()

        # Hybrid Retriever 생성
        hybrid = HybridRetriever(
            rag_tool=rag_tool,
            vector_weight=0.7,
            bm25_weight=0.3
        )

        # BM25 인덱스 동기화
        print("\n📊 Syncing BM25 index with Qdrant...")
        hybrid.sync_bm25_index()

        # 테스트 쿼리
        test_queries = [
            "Python 프로그래밍",
            "머신러닝 알고리즘",
            "웹 개발",
        ]

        print("\n" + "=" * 60)
        print("Hybrid Search Results")
        print("=" * 60)

        for query in test_queries:
            print(f"\n🔍 Query: {query}")
            results = hybrid.search(query, k=3)

            for i, doc in enumerate(results, 1):
                print(f"  {i}. ID: {doc['id']}")
                print(f"     RRF Score: {doc.get('rrf_score', 0):.4f}")
                print(f"     Text: {doc['text'][:60]}...")

        print("\n✅ Hybrid Retriever test completed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("   Make sure Qdrant is running and has documents")
