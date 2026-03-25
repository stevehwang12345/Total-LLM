from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict, List, Optional

from total_llm.retrievers.hybrid_retriever import HybridRetriever
from total_llm.retrievers.query_expander import QueryExpander, RuleBasedQueryExpander


class MultiQueryRetriever:
    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        query_expander: Optional[QueryExpander] = None,
        use_llm_expansion: bool = False,
        num_queries: int = 3,
        aggregation_method: str = "rrf",
    ):
        self.hybrid_retriever = hybrid_retriever
        self.num_queries = num_queries
        self.aggregation_method = aggregation_method

        if query_expander:
            self.query_expander = query_expander
        elif use_llm_expansion:
            try:
                self.query_expander = QueryExpander(num_queries=num_queries)
            except Exception:
                self.query_expander = RuleBasedQueryExpander()
        else:
            self.query_expander = RuleBasedQueryExpander()

    async def search(self, query: str, k: int = 5) -> List[Dict]:
        expanded_queries = await asyncio.to_thread(self.query_expander.expand, query, self.num_queries)
        k_retrieve = max(k * 2, k)
        all_results = await self._parallel_search(expanded_queries, k_retrieve)
        return self._aggregate_results(all_results, method=self.aggregation_method, k=k)

    async def _parallel_search(self, queries: List[str], k: int) -> List[List[Dict]]:
        tasks = [self.hybrid_retriever.search(query, k) for query in queries]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        results: List[List[Dict]] = []
        for item in gathered:
            if isinstance(item, BaseException):
                results.append([])
            else:
                results.append(item)
        return results

    def _aggregate_results(
        self,
        result_sets: List[List[Dict]],
        method: str = "rrf",
        k: int = 5,
    ) -> List[Dict]:
        if method == "rrf":
            return self._aggregate_rrf(result_sets, k)
        if method == "max":
            return self._aggregate_max(result_sets, k)
        if method == "sum":
            return self._aggregate_sum(result_sets, k)
        raise ValueError(f"Unknown aggregation method: {method}")

    def _aggregate_rrf(self, result_sets: List[List[Dict]], k: int, K: int = 60) -> List[Dict]:
        doc_scores = defaultdict(float)
        doc_data: Dict[str, Dict] = {}

        for result_set in result_sets:
            for rank, doc in enumerate(result_set, 1):
                doc_id = str(doc["id"])
                doc_scores[doc_id] += 1.0 / (K + rank)
                if doc_id not in doc_data:
                    doc_data[doc_id] = doc

        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        final_results = []
        for doc_id, score in sorted_docs[:k]:
            if doc_id in doc_data:
                doc = doc_data[doc_id].copy()
                doc["multi_query_score"] = float(score)
                final_results.append(doc)
        return final_results

    def _aggregate_max(self, result_sets: List[List[Dict]], k: int) -> List[Dict]:
        doc_max_scores: Dict[str, float] = {}
        doc_data: Dict[str, Dict] = {}

        for result_set in result_sets:
            for doc in result_set:
                doc_id = str(doc["id"])
                score = float(doc.get("rerank_score", doc.get("rrf_score", doc.get("score", 0))))
                if doc_id not in doc_max_scores or score > doc_max_scores[doc_id]:
                    doc_max_scores[doc_id] = score
                    doc_data[doc_id] = doc

        sorted_docs = sorted(doc_max_scores.items(), key=lambda x: x[1], reverse=True)
        final_results = []
        for doc_id, score in sorted_docs[:k]:
            doc = doc_data[doc_id].copy()
            doc["multi_query_score"] = float(score)
            final_results.append(doc)
        return final_results

    def _aggregate_sum(self, result_sets: List[List[Dict]], k: int) -> List[Dict]:
        doc_sum_scores = defaultdict(float)
        doc_data: Dict[str, Dict] = {}

        for result_set in result_sets:
            for doc in result_set:
                doc_id = str(doc["id"])
                score = float(doc.get("rerank_score", doc.get("rrf_score", doc.get("score", 0))))
                doc_sum_scores[doc_id] += score
                if doc_id not in doc_data:
                    doc_data[doc_id] = doc

        sorted_docs = sorted(doc_sum_scores.items(), key=lambda x: x[1], reverse=True)
        final_results = []
        for doc_id, score in sorted_docs[:k]:
            doc = doc_data[doc_id].copy()
            doc["multi_query_score"] = float(score)
            final_results.append(doc)
        return final_results
