from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


class LLMSettings(BaseAppSettings):
    provider: str = Field(default="vllm", validation_alias="VLLM_PROVIDER")
    base_url: str = Field(default="http://localhost:9000/v1", validation_alias="VLLM_BASE_URL")
    model_name: str = Field(
        default="Qwen/Qwen2.5-14B-Instruct-AWQ",
        validation_alias="VLLM_MODEL_NAME",
    )
    temperature: float = Field(default=0.7, validation_alias="VLLM_TEMPERATURE")
    max_tokens: int = Field(default=4096, validation_alias="VLLM_MAX_TOKENS")
    streaming: bool = Field(default=True, validation_alias="VLLM_STREAMING")
    gpu_device: int = Field(default=0, validation_alias="VLLM_GPU_DEVICE")


class VLMSettings(BaseAppSettings):
    provider: str = Field(default="vllm", validation_alias="VLM_PROVIDER")
    base_url: str = Field(default="http://localhost:9001/v1", validation_alias="VLM_BASE_URL")
    model_name: str = Field(
        default="Qwen/Qwen2.5-VL-7B-Instruct",
        validation_alias="VLM_MODEL_NAME",
    )
    temperature: float = Field(default=0.7, validation_alias="VLM_TEMPERATURE")
    max_tokens: int = Field(default=1024, validation_alias="VLM_MAX_TOKENS")
    max_image_size: int = Field(default=512, validation_alias="VLM_MAX_IMAGE_SIZE")
    jpeg_quality: int = Field(default=85, validation_alias="VLM_JPEG_QUALITY")
    simulation_mode: bool = Field(default=False, validation_alias="VLM_SIMULATION_MODE")


class EmbeddingSettings(BaseAppSettings):
    model_name: str = Field(default="dragonkue/bge-m3-ko", validation_alias="EMBEDDING_MODEL")
    device: str = Field(default="cpu", validation_alias="EMBEDDING_DEVICE")
    batch_size: int = Field(default=32, validation_alias="EMBEDDING_BATCH_SIZE")


class QdrantSettings(BaseAppSettings):
    host: str = Field(default="localhost", validation_alias="QDRANT_HOST")
    port: int = Field(default=6333, validation_alias="QDRANT_PORT")
    collection_name: str = Field(default="documents", validation_alias="QDRANT_COLLECTION")
    logs_collection_name: str = Field(default="security_logs", validation_alias="QDRANT_LOGS_COLLECTION")
    vector_size: int = Field(default=1024, validation_alias="QDRANT_VECTOR_SIZE")
    distance: str = Field(default="Cosine", validation_alias="QDRANT_DISTANCE")


class AdaptiveRAGSettings(BaseAppSettings):
    simple_threshold: float = Field(default=0.3, validation_alias="ADAPTIVE_SIMPLE_THRESHOLD")
    hybrid_threshold: float = Field(default=0.6, validation_alias="ADAPTIVE_HYBRID_THRESHOLD")
    simple_k: int = Field(default=3, validation_alias="ADAPTIVE_SIMPLE_K")
    hybrid_k: int = Field(default=5, validation_alias="ADAPTIVE_HYBRID_K")
    complex_k: int = Field(default=7, validation_alias="ADAPTIVE_COMPLEX_K")


class HybridSettings(BaseAppSettings):
    vector_weight: float = Field(default=0.7, validation_alias="HYBRID_VECTOR_WEIGHT")
    bm25_weight: float = Field(default=0.3, validation_alias="HYBRID_BM25_WEIGHT")
    k_multiplier: int = Field(default=3, validation_alias="HYBRID_K_MULTIPLIER")


class RerankingSettings(BaseAppSettings):
    enabled: bool = Field(default=True, validation_alias="RERANKING_ENABLED")
    model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        validation_alias="RERANKING_MODEL",
    )
    threshold: float = Field(default=0.0, validation_alias="RERANKING_THRESHOLD")


class MCPSettings(BaseAppSettings):
    enabled: bool = Field(default=True, validation_alias="MCP_ENABLED")
    servers: dict[str, Any] = Field(default_factory=dict)


class MultiQuerySettings(BaseAppSettings):
    use_llm: bool = Field(default=False, validation_alias="MULTI_QUERY_USE_LLM")
    num_queries: int = Field(default=3, validation_alias="MULTI_QUERY_NUM_QUERIES")
    aggregation: str = Field(default="rrf", validation_alias="MULTI_QUERY_AGGREGATION")


