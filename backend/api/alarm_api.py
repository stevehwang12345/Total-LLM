#!/usr/bin/env python3
"""
Alarm Management API

알람 조회 및 관리 API
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alarms", tags=["alarms"])


# ============================================
# Request/Response Models
# ============================================

class Alarm(BaseModel):
    """알람 모델"""
    alarm_id: str
    alarm_type: str
    severity: str
    location: str
    timestamp: str
    image_path: Optional[str] = None
    device_id: Optional[str] = None
    description: str = ""
    vlm_analysis: Optional[dict] = None  # VLM 분석 결과
    is_processed: bool = False
    created_at: str


class MarkProcessedRequest(BaseModel):
    """알람 처리 요청"""
    alarm_ids: List[str] = Field(..., description="처리할 알람 ID 리스트")


class MarkProcessedResponse(BaseModel):
    """알람 처리 응답"""
    status: str
    updated_count: int


class AnalyzeAlarmRequest(BaseModel):
    """VLM 분석 요청"""
    force: bool = Field(default=False, description="기존 분석 결과가 있어도 재분석")


class AnalyzeAlarmResponse(BaseModel):
    """VLM 분석 응답"""
    status: str
    alarm_id: str
    analysis: dict


class BatchAnalyzeRequest(BaseModel):
    """배치 VLM 분석 요청"""
    alarm_ids: List[str] = Field(..., description="분석할 알람 ID 리스트")
    force: bool = Field(default=False, description="기존 분석 결과가 있어도 재분석")


class BatchAnalyzeResponse(BaseModel):
    """배치 VLM 분석 응답"""
    status: str
    total: int
    analyzed: int
    failed: int
    results: List[dict]


# ============================================
# Global Variables (main.py에서 주입)
# ============================================

alarm_handler = None


def set_alarm_handler(handler):
    """Alarm Handler 설정"""
    global alarm_handler
    alarm_handler = handler


# ============================================
# API Endpoints
# ============================================

@router.get("", response_model=List[Alarm])
async def get_alarms(
    limit: int = Query(default=50, ge=1, le=200, description="반환할 알람 개수"),
    offset: int = Query(default=0, ge=0, description="페이지네이션 오프셋"),
    severity_filter: Optional[str] = Query(default=None, description="심각도 필터 (CRITICAL, HIGH, MEDIUM, LOW)"),
    processed_only: bool = Query(default=False, description="처리된 알람만 조회")
):
    """
    알람 목록 조회

    Args:
        limit: 반환할 알람 개수 (1-200)
        offset: 페이지네이션 오프셋
        severity_filter: 심각도 필터
        processed_only: 처리된 알람만 조회

    Returns:
        알람 리스트
    """
    if not alarm_handler:
        raise HTTPException(status_code=500, detail="Alarm handler not initialized")

    logger.info(f"📋 Fetching alarms: limit={limit}, offset={offset}, severity={severity_filter}")

    try:
        alarms = await alarm_handler.get_alarms(
            limit=limit,
            offset=offset,
            severity_filter=severity_filter,
            processed_only=processed_only
        )

        return alarms

    except Exception as e:
        logger.error(f"❌ Failed to fetch alarms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{alarm_id}", response_model=Alarm)
async def get_alarm(alarm_id: str):
    """
    특정 알람 조회

    Args:
        alarm_id: 알람 ID

    Returns:
        알람 상세 정보
    """
    if not alarm_handler:
        raise HTTPException(status_code=500, detail="Alarm handler not initialized")

    try:
        alarms = await alarm_handler.get_alarms(limit=1, offset=0)
        alarm = next((a for a in alarms if a["alarm_id"] == alarm_id), None)

        if not alarm:
            raise HTTPException(status_code=404, detail=f"Alarm {alarm_id} not found")

        return alarm

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch alarm: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mark-processed", response_model=MarkProcessedResponse)
async def mark_alarms_processed(request: MarkProcessedRequest):
    """
    알람을 처리됨으로 표시

    Args:
        request: 처리할 알람 ID 리스트

    Returns:
        {
            "status": "success",
            "updated_count": 5
        }
    """
    if not alarm_handler:
        raise HTTPException(status_code=500, detail="Alarm handler not initialized")

    logger.info(f"✅ Marking {len(request.alarm_ids)} alarms as processed")

    try:
        updated_count = await alarm_handler.mark_alarms_processed(request.alarm_ids)

        return MarkProcessedResponse(
            status="success",
            updated_count=updated_count
        )

    except Exception as e:
        logger.error(f"❌ Failed to mark alarms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
async def get_alarm_stats():
    """
    알람 통계 조회

    Returns:
        {
            "total_alarms": 123,
            "by_severity": {
                "CRITICAL": 10,
                "HIGH": 30,
                ...
            },
            "unprocessed_count": 45,
            "recent_count_24h": 20
        }
    """
    if not alarm_handler:
        raise HTTPException(status_code=500, detail="Alarm handler not initialized")

    try:
        # 전체 알람 조회
        all_alarms = await alarm_handler.get_alarms(limit=1000, offset=0)

        # 통계 계산
        total_alarms = len(all_alarms)
        by_severity = {}
        unprocessed_count = 0
        recent_count_24h = 0

        from datetime import timedelta
        now = datetime.now()
        yesterday = now - timedelta(days=1)

        for alarm in all_alarms:
            # Severity 통계
            severity = alarm["severity"]
            by_severity[severity] = by_severity.get(severity, 0) + 1

            # 미처리 통계
            if not alarm["is_processed"]:
                unprocessed_count += 1

            # 24시간 이내 통계
            alarm_time = datetime.fromisoformat(alarm["timestamp"])
            if alarm_time >= yesterday:
                recent_count_24h += 1

        return {
            "total_alarms": total_alarms,
            "by_severity": by_severity,
            "unprocessed_count": unprocessed_count,
            "recent_count_24h": recent_count_24h
        }

    except Exception as e:
        logger.error(f"❌ Failed to get stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cleanup")
async def cleanup_old_images():
    """
    30일 경과 이미지 삭제

    Returns:
        {
            "status": "success",
            "deleted_files": 123,
            "freed_space_mb": 456.78
        }
    """
    if not alarm_handler:
        raise HTTPException(status_code=500, detail="Alarm handler not initialized")

    logger.info("🧹 Starting image cleanup...")

    try:
        result = await alarm_handler.cleanup_old_images()

        return {
            "status": "success",
            **result
        }

    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    헬스 체크

    Returns:
        {"status": "healthy", "alarm_handler": bool}
    """
    return {
        "status": "healthy" if alarm_handler else "not_initialized",
        "alarm_handler": alarm_handler is not None
    }


