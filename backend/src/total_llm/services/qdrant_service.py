from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Dict, List, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from total_llm.core.config import get_settings


class QdrantService:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = AsyncQdrantClient(
            host=settings.qdrant.host,
            port=settings.qdrant.port,
        )
        self.collection_name = settings.qdrant.collection_name
        self.vector_size = settings.qdrant.vector_size

    async def ensure_collection(self) -> None:
        collections = await self.client.get_collections()
        names = [c.name for c in collections.collections]
        if self.collection_name not in names:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )

    async def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        filter: Optional[Filter] = None,
    ) -> List[Dict]:
        results = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            query_filter=filter,
        )
        return [
            {
                "id": str(r.id),
                "text": (r.payload or {}).get("text", ""),
                "score": r.score,
                "metadata": {k: v for k, v in (r.payload or {}).items() if k != "text"},
            }
            for r in results.points
        ]

    async def upsert(
        self,
        texts: List[str],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict]] = None,
    ) -> None:
        points = []
        for i, (text, vec) in enumerate(zip(texts, vectors)):
            payload = {"text": text}
            if metadatas and i < len(metadatas):
                payload.update(metadatas[i])
            points.append(PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload))
        await self.client.upsert(collection_name=self.collection_name, points=points)

    async def scroll_all(self, limit: int = 10000):
        result = await self.client.scroll(
            collection_name=self.collection_name,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return result[0]

    async def retrieve(self, ids: List[str]):
        return await self.client.retrieve(collection_name=self.collection_name, ids=ids)

    async def delete_by_filter(self, key: str, value: str) -> int:
        points = await self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(must=[FieldCondition(key=key, match=MatchValue(value=value))]),
            limit=10000,
            with_payload=False,
            with_vectors=False,
        )
        ids = [p.id for p in points[0]]
        if ids:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=ids),
            )
        return len(ids)

    async def get_collection_info(self):
        return await self.client.get_collection(self.collection_name)


@lru_cache
def get_qdrant_service() -> QdrantService:
    return QdrantService()
