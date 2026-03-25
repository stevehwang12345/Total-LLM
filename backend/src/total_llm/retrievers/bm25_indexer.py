"""
BM25 Indexer for Keyword-based Search
BM25 알고리즘을 사용한 키워드 기반 검색
"""

from typing import List, Dict, Tuple
from rank_bm25 import BM25Okapi
import re
import pickle
from pathlib import Path


class BM25Indexer:
    """BM25 키워드 검색 인덱서"""

    def __init__(self, cache_path: str = None):
        """
        Initialize BM25 Indexer

        Args:
            cache_path: Path to save/load BM25 index cache
        """
        self.bm25 = None
        self.documents = []
        self.doc_ids = []
        self.cache_path = cache_path or "data/bm25_index.pkl"

        # 인덱스 캐시 로드 시도
        if Path(self.cache_path).exists():
            self.load_index()

    def tokenize(self, text: str) -> List[str]:
        """
        텍스트를 토큰으로 분할 (한글/영어 지원)

        Args:
            text: 입력 텍스트

        Returns:
            토큰 리스트
        """
        # 소문자 변환
        text = text.lower()

        # 한글, 영어, 숫자만 남기고 나머지는 공백으로
        text = re.sub(r'[^가-힣a-z0-9\s]', ' ', text)

        # 공백으로 분할
        tokens = text.split()

        return tokens

    def build_index(self, documents: List[Dict]):
        """
        문서 리스트로 BM25 인덱스 구축

        Args:
            documents: 문서 리스트 [{'id': str, 'text': str}, ...]
        """
        self.documents = documents
        self.doc_ids = [doc['id'] for doc in documents]

        # 문서 토큰화
        tokenized_docs = [self.tokenize(doc['text']) for doc in documents]

        # BM25 인덱스 생성
        self.bm25 = BM25Okapi(tokenized_docs)

        print(f"✅ BM25 index built: {len(documents)} documents")

        # 캐시 저장
        self.save_index()

    def add_documents(self, new_documents: List[Dict]):
        """
        새 문서를 기존 인덱스에 추가

        Args:
            new_documents: 추가할 문서 리스트
        """
        # 기존 문서에 추가
        self.documents.extend(new_documents)

        # 전체 인덱스 재구축 (BM25는 incremental update 미지원)
        self.build_index(self.documents)

    def search(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        """
        BM25 검색 수행

        Args:
            query: 검색 쿼리
            k: 반환할 결과 수

        Returns:
            [(doc_id, score), ...] 리스트 (score 내림차순)
        """
        if self.bm25 is None:
            print("⚠️  BM25 index not built yet")
            return []

        # 쿼리 토큰화
        query_tokens = self.tokenize(query)

        # BM25 스코어 계산
        scores = self.bm25.get_scores(query_tokens)

        # (doc_id, score) 튜플 생성
        doc_scores = list(zip(self.doc_ids, scores))

        # 점수 내림차순 정렬
        doc_scores.sort(key=lambda x: x[1], reverse=True)

        # Top-k 반환
        return doc_scores[:k]

    def save_index(self):
        """인덱스를 파일로 저장"""
        cache_dir = Path(self.cache_path).parent
        cache_dir.mkdir(parents=True, exist_ok=True)

        with open(self.cache_path, 'wb') as f:
            pickle.dump({
                'bm25': self.bm25,
                'documents': self.documents,
                'doc_ids': self.doc_ids
            }, f)

        print(f"✅ BM25 index saved to {self.cache_path}")

    def load_index(self):
        """저장된 인덱스 로드"""
        try:
            with open(self.cache_path, 'rb') as f:
                data = pickle.load(f)
                self.bm25 = data['bm25']
                self.documents = data['documents']
                self.doc_ids = data['doc_ids']

            print(f"✅ BM25 index loaded from {self.cache_path}")
            print(f"   Documents: {len(self.documents)}")
        except Exception as e:
            print(f"⚠️  Failed to load BM25 index: {e}")


# 테스트 코드
if __name__ == "__main__":
    print("=" * 60)
    print("BM25 Indexer Test")
    print("=" * 60)

    # 샘플 문서
    documents = [
        {"id": "doc1", "text": "Python은 프로그래밍 언어입니다. 간결하고 읽기 쉽습니다."},
        {"id": "doc2", "text": "JavaScript는 웹 개발에 사용됩니다. 동적인 웹 페이지를 만들 수 있습니다."},
        {"id": "doc3", "text": "Python과 JavaScript는 인기있는 프로그래밍 언어입니다."},
        {"id": "doc4", "text": "머신러닝에는 Python이 자주 사용됩니다. TensorFlow와 PyTorch가 유명합니다."},
        {"id": "doc5", "text": "웹 프론트엔드 개발에는 JavaScript가 필수입니다. React와 Vue가 인기있습니다."},
    ]

    # 인덱서 생성
    indexer = BM25Indexer(cache_path="/tmp/bm25_test.pkl")

    # 인덱스 구축
    indexer.build_index(documents)

    # 테스트 쿼리
    test_queries = [
        "Python 프로그래밍",
        "웹 개발 JavaScript",
        "머신러닝",
        "프로그래밍 언어",
    ]

    print("\n" + "=" * 60)
    print("Search Results")
    print("=" * 60)

    for query in test_queries:
        print(f"\n🔍 Query: {query}")
        results = indexer.search(query, k=3)

        for i, (doc_id, score) in enumerate(results, 1):
            # 문서 찾기
            doc = next(d for d in documents if d['id'] == doc_id)
            print(f"  {i}. {doc_id} (score: {score:.4f})")
            print(f"     {doc['text'][:60]}...")

    print("\n✅ BM25 Indexer test completed!")
