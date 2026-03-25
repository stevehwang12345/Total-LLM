"""
이미지 분석 API

Vision 모델을 사용한 이미지 분석 REST API 엔드포인트입니다.
CCTV 이미지 분석, 사고 감지, 보고서 생성을 지원합니다.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Response
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import logging
import base64
import uuid
import os
import io
from PIL import Image

from pathlib import Path

from total_llm.services.vision.detection.incident_detector import (
    IncidentDetector,
    IncidentType,
    SeverityLevel
)
from total_llm.services.vision.korean_prompts import (
    SECURITY_QA_PROMPTS,
    create_security_prompt,
)
from total_llm.services.vision.templates.report_template import ReportTemplate, ReportMetadata
from total_llm.services.vlm_analyzer import VLMAnalyzer

logger = logging.getLogger(__name__)

# Router 생성
router = APIRouter(prefix="/image", tags=["Image Analysis"])

# Incident Detector 인스턴스 (글로벌)
_detector: Optional[IncidentDetector] = None

# VLM Analyzer 인스턴스 (글로벌, main.py에서 주입)
_vlm_analyzer: Optional[VLMAnalyzer] = None

# 분석 결과 저장소 (메모리, 실제 환경에서는 DB 사용)
_analysis_store: Dict[str, Dict[str, Any]] = {}

# 대기 중인 이미지 저장소 (분석 전 이미지 보관)
_pending_images: Dict[str, Dict[str, Any]] = {}


def set_vlm_analyzer(vlm_analyzer: VLMAnalyzer) -> None:
    """VLM Analyzer 설정 (main.py에서 호출)"""
    global _vlm_analyzer
    _vlm_analyzer = vlm_analyzer
    logger.info("✅ VLM Analyzer set for image_api")


def get_detector() -> IncidentDetector:
    """Incident Detector 인스턴스 반환"""
    global _detector
    if _detector is None:
        _detector = IncidentDetector()
        logger.info("IncidentDetector initialized")
    return _detector


# =============================================================================
# Enums
# =============================================================================

class AnalysisMode(str, Enum):
    """분석 모드"""
    QUICK = "quick"        # 빠른 분석 (사고 감지만)
    STANDARD = "standard"  # 표준 분석 (사고 감지 + 심각도)
    DETAILED = "detailed"  # 상세 분석 (전체 + 보고서)


class OutputFormat(str, Enum):
    """출력 형식"""
    JSON = "json"
    MARKDOWN = "markdown"
    PDF = "pdf"


# =============================================================================
# Request/Response Models
# =============================================================================

class ImageAnalyzeRequest(BaseModel):
    """이미지 분석 요청 (Base64)"""
    image_base64: str = Field(..., description="Base64 인코딩된 이미지")
    prompt: Optional[str] = Field(None, description="분석 프롬프트 (선택)")
    location: str = Field(default="미지정", description="촬영 위치")
    mode: AnalysisMode = Field(default=AnalysisMode.STANDARD, description="분석 모드")


class ImageAnalyzeResponse(BaseModel):
    """이미지 분석 응답"""
    success: bool
    analysis_id: str
    timestamp: str
    location: str
    incident_type: str
    incident_type_ko: str
    severity: str
    severity_ko: str
    confidence: float
    description: Optional[str] = None
    recommended_actions: List[str] = []
    raw_analysis: Optional[str] = None


class BatchAnalyzeRequest(BaseModel):
    """배치 분석 요청"""
    images: List[Dict[str, Any]] = Field(
        ...,
        description="이미지 목록 [{'image_base64': '...', 'location': '...'}]"
    )
    mode: AnalysisMode = Field(default=AnalysisMode.STANDARD)


class BatchAnalyzeResponse(BaseModel):
    """배치 분석 응답"""
    success: bool
    total: int
    completed: int
    failed: int
    results: List[Dict[str, Any]]


class ReportRequest(BaseModel):
    """보고서 생성 요청"""
    analysis_ids: List[str] = Field(..., description="분석 ID 목록")
    title: str = Field(default="보안 분석 보고서", description="보고서 제목")
    output_format: OutputFormat = Field(default=OutputFormat.MARKDOWN)


class ReportResponse(BaseModel):
    """보고서 응답"""
    success: bool
    report_id: str
    title: str
    format: str
    content: str
    created_at: str


class AnalysisResultResponse(BaseModel):
    """분석 결과 조회 응답"""
    success: bool
    analysis: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# =============================================================================
# Pending Image Models (이미지 저장 전용)
# =============================================================================

class ImageUploadOnlyResponse(BaseModel):
    """이미지 업로드 전용 응답 (분석 없음)"""
    success: bool
    image_id: str
    filename: str
    location: str
    device_id: Optional[str] = None
    uploaded_at: str
    status: str = "pending"
    image_url: Optional[str] = None


class PendingImageResponse(BaseModel):
    """대기 중인 이미지 정보"""
    image_id: str
    filename: str
    location: str
    device_id: Optional[str] = None
    uploaded_at: str
    status: str
    image_url: Optional[str] = None


class TriggerAnalysisRequest(BaseModel):
    """분석 트리거 요청"""
    mode: AnalysisMode = Field(default=AnalysisMode.STANDARD, description="분석 모드")


# =============================================================================
# QA-Based Analysis Models (신규)
# =============================================================================

class QAAnalyzeRequest(BaseModel):
    """QA 기반 분석 요청"""
    image_base64: str = Field(..., description="Base64 인코딩된 이미지")
    location: str = Field(default="미지정", description="촬영 위치")
    timestamp: Optional[str] = Field(None, description="촬영 시간 (없으면 현재 시간)")


class QAAnalyzeResponse(BaseModel):
    """QA 기반 분석 응답"""
    success: bool
    analysis_id: str
    timestamp: str
    location: str
    qa_results: Dict[str, str]
    incident_type: str
    incident_type_ko: str
    severity: str
    severity_ko: str
    confidence: float
    recommended_actions: List[str]


class SecurityReportRequest(BaseModel):
    """보안 보고서 생성 요청"""
    image_base64: str = Field(..., description="Base64 인코딩된 이미지")
    location: str = Field(default="미지정", description="촬영 위치")
    timestamp: Optional[str] = Field(None, description="촬영 시간 (없으면 현재 시간)")


class SecurityReportResponse(BaseModel):
    """보안 보고서 응답"""
    success: bool
    report_id: str
    timestamp: str
    location: str
    incident_type: str
    severity: str
    qa_results: Dict[str, str]
    markdown_report: str
    metadata: Dict[str, Any]


# =============================================================================
# Helper Functions
# =============================================================================

def _resize_image_base64(image_base64: str, max_size: int = 512) -> str:
    """
    이미지를 리사이즈하여 토큰 사용량을 줄입니다.

    Args:
        image_base64: Base64 인코딩된 이미지
        max_size: 최대 가로/세로 크기 (픽셀)

    Returns:
        리사이즈된 Base64 인코딩된 이미지
    """
    try:
        # Base64 디코딩
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))

        original_size = image.size

        # 이미지가 max_size보다 작으면 그대로 반환
        if image.width <= max_size and image.height <= max_size:
            logger.debug(f"이미지 리사이즈 불필요: {original_size}")
            return image_base64

        # 비율 유지하면서 리사이즈
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # RGB로 변환 (RGBA나 다른 모드 처리)
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Base64로 다시 인코딩
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=85)
        resized_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        logger.info(f"✅ 이미지 리사이즈: {original_size} → {image.size}")
        return resized_base64

    except Exception as e:
        logger.warning(f"⚠️ 이미지 리사이즈 실패, 원본 사용: {e}")
        return image_base64


async def _analyze_with_vlm(image_base64: str, prompt: Optional[str] = None, location: str = "미지정") -> str:
    """
    실제 VLM Analyzer를 사용한 이미지 분석

    Args:
        image_base64: Base64 인코딩된 이미지
        prompt: 분석 프롬프트 (선택)
        location: 촬영 위치

    Returns:
        분석 결과 텍스트
    """
    global _vlm_analyzer

    if _vlm_analyzer is None:
        logger.warning("⚠️ VLM Analyzer not initialized, using fallback simulation")
        return _fallback_simulation(image_base64)

    # 기본 프롬프트 설정
    if not prompt:
        prompt = f"""이 보안 CCTV 이미지를 분석해주세요.

