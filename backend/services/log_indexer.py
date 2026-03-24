#!/usr/bin/env python3
"""
Log Indexer Service

Fluentd로부터 수신한 로그를 Qdrant에 인덱싱하는 서비스
"""

import asyncpg
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from tools.rag_tool import RAGTool

logger = logging.getLogger(__name__)


class LogIndexer:
    """
    로그 인덱싱 서비스

    역할:
    1. Fluentd HTTP input으로부터 로그 수신
    2. 로그 파싱 및 정규화
    3. Qdrant 벡터 DB에 인덱싱 (별도 security_logs 컬렉션 사용)
    4. PostgreSQL에 로그 메타데이터 저장 (log_index 테이블)

    주의: 문서 RAG와 분리된 별도 컬렉션(security_logs)을 사용합니다.
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        rag_tool: RAGTool,
        supported_sources: Optional[List[str]] = None
    ):
        """
        Args:
            db_pool: asyncpg 연결 풀
            rag_tool: RAG Tool 인스턴스 (Qdrant 인덱싱용)
            supported_sources: 지원하는 로그 소스 타입 리스트
        """
        self.db_pool = db_pool
        self.rag_tool = rag_tool

        # 로그 전용 컬렉션 이름 (config에서 읽거나 기본값 사용)
        # 문서 RAG collection(documents)과 분리하여 로그는 security_logs 사용
        self.logs_collection_name = rag_tool.config.get('qdrant', {}).get(
            'logs_collection_name', 'security_logs'
        )

        # 로그 컬렉션 생성 (없으면)
        self._ensure_logs_collection()

        # 지원하는 로그 소스
        if supported_sources is None:
            supported_sources = [
                "security_device",    # 보안 장비 로그
                "access_control",     # 출입 통제 로그
                "network_firewall",   # 방화벽 로그
                "application",        # 애플리케이션 로그
                "system"              # 시스템 로그
            ]
        self.supported_sources = supported_sources

        logger.info(f"✅ LogIndexer initialized (collection={self.logs_collection_name}, sources={supported_sources})")

    def _ensure_logs_collection(self):
        """로그 전용 컬렉션이 없으면 생성"""
        from qdrant_client.models import Distance, VectorParams

        collections = self.rag_tool.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.logs_collection_name not in collection_names:
            qdrant_config = self.rag_tool.config.get('qdrant', {})
            self.rag_tool.client.create_collection(
                collection_name=self.logs_collection_name,
                vectors_config=VectorParams(
                    size=qdrant_config.get('vector_size', 384),
                    distance=Distance.COSINE
                )
            )
            logger.info(f"✅ Created logs collection: {self.logs_collection_name}")

    # ============================================
    # 로그 인덱싱
    # ============================================

    async def index_log(self, log_data: Dict[str, Any]) -> str:
        """
        로그 인덱싱 메인 로직

        Args:
            log_data: Fluentd로부터 받은 로그 데이터
                {
                    "source_type": str,
                    "timestamp": str,
                    "message": str,
                    "level": str,
                    "host": str,
                    "metadata": {...}
                }

        Returns:
            Qdrant document ID
        """
        # 1. 로그 검증 및 정규화
        normalized_log = self._normalize_log(log_data)

        source_type = normalized_log["source_type"]
        message = normalized_log["message"]

        logger.debug(f"📝 Indexing log: source={source_type}, message_len={len(message)}")

        # 2. Qdrant에 벡터 인덱싱
        metadata = {
            "type": "log",
            "source_type": source_type,
            "timestamp": normalized_log["timestamp"],
            "level": normalized_log.get("level", "INFO"),
            "host": normalized_log.get("host", "unknown")
        }

        # 추가 메타데이터 병합
        if "metadata" in normalized_log:
            metadata.update(normalized_log["metadata"])

        # Qdrant에 추가
        qdrant_id = await self._add_to_qdrant(message, metadata)

        # 3. PostgreSQL log_index 테이블에 저장
        await self._save_to_log_index(
            source_type=source_type,
            qdrant_id=qdrant_id,
            raw_message=message
        )

        logger.info(f"✅ Log indexed: {qdrant_id}")
        return qdrant_id

    async def index_logs_batch(self, logs: List[Dict[str, Any]]) -> List[str]:
        """
        로그 배치 인덱싱

        Args:
            logs: 로그 데이터 리스트

        Returns:
            Qdrant document IDs 리스트
        """
        logger.info(f"📝 Batch indexing {len(logs)} logs...")

        qdrant_ids = []
        for log_data in logs:
            try:
                qdrant_id = await self.index_log(log_data)
                qdrant_ids.append(qdrant_id)
            except Exception as e:
                logger.error(f"❌ Failed to index log: {e}")
                continue

        logger.info(f"✅ Batch indexed {len(qdrant_ids)}/{len(logs)} logs")
        return qdrant_ids

    # ============================================
    # 로그 정규화
    # ============================================

    def _normalize_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        로그 데이터 검증 및 정규화

        Returns:
            {
                "source_type": str,
                "timestamp": str (ISO 8601),
                "message": str,
                "level": str,
                "host": str,
                "metadata": {...}
            }
        """
        # 필수 필드 검증
        if "source_type" not in log_data:
            raise ValueError("Missing required field: source_type")

        if "message" not in log_data:
            raise ValueError("Missing required field: message")

        source_type = log_data["source_type"]

        # 지원하는 소스 타입인지 확인
        if source_type not in self.supported_sources:
            logger.warning(f"⚠️ Unsupported source type: {source_type}")

        # Timestamp 정규화
        timestamp = log_data.get("timestamp")
        if timestamp:
            try:
                # ISO 8601 형식으로 변환
                if isinstance(timestamp, str):
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    dt = datetime.fromtimestamp(timestamp)
                timestamp = dt.isoformat()
            except Exception as e:
                logger.warning(f"⚠️ Invalid timestamp: {e}, using current time")
                timestamp = datetime.now().isoformat()
        else:
            timestamp = datetime.now().isoformat()

        # 정규화된 로그
        normalized = {
            "source_type": source_type,
            "timestamp": timestamp,
            "message": str(log_data["message"]),
            "level": log_data.get("level", "INFO"),
            "host": log_data.get("host", "unknown"),
            "metadata": log_data.get("metadata", {})
        }

        return normalized

    # ============================================
    # Qdrant 인덱싱
    # ============================================

    async def _add_to_qdrant(self, message: str, metadata: Dict[str, Any]) -> str:
        """
        Qdrant 로그 전용 컬렉션에 로그 추가

        Args:
            message: 로그 메시지
            metadata: 메타데이터

        Returns:
            Qdrant document ID
        """
        # Document ID 생성 (메시지 해시 기반)
        message_hash = hashlib.md5(message.encode()).hexdigest()
        timestamp = datetime.now().isoformat()
        doc_id = f"log_{timestamp}_{message_hash[:8]}"

        # Qdrant에 추가 (로그 전용 컬렉션 사용)
        # Note: RAGTool이 동기 함수인 경우 asyncio.to_thread 사용 고려
        try:
            # Embedding 생성
            embedding = self.rag_tool.embeddings.embed_query(message)

            # Qdrant에 삽입 (로그 전용 컬렉션 사용 - 문서 컬렉션과 분리)
            self.rag_tool.client.upsert(
                collection_name=self.logs_collection_name,  # 별도 로그 컬렉션 사용
                points=[{
                    "id": doc_id,
                    "vector": embedding,
                    "payload": {
                        "content": message,
                        "metadata": metadata
                    }
                }]
            )

            logger.debug(f"   Qdrant logs collection indexed: {doc_id}")
            return doc_id

        except Exception as e:
            logger.error(f"❌ Qdrant log indexing failed: {e}", exc_info=True)
            raise

    # ============================================
    # PostgreSQL log_index 저장
    # ============================================

    async def _save_to_log_index(
        self,
        source_type: str,
        qdrant_id: str,
        raw_message: str
    ) -> None:
        """
        log_index 테이블에 메타데이터 저장

        Args:
            source_type: 로그 소스 타입
            qdrant_id: Qdrant document ID
            raw_message: 원본 로그 메시지
        """
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO log_index (
                    source_type, qdrant_id, raw_message, indexed_at
                )
                VALUES ($1, $2, $3, $4)
                """,
                source_type, qdrant_id, raw_message, datetime.now()
            )

    # ============================================
    # 로그 검색 (RAG 통합)
    # ============================================

    async def search_logs(
        self,
        query: str,
        source_type_filter: Optional[str] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        로그 검색 (벡터 유사도 기반) - 로그 전용 컬렉션에서 검색

        Args:
            query: 검색 쿼리
            source_type_filter: 소스 타입 필터 (선택)
            top_k: 반환할 로그 개수

        Returns:
            검색된 로그 리스트
        """
        logger.info(f"🔍 Searching logs: query='{query}', source_type={source_type_filter}")

        try:
            # Embedding 생성
            query_embedding = self.rag_tool.embeddings.embed_query(query)

            # 로그 전용 컬렉션에서 검색 (qdrant-client 1.7+ uses query_points)
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            query_filter = None
            if source_type_filter:
                query_filter = Filter(
                    must=[
                        FieldCondition(key="metadata.type", match=MatchValue(value="log")),
                        FieldCondition(key="metadata.source_type", match=MatchValue(value=source_type_filter))
                    ]
                )

            try:
                search_results = self.rag_tool.client.query_points(
                    collection_name=self.logs_collection_name,
                    query=query_embedding,
                    limit=top_k,
                    query_filter=query_filter
                ).points
            except AttributeError:
                search_results = self.rag_tool.client.search(
                    collection_name=self.logs_collection_name,
                    query_vector=query_embedding,
                    limit=top_k
                )

            # 결과 포맷팅
            logs = []
            for hit in search_results:
                logs.append({
                    "content": hit.payload.get("content", ""),
                    "metadata": hit.payload.get("metadata", {}),
                    "score": hit.score
                })

            logger.info(f"   Found {len(logs)} logs in security_logs collection")
            return logs

        except Exception as e:
            logger.error(f"❌ Log search failed: {e}", exc_info=True)
            return []

    # ============================================
    # 통계 조회
    # ============================================

    async def get_stats(self) -> Dict[str, Any]:
        """
        로그 인덱싱 통계 조회

        Returns:
            {
                "total_logs": int,
                "by_source_type": {...},
                "last_indexed": str
            }
        """
        async with self.db_pool.acquire() as conn:
            # 전체 로그 개수
            total_logs = await conn.fetchval("SELECT COUNT(*) FROM log_index")

            # 소스 타입별 개수
            source_type_counts = await conn.fetch(
                """
                SELECT source_type, COUNT(*) as count
                FROM log_index
                GROUP BY source_type
                ORDER BY count DESC
                """
            )

            by_source_type = {row["source_type"]: row["count"] for row in source_type_counts}

            # 마지막 인덱싱 시간
            last_indexed = await conn.fetchval(
                "SELECT MAX(indexed_at) FROM log_index"
            )

            return {
                "total_logs": total_logs,
                "by_source_type": by_source_type,
                "last_indexed": last_indexed.isoformat() if last_indexed else None
            }