class DocumentSettings(BaseAppSettings):
    chunk_size: int = Field(default=512, validation_alias="DOCUMENT_CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, validation_alias="DOCUMENT_CHUNK_OVERLAP")
    supported_formats: list[str] = Field(default_factory=lambda: ["txt", "pdf", "md", "docx"])


class RedisCacheSettings(BaseAppSettings):
    enabled: bool = True
    ttl_seconds: int
    key_prefix: str


class RedisSettings(BaseAppSettings):
    host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    port: int = Field(default=6379, validation_alias="REDIS_PORT")
    db: int = Field(default=0, validation_alias="REDIS_DB")
    password: str = Field(default="", validation_alias="REDIS_PASSWORD")
    rag_cache: RedisCacheSettings = Field(
        default_factory=lambda: RedisCacheSettings(
            enabled=True,
            ttl_seconds=3600,
            key_prefix="rag:",
        )
    )
    conversation_cache: RedisCacheSettings = Field(
        default_factory=lambda: RedisCacheSettings(
            enabled=True,
            ttl_seconds=86400,
            key_prefix="conv:",
        )
    )


class DatabaseSettings(BaseAppSettings):
    host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    database: str = Field(default="total_llm", validation_alias="POSTGRES_DB")
    username: str = Field(default="total_llm", validation_alias="POSTGRES_USER")
    password: str = Field(default="total_llm_secret", validation_alias="POSTGRES_PASSWORD")
    pool_size: int = Field(default=10, validation_alias="POSTGRES_POOL_SIZE")
    max_overflow: int = Field(default=20, validation_alias="POSTGRES_MAX_OVERFLOW")


class KafkaSettings(BaseAppSettings):
    bootstrap_servers: list[str] = Field(
        default_factory=lambda: ["localhost:9092"],
        validation_alias="KAFKA_BOOTSTRAP_SERVERS",
    )
    topic: str = Field(default="security.alarms", validation_alias="KAFKA_TOPIC")
    group_id: str = Field(default="vllm-security-monitoring", validation_alias="KAFKA_GROUP_ID")

    @field_validator("bootstrap_servers", mode="before")
    @classmethod
    def parse_bootstrap_servers(cls, value: Any) -> list[str] | Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class AlarmImageSettings(BaseAppSettings):
    storage_path: str = Field(
        default="/home/sphwang/dev/vLLM/data/alarms",
        validation_alias="ALARM_IMAGES_PATH",
    )
    retention_days: int = Field(default=30, validation_alias="ALARM_RETENTION_DAYS")


class ReportsSettings(BaseAppSettings):
    storage_path: str = Field(
        default="/home/sphwang/dev/vLLM/data/reports",
        validation_alias="REPORT_PATH",
    )


class SecurityDeviceControlSettings(BaseAppSettings):
    rollback_timeout_seconds: int = Field(default=10, validation_alias="ROLLBACK_TIMEOUT_SECONDS")
    max_retry_attempts: int = Field(default=3, validation_alias="MAX_RETRY_ATTEMPTS")


class SecuritySettings(BaseAppSettings):
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    alarm_images: AlarmImageSettings = Field(default_factory=AlarmImageSettings)
    reports: ReportsSettings = Field(default_factory=ReportsSettings)
    device_control: SecurityDeviceControlSettings = Field(default_factory=SecurityDeviceControlSettings)


class DeviceControlSimulationSettings(BaseAppSettings):
    enabled: bool = True
    response_delay_ms: int = 100


class DeviceControlRealSettings(BaseAppSettings):
    connection_timeout: int = 10
    command_timeout: int = 30
    retry_count: int = 3
    retry_delay: int = 1


class DeviceControlHybridSettings(BaseAppSettings):
    prefer_real: bool = True
    fallback_to_simulation: bool = True


class OnvifAdapterSettings(BaseAppSettings):
    wsdl_cache: bool = True
    discovery_timeout: int = 5


class HanwhaAdapterSettings(BaseAppSettings):
    api_version: str = "v2"


class HikvisionAdapterSettings(BaseAppSettings):
    use_digest_auth: bool = True


class ZktecoAdapterSettings(BaseAppSettings):
    sdk_path: str = ""


class SupremaAdapterSettings(BaseAppSettings):
    api_version: str = "2.8"


class DeviceControlAdaptersSettings(BaseAppSettings):
    onvif: OnvifAdapterSettings = Field(default_factory=OnvifAdapterSettings)
    hanwha: HanwhaAdapterSettings = Field(default_factory=HanwhaAdapterSettings)
    hikvision: HikvisionAdapterSettings = Field(default_factory=HikvisionAdapterSettings)
    zkteco: ZktecoAdapterSettings = Field(default_factory=ZktecoAdapterSettings)
    suprema: SupremaAdapterSettings = Field(default_factory=SupremaAdapterSettings)


class DeviceControlSettings(BaseAppSettings):
    default_mode: str = "hybrid"
    simulation: DeviceControlSimulationSettings = Field(default_factory=DeviceControlSimulationSettings)
    real: DeviceControlRealSettings = Field(default_factory=DeviceControlRealSettings)
    hybrid: DeviceControlHybridSettings = Field(default_factory=DeviceControlHybridSettings)
    adapters: DeviceControlAdaptersSettings = Field(default_factory=DeviceControlAdaptersSettings)


class APISettings(BaseAppSettings):
    host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    port: int = Field(default=9002, validation_alias="API_PORT")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:9004"],
        validation_alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str] | Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


class AuthSettings(BaseAppSettings):
    jwt_secret_key: str = Field(default="change-me", validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=30, validation_alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")


class PathsSettings(BaseAppSettings):
    data_path: str = Field(default="/app/data", validation_alias="DATA_PATH")
    upload_path: str = Field(default="/app/data/uploads", validation_alias="UPLOAD_PATH")
    log_path: str = Field(default="/app/logs", validation_alias="LOG_PATH")


class Settings(BaseAppSettings):
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")

    llm: LLMSettings = Field(default_factory=LLMSettings)
    vlm: VLMSettings = Field(default_factory=VLMSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    adaptive: AdaptiveRAGSettings = Field(default_factory=AdaptiveRAGSettings)
    hybrid: HybridSettings = Field(default_factory=HybridSettings)
    reranking: RerankingSettings = Field(default_factory=RerankingSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    multi_query: MultiQuerySettings = Field(default_factory=MultiQuerySettings)
    document: DocumentSettings = Field(default_factory=DocumentSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    device_control: DeviceControlSettings = Field(default_factory=DeviceControlSettings)
    api: APISettings = Field(default_factory=APISettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    device_credential_key: str = Field(default="", validation_alias="DEVICE_CREDENTIAL_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