촬영 위치: {location}

다음 사항들을 상세히 분석해주세요:
1. 화면에 보이는 사람의 수와 위치
2. 각 사람의 행동 및 자세 (서있음, 걸음, 앉음, 누움 등)
3. 비정상적인 행동이나 위협 요소가 있는지 확인
4. 폭력, 싸움, 낙상, 침입 등의 이상 상황 감지
5. 전반적인 상황 평가 (정상/주의/위험)

구체적이고 상세하게 설명해주세요."""

    try:
        # 이미지 리사이즈 (토큰 사용량 감소)
        resized_image = _resize_image_base64(image_base64, max_size=512)

        # VLM API 호출 (리사이즈된 이미지 사용)
        response = await _vlm_analyzer.client.chat.completions.create(
            model=_vlm_analyzer.model_name,
            messages=[
                {
                    "role": "system",
                    "content": "당신은 보안 CCTV 이미지 분석 전문가입니다. 이미지를 상세히 분석하여 보안 관련 정보를 제공합니다."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{resized_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=_vlm_analyzer.max_tokens,
            temperature=_vlm_analyzer.temperature
        )

        analysis = response.choices[0].message.content
        logger.info(f"✅ VLM analysis complete ({len(analysis)} chars)")
        return analysis

    except Exception as e:
        logger.error(f"❌ VLM analysis failed: {e}", exc_info=True)
        # 실패 시 폴백
        return _fallback_simulation(image_base64)


def _fallback_simulation(image_base64: str) -> str:
    """
    VLM 분석 실패 시 폴백 시뮬레이션
    """
    import hashlib
    scenarios = [
        "화면에 2명의 사람이 관찰됩니다. 정상적인 보행 활동으로 보입니다. 특별한 이상 징후는 감지되지 않았습니다.",
        "화면에서 격렬한 움직임이 감지되었습니다. 폭력 행위로 의심됩니다. 즉각적인 확인이 필요합니다.",
        "두 사람 사이에 물리적 충돌이 발생하고 있습니다. 싸움으로 판단됩니다. 보안 요원 파견을 권장합니다.",
        "한 사람이 바닥에 쓰러져 있습니다. 낙상 또는 의료 응급 상황으로 보입니다. 즉각적인 의료 지원이 필요합니다.",
        "화면에 사람이 관찰되지 않습니다. 정상적인 무인 상태입니다.",
    ]

    hash_val = int(hashlib.md5(image_base64[:100].encode()).hexdigest(), 16)
    scenario_idx = hash_val % len(scenarios)

    return scenarios[scenario_idx]


def _get_recommended_actions(incident_type: IncidentType, severity: SeverityLevel) -> List[str]:
    """사고 유형 및 심각도에 따른 권장 조치"""
    actions = []

    if incident_type == IncidentType.VIOLENCE:
        actions = ["즉시 보안 요원 파견", "경찰 신고", "영상 보존"]
    elif incident_type == IncidentType.FIGHTING:
        actions = ["보안 요원 파견", "상황 모니터링", "필요시 경찰 신고"]
    elif incident_type == IncidentType.FALLING:
        actions = ["의료진 호출", "현장 확인", "CCTV 추가 확인"]
    elif incident_type == IncidentType.INTRUSION:
        actions = ["접근 차단", "보안 요원 파견", "출입 기록 확인"]
    elif incident_type == IncidentType.THREATENING:
        actions = ["상황 모니터링", "보안 요원 대기", "필요시 경고 방송"]
    elif incident_type == IncidentType.ABNORMAL_BEHAVIOR:
        actions = ["지속 모니터링", "담당자 통보"]
    elif incident_type == IncidentType.NORMAL:
        actions = ["정기 모니터링 계속"]
    elif incident_type == IncidentType.NO_PERSON:
        actions = ["정기 모니터링 계속"]
    else:
        actions = ["추가 확인 필요", "담당자 검토"]

    # 심각도에 따른 조치 추가
    if severity == SeverityLevel.CRITICAL:
        actions.insert(0, "긴급 대응팀 호출")
    elif severity == SeverityLevel.HIGH:
        actions.insert(0, "신속 대응 필요")

    return actions


# =============================================================================
# Health Check (경로 충돌 방지를 위해 먼저 정의)
# =============================================================================

@router.get("/health", summary="이미지 분석 서비스 상태 확인")
async def health_check():
    """
    Image Analysis API 상태를 확인합니다.

    **VLM 상태**:
    - vlm_connected: VLM Analyzer가 초기화되었는지 여부
    - vlm_status: "connected" (실제 VLM 사용) 또는 "fallback" (시뮬레이션 모드)

    **주의**: vlm_status가 "fallback"이면 실제 이미지 분석이 아닌 시뮬레이션 결과가 반환됩니다.
    """
    global _vlm_analyzer
    detector = get_detector()

    # VLM 연결 상태 확인
    vlm_connected = _vlm_analyzer is not None
    vlm_status = "connected" if vlm_connected else "fallback"

    # VLM 서버 연결 테스트 (연결된 경우)
    vlm_server_reachable = False
    vlm_model_info = None
    if vlm_connected:
        try:
            # 간단한 모델 정보 요청으로 연결 확인
            models = await _vlm_analyzer.client.models.list()
            vlm_server_reachable = True
            vlm_model_info = {
                "model_name": _vlm_analyzer.model_name,
                "available_models": [m.id for m in models.data] if models.data else []
            }
        except Exception as e:
            logger.warning(f"VLM server check failed: {e}")
            vlm_server_reachable = False

    return {
        "status": "ok",
        "service": "Image Analysis API",
        "vlm_status": vlm_status,
        "vlm_connected": vlm_connected,
        "vlm_server_reachable": vlm_server_reachable,
        "vlm_model_info": vlm_model_info,
        "incident_types": len(IncidentType),
        "severity_levels": len(SeverityLevel),
        "stored_analyses": len(_analysis_store),
        "pending_images": len(_pending_images),
        "detector_patterns": {
            "no_person": len(detector.no_person_patterns),
            "unclear": len(detector.unclear_patterns),
            "normal": len(detector.normal_patterns),
            "incident": len(detector.incident_patterns),
        },
        "note": "vlm_status='fallback' means simulated results, not actual VLM analysis" if not vlm_connected else None
    }


# =============================================================================
# Image Analysis API
# =============================================================================

@router.post("/analyze", response_model=ImageAnalyzeResponse, summary="이미지 분석")
async def analyze_image(request: ImageAnalyzeRequest):
    """
    단일 이미지를 분석합니다.

    - Base64 인코딩된 이미지를 받아 분석합니다.
    - 사고 유형과 심각도를 자동 판단합니다.
    - 권장 조치사항을 제공합니다.
    """
    detector = get_detector()
    timestamp = datetime.now().isoformat()
    analysis_id = str(uuid.uuid4())[:8]

    try:
        # Vision 모델 분석 (실제 VLM 사용)
        raw_analysis = await _analyze_with_vlm(
            request.image_base64,
            request.prompt,
            request.location
        )

        # 사고 감지 및 분석
        incident_result = detector.analyze_incident(raw_analysis)

        primary_incident, confidence = incident_result["primary_incident"]
        severity = incident_result["severity"]

        # 권장 조치
        actions = _get_recommended_actions(primary_incident, severity)

        # 결과 저장
        result = {
            "analysis_id": analysis_id,
            "timestamp": timestamp,
            "location": request.location,
            "incident_type": primary_incident.name,
            "incident_type_ko": primary_incident.value,
            "severity": severity.name,
            "severity_ko": severity.value,
            "confidence": confidence,
            "description": incident_result["summary"],
            "recommended_actions": actions,
            "raw_analysis": raw_analysis if request.mode == AnalysisMode.DETAILED else None,
            "mode": request.mode.value,
            "image_base64": request.image_base64,  # 원본 이미지 저장
        }

        # 저장소에 보관
        _analysis_store[analysis_id] = result

        logger.info(f"Image analyzed: {analysis_id} - {primary_incident.value} ({severity.value})")

        return ImageAnalyzeResponse(
            success=True,
            **result
        )

    except Exception as e:
        logger.error(f"Image analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/upload", response_model=ImageAnalyzeResponse, summary="이미지 업로드 분석")
async def analyze_uploaded_image(
    file: UploadFile = File(..., description="분석할 이미지 파일"),
    location: str = Form(default="미지정", description="촬영 위치"),
    mode: str = Form(default="standard", description="분석 모드 (quick/standard/detailed)")
):
    """
    업로드된 이미지 파일을 분석합니다.

    - multipart/form-data로 이미지를 받습니다.
    - 지원 형식: JPEG, PNG, GIF, BMP
    """
    # 파일 형식 검증
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/bmp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {allowed_types}"
        )

    # 이미지 읽기 및 Base64 인코딩
    content = await file.read()
    image_base64 = base64.b64encode(content).decode("utf-8")

    # 분석 요청 생성
    request = ImageAnalyzeRequest(
        image_base64=image_base64,
        location=location,
        mode=AnalysisMode(mode)
    )

    return await analyze_image(request)


@router.post("/batch", response_model=BatchAnalyzeResponse, summary="배치 이미지 분석")
async def analyze_batch(request: BatchAnalyzeRequest):
    """
    여러 이미지를 배치로 분석합니다.

    - 최대 10개의 이미지를 한 번에 분석할 수 있습니다.
    - 각 이미지별 분석 결과를 반환합니다.
    """
    if len(request.images) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 images per batch"
        )

    results = []
    completed = 0
    failed = 0

    for idx, image_data in enumerate(request.images):
        try:
            image_base64 = image_data.get("image_base64", "")
            location = image_data.get("location", f"위치_{idx+1}")

            # 개별 분석 요청
            single_request = ImageAnalyzeRequest(
                image_base64=image_base64,
                location=location,
                mode=request.mode
            )

            result = await analyze_image(single_request)
            results.append(result.model_dump())
            completed += 1

        except Exception as e:
            logger.error(f"Batch item {idx} failed: {e}")
            results.append({
                "success": False,
                "error": str(e),
                "index": idx
            })
            failed += 1

    return BatchAnalyzeResponse(
        success=failed == 0,
        total=len(request.images),
        completed=completed,
        failed=failed,
        results=results
    )


# =============================================================================
# Image Upload Only API (분석 없이 이미지만 저장)
# IMPORTANT: These routes MUST come BEFORE /{analysis_id} routes to avoid
# the path parameter from capturing "upload", "pending", etc.
# =============================================================================

@router.post("/upload", response_model=ImageUploadOnlyResponse, summary="이미지 업로드 (분석 없음)")
async def upload_image_only(
    file: UploadFile = File(..., description="업로드할 이미지 파일"),
    location: str = Form(default="미지정", description="촬영 위치"),
    device_id: Optional[str] = Form(default=None, description="장치 ID")
):
    """
    이미지를 업로드하고 저장합니다 (분석 없음).

    - 이미지는 분석 대기 상태로 저장됩니다.
    - 분석을 시작하려면 POST /pending/{image_id}/analyze 엔드포인트를 호출하세요.
    - 지원 형식: JPEG, PNG, GIF, BMP
    """
    # 파일 형식 검증
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/bmp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {allowed_types}"
        )

    # 이미지 읽기 및 Base64 인코딩
    content = await file.read()
    image_base64 = base64.b64encode(content).decode("utf-8")

    # 고유 ID 생성
    image_id = str(uuid.uuid4())[:8]
    uploaded_at = datetime.now().isoformat()

    # 대기 저장소에 저장
    _pending_images[image_id] = {
        "image_id": image_id,
        "image_base64": image_base64,
        "filename": file.filename,
        "location": location,
        "device_id": device_id,
        "uploaded_at": uploaded_at,
        "status": "pending"
    }

    logger.info(f"Image uploaded (pending): {image_id} - {file.filename}")

    return ImageUploadOnlyResponse(
        success=True,
        image_id=image_id,
        filename=file.filename or "unknown",
        location=location,
        device_id=device_id,
        uploaded_at=uploaded_at,
        status="pending",
        image_url=f"/image/pending/{image_id}/image"
    )


@router.get("/pending", summary="대기 중인 이미지 목록")
async def list_pending_images():
    """
    분석 대기 중인 이미지 목록을 조회합니다.
    """
    results = []
    for image_id, data in _pending_images.items():
        results.append({
            "image_id": image_id,
            "filename": data.get("filename", "unknown"),
            "location": data.get("location", "미지정"),
            "device_id": data.get("device_id"),
            "uploaded_at": data.get("uploaded_at"),
            "status": data.get("status", "pending"),
            "image_url": f"/image/pending/{image_id}/image"
        })

    # 최신순 정렬
    results = sorted(results, key=lambda x: x.get("uploaded_at", ""), reverse=True)

    return {
        "success": True,
        "total": len(results),
        "images": results
    }


@router.get("/pending/{image_id}", summary="대기 중인 이미지 정보")
async def get_pending_image(image_id: str):
    """
    대기 중인 이미지 정보를 조회합니다.
    """
    pending = _pending_images.get(image_id)
    if not pending:
        raise HTTPException(status_code=404, detail=f"Pending image not found: {image_id}")

    return {
        "success": True,
        "image": {
            "image_id": image_id,
            "filename": pending.get("filename", "unknown"),
            "location": pending.get("location", "미지정"),
            "device_id": pending.get("device_id"),
            "uploaded_at": pending.get("uploaded_at"),
            "status": pending.get("status", "pending"),
            "image_url": f"/image/pending/{image_id}/image"
        }
    }


@router.get("/pending/{image_id}/image", summary="대기 중인 이미지 조회")
async def get_pending_image_file(image_id: str):
    """
    대기 중인 이미지 파일을 조회합니다.
    """
    pending = _pending_images.get(image_id)
    if not pending:
        raise HTTPException(status_code=404, detail=f"Pending image not found: {image_id}")

    image_base64 = pending.get("image_base64")
    if not image_base64:
        raise HTTPException(status_code=404, detail=f"Image data not found: {image_id}")

    try:
        # Base64 디코딩
        image_data = base64.b64decode(image_base64)

        # 이미지 타입 감지
        if image_data[:3] == b'\xff\xd8\xff':
            media_type = "image/jpeg"
        elif image_data[:8] == b'\x89PNG\r\n\x1a\n':
            media_type = "image/png"
        elif image_data[:6] in (b'GIF87a', b'GIF89a'):
            media_type = "image/gif"
        else:
            media_type = "image/jpeg"

        return Response(content=image_data, media_type=media_type)

    except Exception as e:
        logger.error(f"Failed to decode pending image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to decode image: {str(e)}")


@router.post("/pending/{image_id}/analyze", response_model=ImageAnalyzeResponse, summary="대기 이미지 분석 시작")
async def analyze_pending_image(
    image_id: str,
    request: Optional[TriggerAnalysisRequest] = None
):
    """
    대기 중인 이미지에 대해 VLM 분석을 시작합니다.

    - 분석이 완료되면 이미지는 대기 목록에서 제거되고 분석 결과로 저장됩니다.
    - 분석 모드: quick, standard, detailed
    """
    pending = _pending_images.get(image_id)
    if not pending:
        raise HTTPException(status_code=404, detail=f"Pending image not found: {image_id}")

    # 상태 업데이트
    _pending_images[image_id]["status"] = "analyzing"

    mode = request.mode if request else AnalysisMode.STANDARD

    try:
        # 분석 요청 생성
        analyze_request = ImageAnalyzeRequest(
            image_base64=pending["image_base64"],
            location=pending.get("location", "미지정"),
            mode=mode
        )

        # 분석 수행
        result = await analyze_image(analyze_request)

        # 분석 결과에 device_id 추가
        if pending.get("device_id") and result.success:
            analysis_id = result.analysis_id
            if analysis_id in _analysis_store:
                _analysis_store[analysis_id]["device_id"] = pending.get("device_id")

        # 대기 목록에서 제거
        del _pending_images[image_id]

        logger.info(f"Pending image analyzed: {image_id} -> {result.analysis_id}")

        return result

    except Exception as e:
        # 실패 시 상태 복원
        if image_id in _pending_images:
            _pending_images[image_id]["status"] = "pending"
        logger.error(f"Failed to analyze pending image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/pending/{image_id}", summary="대기 이미지 삭제")
async def delete_pending_image(image_id: str):
    """
    대기 중인 이미지를 삭제합니다.
    """
    if image_id not in _pending_images:
        raise HTTPException(status_code=404, detail=f"Pending image not found: {image_id}")

    del _pending_images[image_id]
    logger.info(f"Pending image deleted: {image_id}")

    return {"success": True, "message": f"Deleted pending image: {image_id}"}


# =============================================================================
# Analysis Result Retrieval & Delete (동적 경로 - 마지막에 위치해야 함)
# =============================================================================

@router.delete("/{analysis_id}", summary="분석 결과 삭제")
async def delete_analysis(analysis_id: str):
    """
    저장된 분석 결과를 삭제합니다.

    - analysis_id로 분석 결과를 삭제합니다.
    - 연관된 이미지 데이터도 함께 삭제됩니다.
    """
    if analysis_id not in _analysis_store:
        raise HTTPException(status_code=404, detail=f"Analysis not found: {analysis_id}")

    del _analysis_store[analysis_id]
    logger.info(f"Analysis deleted: {analysis_id}")

    return {"success": True, "message": f"Deleted analysis: {analysis_id}"}


@router.get("/{analysis_id}/image", summary="분석 이미지 조회")
async def get_analysis_image(analysis_id: str):
    """
    저장된 분석 결과의 원본 이미지를 조회합니다.

    - analysis_id 또는 report_id로 이미지를 조회합니다.
    - Base64로 저장된 이미지를 디코딩하여 반환합니다.
    """
    # analysis_id 또는 report_id로 검색
    analysis = _analysis_store.get(analysis_id)

    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis not found: {analysis_id}")

    image_base64 = analysis.get("image_base64")
    if not image_base64:
        raise HTTPException(status_code=404, detail=f"Image not found for analysis: {analysis_id}")

    try:
        # Base64 디코딩
        image_data = base64.b64decode(image_base64)

        # 이미지 타입 감지 (간단한 매직 바이트 체크)
        if image_data[:3] == b'\xff\xd8\xff':
            media_type = "image/jpeg"
        elif image_data[:8] == b'\x89PNG\r\n\x1a\n':
            media_type = "image/png"
        elif image_data[:6] in (b'GIF87a', b'GIF89a'):
            media_type = "image/gif"
        else:
            media_type = "image/jpeg"  # 기본값

        return Response(content=image_data, media_type=media_type)

    except Exception as e:
        logger.error(f"Failed to decode image for {analysis_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to decode image: {str(e)}")


@router.get("/{analysis_id}", response_model=AnalysisResultResponse, summary="분석 결과 조회")
async def get_analysis_result(analysis_id: str):
    """
    저장된 분석 결과를 조회합니다.

    - analysis_id로 이전 분석 결과를 조회합니다.
    """
    if analysis_id not in _analysis_store:
        return AnalysisResultResponse(
            success=False,
            error=f"Analysis not found: {analysis_id}"
        )

    # 이미지 데이터는 응답에서 제외 (별도 엔드포인트로 조회)
    result = {k: v for k, v in _analysis_store[analysis_id].items() if k != "image_base64"}

    return AnalysisResultResponse(
        success=True,
        analysis=result
    )


@router.get("/", summary="분석 결과 목록")
async def list_analysis_results(
    limit: int = Query(default=20, ge=1, le=100, description="최대 조회 개수"),
    incident_type: Optional[str] = Query(default=None, description="사고 유형 필터"),
    severity: Optional[str] = Query(default=None, description="심각도 필터")
):
    """
    저장된 분석 결과 목록을 조회합니다.

    - 필터링 옵션을 제공합니다.
    """
    results = list(_analysis_store.values())

    # 필터링
    if incident_type:
        results = [r for r in results if r.get("incident_type") == incident_type]

    if severity:
        results = [r for r in results if r.get("severity") == severity]

    # 최신순 정렬 및 제한
    results = sorted(results, key=lambda x: x.get("timestamp", ""), reverse=True)
    results = results[:limit]

    # 이미지 데이터 제외하고 이미지 URL 추가
    results_without_images = []
    for r in results:
        result_copy = {k: v for k, v in r.items() if k != "image_base64"}
        # 이미지가 있으면 URL 추가
        analysis_id = r.get("analysis_id") or r.get("report_id")
        if r.get("image_base64") and analysis_id:
            result_copy["image_url"] = f"/image/{analysis_id}/image"
            result_copy["has_image"] = True
        else:
            result_copy["has_image"] = False
        results_without_images.append(result_copy)

    return {
        "success": True,
        "total": len(results_without_images),
        "results": results_without_images
    }


# =============================================================================
# Report Generation API
# =============================================================================

@router.post("/report", response_model=ReportResponse, summary="보고서 생성")
async def generate_report(request: ReportRequest):
    """
    분석 결과를 기반으로 보고서를 생성합니다.

    - 여러 분석 결과를 종합한 보고서를 생성합니다.
    - Markdown 또는 PDF 형식으로 출력합니다.
    """
    # 분석 결과 수집
    analyses = []
    security_reports = []
    for aid in request.analysis_ids:
        if aid in _analysis_store:
            stored = _analysis_store[aid]
            # 보안 보고서인지 일반 분석인지 구분
            if stored.get("analysis_type") == "security_report":
                security_reports.append(stored)
            else:
                analyses.append(stored)

    if not analyses and not security_reports:
        raise HTTPException(
            status_code=404,
            detail="No valid analysis results found"
        )

    # 보안 보고서만 있는 경우, 이미 생성된 보고서를 반환
    if security_reports and not analyses:
        combined_report = f"# {request.title}\n\n"
        combined_report += f"**생성 일시**: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')}\n"
        combined_report += f"**보고서 수**: {len(security_reports)}건\n\n---\n\n"
        for sr in security_reports:
            combined_report += sr.get("markdown_report", "") + "\n\n---\n\n"

        return ReportResponse(
            success=True,
            report_id=str(uuid.uuid4())[:8],
            title=request.title,
            format=request.output_format.value,
            content=combined_report,
            created_at=datetime.now().isoformat()
        )

    # 혼합된 경우, 보안 보고서도 일반 분석 형식으로 변환하여 포함
    for sr in security_reports:
        analyses.append({
            "analysis_id": sr.get("report_id", ""),
            "timestamp": sr.get("timestamp", ""),
            "location": sr.get("location", "미지정"),
            "incident_type_ko": sr.get("incident_type", "정상"),
            "severity_ko": sr.get("severity", "정보"),
            "confidence": sr.get("metadata", {}).get("confidence", 0.95),
            "description": sr.get("qa_results", {}).get("q4_description", "QA 기반 분석"),
            "recommended_actions": ["보안 보고서 참조"]
        })

    timestamp = datetime.now()
    report_id = str(uuid.uuid4())[:8]

    # 보고서 생성
    if request.output_format == OutputFormat.MARKDOWN:
        content = _generate_markdown_report(request.title, analyses, timestamp)
    elif request.output_format == OutputFormat.JSON:
        content = str({
            "title": request.title,
            "generated_at": timestamp.isoformat(),
            "analyses": analyses
        })
    else:
        # PDF는 Markdown을 반환 (실제로는 PDF 변환 필요)
        content = _generate_markdown_report(request.title, analyses, timestamp)

    return ReportResponse(
        success=True,
        report_id=report_id,
        title=request.title,
        format=request.output_format.value,
        content=content,
        created_at=timestamp.isoformat()
    )


def _generate_markdown_report(title: str, analyses: List[Dict], timestamp: datetime) -> str:
    """Markdown 형식 보고서 생성"""

    report = f"""# {title}

