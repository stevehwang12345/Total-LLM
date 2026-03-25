from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
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
from total_llm.services.embedding_service import get_embedding_service
from total_llm.services.qdrant_service import get_qdrant_service


class RAGTool:
    def __init__(self, config_path: Optional[str] = None):
        _ = config_path
        settings = get_settings()

        self.collection_name = settings.qdrant.collection_name
        self.vector_size = settings.qdrant.vector_size

        self.client = QdrantClient(host=settings.qdrant.host, port=settings.qdrant.port)
        self.qdrant_client = self.client
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding.model_name,
            model_kwargs={"device": settings.embedding.device},
            encode_kwargs={"batch_size": settings.embedding.batch_size},
        )

        self.embedding_service = get_embedding_service()
        self.qdrant_service = get_qdrant_service()

        self.config: Dict[str, Any] = {
            "qdrant": {
                "host": settings.qdrant.host,
                "port": settings.qdrant.port,
                "collection_name": settings.qdrant.collection_name,
                "logs_collection_name": settings.qdrant.logs_collection_name,
                "vector_size": settings.qdrant.vector_size,
            },
            "embedding": {
                "model_name": settings.embedding.model_name,
                "device": settings.embedding.device,
                "batch_size": settings.embedding.batch_size,
            },
            "document": {
                "chunk_size": settings.document.chunk_size,
                "chunk_overlap": settings.document.chunk_overlap,
            },
        }

        self._ensure_collection_sync()

    def _ensure_collection_sync(self) -> None:
        collections = self.client.get_collections().collections
        names = [c.name for c in collections]
        if self.collection_name not in names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )

    async def _ensure_collection_async(self) -> None:
        await self.qdrant_service.ensure_collection()

    def add_documents(self, texts: List[str], metadatas: Optional[List[Dict]] = None) -> None:
        if not texts:
            return

        embeddings = self.embeddings.embed_documents(texts)
        points = []
        for idx, (text, embedding) in enumerate(zip(texts, embeddings)):
            payload = {"text": text}
            if metadatas and idx < len(metadatas):
                payload.update(metadatas[idx])
            points.append(PointStruct(id=str(uuid.uuid4()), vector=embedding, payload=payload))

        self.client.upsert(collection_name=self.collection_name, points=points)

    async def add_documents_async(self, texts: List[str], metadatas: Optional[List[Dict]] = None) -> None:
        if not texts:
            return
        await self._ensure_collection_async()
        vectors = await self.embedding_service.embed_documents(texts)
        await self.qdrant_service.upsert(texts=texts, vectors=vectors, metadatas=metadatas)

    async def add_document(self, content: str, metadata: Dict[str, Any]) -> str:
        await self._ensure_collection_async()
        doc_id = str(uuid.uuid4())
        vector = await self.embedding_service.embed_query(content)
        payload = {"text": content}
        payload.update(metadata)
        await self.qdrant_service.client.upsert(
            collection_name=self.collection_name,
            points=[PointStruct(id=doc_id, vector=vector, payload=payload)],
        )
        return doc_id

    def search(self, query: str, k: int = 3) -> List[Dict]:
        query_embedding = self.embeddings.embed_query(query)
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=k,
        ).points
        return [
            {
                "id": str(result.id),
                "text": (result.payload or {}).get("text", ""),
                "score": float(result.score),
                "metadata": {m_key: m_val for m_key, m_val in (result.payload or {}).items() if m_key != "text"},
            }
            for result in results
        ]

    async def search_async(self, query: str, k: int = 3) -> List[Dict]:
        await self._ensure_collection_async()
        query_embedding = await self.embedding_service.embed_query(query)
        return await self.qdrant_service.search(query_vector=query_embedding, limit=k)

    def upload_file(self, file_path: str) -> None:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        doc_config = self.config["document"]
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=doc_config["chunk_size"],
            chunk_overlap=doc_config["chunk_overlap"],
        )
        chunks = splitter.split_text(text)
        metadatas = [{"source": file_path, "chunk_id": i} for i in range(len(chunks))]
        self.add_documents(chunks, metadatas)

    async def upload_file_async(self, file_path: str) -> None:
        text = await asyncio.to_thread(Path(file_path).read_text, encoding="utf-8")
        doc_config = self.config["document"]
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=doc_config["chunk_size"],
            chunk_overlap=doc_config["chunk_overlap"],
        )
        chunks = await asyncio.to_thread(splitter.split_text, text)
        metadatas = [{"source": file_path, "chunk_id": i} for i in range(len(chunks))]
        await self.add_documents_async(chunks, metadatas)

    def get_documents(self) -> List[Dict]:
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )

        documents_map: Dict[str, Dict[str, Any]] = {}
        for point in points:
            payload = point.payload or {}
            source = payload.get("source", "unknown")
            if source not in documents_map:
                display_name = payload.get("display_name")
                file_path = Path(source)
                file_name = display_name if display_name else file_path.name
                file_type = file_path.suffix.lstrip(".")
                documents_map[source] = {
                    "id": source,
                    "filename": file_name,
                    "fileType": file_type,
                    "fileSize": 0,
                    "uploadedAt": None,
                    "chunkCount": 0,
                    "status": "processed",
                }
            documents_map[source]["chunkCount"] += 1

        return list(documents_map.values())

    async def get_documents_async(self) -> List[Dict]:
        return await asyncio.to_thread(self.get_documents)

    def get_document_content(self, doc_id: str) -> Optional[str]:
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(must=[FieldCondition(key="source", match=MatchValue(value=doc_id))]),
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )

        if not points:
            return None

        sorted_points = sorted(points, key=lambda p: (p.payload or {}).get("chunk_id", 0))
        return "\n".join([(p.payload or {}).get("text", "") for p in sorted_points])

    async def get_document_content_async(self, doc_id: str) -> Optional[str]:
        return await asyncio.to_thread(self.get_document_content, doc_id)

    def rename_document(self, doc_id: str, new_name: str) -> int:
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(must=[FieldCondition(key="source", match=MatchValue(value=doc_id))]),
            limit=10000,
            with_payload=False,
            with_vectors=False,
        )
        point_ids = [p.id for p in points]

        if point_ids:
            self.client.set_payload(
                collection_name=self.collection_name,
                payload={"display_name": new_name},
                points=PointIdsList(points=point_ids),
            )
            return len(point_ids)

        return 0

    async def rename_document_async(self, doc_id: str, new_name: str) -> int:
        return await asyncio.to_thread(self.rename_document, doc_id, new_name)

    def delete_document(self, doc_id: str) -> None:
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(must=[FieldCondition(key="source", match=MatchValue(value=doc_id))]),
            limit=10000,
            with_payload=False,
            with_vectors=False,
        )
        point_ids = [p.id for p in points]
        if point_ids:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=point_ids),
            )

    async def delete_document_async(self, doc_id: str) -> None:
        await asyncio.to_thread(self.delete_document, doc_id)

    def clear_all_documents(self) -> int:
        try:
            collection_info = self.client.get_collection(self.collection_name)
            points_count = int(collection_info.points_count or 0)
        except Exception:
            points_count = 0

        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass

        self._ensure_collection_sync()
        return points_count

    async def clear_all_documents_async(self) -> int:
        return await asyncio.to_thread(self.clear_all_documents)