# ============================================
# VLM Analysis Endpoints
# ============================================

@router.post("/{alarm_id}/analyze", response_model=AnalyzeAlarmResponse)
async def analyze_alarm_image(alarm_id: str, request: AnalyzeAlarmRequest):
    """
    특정 알람 이미지를 VLM으로 분석

    Args:
        alarm_id: 분석할 알람 ID
        request: 분석 옵션 (force 재분석 여부)

    Returns:
        {
            "status": "success",
            "alarm_id": "alarm_001",
            "analysis": {
                "threat_detected": true,
                "threat_level": "HIGH",
                "description": "...",
                "recommended_actions": [...],
                "confidence": 0.95
            }
        }
    """
    if not alarm_handler:
        raise HTTPException(status_code=500, detail="Alarm handler not initialized")

    logger.info(f"🔍 Analyzing alarm image: {alarm_id} (force={request.force})")

    try:
        analysis = await alarm_handler.analyze_alarm_image(
            alarm_id=alarm_id,
            force=request.force
        )

        if not analysis:
            raise HTTPException(
                status_code=404,
                detail=f"Alarm {alarm_id} not found or has no image"
            )

        return AnalyzeAlarmResponse(
            status="success",
            alarm_id=alarm_id,
            analysis=analysis
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to analyze alarm: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/batch", response_model=BatchAnalyzeResponse)
async def batch_analyze_alarms(request: BatchAnalyzeRequest):
    """
    여러 알람 이미지를 병렬로 VLM 분석

    Args:
        request: {
            "alarm_ids": ["alarm_001", "alarm_002", ...],
            "force": false
        }

    Returns:
        {
            "status": "success",
            "total": 10,
            "analyzed": 8,
            "failed": 2,
            "results": [
                {
                    "alarm_id": "alarm_001",
                    "status": "success",
                    "analysis": {...}
                },
                ...
            ]
        }
    """
    if not alarm_handler:
        raise HTTPException(status_code=500, detail="Alarm handler not initialized")

    logger.info(f"🔍 Batch analyzing {len(request.alarm_ids)} alarms (force={request.force})")

    try:
        results = await alarm_handler.analyze_batch_alarms(
            alarm_ids=request.alarm_ids,
            force=request.force,
            max_concurrent=5
        )

        analyzed = sum(1 for r in results if r["status"] == "success")
        failed = len(results) - analyzed

        return BatchAnalyzeResponse(
            status="success",
            total=len(request.alarm_ids),
            analyzed=analyzed,
            failed=failed,
            results=results
        )

    except Exception as e:
        logger.error(f"❌ Failed to batch analyze: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
