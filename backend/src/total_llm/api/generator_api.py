"""
API Generator REST API Endpoints

LLM 기반 API 생성기의 REST API 엔드포인트를 정의합니다.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Path, Body, BackgroundTasks
from pydantic import BaseModel, Field

from total_llm.services.api_generator import (
    DeviceAnalyzer,
    DocumentationParser,
    APISpecExtractor,
    AdapterGenerator,
    SchemaGenerator,
    EndpointGenerator,
)
from total_llm.services.api_generator.analyzer import DeviceAnalysis, DeviceFingerprint
from total_llm.services.api_generator.spec_extractor import ExtractedAPI
from total_llm.services.api_generator.generators.base import GeneratedArtifact, ArtifactType, ArtifactStatus
from total_llm.services.api_generator.review import (
    ReviewWorkflow,
    ReviewItem,
    ReviewStatus,
    CodeValidator,
    AdapterDeployer,
)
from total_llm.core.dependencies import (
    GeneratorAnalysesDep,
    GeneratorArtifactsDep,
    GeneratorDeviceAnalyzerDep,
    GeneratorDeployerDep,
    GeneratorReviewWorkflowDep,
    GeneratorSpecsDep,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/generator",
    tags=["API Generator"],
)



# ========================================
# Request/Response Models
# ========================================

class DeviceAnalyzeRequest(BaseModel):
    """장치 분석 요청"""
    device_id: str = Field(..., description="장치 ID")
    ip: Optional[str] = Field(None, description="장치 IP")
    port: Optional[int] = Field(80, description="장치 포트")
    fingerprint: Optional[Dict[str, Any]] = Field(None, description="장치 핑거프린트")
    include_docs: bool = Field(True, description="API 문서 수집 여부")


class DeviceAnalyzeResponse(BaseModel):
    """장치 분석 응답"""
    analysis_id: str
    device_type: str
    manufacturer: str
    model: Optional[str]
    protocols: List[str]
    confidence: float
    status: str
    api_spec: Optional[Dict[str, Any]] = None


class CodeGenerateRequest(BaseModel):
    """코드 생성 요청"""
    analysis_id: str = Field(..., description="분석 ID")
    targets: List[str] = Field(
        default=["adapter", "schema", "endpoint"],
        description="생성 대상 (adapter, schema, endpoint, test)"
    )


class CodeGenerateResponse(BaseModel):
    """코드 생성 응답"""
    generation_id: str
    artifacts: List[Dict[str, Any]]
    status: str


class ReviewSubmitRequest(BaseModel):
    """리뷰 제출 요청"""
    artifact_id: str = Field(..., description="아티팩트 ID")
    auto_validate: bool = Field(True, description="자동 검증 수행")


class ReviewActionRequest(BaseModel):
    """리뷰 액션 요청"""
    reviewer_id: str = Field(..., description="리뷰어 ID")
    comment: Optional[str] = Field(None, description="코멘트")


class DeployRequest(BaseModel):
    """배포 요청"""
    review_id: str = Field(..., description="리뷰 ID")
    dry_run: bool = Field(False, description="테스트 실행")


# ========================================
# Analysis Endpoints
# ========================================

@router.post(
    "/analyze",
    response_model=DeviceAnalyzeResponse,
    summary="장치 분석",
    description="발견된 장치를 LLM으로 분석합니다.",
)
async def analyze_device(
    request: DeviceAnalyzeRequest,
    background_tasks: BackgroundTasks,
    analyzer: GeneratorDeviceAnalyzerDep = None,
    analyses: GeneratorAnalysesDep = None,
    specs: GeneratorSpecsDep = None,
):
    """
    장치 분석

    1. 장치 핑거프린트 분석
    2. 제조사/모델/프로토콜 식별
    3. API 문서 수집 (선택)
    4. API 스펙 추출
    """
    try:
        # 핑거프린트 생성
        fingerprint = DeviceFingerprint(
            ip=request.ip or "unknown",
            ports=[request.port] if request.port else [],
            http_headers=request.fingerprint.get("headers", {}) if request.fingerprint else {},
            http_response=request.fingerprint.get("responses", "") if request.fingerprint else None,
            banner=request.fingerprint.get("banners", "") if request.fingerprint else None,
        )

        # 장치 분석
        analysis = await analyzer.analyze(fingerprint)

        # 분석 결과 저장
        analysis_id = analysis.analysis_id
        analyses[analysis_id] = analysis

        # API 문서 수집 및 스펙 추출 (백그라운드)
        api_spec_dict = None
        if request.include_docs:
            # 동기적으로 처리 (데모용, 실제로는 백그라운드 태스크)
            try:
                doc_parser = DocumentationParser()
                docs = await doc_parser.fetch_documentation(
                    analysis.manufacturer,
                    analysis.model,
                )

                if docs:
                    spec_extractor = APISpecExtractor()
                    spec = await spec_extractor.extract(analysis, docs)
                    specs[analysis_id] = spec
                    api_spec_dict = {
                        "base_url": spec.base_url,
                        "auth_type": spec.auth_type,
                        "endpoint_count": len(spec.endpoints),
                    }
            except Exception as e:
                logger.warning(f"Failed to fetch docs: {e}")

        return DeviceAnalyzeResponse(
            analysis_id=analysis_id,
            device_type=analysis.device_type.value,
            manufacturer=analysis.manufacturer,
            model=analysis.model,
            protocols=[p.value for p in analysis.protocols],
            confidence=analysis.confidence,
            status="completed",
            api_spec=api_spec_dict,
        )

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/analyze/{analysis_id}",
    response_model=DeviceAnalyzeResponse,
    summary="분석 결과 조회",
)
async def get_analysis(
    analysis_id: str = Path(..., description="분석 ID"),
    analyses: GeneratorAnalysesDep = None,
    specs: GeneratorSpecsDep = None,
):
    """분석 결과 조회"""
    analysis = analyses.get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis not found: {analysis_id}")

    spec = specs.get(analysis_id)
    api_spec_dict = None
    if spec:
        api_spec_dict = {
            "base_url": spec.base_url,
            "auth_type": spec.auth_type,
            "endpoint_count": len(spec.endpoints),
        }

    return DeviceAnalyzeResponse(
        analysis_id=analysis_id,
        device_type=analysis.device_type.value,
        manufacturer=analysis.manufacturer,
        model=analysis.model,
        protocols=[p.value for p in analysis.protocols],
        confidence=analysis.confidence,
        status="completed",
        api_spec=api_spec_dict,
    )


# ========================================
# Generation Endpoints
# ========================================

@router.post(
    "/generate",
    response_model=CodeGenerateResponse,
    summary="코드 생성",
    description="분석 결과를 기반으로 코드를 생성합니다.",
)
async def generate_code(
    request: CodeGenerateRequest,
    analyses: GeneratorAnalysesDep = None,
    specs: GeneratorSpecsDep = None,
    artifacts_store: GeneratorArtifactsDep = None,
):
    """
    코드 생성

    1. 어댑터 코드 생성
    2. Pydantic 스키마 생성
    3. FastAPI 엔드포인트 생성
    4. 테스트 코드 생성 (선택)
    """
    analysis = analyses.get(request.analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis not found: {request.analysis_id}"
        )

    spec = specs.get(request.analysis_id)
    if not spec:
        # 기본 스펙 생성
        spec = ExtractedAPI(
            base_url="/api",
            auth_type="basic",
            content_type="application/json",
            endpoints=[],
        )

    artifacts = []
    generation_id = f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        # 어댑터 생성
        if "adapter" in request.targets:
            generator = AdapterGenerator()
            artifact = generator.generate(analysis, spec, request.analysis_id)
            artifacts_store[f"{generation_id}_adapter"] = artifact
            artifacts.append({
                "id": f"{generation_id}_adapter",
                "type": "adapter",
                "file_name": artifact.file_name,
                "status": artifact.status.value,
                "lines": len(artifact.content.splitlines()),
            })

        # 스키마 생성
        if "schema" in request.targets:
            generator = SchemaGenerator()
            artifact = generator.generate(analysis, spec, request.analysis_id)
            artifacts_store[f"{generation_id}_schema"] = artifact
            artifacts.append({
                "id": f"{generation_id}_schema",
                "type": "schema",
                "file_name": artifact.file_name,
                "status": artifact.status.value,
                "lines": len(artifact.content.splitlines()),
            })

        # 엔드포인트 생성
        if "endpoint" in request.targets:
            generator = EndpointGenerator()
            artifact = generator.generate(analysis, spec, request.analysis_id)
            artifacts_store[f"{generation_id}_endpoint"] = artifact
            artifacts.append({
                "id": f"{generation_id}_endpoint",
                "type": "endpoint",
                "file_name": artifact.file_name,
                "status": artifact.status.value,
                "lines": len(artifact.content.splitlines()),
            })

        return CodeGenerateResponse(
            generation_id=generation_id,
            artifacts=artifacts,
            status="completed",
        )

    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/artifact/{artifact_id}",
    summary="아티팩트 조회",
)
async def get_artifact(
    artifact_id: str = Path(..., description="아티팩트 ID"),
    artifacts_store: GeneratorArtifactsDep = None,
):
    """생성된 아티팩트 조회"""
    artifact = artifacts_store.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_id}")

    return {
        "id": artifact_id,
        "type": artifact.artifact_type.value,
        "file_name": artifact.file_name,
        "status": artifact.status.value,
        "content": artifact.content,
        "metadata": artifact.metadata,
    }


@router.get(
    "/artifact/{artifact_id}/preview",
    summary="아티팩트 미리보기",
)
async def preview_artifact(
    artifact_id: str = Path(..., description="아티팩트 ID"),
    lines: int = Query(50, description="미리보기 라인 수"),
    artifacts_store: GeneratorArtifactsDep = None,
):
    """아티팩트 코드 미리보기"""
    artifact = artifacts_store.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_id}")

    content_lines = artifact.content.splitlines()
    preview = "\n".join(content_lines[:lines])

    return {
        "id": artifact_id,
        "file_name": artifact.file_name,
        "total_lines": len(content_lines),
        "preview_lines": min(lines, len(content_lines)),
        "preview": preview,
    }


# ========================================
# Review Endpoints
# ========================================

@router.post(
    "/review/submit",
    summary="리뷰 제출",
)
async def submit_for_review(
    request: ReviewSubmitRequest,
    artifacts_store: GeneratorArtifactsDep = None,
    workflow: GeneratorReviewWorkflowDep = None,
):
    """아티팩트를 리뷰 큐에 제출"""
    artifact = artifacts_store.get(request.artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=404,
            detail=f"Artifact not found: {request.artifact_id}"
        )

    review_item = await workflow.submit_for_review(
        artifact,
        auto_validate=request.auto_validate
    )

    return {
        "review_id": review_item.id,
        "status": review_item.status.value,
        "validation_result": review_item.validation_result.to_dict() if review_item.validation_result else None,
    }


@router.get(
    "/review/{review_id}",
    summary="리뷰 상태 조회",
)
async def get_review_status(
    review_id: str = Path(..., description="리뷰 ID"),
    workflow: GeneratorReviewWorkflowDep = None,
):
    """리뷰 상태 조회"""
    review_item = workflow.get_review(review_id)

    if not review_item:
        raise HTTPException(status_code=404, detail=f"Review not found: {review_id}")

    return review_item.to_dict()


@router.post(
    "/review/{review_id}/approve",
    summary="리뷰 승인",
)
async def approve_review(
    review_id: str = Path(..., description="리뷰 ID"),
    request: ReviewActionRequest = Body(...),
    workflow: GeneratorReviewWorkflowDep = None,
):
    """리뷰 승인"""
    try:
        review_item = await workflow.approve(
            review_id,
            request.reviewer_id,
            request.comment
        )
        return review_item.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/review/{review_id}/reject",
    summary="리뷰 거부",
)
async def reject_review(
    review_id: str = Path(..., description="리뷰 ID"),
    request: ReviewActionRequest = Body(...),
    workflow: GeneratorReviewWorkflowDep = None,
):
    """리뷰 거부"""
    if not request.comment:
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    try:
        review_item = await workflow.reject(
            review_id,
            request.reviewer_id,
            request.comment
        )
        return review_item.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/review/pending",
    summary="대기 중인 리뷰 목록",
)
async def list_pending_reviews(workflow: GeneratorReviewWorkflowDep = None):
    """대기 중인 리뷰 목록 조회"""
    pending = workflow.get_pending_reviews()

    return {
        "count": len(pending),
        "reviews": [item.to_dict() for item in pending],
    }


@router.get(
    "/review/statistics",
    summary="리뷰 통계",
)
async def get_review_statistics(workflow: GeneratorReviewWorkflowDep = None):
    """리뷰 통계 조회"""
    return workflow.get_statistics()


# ========================================
# Deployment Endpoints
# ========================================

@router.post(
    "/deploy",
    summary="배포",
    description="승인된 아티팩트를 시스템에 배포합니다.",
)
async def deploy_artifact(
    request: DeployRequest,
    workflow: GeneratorReviewWorkflowDep = None,
    deployer: GeneratorDeployerDep = None,
):
    """아티팩트 배포"""
    review_item = workflow.get_review(request.review_id)
    if not review_item:
        raise HTTPException(status_code=404, detail=f"Review not found: {request.review_id}")

    if review_item.status != ReviewStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail=f"Review not approved: {review_item.status.value}"
        )

    result = deployer.deploy(review_item, dry_run=request.dry_run)

    return {
        "success": result.success,
        "artifact_type": result.artifact_type,
        "file_path": result.file_path,
        "error": result.error,
        "deployed_at": result.deployed_at,
        "dry_run": request.dry_run,
    }


@router.get(
    "/deployed",
    summary="배포된 어댑터 목록",
)
async def list_deployed_adapters(deployer: GeneratorDeployerDep = None):
    """배포된 어댑터 목록 조회"""
    adapters = deployer.get_deployed_adapters()

    return {
        "count": len(adapters),
        "adapters": adapters,
    }


# ========================================
# Pipeline Endpoints
# ========================================

@router.get(
    "/pipeline/status",
    summary="파이프라인 상태",
)
async def get_pipeline_status(
    analyses: GeneratorAnalysesDep = None,
    specs: GeneratorSpecsDep = None,
    artifacts_store: GeneratorArtifactsDep = None,
    workflow: GeneratorReviewWorkflowDep = None,
    deployer: GeneratorDeployerDep = None,
):
    """현재 파이프라인 상태 조회"""
    return {
        "analyses_count": len(analyses),
        "specs_count": len(specs),
        "artifacts_count": len(artifacts_store),
        "pending_reviews": len(workflow.get_pending_reviews()),
        "deployed_adapters": len(deployer.get_deployed_adapters()),
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


@router.post(
    "/pipeline/full",
    summary="전체 파이프라인 실행",
    description="장치 분석 → 코드 생성 → 리뷰 제출까지 전체 파이프라인을 실행합니다.",
)
async def run_full_pipeline(
    device_id: str = Body(..., description="장치 ID"),
    ip: str = Body(..., description="장치 IP"),
    port: int = Body(80, description="장치 포트"),
    fingerprint: Optional[Dict[str, Any]] = Body(None, description="장치 핑거프린트"),
    targets: List[str] = Body(["adapter", "schema", "endpoint"], description="생성 대상"),
    auto_approve: bool = Body(True, description="자동 승인 시도"),
):
    """
    전체 파이프라인 실행

    1. 장치 분석
    2. API 문서 수집
    3. 코드 생성
    4. 자동 검증 및 리뷰 제출
    """
    results = {
        "device_id": device_id,
        "steps": [],
        "status": "running",
    }

    try:
        # Step 1: 장치 분석
        analyze_request = DeviceAnalyzeRequest(
            device_id=device_id,
            ip=ip,
            port=port,
            fingerprint=fingerprint,
            include_docs=True,
        )
        analysis_response = await analyze_device(analyze_request, BackgroundTasks())
        results["steps"].append({
            "step": "analyze",
            "status": "completed",
            "analysis_id": analysis_response.analysis_id,
        })

        # Step 2: 코드 생성
        generate_request = CodeGenerateRequest(
            analysis_id=analysis_response.analysis_id,
            targets=targets,
        )
        generation_response = await generate_code(generate_request)
        results["steps"].append({
            "step": "generate",
            "status": "completed",
            "generation_id": generation_response.generation_id,
            "artifacts": generation_response.artifacts,
        })

        # Step 3: 리뷰 제출
        review_results = []
        for artifact in generation_response.artifacts:
            review_request = ReviewSubmitRequest(
                artifact_id=artifact["id"],
                auto_validate=True,
            )
            review_response = await submit_for_review(review_request)
            review_results.append(review_response)

        results["steps"].append({
            "step": "review",
            "status": "completed",
            "reviews": review_results,
        })

        results["status"] = "completed"
        return results

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        results["status"] = "failed"
        results["error"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))
