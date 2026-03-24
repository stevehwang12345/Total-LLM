#!/usr/bin/env python3
"""
Conversation Service for RAG QA

PostgreSQL 기반 대화 지속성 서비스
- 대화 세션 관리
- 메시지 히스토리 저장/복원
- 컨텍스트 윈도우 관리
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
import os

import asyncpg
import yaml

logger = logging.getLogger(__name__)


class ConversationService:
    """
    대화 지속성 서비스

    기능:
    1. 대화 세션 생성/조회/종료
    2. 메시지 저장/조회
    3. 컨텍스트 윈도우 관리 (최근 N턴)
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

        db_config = config.get('database', {})

        # 환경변수 오버라이드
        self.host = os.getenv('POSTGRES_HOST', db_config.get('host', 'localhost'))
        self.port = int(os.getenv('POSTGRES_PORT', db_config.get('port', 5432)))
        self.database = os.getenv('POSTGRES_DB', db_config.get('database', 'total_llm'))
        self.username = os.getenv('POSTGRES_USER', db_config.get('username', 'total_llm'))
        self.password = os.getenv('POSTGRES_PASSWORD', db_config.get('password', ''))

        self.pool_size = db_config.get('pool_size', 10)
        self.max_overflow = db_config.get('max_overflow', 20)

        self._pool: Optional[asyncpg.Pool] = None
        self._connected = False

        # 기본 컨텍스트 윈도우 설정
        self.default_context_window = 5  # 최근 5턴

    async def connect(self) -> bool:
        """데이터베이스 연결"""
        if self._connected:
            return True

        try:
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                user=self.username,
                password=self.password,
                database=self.database,
                min_size=2,
                max_size=self.pool_size
            )

            self._connected = True
            logger.info(f"✅ PostgreSQL connected: {self.host}:{self.port}/{self.database}")
            return True

        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """데이터베이스 연결 종료"""
        if self._pool:
            await self._pool.close()
            self._connected = False
            logger.info("PostgreSQL disconnected")

    # ============================================
    # 대화 세션 관리
    # ============================================

    async def create_conversation(
        self,
        user_id: str = "anonymous",
        mode: str = "qa",
        title: Optional[str] = None
    ) -> Optional[str]:
        """
        새 대화 세션 생성

        Args:
            user_id: 사용자 ID
            mode: 대화 모드 (qa, device_register, device_control)
            title: 대화 제목 (선택)

        Returns:
            conversation_id (UUID) 또는 None
        """
        if not self._connected:
            logger.warning("Database not connected")
            return None

        try:
            async with self._pool.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    INSERT INTO conversations (user_id, mode, title)
                    VALUES ($1, $2, $3)
                    RETURNING conversation_id
                    """,
                    user_id, mode, title
                )

                conversation_id = str(result['conversation_id'])
                logger.info(f"✅ Conversation created: {conversation_id}")
                return conversation_id

        except Exception as e:
            logger.error(f"❌ Failed to create conversation: {e}")
            return None

    async def get_conversation(
        self,
        conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        대화 세션 조회

        Args:
            conversation_id: 대화 ID

        Returns:
            대화 정보 dict
        """
        if not self._connected:
            return None

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT conversation_id, user_id, title, mode,
                           is_active, message_count,
                           created_at, updated_at, last_message_at
                    FROM conversations
                    WHERE conversation_id = $1
                    """,
                    uuid.UUID(conversation_id)
                )

                if row:
                    return {
                        "conversation_id": str(row['conversation_id']),
                        "user_id": row['user_id'],
                        "title": row['title'],
                        "mode": row['mode'],
                        "is_active": row['is_active'],
                        "message_count": row['message_count'],
                        "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                        "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None,
                        "last_message_at": row['last_message_at'].isoformat() if row['last_message_at'] else None,
                    }

                return None

        except Exception as e:
            logger.error(f"Failed to get conversation: {e}")
            return None

    async def list_conversations(
        self,
        user_id: str = "anonymous",
        limit: int = 20,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        사용자의 대화 목록 조회

        Args:
            user_id: 사용자 ID
            limit: 최대 조회 수
            include_inactive: 비활성 대화 포함 여부

        Returns:
            대화 목록
        """
        if not self._connected:
            return []

        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT conversation_id, title, mode, message_count,
                           created_at, updated_at, last_message_at
                    FROM conversations
                    WHERE user_id = $1
                """
                params = [user_id]

                if not include_inactive:
                    query += " AND is_active = TRUE"

                query += " ORDER BY updated_at DESC LIMIT $2"
                params.append(limit)

                rows = await conn.fetch(query, *params)

                return [
                    {
                        "conversation_id": str(row['conversation_id']),
                        "title": row['title'] or "새 대화",
                        "mode": row['mode'],
                        "message_count": row['message_count'],
                        "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                        "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None,
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            return []

    async def close_conversation(self, conversation_id: str) -> bool:
        """대화 세션 종료"""
        if not self._connected:
            return False

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE conversations
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE conversation_id = $1
                    """,
                    uuid.UUID(conversation_id)
                )
                return True

        except Exception as e:
            logger.error(f"Failed to close conversation: {e}")
            return False

    async def update_conversation_title(
        self,
        conversation_id: str,
        title: str
    ) -> bool:
        """대화 제목 업데이트"""
        if not self._connected:
            return False

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE conversations
                    SET title = $2, updated_at = CURRENT_TIMESTAMP
                    WHERE conversation_id = $1
                    """,
                    uuid.UUID(conversation_id), title[:200]  # 최대 200자
                )
                return True

        except Exception as e:
            logger.error(f"Failed to update conversation title: {e}")
            return False

    # ============================================
    # 메시지 관리
    # ============================================

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        source_documents: Optional[List[Dict[str, Any]]] = None,
        retriever_strategy: Optional[str] = None,
        tokens_used: Optional[int] = None
    ) -> Optional[int]:
        """
        메시지 저장

        Args:
            conversation_id: 대화 ID
            role: 역할 (user, assistant, system, function)
            content: 메시지 내용
            metadata: 추가 메타데이터
            source_documents: 참조된 문서 정보 (RAG 용)
            retriever_strategy: 사용된 검색 전략
            tokens_used: 사용된 토큰 수

        Returns:
            message_id 또는 None
        """
        if not self._connected:
            return None

        try:
            import json

            async with self._pool.acquire() as conn:
                # 메시지 추가
                result = await conn.fetchrow(
                    """
                    INSERT INTO conversation_messages
                        (conversation_id, role, content, metadata, source_documents,
                         retriever_strategy, tokens_used)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING message_id
                    """,
                    uuid.UUID(conversation_id),
                    role,
                    content,
                    json.dumps(metadata) if metadata else None,
                    json.dumps(source_documents) if source_documents else None,
                    retriever_strategy,
                    tokens_used
                )

                # 대화 통계 업데이트
                await conn.execute(
                    """
                    UPDATE conversations
                    SET message_count = message_count + 1,
                        updated_at = CURRENT_TIMESTAMP,
                        last_message_at = CURRENT_TIMESTAMP
                    WHERE conversation_id = $1
                    """,
                    uuid.UUID(conversation_id)
                )

                # 첫 번째 사용자 메시지로 제목 자동 생성
                if role == 'user':
                    await conn.execute(
                        """
                        UPDATE conversations
                        SET title = COALESCE(title, LEFT($2, 50) || CASE WHEN LENGTH($2) > 50 THEN '...' ELSE '' END)
                        WHERE conversation_id = $1 AND title IS NULL
                        """,
                        uuid.UUID(conversation_id),
                        content
                    )

                return result['message_id']

        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            return None

    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
        roles: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        대화 메시지 조회

        Args:
            conversation_id: 대화 ID
            limit: 최대 조회 수
            offset: 건너뛸 메시지 수
            roles: 필터링할 역할 목록

        Returns:
            메시지 목록
        """
        if not self._connected:
            return []

        try:
            import json

            async with self._pool.acquire() as conn:
                query = """
                    SELECT message_id, role, content, metadata,
                           source_documents, retriever_strategy, tokens_used, created_at
                    FROM conversation_messages
                    WHERE conversation_id = $1
                """
                params = [uuid.UUID(conversation_id)]

                if roles:
                    query += f" AND role = ANY($2)"
                    params.append(roles)

                query += " ORDER BY created_at ASC"

                if limit:
                    query += f" LIMIT ${len(params) + 1}"
                    params.append(limit)

                if offset > 0:
                    query += f" OFFSET ${len(params) + 1}"
                    params.append(offset)

                rows = await conn.fetch(query, *params)

                return [
                    {
                        "message_id": row['message_id'],
                        "role": row['role'],
                        "content": row['content'],
                        "metadata": json.loads(row['metadata']) if row['metadata'] else None,
                        "source_documents": json.loads(row['source_documents']) if row['source_documents'] else None,
                        "retriever_strategy": row['retriever_strategy'],
                        "tokens_used": row['tokens_used'],
                        "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []

    async def get_context_messages(
        self,
        conversation_id: str,
        context_window: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        LLM 컨텍스트용 최근 메시지 조회

        Args:
            conversation_id: 대화 ID
            context_window: 컨텍스트 윈도우 크기 (턴 수)

        Returns:
            OpenAI 형식의 메시지 목록 [{"role": ..., "content": ...}]
        """
        if not self._connected:
            return []

        window = context_window or self.default_context_window

        try:
            async with self._pool.acquire() as conn:
                # 최근 N개의 user/assistant 쌍 조회
                rows = await conn.fetch(
                    """
                    SELECT role, content
                    FROM conversation_messages
                    WHERE conversation_id = $1
                      AND role IN ('user', 'assistant')
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    uuid.UUID(conversation_id),
                    window * 2  # user + assistant pairs
                )

                # 시간순으로 정렬
                messages = [
                    {"role": row['role'], "content": row['content']}
                    for row in reversed(rows)
                ]

                return messages

        except Exception as e:
            logger.error(f"Failed to get context messages: {e}")
            return []

    # ============================================
    # 유틸리티
    # ============================================

    async def delete_conversation(self, conversation_id: str) -> bool:
        """대화 완전 삭제 (CASCADE로 메시지도 삭제됨)"""
        if not self._connected:
            return False

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM conversations WHERE conversation_id = $1",
                    uuid.UUID(conversation_id)
                )
                logger.info(f"🗑️ Conversation deleted: {conversation_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """대화 통계 조회"""
        if not self._connected:
            return {"connected": False}

        try:
            async with self._pool.acquire() as conn:
                # 전체 대화 수
                total = await conn.fetchval(
                    "SELECT COUNT(*) FROM conversations"
                )

                # 활성 대화 수
                active = await conn.fetchval(
                    "SELECT COUNT(*) FROM conversations WHERE is_active = TRUE"
                )

                # 전체 메시지 수
                messages = await conn.fetchval(
                    "SELECT COUNT(*) FROM conversation_messages"
                )

                return {
                    "connected": True,
                    "total_conversations": total,
                    "active_conversations": active,
                    "total_messages": messages,
                }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"connected": False, "error": str(e)}

    async def health_check(self) -> bool:
        """헬스 체크"""
        if not self._pool:
            return False

        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except Exception:
            return False


# 싱글톤 인스턴스
_conversation_service: Optional[ConversationService] = None


async def get_conversation_service() -> ConversationService:
    """Conversation Service 싱글톤 반환"""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
        await _conversation_service.connect()
    return _conversation_service
