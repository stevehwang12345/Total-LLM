"""
LLM-Powered API Generator
네트워크 탐색 → LLM 분석 → 시스템 연동 코드 자동 생성

Components:
- DeviceAnalyzer: LLM 기반 장치 식별/분류
- DocumentationParser: API 문서 수집/파싱
- APISpecExtractor: LLM 기반 API 스펙 추출
- Generators: 어댑터/스키마/엔드포인트 코드 생성
- ReviewWorkflow: 리뷰 및 배포 워크플로우

Pipeline:
1. 네트워크 탐색으로 장치 발견
2. DeviceAnalyzer로 장치 분석 (LLM)
3. DocumentationParser로 API 문서 수집
4. APISpecExtractor로 API 스펙 추출 (LLM)
5. Generators로 코드 생성
6. ReviewWorkflow로 검증 및 승인
7. AdapterDeployer로 배포
"""

from .analyzer import DeviceAnalyzer, DeviceAnalysis, DeviceFingerprint, DeviceType, Protocol
from .doc_parser import DocumentationParser, APIDocument, APISpecification, DocType
from .spec_extractor import APISpecExtractor, ExtractedAPI, EndpointDetail
from .generators import (
    BaseGenerator,
    GeneratedArtifact,
    AdapterGenerator,
    SchemaGenerator,
    EndpointGenerator,
)
from .generators.base import ArtifactType, ArtifactStatus
from .review import (
    ReviewWorkflow,
    ReviewItem,
    ReviewStatus,
    CodeValidator,
    ValidationResult,
    AdapterDeployer,
    DeploymentResult,
)

__all__ = [
    # Analyzer
    "DeviceAnalyzer",
    "DeviceAnalysis",
    "DeviceFingerprint",
    "DeviceType",
    "Protocol",
    # Documentation
    "DocumentationParser",
    "APIDocument",
    "APISpecification",
    "DocType",
    # Spec Extractor
    "APISpecExtractor",
    "ExtractedAPI",
    "EndpointDetail",
    # Generators
    "BaseGenerator",
    "GeneratedArtifact",
    "ArtifactType",
    "ArtifactStatus",
    "AdapterGenerator",
    "SchemaGenerator",
    "EndpointGenerator",
    # Review
    "ReviewWorkflow",
    "ReviewItem",
    "ReviewStatus",
    "CodeValidator",
    "ValidationResult",
    "AdapterDeployer",
    "DeploymentResult",
]
