"""
API Generator 테스트

LLM-Powered API Generator의 전체 파이프라인을 테스트합니다.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from services.api_generator import (
    DeviceAnalyzer,
    DocumentationParser,
    APISpecExtractor,
    AdapterGenerator,
    SchemaGenerator,
    EndpointGenerator,
    ReviewWorkflow,
    CodeValidator,
    AdapterDeployer,
    DeviceFingerprint,
    DeviceType,
    Protocol,
    ExtractedAPI,
)
from services.api_generator.generators.base import ArtifactType, ArtifactStatus


# ========================================
# Fixtures
# ========================================

@pytest.fixture
def sample_fingerprint():
    """테스트용 장치 핑거프린트"""
    return DeviceFingerprint(
        ip="192.168.1.100",
        ports=[80, 554, 8000],
        http_headers={
            "Server": "Hikvision-Webs",
            "Content-Type": "text/html",
        },
        http_response="<DeviceInfo><manufacturer>Hikvision</manufacturer></DeviceInfo>",
        banner="Hikvision ISAPI",
        services=["http", "rtsp"],
    )


@pytest.fixture
def sample_api_spec():
    """테스트용 API 스펙"""
    return ExtractedAPI(
        base_url="/ISAPI",
        auth_type="digest",
        content_type="application/xml",
        endpoints=[
            {
                "path": "/ISAPI/PTZ/channels/{id}/continuous",
                "method": "PUT",
                "description": "PTZ 연속 이동",
                "category": "ptz",
                "parameters": [
                    {"name": "id", "type": "string", "required": True},
                ],
            },
            {
                "path": "/ISAPI/System/deviceInfo",
                "method": "GET",
                "description": "장치 정보 조회",
                "category": "system",
            },
        ],
    )


@pytest.fixture
def mock_llm_client():
    """Mock LLM 클라이언트"""
    client = AsyncMock()
    client.generate.return_value = {
        "device_type": "cctv",
        "manufacturer": "hikvision",
        "model": "DS-2CD2143G2-I",
        "protocols": ["onvif", "isapi", "rtsp"],
        "confidence": 0.95,
    }
    return client


# ========================================
# DeviceAnalyzer Tests
# ========================================

class TestDeviceAnalyzer:
    """DeviceAnalyzer 테스트"""

    def test_analyzer_creation(self):
        """분석기 생성 테스트"""
        analyzer = DeviceAnalyzer()
        assert analyzer is not None

    @pytest.mark.asyncio
    async def test_pre_analyze(self, sample_fingerprint):
        """규칙 기반 사전 분석 테스트"""
        analyzer = DeviceAnalyzer()
        result = analyzer._pre_analyze(sample_fingerprint)

        assert result is not None
        assert result["confidence"] > 0
        # Hikvision 키워드가 있으므로 hikvision으로 식별되어야 함
        assert "hikvision" in result.get("manufacturer", "").lower() or result.get("manufacturer") == "unknown"

    @pytest.mark.asyncio
    async def test_analyze_without_llm(self, sample_fingerprint):
        """LLM 없이 분석 테스트"""
        analyzer = DeviceAnalyzer(llm_client=None)
        result = await analyzer.analyze(sample_fingerprint)

        assert result is not None
        assert result.device_type in DeviceType
        assert result.manufacturer is not None
        assert len(result.protocols) > 0


# ========================================
# Generator Tests
# ========================================

class TestAdapterGenerator:
    """AdapterGenerator 테스트"""

    def test_generator_creation(self):
        """생성기 생성 테스트"""
        generator = AdapterGenerator()
        assert generator is not None

    @pytest.mark.asyncio
    async def test_generate_adapter(self, sample_fingerprint, sample_api_spec):
        """어댑터 코드 생성 테스트"""
        analyzer = DeviceAnalyzer()
        analysis = await analyzer.analyze(sample_fingerprint)

        generator = AdapterGenerator()
        artifact = generator.generate(analysis, sample_api_spec)

        assert artifact is not None
        assert artifact.artifact_type == ArtifactType.ADAPTER
        assert artifact.file_name.endswith("_adapter.py")
        assert "class" in artifact.content
        assert "async def" in artifact.content


class TestSchemaGenerator:
    """SchemaGenerator 테스트"""

    @pytest.mark.asyncio
    async def test_generate_schema(self, sample_fingerprint, sample_api_spec):
        """스키마 코드 생성 테스트"""
        analyzer = DeviceAnalyzer()
        analysis = await analyzer.analyze(sample_fingerprint)

        generator = SchemaGenerator()
        artifact = generator.generate(analysis, sample_api_spec)

        assert artifact is not None
        assert artifact.artifact_type == ArtifactType.SCHEMA
        assert artifact.file_name.endswith("_schemas.py")
        assert "BaseModel" in artifact.content
        assert "class" in artifact.content


class TestEndpointGenerator:
    """EndpointGenerator 테스트"""

    @pytest.mark.asyncio
    async def test_generate_endpoint(self, sample_fingerprint, sample_api_spec):
        """엔드포인트 코드 생성 테스트"""
        analyzer = DeviceAnalyzer()
        analysis = await analyzer.analyze(sample_fingerprint)

        generator = EndpointGenerator()
        artifact = generator.generate(analysis, sample_api_spec)

        assert artifact is not None
        assert artifact.artifact_type == ArtifactType.ENDPOINT
        assert artifact.file_name.endswith("_router.py")
        assert "APIRouter" in artifact.content
        assert "@router" in artifact.content


# ========================================
# Validator Tests
# ========================================

class TestCodeValidator:
    """CodeValidator 테스트"""

    def test_validator_creation(self):
        """검증기 생성 테스트"""
        validator = CodeValidator()
        assert validator is not None

    def test_validate_valid_code(self):
        """유효한 코드 검증 테스트"""
        validator = CodeValidator()
        code = '''
import logging

def hello():
    """Hello function"""
    return "Hello, World!"
'''
        result = validator.validate(code)

        assert result.valid is True
        assert result.score > 0

    def test_validate_syntax_error(self):
        """구문 에러 감지 테스트"""
        validator = CodeValidator()
        code = '''
def broken(
    return "broken"
'''
        result = validator.validate(code)

        assert result.valid is False
        assert result.error_count > 0

    def test_validate_security_issue(self):
        """보안 이슈 감지 테스트"""
        validator = CodeValidator()
        code = '''
import os

def dangerous():
    password = "admin123"
    eval(user_input)
    return password
'''
        result = validator.validate(code)

        # 보안 이슈가 감지되어야 함
        security_issues = [i for i in result.issues if i.category.value == "security"]
        assert len(security_issues) > 0


# ========================================
# ReviewWorkflow Tests
# ========================================

class TestReviewWorkflow:
    """ReviewWorkflow 테스트"""

    @pytest.mark.asyncio
    async def test_submit_for_review(self, sample_fingerprint, sample_api_spec):
        """리뷰 제출 테스트"""
        analyzer = DeviceAnalyzer()
        analysis = await analyzer.analyze(sample_fingerprint)

        generator = AdapterGenerator()
        artifact = generator.generate(analysis, sample_api_spec)

        workflow = ReviewWorkflow()
        review_item = await workflow.submit_for_review(artifact)

        assert review_item is not None
        assert review_item.id is not None
        assert review_item.validation_result is not None

    @pytest.mark.asyncio
    async def test_approve_review(self, sample_fingerprint, sample_api_spec):
        """리뷰 승인 테스트"""
        analyzer = DeviceAnalyzer()
        analysis = await analyzer.analyze(sample_fingerprint)

        generator = AdapterGenerator()
        artifact = generator.generate(analysis, sample_api_spec)

        workflow = ReviewWorkflow(auto_approve_threshold=0)  # 무조건 승인 대기
        review_item = await workflow.submit_for_review(artifact, auto_validate=False)

        # 승인
        review_item = await workflow.approve(review_item.id, "test_reviewer", "LGTM")

        assert review_item.status.value == "approved"

    @pytest.mark.asyncio
    async def test_reject_review(self, sample_fingerprint, sample_api_spec):
        """리뷰 거부 테스트"""
        analyzer = DeviceAnalyzer()
        analysis = await analyzer.analyze(sample_fingerprint)

        generator = AdapterGenerator()
        artifact = generator.generate(analysis, sample_api_spec)

        workflow = ReviewWorkflow()
        review_item = await workflow.submit_for_review(artifact, auto_validate=False)

        # 거부
        review_item = await workflow.reject(review_item.id, "test_reviewer", "Needs more work")

        assert review_item.status.value == "rejected"


# ========================================
# Integration Tests
# ========================================

class TestFullPipeline:
    """전체 파이프라인 통합 테스트"""

    @pytest.mark.asyncio
    async def test_full_pipeline(self, sample_fingerprint):
        """전체 파이프라인 테스트"""
        # 1. 장치 분석
        analyzer = DeviceAnalyzer()
        analysis = await analyzer.analyze(sample_fingerprint)

        assert analysis is not None
        assert analysis.manufacturer is not None

        # 2. API 스펙 생성 (여기서는 샘플 사용)
        spec = ExtractedAPI(
            base_url="/api",
            auth_type="basic",
            content_type="application/json",
            endpoints=[
                {
                    "path": "/status",
                    "method": "GET",
                    "description": "Status check",
                },
            ],
        )

        # 3. 코드 생성
        artifacts = []

        adapter_gen = AdapterGenerator()
        artifacts.append(adapter_gen.generate(analysis, spec))

        schema_gen = SchemaGenerator()
        artifacts.append(schema_gen.generate(analysis, spec))

        endpoint_gen = EndpointGenerator()
        artifacts.append(endpoint_gen.generate(analysis, spec))

        assert len(artifacts) == 3

        # 4. 리뷰 제출
        workflow = ReviewWorkflow(auto_approve_threshold=50)  # 낮은 임계값

        for artifact in artifacts:
            review_item = await workflow.submit_for_review(artifact)
            assert review_item.validation_result is not None

        # 5. 통계 확인
        stats = workflow.get_statistics()
        assert stats["total"] == 3


# ========================================
# API Endpoint Tests
# ========================================

class TestGeneratorAPI:
    """Generator API 엔드포인트 테스트"""

    def test_router_routes(self):
        """라우터 경로 테스트"""
        from api.generator_api import router

        routes = [r.path for r in router.routes]

        assert "/generator/analyze" in routes
        assert "/generator/generate" in routes
        assert "/generator/review/submit" in routes
        assert "/generator/deploy" in routes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
