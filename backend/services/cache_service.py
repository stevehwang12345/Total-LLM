#!/usr/bin/env python3
"""
Cache Service for RAG and Conversations

Redis 기반 캐싱 서비스
- RAG 쿼리-응답 캐싱
- 대화 컨텍스트 캐싱
"""

import logging
import hashlib
import json
from typing import Any, Dict, List, Optional
from pathlib import Path
import os

import redis.asyncio as redis
import yaml

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis 기반 캐싱 서비스

    기능:
    1. RAG 쿼리 결과 캐싱
    2. 대화 컨텍스트 임시 캐싱
    3. TTL 기반 자동 만료
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: config.yaml 경로
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "config.yaml"

        with open(config_path) as f:
            config = yaml.safe_load(f)

        redis_config = config.get('redis', {})

        # 환경변수 오버라이드
        self.host = os.getenv('REDIS_HOST', redis_config.get('host', 'localhost'))
        self.port = int(os.getenv('REDIS_PORT', redis_config.get('port', 6379)))
        self.db = int(os.getenv('REDIS_DB', redis_config.get('db', 0)))
        self.password = os.getenv('REDIS_PASSWORD', redis_config.get('password', '')) or None

        # 캐싱 설정
        rag_cache_config = redis_config.get('rag_cache', {})
        self.rag_cache_enabled = rag_cache_config.get('enabled', True)
        self.rag_cache_ttl = rag_cache_config.get('ttl_seconds', 3600)
        self.rag_key_prefix = rag_cache_config.get('key_prefix', 'rag:')

        conv_cache_config = redis_config.get('conversation_cache', {})
        self.conv_cache_enabled = conv_cache_config.get('enabled', True)
        self.conv_cache_ttl = conv_cache_config.get('ttl_seconds', 86400)
        self.conv_key_prefix = conv_cache_config.get('key_prefix', 'conv:')

        self._client: Optional[redis.Redis] = None
        self._connected = False

    async def connect(self) -> bool:
        """Redis 연결"""
        if self._connected:
            return True

        try:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0
            )

            # 연결 테스트
            await self._client.ping()
            self._connected = True
            logger.info(f"✅ Redis connected: {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}. Caching disabled.")
            self._connected = False
            return False

    async def disconnect(self):
        """Redis 연결 종료"""
        if self._client:
            await self._client.close()
            self._connected = False
            logger.info("Redis disconnected")

    # ============================================
    # RAG 캐싱
    # ============================================

    def _generate_rag_cache_key(
        self,
        query: str,
        retriever_type: str = "default",
        filter_metadata: Optional[Dict] = None
    ) -> str:
        """RAG 캐시 키 생성"""
        key_data = {
            "query": query.strip().lower(),
            "retriever": retriever_type,
            "filter": filter_metadata or {}
        }
        key_hash = hashlib.sha256(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()[:16]

        return f"{self.rag_key_prefix}{key_hash}"

    async def get_rag_cache(
        self,
        query: str,
        retriever_type: str = "default",
        filter_metadata: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        RAG 캐시 조회

        Args:
            query: 검색 쿼리
            retriever_type: 검색기 유형
            filter_metadata: 메타데이터 필터

        Returns:
            캐시된 결과 또는 None
        """
        if not self.rag_cache_enabled or not self._connected:
            return None

        try:
            key = self._generate_rag_cache_key(query, retriever_type, filter_metadata)
            cached = await self._client.get(key)

            if cached:
                logger.info(f"🎯 RAG cache hit: {key}")
                return json.loads(cached)

            return None

        except Exception as e:
            logger.warning(f"RAG cache get error: {e}")
            return None

    async def set_rag_cache(
        self,
        query: str,
        result: Dict[str, Any],
        retriever_type: str = "default",
        filter_metadata: Optional[Dict] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """
        RAG 결과 캐싱

        Args:
            query: 검색 쿼리
            result: 캐싱할 결과
            retriever_type: 검색기 유형
            filter_metadata: 메타데이터 필터
            ttl: TTL (초), 기본값 사용 시 None

        Returns:
            성공 여부
        """
        if not self.rag_cache_enabled or not self._connected:
            return False

        try:
            key = self._generate_rag_cache_key(query, retriever_type, filter_metadata)
            ttl = ttl or self.rag_cache_ttl

            await self._client.set(
                key,
                json.dumps(result, ensure_ascii=False),
                ex=ttl
            )
            logger.info(f"💾 RAG cache set: {key} (TTL: {ttl}s)")
            return True

        except Exception as e:
            logger.warning(f"RAG cache set error: {e}")
            return False

    async def invalidate_rag_cache(self, pattern: str = "*") -> int:
        """
        RAG 캐시 무효화

        Args:
            pattern: 키 패턴 (기본: 전체)

        Returns:
            삭제된 키 수
        """
        if not self._connected:
            return 0

        try:
            full_pattern = f"{self.rag_key_prefix}{pattern}"
            keys = []
            async for key in self._client.scan_iter(match=full_pattern):
                keys.append(key)

            if keys:
                deleted = await self._client.delete(*keys)
                logger.info(f"🗑️ RAG cache invalidated: {deleted} keys")
                return deleted

            return 0

        except Exception as e:
            logger.warning(f"RAG cache invalidation error: {e}")
            return 0

    # ============================================
    # 대화 컨텍스트 캐싱
    # ============================================

    async def get_conversation_context(
        self,
        conversation_id: str,
        max_messages: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """
        대화 컨텍스트 조회 (빠른 접근용)

        Args:
            conversation_id: 대화 ID
            max_messages: 최대 메시지 수

        Returns:
            최근 메시지 리스트
        """
        if not self.conv_cache_enabled or not self._connected:
            return None

        try:
            key = f"{self.conv_key_prefix}{conversation_id}"
            cached = await self._client.get(key)

            if cached:
                messages = json.loads(cached)
                return messages[-max_messages:] if len(messages) > max_messages else messages

            return None

        except Exception as e:
            logger.warning(f"Conversation cache get error: {e}")
            return None

    async def set_conversation_context(
        self,
        conversation_id: str,
        messages: List[Dict[str, Any]],
        ttl: Optional[int] = None
    ) -> bool:
        """
        대화 컨텍스트 캐싱

        Args:
            conversation_id: 대화 ID
            messages: 메시지 리스트
            ttl: TTL (초)

        Returns:
            성공 여부
        """
        if not self.conv_cache_enabled or not self._connected:
            return False

        try:
            key = f"{self.conv_key_prefix}{conversation_id}"
            ttl = ttl or self.conv_cache_ttl

            await self._client.set(
                key,
                json.dumps(messages, ensure_ascii=False),
                ex=ttl
            )
            return True

        except Exception as e:
            logger.warning(f"Conversation cache set error: {e}")
            return False

    async def append_conversation_message(
        self,
        conversation_id: str,
        message: Dict[str, Any],
        max_messages: int = 20
    ) -> bool:
        """
        대화에 메시지 추가

        Args:
            conversation_id: 대화 ID
            message: 추가할 메시지
            max_messages: 유지할 최대 메시지 수

        Returns:
            성공 여부
        """
        if not self.conv_cache_enabled or not self._connected:
            return False

        try:
            key = f"{self.conv_key_prefix}{conversation_id}"
            cached = await self._client.get(key)

            messages = json.loads(cached) if cached else []
            messages.append(message)

            # 최대 메시지 수 제한
            if len(messages) > max_messages:
                messages = messages[-max_messages:]

            await self._client.set(
                key,
                json.dumps(messages, ensure_ascii=False),
                ex=self.conv_cache_ttl
            )
            return True

        except Exception as e:
            logger.warning(f"Conversation message append error: {e}")
            return False

    async def delete_conversation_context(self, conversation_id: str) -> bool:
        """대화 컨텍스트 삭제"""
        if not self._connected:
            return False

        try:
            key = f"{self.conv_key_prefix}{conversation_id}"
            await self._client.delete(key)
            return True

        except Exception as e:
            logger.warning(f"Conversation cache delete error: {e}")
            return False

    # ============================================
    # 통계 및 관리
    # ============================================

    async def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        if not self._connected:
            return {"connected": False}

        try:
            info = await self._client.info("memory")

            # RAG 캐시 키 수
            rag_keys = 0
            async for _ in self._client.scan_iter(match=f"{self.rag_key_prefix}*"):
                rag_keys += 1

            # 대화 캐시 키 수
            conv_keys = 0
            async for _ in self._client.scan_iter(match=f"{self.conv_key_prefix}*"):
                conv_keys += 1

            return {
                "connected": True,
                "memory_used_human": info.get("used_memory_human", "N/A"),
                "rag_cache_keys": rag_keys,
                "conversation_cache_keys": conv_keys,
                "rag_cache_enabled": self.rag_cache_enabled,
                "rag_cache_ttl": self.rag_cache_ttl,
                "conv_cache_enabled": self.conv_cache_enabled,
                "conv_cache_ttl": self.conv_cache_ttl,
            }

        except Exception as e:
            logger.warning(f"Cache stats error: {e}")
            return {"connected": False, "error": str(e)}

    async def health_check(self) -> bool:
        """헬스 체크"""
        if not self._client:
            return False

        try:
            await self._client.ping()
            return True
        except Exception:
            return False


# 싱글톤 인스턴스
_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """Cache Service 싱글톤 반환"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
        await _cache_service.connect()
    return _cache_service
