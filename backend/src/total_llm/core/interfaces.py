"""Protocol interfaces for core services."""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class RetrievalService(Protocol):
    """Interface for document retrieval services."""

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]: ...

    async def index_document(self, content: str, metadata: Dict[str, Any]) -> str: ...


@runtime_checkable
class AnalysisService(Protocol):
    """Interface for content analysis services (VLM, etc.)."""

    async def analyze(self, content: Any, **kwargs) -> Dict[str, Any]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Interface for embedding services."""

    async def embed_query(self, text: str) -> List[float]: ...

    async def embed_documents(self, texts: List[str]) -> List[List[float]]: ...


@runtime_checkable
class VectorStore(Protocol):
    """Interface for vector database operations."""

    async def search(self, query_vector: List[float], limit: int = 5) -> List[Dict]: ...

    async def upsert(
        self,
        texts: List[str],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict]] = None,
    ): ...


@runtime_checkable
class CacheProvider(Protocol):
    """Interface for caching services."""

    async def get(self, key: str) -> Optional[Any]: ...

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None: ...

    async def delete(self, key: str) -> None: ...


@runtime_checkable
class DeviceController(Protocol):
    """Interface for device control."""

    async def execute_command(self, device_id: str, command: str, **kwargs) -> Dict[str, Any]: ...

    async def get_status(self, device_id: str) -> Dict[str, Any]: ...
