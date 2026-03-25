#!/usr/bin/env python3
"""
Report Generation API

PDF 보고서 생성 및 다운로드 API
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])


# ============================================
# Request/Response Models
# ============================================

class ReportGenerateRequest(BaseModel):
    """보고서 생성 요청"""
    alarm_ids: List[str] = Field(..., description="보고서에 포함할 알람 ID 리스트")
    include_images: bool = Field(default=True, description="이미지 포함 여부")
    analyze_with_vlm: bool = Field(default=True, description="QwenVLM 이미지 분석 여부")


class ReportGenerateResponse(BaseModel):
    """보고서 생성 응답"""
    report_id: int
    pdf_path: str
    total_alarms: int
    critical_count: int
    file_size_kb: float


# ============================================
# Global Variables (main.py에서 주입)
# ============================================

report_generator = None


def set_report_generator(generator):
    """Report Generator 설정"""
    global report_generator
    report_generator = generator


# ============================================
# API Endpoints
# ============================================

@router.post("/generate", response_model=ReportGenerateResponse)
async def generate_report(request: ReportGenerateRequest):
    """
    보고서 생성

    Args:
        request: 보고서 생성 요청

    Returns:
        {
            "report_id": 123,
            "pdf_path": "/path/to/report.pdf",
            "total_alarms": 10,
            "critical_count": 3,
            "file_size_kb": 1234.56
        }
    """
    if not report_generator:
        raise HTTPException(status_code=500, detail="Report generator not initialized")

    logger.info(f"📄 Generating report for {len(request.alarm_ids)} alarms")

    try:
        result = await report_generator.generate_report(
            alarm_ids=request.alarm_ids,
            generated_by="web_user",
            include_images=request.include_images,
            analyze_with_vlm=request.analyze_with_vlm
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to generate report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{report_id}/download")
async def download_report(report_id: int):
    """
    보고서 다운로드

    Args:
        report_id: 보고서 ID

    Returns:
        PDF 파일
    """
    if not report_generator:
        raise HTTPException(status_code=500, detail="Report generator not initialized")

    logger.info(f"⬇️ Downloading report: {report_id}")

    try:
        # DB에서 보고서 경로 조회
        async with report_generator.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT pdf_path FROM reports WHERE report_id = $1",
                report_id
            )

            if not row:
                raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

            pdf_path = Path(row["pdf_path"])

            if not pdf_path.exists():
                raise HTTPException(status_code=404, detail="PDF file not found")

            return FileResponse(
                path=str(pdf_path),
                media_type="application/pdf",
                filename=f"security_report_{report_id}.pdf"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to download report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{report_id}")
async def get_report_info(report_id: int):
    """
    보고서 정보 조회

    Args:
        report_id: 보고서 ID

    Returns:
        {
            "report_id": 123,
            "alarm_ids": [...],
            "total_alarms": 10,
            "critical_count": 3,
            "generated_at": "...",
            "generated_by": "..."
        }
    """
    if not report_generator:
        raise HTTPException(status_code=500, detail="Report generator not initialized")

    try:
        async with report_generator.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    report_id, alarm_ids, total_alarms, critical_count,
                    generated_at, generated_by, pdf_path
                FROM reports
                WHERE report_id = $1
                """,
                report_id
            )

            if not row:
                raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

            return {
                "report_id": row["report_id"],
                "alarm_ids": row["alarm_ids"],
                "total_alarms": row["total_alarms"],
                "critical_count": row["critical_count"],
                "generated_at": row["generated_at"].isoformat(),
                "generated_by": row["generated_by"],
                "pdf_path": row["pdf_path"]
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get report info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_reports(
    limit: int = 50,
    offset: int = 0
):
    """
    보고서 목록 조회

    Args:
        limit: 반환할 보고서 개수
        offset: 페이지네이션 오프셋

    Returns:
        보고서 리스트
    """
    if not report_generator:
        raise HTTPException(status_code=500, detail="Report generator not initialized")

    try:
        async with report_generator.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    report_id, total_alarms, critical_count,
                    generated_at, generated_by
                FROM reports
                ORDER BY generated_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit, offset
            )

            reports = []
            for row in rows:
                reports.append({
                    "report_id": row["report_id"],
                    "total_alarms": row["total_alarms"],
                    "critical_count": row["critical_count"],
                    "generated_at": row["generated_at"].isoformat(),
                    "generated_by": row["generated_by"]
                })

            return reports

    except Exception as e:
        logger.error(f"❌ Failed to list reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{report_id}")
async def delete_report(report_id: int):
    """
    보고서 삭제

    Args:
        report_id: 보고서 ID

    Returns:
        {"status": "success", "deleted": true}
    """
    if not report_generator:
        raise HTTPException(status_code=500, detail="Report generator not initialized")

    logger.info(f"🗑️ Deleting report: {report_id}")

    try:
        async with report_generator.db_pool.acquire() as conn:
            # PDF 파일 경로 조회
            row = await conn.fetchrow(
                "SELECT pdf_path FROM reports WHERE report_id = $1",
                report_id
            )

            if not row:
                raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

            pdf_path = Path(row["pdf_path"])

            # 파일 삭제
            if pdf_path.exists():
                pdf_path.unlink()

            # DB에서 삭제
            await conn.execute(
                "DELETE FROM reports WHERE report_id = $1",
                report_id
            )

            return {"status": "success", "deleted": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    헬스 체크

    Returns:
        {"status": "healthy", "generator": bool}
    """
    return {
        "status": "healthy" if report_generator else "not_initialized",
        "generator": report_generator is not None
    }
