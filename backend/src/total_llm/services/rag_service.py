from __future__ import annotations

import logging
from importlib import import_module
from typing import Any, Dict, List, Optional

from total_llm.retrievers.adaptive_retriever import AdaptiveRetriever
from total_llm.services.cache_service import CacheService, get_cache_service

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self, config_path: Optional[str] = None, cache_service: Optional[CacheService] = None):
        _ = config_path
        self.retriever = AdaptiveRetriever()
        rag_graph_module = import_module("total_llm.services.rag_graph")
        self.rag_graph = rag_graph_module.AdaptiveRAGGraph(self.retriever)

        self._cache_service = cache_service
        self._cache_initialized = False

    async def _get_cache(self) -> Optional[CacheService]:
        if not self._cache_initialized:
            try:
                self._cache_service = await get_cache_service()
            except Exception as exc:
                logger.warning("Cache service initialization failed: %s", exc)
            finally:
                self._cache_initialized = True

        return self._cache_service

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, str]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        cache = await self._get_cache() if use_cache else None
        retriever_type = "adaptive"

        if cache:
            cached_result = await cache.get_rag_cache(query, retriever_type, filter_metadata)
            if cached_result:
                cached_result["documents"] = cached_result.get("documents", [])[:top_k]
                cached_result["cached"] = True
                return cached_result

        try:
            result = await self.rag_graph.ainvoke(
                query=query,
                top_k=top_k,
                filter_metadata=filter_metadata,
            )
        except Exception as exc:
            logger.error("RAG graph execution failed: %s", exc)
            result = {
                "query": query,
                "complexity": {},
                "strategy": "fallback",
                "documents": [],
                "k": top_k,
                "error": str(exc),
            }

        documents = result.get("documents", [])
        strategy = result.get("strategy", "unknown")

        formatted_documents = [
            {
                "content": doc.get("content", doc.get("text", "")),
                "metadata": doc.get("metadata", {}),
                "score": float(doc.get("score", doc.get("rrf_score", doc.get("rerank_score", 0.0)))),
            }
            for doc in documents
        ]

        result_data = {
            "documents": formatted_documents[:top_k],
            "strategy": strategy,
            "cached": False,
            "complexity": result.get("complexity", {}),
            "error": result.get("error"),
        }

        if cache and formatted_documents:
            await cache.set_rag_cache(
                query=query,
                result=result_data,
                retriever_type=retriever_type,
                filter_metadata=filter_metadata,
            )

        return result_data

    async def search_simple(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        result = await self.search(query, top_k, filter_metadata)
        return result.get("documents", [])

    async def index_document(self, content: str, metadata: Dict[str, Any]) -> str:
        rag_tool = self.retriever.rag_tool
        doc_id = await rag_tool.add_document(content, metadata)
        return doc_id

    async def get_collection_stats(self) -> Dict[str, Any]:
        rag_tool = self.retriever.rag_tool
        stats = {
            "collection_name": rag_tool.collection_name,
            "vector_size": rag_tool.vector_size,
            "total_documents": 0,
        }

        try:
            info = await rag_tool.qdrant_service.get_collection_info()
            stats["total_documents"] = int(info.points_count or 0)
        except Exception as exc:
            logger.warning("Failed to get collection stats: %s", exc)

        try:
            cache = await self._get_cache()
            if cache:
                stats["cache_stats"] = await cache.get_cache_stats()
        except Exception as exc:
            logger.warning("Failed to get cache stats: %s", exc)

        return stats

    async def invalidate_cache(self, pattern: str = "*") -> int:
        try:
            cache = await self._get_cache()
            if cache:
                return await cache.invalidate_rag_cache(pattern)
            return 0
        except Exception as exc:
            logger.warning("Failed to invalidate cache: %s", exc)
            return 0
