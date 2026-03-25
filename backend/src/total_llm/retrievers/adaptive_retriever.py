from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from total_llm.core.complexity_analyzer import ComplexityAnalyzer
from total_llm.core.config import get_settings
from total_llm.retrievers.hybrid_retriever import HybridRetriever
from total_llm.retrievers.multi_query_retriever import MultiQueryRetriever
from total_llm.services.embedding_service import EmbeddingService, get_embedding_service
from total_llm.services.qdrant_service import QdrantService, get_qdrant_service
from total_llm.tools.rag_tool import RAGTool


class AdaptiveRetriever:
    def __init__(
        self,
        config_path: str | None = None,
        embedding_service: EmbeddingService | None = None,
        qdrant_service: QdrantService | None = None,
    ):
        _ = config_path
        settings = get_settings()

        self.analyzer = ComplexityAnalyzer()
        self.embedding_service = embedding_service or get_embedding_service()
        self.qdrant_service = qdrant_service or get_qdrant_service()

        self.rag_tool = RAGTool()

        self.hybrid_retriever = HybridRetriever(
            rag_tool=self.rag_tool,
            vector_weight=settings.hybrid.vector_weight,
            bm25_weight=settings.hybrid.bm25_weight,
            k_multiplier=settings.hybrid.k_multiplier,
            enable_reranking=settings.reranking.enabled,
            reranker_model=settings.reranking.model,
            embedding_service=self.embedding_service,
            qdrant_service=self.qdrant_service,
        )

        self.multi_query_retriever = MultiQueryRetriever(
            hybrid_retriever=self.hybrid_retriever,
            use_llm_expansion=settings.multi_query.use_llm,
            num_queries=settings.multi_query.num_queries,
            aggregation_method=settings.multi_query.aggregation,
        )

        self.adaptive_config = settings.adaptive

    async def warmup(self) -> None:
        await self.qdrant_service.ensure_collection()
        await self.hybrid_retriever.sync_bm25_index()

    async def retrieve(self, query: str) -> Dict[str, Any]:
        complexity = self.analyzer.analyze(query)
        category = complexity["category"]

        if category == "simple":
            strategy = "simple_vector"
            k = self.adaptive_config.simple_k
        elif category == "hybrid":
            strategy = "hybrid_search"
            k = self.adaptive_config.hybrid_k
        else:
            strategy = "multi_query"
            k = self.adaptive_config.complex_k

        if strategy == "simple_vector":
            documents = await self._simple_search(query, k)
        elif strategy == "hybrid_search":
            documents = await self._hybrid_search(query, k)
        else:
            documents = await self._multi_query_search(query, k)

        return {
            "query": query,
            "complexity": complexity,
            "strategy": strategy,
            "documents": documents,
            "k": k,
        }

    def retrieve_sync(self, query: str) -> Dict[str, Any]:
        return self._run_async(self.retrieve(query))

    async def _simple_search(self, query: str, k: int) -> List[Dict]:
        await self.qdrant_service.ensure_collection()
        query_embedding = await self.embedding_service.embed_query(query)
        return await self.qdrant_service.search(query_embedding, limit=k)

    async def _hybrid_search(self, query: str, k: int) -> List[Dict]:
        return await self.hybrid_retriever.search(query, k=k)

    async def _multi_query_search(self, query: str, k: int) -> List[Dict]:
        return await self.multi_query_retriever.search(query, k=k)

    @staticmethod
    def _run_async(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        raise RuntimeError("Cannot run sync retrieve while an event loop is active")
