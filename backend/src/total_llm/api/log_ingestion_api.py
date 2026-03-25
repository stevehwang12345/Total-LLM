#!/usr/bin/env python3
"""
Log Ingestion API

Fluentd로부터 로그를 수신하는 HTTP API
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from total_llm.core.dependencies import LogIndexerDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])


# ============================================
# Request Models
# ============================================

class LogEntry(BaseModel):
    """로그 엔트리 모델"""
    source_type: str = Field(..., description="로그 소스 타입")
    timestamp: Optional[str] = Field(None, description="로그 타임스탬프 (ISO 8601)")
    message: str = Field(..., description="로그 메시지")
    level: str = Field(default="INFO", description="로그 레벨")
    host: str = Field(default="unknown", description="호스트명")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


class LogIngestRequest(BaseModel):
    """로그 수집 요청 (배치)"""
    logs: List[LogEntry] = Field(..., description="로그 엔트리 리스트")


class LogSearchRequest(BaseModel):
    """로그 검색 요청"""
    query: str = Field(..., description="검색 쿼리")
    source_type_filter: Optional[str] = Field(None, description="소스 타입 필터")
    top_k: int = Field(default=10, ge=1, le=100, description="반환할 로그 개수")


# ============================================
# Response Models
# ============================================

class LogIngestResponse(BaseModel):
    """로그 수집 응답"""
    status: str
    indexed_count: int
    failed_count: int
    qdrant_ids: List[str]


class LogSearchResponse(BaseModel):
    """로그 검색 응답"""
    status: str
    total_results: int
    logs: List[Dict[str, Any]]


class LogStatsResponse(BaseModel):
    """로그 통계 응답"""
    total_logs: int
    by_source_type: Dict[str, int]
    last_indexed: Optional[str]


# ============================================
# API Endpoints
# ============================================

@router.post("/ingest", response_model=LogIngestResponse)
async def ingest_logs(
    request: LogIngestRequest,
    background_tasks: BackgroundTasks,
    log_indexer: LogIndexerDep = None,
):
    """
    Fluentd로부터 로그 배치 수신

    Args:
        request: 로그 엔트리 리스트
        background_tasks: FastAPI 백그라운드 작업

    Returns:
        {
            "status": "success",
            "indexed_count": 95,
            "failed_count": 5,
            "qdrant_ids": [...]
        }
    """
    logger.info(f"📥 Received {len(request.logs)} logs from Fluentd")

    try:
        # 로그 데이터 변환
        logs_data = [log.dict() for log in request.logs]

        # 백그라운드에서 인덱싱 (응답 속도 개선)
        qdrant_ids = await log_indexer.index_logs_batch(logs_data)

        indexed_count = len(qdrant_ids)
        failed_count = len(request.logs) - indexed_count

        return LogIngestResponse(
            status="success",
            indexed_count=indexed_count,
            failed_count=failed_count,
            qdrant_ids=qdrant_ids
        )

    except Exception as e:
        logger.error(f"❌ Log ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=LogSearchResponse)
async def search_logs(request: LogSearchRequest, log_indexer: LogIndexerDep = None):
    """
    로그 검색 (벡터 유사도 기반)

    Args:
        request: 검색 요청

    Returns:
        {
            "status": "success",
            "total_results": 10,
            "logs": [...]
        }
    """
    logger.info(f"🔍 Searching logs: query='{request.query}'")

    try:
        logs = await log_indexer.search_logs(
            query=request.query,
            source_type_filter=request.source_type_filter,
            top_k=request.top_k
        )

        return LogSearchResponse(
            status="success",
            total_results=len(logs),
            logs=logs
        )

    except Exception as e:
        logger.error(f"❌ Log search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=LogStatsResponse)
async def get_log_stats(log_indexer: LogIndexerDep = None):
    """
    로그 인덱싱 통계 조회

    Returns:
        {
            "total_logs": 12345,
            "by_source_type": {
                "security_device": 5000,
                "access_control": 3000,
                ...
            },
            "last_indexed": "2025-01-09T15:30:45.123Z"
        }
    """
    try:
        stats = await log_indexer.get_stats()

        return LogStatsResponse(
            total_logs=stats["total_logs"],
            by_source_type=stats["by_source_type"],
            last_indexed=stats["last_indexed"]
        )

    except Exception as e:
        logger.error(f"❌ Failed to get stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check(log_indexer: LogIndexerDep = None):
    """
    헬스 체크

    Returns:
        {"status": "healthy", "timestamp": "..."}
    """
    return {
        "status": "healthy" if log_indexer else "not_initialized",
        "timestamp": datetime.now().isoformat()
    }