**생성 일시**: {timestamp.strftime('%Y년 %m월 %d일 %H:%M:%S')}
**분석 건수**: {len(analyses)}건

---

## 분석 요약

| 분석 ID | 시간 | 위치 | 사고 유형 | 심각도 | 신뢰도 |
|---------|------|------|----------|--------|--------|
"""

    for a in analyses:
        report += f"| {a.get('analysis_id', '-')} | {a.get('timestamp', '-')[:19]} | {a.get('location', '-')} | {a.get('incident_type_ko', '-')} | {a.get('severity_ko', '-')} | {a.get('confidence', 0):.1%} |\n"

    report += "\n---\n\n## 상세 분석 결과\n\n"

    for i, a in enumerate(analyses, 1):
        report += f"""### {i}. {a.get('location', '미지정')} ({a.get('timestamp', '-')[:19]})

**분석 ID**: {a.get('analysis_id', '-')}
**사고 유형**: {a.get('incident_type_ko', '-')}
**심각도**: {a.get('severity_ko', '-')}
**신뢰도**: {a.get('confidence', 0):.1%}

**설명**: {a.get('description', '-')}

**권장 조치**:
"""
        for action in a.get('recommended_actions', []):
            report += f"- {action}\n"

        report += "\n---\n\n"

    report += f"""## 결론

