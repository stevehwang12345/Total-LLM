"""
Multi-Query Retriever - Parallel Search with Query Expansion

Expands queries and performs parallel search to improve coverage and recall.
"""

from typing import List, Dict, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from retrievers.query_expander import QueryExpander, RuleBasedQueryExpander
from retrievers.hybrid_retriever import HybridRetriever

logger = logging.getLogger(__name__)


class MultiQueryRetriever:
    """
    Multi-Query 검색기 (Query Expansion + Parallel Search + Aggregation)

    Process:
    1. Query Expansion: 원본 쿼리 → 다수의 변형 쿼리 생성
    2. Parallel Search: 모든 쿼리로 병렬 검색
    3. Result Aggregation: 결과 통합 및 중복 제거
    4. Re-ranking: 최종 점수 계산 및 정렬

    Benefits:
    - 모호한 쿼리 처리 개선
    - Recall 향상 (더 많은 관련 문서 발견)
    - 다양한 관점에서 검색
    """

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        query_expander: Optional[QueryExpander] = None,
        use_llm_expansion: bool = False,
        num_queries: int = 3,
        aggregation_method: str = "rrf"
    ):
        """
        Initialize Multi-Query Retriever

        Args:
            hybrid_retriever: HybridRetriever instance
            query_expander: QueryExpander instance (optional)
            use_llm_expansion: Use LLM for expansion (vs rule-based)
            num_queries: Number of query variations
            aggregation_method: How to aggregate results ("rrf", "max", "sum")
        """
        self.hybrid_retriever = hybrid_retriever
        self.num_queries = num_queries
        self.aggregation_method = aggregation_method

        # Initialize query expander
        if query_expander:
            self.query_expander = query_expander
        elif use_llm_expansion:
            try:
                self.query_expander = QueryExpander(num_queries=num_queries)
                logger.info("Using LLM-based query expansion")
            except Exception as e:
                logger.warning(f"LLM expansion failed, falling back to rule-based: {e}")
                self.query_expander = RuleBasedQueryExpander()
        else:
            self.query_expander = RuleBasedQueryExpander()
            logger.info("Using rule-based query expansion")

        print("✅ Multi-Query Retriever initialized")
        print(f"   Query expansion: {'LLM' if use_llm_expansion else 'Rule-based'}")
        print(f"   Num queries: {num_queries}")
        print(f"   Aggregation: {aggregation_method}")

    def search(self, query: str, k: int = 5) -> List[Dict]:
        """
        Multi-query 검색 수행

        Args:
            query: 원본 쿼리
            k: 최종 반환 문서 수

        Returns:
            통합된 검색 결과 리스트
        """
        # 1. Query Expansion
        expanded_queries = self.query_expander.expand(query, num_queries=self.num_queries)

        logger.info(f"Expanded 1 query → {len(expanded_queries)} queries")
        for i, q in enumerate(expanded_queries):
            logger.debug(f"  Query {i+1}: {q}")

        # 2. Parallel Search
        # Over-retrieve for better aggregation
        k_retrieve = k * 2

        all_results = self._parallel_search(expanded_queries, k_retrieve)

        # 3. Result Aggregation & Deduplication
        aggregated_results = self._aggregate_results(
            all_results,
            method=self.aggregation_method,
            k=k
        )

        logger.info(f"Aggregated {len(all_results)} result sets → {len(aggregated_results)} unique docs")

        return aggregated_results

    def _parallel_search(
        self,
        queries: List[str],
        k: int
    ) -> List[List[Dict]]:
        """
        병렬로 여러 쿼리 검색

        Args:
            queries: 쿼리 리스트
            k: 각 쿼리당 검색 개수

        Returns:
            각 쿼리의 검색 결과 리스트
        """
        results = []

        # Use ThreadPoolExecutor for parallel search
        with ThreadPoolExecutor(max_workers=min(len(queries), 5)) as executor:
            # Submit all search tasks
            future_to_query = {
                executor.submit(self.hybrid_retriever.search, query, k): query
                for query in queries
            }

            # Collect results as they complete
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.debug(f"Search completed for: {query[:50]}...")
                except Exception as e:
                    logger.error(f"Search failed for query '{query}': {e}")
                    results.append([])

        return results

    def _aggregate_results(
        self,
        result_sets: List[List[Dict]],
        method: str = "rrf",
        k: int = 5
    ) -> List[Dict]:
        """
        여러 검색 결과를 통합 및 중복 제거

        Args:
            result_sets: 각 쿼리의 검색 결과 리스트
            method: 통합 방법 ("rrf", "max", "sum")
            k: 최종 반환 개수

        Returns:
            통합된 문서 리스트
        """
        if method == "rrf":
            return self._aggregate_rrf(result_sets, k)
        elif method == "max":
            return self._aggregate_max(result_sets, k)
        elif method == "sum":
            return self._aggregate_sum(result_sets, k)
        else:
            raise ValueError(f"Unknown aggregation method: {method}")

    def _aggregate_rrf(
        self,
        result_sets: List[List[Dict]],
        k: int,
        K: int = 60
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion으로 결과 통합

        Args:
            result_sets: 각 쿼리의 검색 결과
            k: 최종 반환 개수
            K: RRF 상수

        Returns:
            RRF 점수로 정렬된 문서 리스트
        """
        doc_scores = defaultdict(float)
        doc_data = {}

        # Calculate RRF scores
        for result_set in result_sets:
            for rank, doc in enumerate(result_set, 1):
                doc_id = str(doc['id'])
                rrf_score = 1.0 / (K + rank)
                doc_scores[doc_id] += rrf_score

                # Store document data
                if doc_id not in doc_data:
                    doc_data[doc_id] = doc

        # Sort by aggregated RRF score
        sorted_docs = sorted(
            doc_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Build final results
        final_results = []
        for doc_id, score in sorted_docs[:k]:
            if doc_id in doc_data:
                doc = doc_data[doc_id].copy()
                doc['multi_query_score'] = score
                final_results.append(doc)

        return final_results

    def _aggregate_max(
        self,
        result_sets: List[List[Dict]],
        k: int
    ) -> List[Dict]:
        """
        최대 점수로 통합 (각 문서의 최고 점수 사용)

        Args:
            result_sets: 각 쿼리의 검색 결과
            k: 최종 반환 개수

        Returns:
            최대 점수로 정렬된 문서 리스트
        """
        doc_max_scores = {}
        doc_data = {}

        for result_set in result_sets:
            for doc in result_set:
                doc_id = str(doc['id'])
                score = doc.get('rerank_score', doc.get('rrf_score', doc.get('score', 0)))

                # Keep max score
                if doc_id not in doc_max_scores or score > doc_max_scores[doc_id]:
                    doc_max_scores[doc_id] = score
                    doc_data[doc_id] = doc

        # Sort by max score
        sorted_docs = sorted(
            doc_max_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Build final results
        final_results = []
        for doc_id, score in sorted_docs[:k]:
            doc = doc_data[doc_id].copy()
            doc['multi_query_score'] = score
            final_results.append(doc)

        return final_results

    def _aggregate_sum(
        self,
        result_sets: List[List[Dict]],
        k: int
    ) -> List[Dict]:
        """
        점수 합계로 통합 (문서가 여러 쿼리에서 나올수록 높은 점수)

        Args:
            result_sets: 각 쿼리의 검색 결과
            k: 최종 반환 개수

        Returns:
            점수 합계로 정렬된 문서 리스트
        """
        doc_sum_scores = defaultdict(float)
        doc_data = {}

        for result_set in result_sets:
            for doc in result_set:
                doc_id = str(doc['id'])
                score = doc.get('rerank_score', doc.get('rrf_score', doc.get('score', 0)))

                doc_sum_scores[doc_id] += score

                # Store document data
                if doc_id not in doc_data:
                    doc_data[doc_id] = doc

        # Sort by sum score
        sorted_docs = sorted(
            doc_sum_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Build final results
        final_results = []
        for doc_id, score in sorted_docs[:k]:
            doc = doc_data[doc_id].copy()
            doc['multi_query_score'] = score
            final_results.append(doc)

        return final_results


# Example usage and testing
if __name__ == "__main__":
    from tools.rag_tool import RAGTool

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 70)
    print("Multi-Query Retriever Testing")
    print("=" * 70)
    print()

    try:
        # Initialize components
        rag_tool = RAGTool()
        hybrid_retriever = HybridRetriever(
            rag_tool=rag_tool,
            enable_reranking=False  # Disable for faster testing
        )

        # Sync BM25 index
        hybrid_retriever.sync_bm25_index()

        # Initialize multi-query retriever
        multi_retriever = MultiQueryRetriever(
            hybrid_retriever=hybrid_retriever,
            use_llm_expansion=False,  # Use rule-based for testing
            num_queries=2,
            aggregation_method="rrf"
        )

        print()
        print("Test Query: What is machine learning?")
        print("-" * 70)

        # Perform search
        results = multi_retriever.search("What is machine learning?", k=3)

        print(f"\nResults: {len(results)} documents")
        for i, doc in enumerate(results, 1):
            score = doc.get('multi_query_score', 0)
            text = doc.get('text', '')[:100]
            print(f"\n{i}. Score: {score:.4f}")
            print(f"   {text}...")

        print("\n" + "=" * 70)
        print("✅ Multi-Query Retriever test completed!")
        print("=" * 70)

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
