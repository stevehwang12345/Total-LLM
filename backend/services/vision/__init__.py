"""
Vision Analysis Services for Total-LLM

보안 이미지 분석을 위한 서비스 모듈
(granite-vision-korean-poc 통합)

Components:
    - detection.incident_detector: 사고 유형 및 심각도 탐지
    - korean_prompts: 한국어 분석 프롬프트 (QA 기반 보안 분석 포함)
    - templates.report_template: 보고서 템플릿
    - security_analyzer: 통합 보안 분석 파이프라인

Features:
    - 4단계 QA 기반 구조화 분석
    - 9가지 사고 유형 분류 (폭력, 싸움, 낙상, 침입, 위협, 비정상행동, 정상, 분석불가, 불분명)
    - 5단계 심각도 평가 (매우높음, 높음, 중간, 낮음, 정보)
    - 6섹션 마크다운 보고서 생성
"""

__version__ = "1.0.0"

# Detection module
from .detection.incident_detector import (
    IncidentDetector,
    IncidentType,
    SeverityLevel,
)

# Prompts module
from .korean_prompts import (
    get_prompt,
    list_available_prompts,
    SECURITY_QA_PROMPTS,
    create_security_prompt,
    create_structured_security_prompt,
    BASIC_SCENE_PROMPT,
    DETAILED_SCENE_PROMPT,
)

# Templates module
from .templates.report_template import (
    ReportTemplate,
    ReportMetadata,
)

__all__ = [
    # Detection
    "IncidentDetector",
    "IncidentType",
    "SeverityLevel",
    # Prompts
    "get_prompt",
    "list_available_prompts",
    "SECURITY_QA_PROMPTS",
    "create_security_prompt",
    "create_structured_security_prompt",
    "BASIC_SCENE_PROMPT",
    "DETAILED_SCENE_PROMPT",
    # Templates
    "ReportTemplate",
    "ReportMetadata",
]