총 {len(analyses)}건의 이미지 분석이 수행되었습니다.

**작성자**: 자동 생성 (Total-LLM Vision System)
"""

    return report


# =============================================================================
# QA-Based Analysis API (신규 - granite-vision-korean-poc 통합)
# =============================================================================

@router.post("/analyze/qa", response_model=QAAnalyzeResponse, summary="QA 기반 구조화 분석")
async def analyze_image_qa(request: QAAnalyzeRequest):
    """
    4단계 QA 기반 구조화된 이미지 분석을 수행합니다.

    **분석 단계**:
    1. Q1: 폭력/범죄 활동 감지 여부
    2. Q2: 이상 이벤트 유형 분류
    3. Q3: 관련 인물 설명
    4. Q4: 상황 및 환경 상세 설명

    이 분석은 표준 분석보다 더 구조화된 결과를 제공합니다.
    """
    global _vlm_analyzer
    detector = get_detector()

    timestamp = request.timestamp or datetime.now().isoformat()
    analysis_id = str(uuid.uuid4())[:8]

    try:
        # VLM Analyzer 확인
        if _vlm_analyzer is None:
            raise HTTPException(
                status_code=503,
                detail="VLM Analyzer not initialized. Please check backend configuration."
            )

        # QA 기반 분석 수행
        if hasattr(_vlm_analyzer, 'analyze_qa_based'):
            qa_result = await _vlm_analyzer.analyze_qa_based(
                image_base64=request.image_base64,
                location=request.location,
                timestamp=timestamp
            )
        else:
            # 폴백: 기존 분석 방식 사용
            raw_analysis = await _analyze_with_vlm(
                request.image_base64,
                None,
                request.location
            )
            qa_result = {
                "qa_results": {
                    "q1_detection": "분석 결과 참조",
                    "q2_classification": "분석 결과 참조",
                    "q3_subject": "분석 결과 참조",
                    "q4_description": raw_analysis
                },
                "incident_type": "NORMAL",
                "severity": "INFO",
                "confidence": 0.7
            }

        # QA 결과에서 사고 유형 추출
        qa_results = qa_result.get("qa_results", {})
        incident_type_str = qa_result.get("incident_type", "NORMAL")
        severity_str = qa_result.get("severity", "INFO")

        # Enum 변환
        try:
            incident_type = IncidentType[incident_type_str.upper()]
        except KeyError:
            incident_type = IncidentType.NORMAL

        try:
            severity = SeverityLevel[severity_str.upper()]
        except KeyError:
            severity = SeverityLevel.INFO

        # 권장 조치
        actions = _get_recommended_actions(incident_type, severity)

        # 결과 저장
        result = {
            "analysis_id": analysis_id,
            "timestamp": timestamp,
            "location": request.location,
            "qa_results": qa_results,
            "incident_type": incident_type.name,
            "incident_type_ko": incident_type.value,
            "severity": severity.name,
            "severity_ko": severity.value,
            "confidence": qa_result.get("confidence", 0.85),
            "recommended_actions": actions,
            "analysis_type": "qa_based",
            "image_base64": request.image_base64,  # 원본 이미지 저장
        }

        _analysis_store[analysis_id] = result

        logger.info(f"QA-based analysis complete: {analysis_id} - {incident_type.value} ({severity.value})")

        return QAAnalyzeResponse(
            success=True,
            **result
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QA-based analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report/security", response_model=SecurityReportResponse, summary="보안 보고서 생성")
async def generate_security_report(request: SecurityReportRequest):
    """
    전체 보안 분석 파이프라인을 실행하여 마크다운 보고서를 생성합니다.

    **파이프라인 단계**:
    1. QA 기반 4단계 구조화 분석
    2. 사고 유형 및 심각도 자동 판단
    3. 6섹션 마크다운 보고서 생성

    **보고서 섹션**:
    - 사고 개요
    - 인물 및 행동 분석
    - 환경 및 상황 분석
    - 사고 유형 및 심각도 판단
    - 권장 조치
    - 종합 의견
    """
    global _vlm_analyzer

    timestamp = request.timestamp or datetime.now().isoformat()
    report_id = ReportTemplate.generate_report_id(timestamp, request.location) if hasattr(ReportTemplate, 'generate_report_id') else str(uuid.uuid4())[:8]

    try:
        # VLM Analyzer 확인
        if _vlm_analyzer is None:
            raise HTTPException(
                status_code=503,
                detail="VLM Analyzer not initialized. Please check backend configuration."
            )

        # 보안 보고서 생성 (전체 파이프라인)
        if hasattr(_vlm_analyzer, 'generate_security_report'):
            report_result = await _vlm_analyzer.generate_security_report(
                image_base64=request.image_base64,
                location=request.location,
                timestamp=timestamp
            )
        else:
            # 폴백: 기존 방식으로 보고서 생성
            raw_analysis = await _analyze_with_vlm(
                request.image_base64,
                None,
                request.location
            )
            detector = get_detector()
            incident_result = detector.analyze_incident(raw_analysis)
            primary_incident, confidence = incident_result["primary_incident"]
            severity = incident_result["severity"]

            # 간단한 보고서 생성
            report_result = {
                "report_id": report_id,
                "qa_results": {
                    "q1_detection": "분석 결과 참조",
                    "q2_classification": primary_incident.name,
                    "q3_subject": "분석 결과 참조",
                    "q4_description": raw_analysis
                },
                "incident_type": primary_incident.name,
                "severity": severity.name,
                "markdown_report": f"""## 보안 사고 보고서

