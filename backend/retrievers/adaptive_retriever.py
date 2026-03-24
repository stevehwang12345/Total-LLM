"""
Adaptive Retriever
쿼리 복잡도에 따라 다른 검색 전략 사용
"""

from typing import List, Dict
import yaml
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from core.complexity_analyzer import ComplexityAnalyzer
from tools.rag_tool import RAGTool
from retrievers.hybrid_retriever import HybridRetriever
from retrievers.multi_query_retriever import MultiQueryRetriever


class AdaptiveRetriever:
    """복잡도 기반 Adaptive 검색"""

    def __init__(self, config_path: str = None):
        """
        Initialize Adaptive Retriever

        Args:
            config_path: Path to config.yaml
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "config.yaml"

        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # 복잡도 분석기
        self.analyzer = ComplexityAnalyzer()

        # RAG 도구
        self.rag_tool = RAGTool(config_path)

        # Hybrid Retriever 초기화
        hybrid_config = self.config.get('hybrid', {})
        reranking_config = self.config.get('reranking', {})
        self.hybrid_retriever = HybridRetriever(
            rag_tool=self.rag_tool,
            vector_weight=hybrid_config.get('vector_weight', 0.7),
            bm25_weight=hybrid_config.get('bm25_weight', 0.3),
            k_multiplier=hybrid_config.get('k_multiplier', 3),
            enable_reranking=reranking_config.get('enabled', True),
            reranker_model=reranking_config.get('model', 'cross-encoder/ms-marco-MiniLM-L-6-v2')
        )

        # BM25 인덱스 동기화
        try:
            self.hybrid_retriever.sync_bm25_index()
        except Exception as e:
            print(f"⚠️  BM25 index sync failed: {e}")

        # Multi-Query Retriever 초기화
        multi_query_config = self.config.get('multi_query', {})
        self.multi_query_retriever = MultiQueryRetriever(
            hybrid_retriever=self.hybrid_retriever,
            use_llm_expansion=multi_query_config.get('use_llm', False),
            num_queries=multi_query_config.get('num_queries', 3),
            aggregation_method=multi_query_config.get('aggregation', 'rrf')
        )

        # Adaptive 설정
        self.adaptive_config = self.config['adaptive']

        print("✅ Adaptive Retriever initialized")

    def retrieve(self, query: str) -> Dict:
        """
        쿼리에 따라 적절한 검색 전략 선택 및 실행

        Args:
            query: 사용자 쿼리

        Returns:
            {
                'query': str,
                'complexity': dict,
                'strategy': str,
                'documents': List[dict],
                'k': int
            }
        """
        # 1. 복잡도 분석
        complexity = self.analyzer.analyze(query)
        category = complexity['category']

        # 2. 전략 선택 및 k 값 결정
        if category == 'simple':
            strategy = 'simple_vector'
            k = self.adaptive_config['simple_k']
        elif category == 'hybrid':
            strategy = 'hybrid_search'
            k = self.adaptive_config['hybrid_k']
        else:  # complex
            strategy = 'multi_query'
            k = self.adaptive_config['complex_k']

        # 3. 검색 실행
        if strategy == 'simple_vector':
            documents = self._simple_search(query, k)
        elif strategy == 'hybrid_search':
            documents = self._hybrid_search(query, k)
        else:  # multi_query
            documents = self._multi_query_search(query, k)

        return {
            'query': query,
            'complexity': complexity,
            'strategy': strategy,
            'documents': documents,
            'k': k
        }

    def _simple_search(self, query: str, k: int) -> List[Dict]:
        """
        단순 벡터 검색

        Args:
            query: 검색 쿼리
            k: 반환 문서 수

        Returns:
            검색 결과
        """
        return self.rag_tool.search(query, k=k)

    def _hybrid_search(self, query: str, k: int) -> List[Dict]:
        """
        하이브리드 검색 (BM25 + Vector with RRF)

        Args:
            query: 검색 쿼리
            k: 반환 문서 수

        Returns:
            검색 결과
        """
        # Hybrid Retriever 사용 (BM25 + Vector + RRF)
        return self.hybrid_retriever.search(query, k=k)

    def _multi_query_search(self, query: str, k: int) -> List[Dict]:
        """
        다중 쿼리 검색 (쿼리 확장 + 병렬 검색 + 결과 통합)

        Args:
            query: 검색 쿼리
            k: 반환 문서 수

        Returns:
            통합된 검색 결과
        """
        # Multi-Query Retriever 사용
        # 1. 쿼리 확장 (LLM 또는 Rule-based)
        # 2. 병렬 검색
        # 3. 결과 통합 (RRF)
        return self.multi_query_retriever.search(query, k=k)


# 테스트
if __name__ == "__main__":
    retriever = AdaptiveRetriever()

    test_queries = [
        "안녕",
        "Python이 뭐야?",
        "Python과 JavaScript의 차이점을 상세히 설명해줘",
    ]

    print("\n" + "=" * 60)
    print("Adaptive Retriever Test")
    print("=" * 60)

    for query in test_queries:
        print(f"\n검색: {query}")
        result = retriever.retrieve(query)

        print(f"  복잡도: {result['complexity']['score']} ({result['complexity']['category']})")
        print(f"  전략: {result['strategy']}")
        print(f"  k: {result['k']}")
        print(f"  결과: {len(result['documents'])} 문서")

        if result['documents']:
            print(f"  Top 1: {result['documents'][0]['text'][:100]}...")
