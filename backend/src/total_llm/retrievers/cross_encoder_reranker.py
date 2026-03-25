from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional

import numpy as np
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str = "cpu",
        max_length: int = 512,
    ):
        self.model_name = model_name
        self.device = device
        self.max_length = max_length
        self.model = CrossEncoder(model_name, max_length=max_length, device=device)

    def rerank_sync(
        self,
        query: str,
        documents: List[Dict],
        top_k: Optional[int] = None,
    ) -> List[Dict]:
        if not documents:
            return []

        pairs = [[query, doc.get("text", "")] for doc in documents]
        try:
            scores = self.model.predict(pairs, show_progress_bar=False)
            if not isinstance(scores, np.ndarray):
                scores = np.array(scores)

            reranked_docs = []
            for idx, doc in enumerate(documents):
                doc_copy = doc.copy()
                doc_copy["rerank_score"] = float(scores[idx])
                doc_copy["original_score"] = float(doc.get("score", 0.0))
                reranked_docs.append(doc_copy)

            reranked_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
            if top_k is not None:
                return reranked_docs[:top_k]
            return reranked_docs
        except Exception as exc:
            logger.error("Re-ranking failed: %s", exc)
            return documents[:top_k] if top_k is not None else documents

    async def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: Optional[int] = None,
    ) -> List[Dict]:
        return await asyncio.to_thread(self.rerank_sync, query, documents, top_k)

    async def rerank_with_threshold(
        self,
        query: str,
        documents: List[Dict],
        threshold: float = 0.0,
        top_k: Optional[int] = None,
    ) -> List[Dict]:
        reranked = await self.rerank(query, documents, top_k=None)
        filtered = [doc for doc in reranked if doc.get("rerank_score", 0.0) >= threshold]
        if top_k is not None:
            return filtered[:top_k]
        return filtered

    def compute_score_sync(self, query: str, text: str) -> float:
        try:
            score = self.model.predict([[query, text]], show_progress_bar=False)
            return float(score[0])
        except Exception as exc:
            logger.error("Score computation failed: %s", exc)
            return 0.0

    async def compute_score(self, query: str, text: str) -> float:
        return await asyncio.to_thread(self.compute_score_sync, query, text)

    def batch_score_sync(self, query: str, texts: List[str], batch_size: int = 32) -> List[float]:
        if not texts:
            return []
        pairs = [[query, text] for text in texts]
        try:
            scores = self.model.predict(pairs, batch_size=batch_size, show_progress_bar=False)
            return [float(s) for s in scores]
        except Exception as exc:
            logger.error("Batch scoring failed: %s", exc)
            return [0.0] * len(texts)

    async def batch_score(self, query: str, texts: List[str], batch_size: int = 32) -> List[float]:
        return await asyncio.to_thread(self.batch_score_sync, query, texts, batch_size)