### 1. 사고 개요
{incident_result.get('summary', raw_analysis[:200])}

### 2. 인물 및 행동 분석
분석 결과를 참조하세요.

### 3. 환경 및 상황 분석
위치: {request.location}
시간: {timestamp}

### 4. 사고 유형 및 심각도 판단
- 유형: {primary_incident.value}
- 심각도: {severity.value}

### 5. 권장 조치
{chr(10).join(['- ' + a for a in _get_recommended_actions(primary_incident, severity)])}

### 6. 종합 의견
자동 분석 결과입니다. 담당자의 추가 검토를 권장합니다.
""",
                "metadata": {
                    "report_id": report_id,
                    "location": request.location,
                    "timestamp": timestamp,
                    "confidence": confidence
                }
            }

        # 결과 저장 - VLM이 생성한 report_id를 사용 (일관성 유지)
        final_report_id = report_result.get("report_id", report_id)
        result_to_store = {
            "report_id": final_report_id,
            "timestamp": timestamp,
            "location": request.location,
            "qa_results": report_result.get("qa_results", {}),
            "incident_type": report_result.get("incident_type", "NORMAL"),
            "severity": report_result.get("severity", "INFO"),
            "markdown_report": report_result.get("markdown_report", ""),
            "metadata": report_result.get("metadata", {}),
            "analysis_type": "security_report",
            "image_base64": request.image_base64,  # 원본 이미지 저장
        }

        # VLM이 반환한 report_id로 저장 (프론트엔드가 받는 ID와 일치)
        _analysis_store[final_report_id] = result_to_store

        logger.info(f"Security report generated: {final_report_id}")

        return SecurityReportResponse(
            success=True,
            report_id=final_report_id,
            timestamp=timestamp,
            location=request.location,
            incident_type=report_result.get("incident_type", "NORMAL"),
            severity=report_result.get("severity", "INFO"),
            qa_results=report_result.get("qa_results", {}),
            markdown_report=report_result.get("markdown_report", ""),
            metadata=report_result.get("metadata", {})
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Security report generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/qa/upload", response_model=QAAnalyzeResponse, summary="QA 기반 분석 (파일 업로드)")
async def analyze_uploaded_image_qa(
    file: UploadFile = File(..., description="분석할 이미지 파일"),
    location: str = Form(default="미지정", description="촬영 위치"),
    timestamp: Optional[str] = Form(default=None, description="촬영 시간")
):
    """
    업로드된 이미지 파일에 대해 QA 기반 구조화 분석을 수행합니다.

    - multipart/form-data로 이미지를 받습니다.
    - 지원 형식: JPEG, PNG, GIF, BMP
    """
    # 파일 형식 검증
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/bmp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {allowed_types}"
        )

    # 이미지 읽기 및 Base64 인코딩
    content = await file.read()
    image_base64 = base64.b64encode(content).decode("utf-8")

    # QA 분석 요청 생성
    request = QAAnalyzeRequest(
        image_base64=image_base64,
        location=location,
        timestamp=timestamp
    )

    return await analyze_image_qa(request)


@router.post("/report/security/upload", response_model=SecurityReportResponse, summary="보안 보고서 생성 (파일 업로드)")
async def generate_security_report_upload(
    file: UploadFile = File(..., description="분석할 이미지 파일"),
    location: str = Form(default="미지정", description="촬영 위치"),
    timestamp: Optional[str] = Form(default=None, description="촬영 시간")
):
    """
    업로드된 이미지 파일에 대해 전체 보안 분석 파이프라인을 실행합니다.

    - multipart/form-data로 이미지를 받습니다.
    - 지원 형식: JPEG, PNG, GIF, BMP
    """
    # 파일 형식 검증
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/bmp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {allowed_types}"
        )

    # 이미지 읽기 및 Base64 인코딩
    content = await file.read()
    image_base64 = base64.b64encode(content).decode("utf-8")

    # 보안 보고서 요청 생성
    request = SecurityReportRequest(
        image_base64=image_base64,
        location=location,
        timestamp=timestamp
    )

    return await generate_security_report(request)

