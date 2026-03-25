from __future__ import annotations

from typing import Any, Dict, List, Tuple

from total_llm.core.config import get_settings
from total_llm.retrievers.bm25_indexer import BM25Indexer
from total_llm.retrievers.cross_encoder_reranker import CrossEncoderReranker
from total_llm.services.embedding_service import EmbeddingService, get_embedding_service
from total_llm.services.qdrant_service import QdrantService, get_qdrant_service


class HybridRetriever:
    def __init__(
        self,
        rag_tool: Any | None = None,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        k_multiplier: int = 3,
        enable_reranking: bool = True,
        reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        embedding_service: EmbeddingService | None = None,
        qdrant_service: QdrantService | None = None,
    ):
        settings = get_settings()
        self.rag_tool = rag_tool
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.k_multiplier = k_multiplier
        self.enable_reranking = enable_reranking

        self.embedding_service = embedding_service or get_embedding_service()
        self.qdrant_service = qdrant_service or get_qdrant_service()

        self.bm25_indexer = BM25Indexer(cache_path="data/bm25_index.pkl")

        self.reranker = None
        if enable_reranking:
            try:
                self.reranker = CrossEncoderReranker(
                    model_name=reranker_model,
                    device=settings.embedding.device,
                )
            except Exception:
                self.enable_reranking = False
                self.reranker = None

    async def sync_bm25_index(self) -> None:
        try:
            await self.qdrant_service.ensure_collection()
            points = await self.qdrant_service.scroll_all(limit=10000)
            documents = [
                {
                    "id": str(point.id),
                    "text": (point.payload or {}).get("text", ""),
                }
                for point in points
            ]
            if documents:
                await self.bm25_indexer.build_index(documents)
        except Exception:
            return

    def reciprocal_rank_fusion(
        self,
        vector_results: List[Dict],
        bm25_results: List[Tuple[str, float]],
        k: int,
        bm25_only_docs: Dict[str, Dict] | None = None,
    ) -> List[Dict]:
        K = 60
        rrf_scores: Dict[str, float] = {}
        doc_data: Dict[str, Dict] = {}

        for rank, doc in enumerate(vector_results, 1):
            doc_id = str(doc["id"])
            rrf_score = self.vector_weight / (K + rank)
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + rrf_score
            doc_data[doc_id] = doc

        bm25_only_docs = bm25_only_docs or {}
        for rank, (doc_id, _) in enumerate(bm25_results, 1):
            rrf_score = self.bm25_weight / (K + rank)
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + rrf_score
            if doc_id not in doc_data and doc_id in bm25_only_docs:
                doc_data[doc_id] = bm25_only_docs[doc_id]

        sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        final_results = []
        for doc_id, rrf_score in sorted_docs[:k]:
            if doc_id in doc_data:
                doc = doc_data[doc_id].copy()
                doc["rrf_score"] = float(rrf_score)
                final_results.append(doc)

        return final_results

    async def search(self, query: str, k: int = 5) -> List[Dict]:
        await self.qdrant_service.ensure_collection()
        k_retrieve = max(k * self.k_multiplier, k)

        query_embedding = await self.embedding_service.embed_query(query)
        vector_results = await self.qdrant_service.search(query_embedding, limit=k_retrieve)

        bm25_results = await self.bm25_indexer.search(query, k=k_retrieve)

        vector_ids = {str(doc["id"]) for doc in vector_results}
        bm25_only_ids = [doc_id for doc_id, _ in bm25_results if doc_id not in vector_ids]
        bm25_only_docs: Dict[str, Dict] = {}
        if bm25_only_ids:
            points = await self.qdrant_service.retrieve(bm25_only_ids)
            for point in points:
                payload = point.payload or {}
                bm25_only_docs[str(point.id)] = {
                    "id": str(point.id),
                    "text": payload.get("text", ""),
                    "score": 0.0,
                    "metadata": {k: v for k, v in payload.items() if k != "text"},
                }

        fused_results = self.reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            k=k_retrieve,
            bm25_only_docs=bm25_only_docs,
        )

        if self.enable_reranking and self.reranker:
            return await self.reranker.rerank(query, fused_results, top_k=k)

        return fused_results[:k]
