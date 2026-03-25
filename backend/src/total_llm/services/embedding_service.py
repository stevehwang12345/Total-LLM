from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import List

from langchain_community.embeddings import HuggingFaceEmbeddings

from total_llm.core.config import get_settings


class EmbeddingService:

    def __init__(self) -> None:
        settings = get_settings()
        self._model = HuggingFaceEmbeddings(
            model_name=settings.embedding.model_name,
            model_kwargs={"device": settings.embedding.device},
            encode_kwargs={"batch_size": settings.embedding.batch_size},
        )

    async def embed_query(self, text: str) -> List[float]:
        return await asyncio.to_thread(self._model.embed_query, text)

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return await asyncio.to_thread(self._model.embed_documents, texts)

    def embed_query_sync(self, text: str) -> List[float]:
        return self._model.embed_query(text)

    def embed_documents_sync(self, texts: List[str]) -> List[List[float]]:
        return self._model.embed_documents(texts)


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
