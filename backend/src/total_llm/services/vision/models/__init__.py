"""
보안 분석 모델 패키지

Components:
    - QwenVisionModel: Qwen2-VL-7B-Instruct (CCTV 분석 + 보고서 생성)
    - ModelOrchestrator: 단일 모델 관리자

    # Legacy (deprecated):
    - SecurityVisionModel: Granite Vision 3.2 2B
    - SecurityReportGenerator: Granite 3.2 8B Instruct
"""

from .qwen_vision import QwenVisionModel
from .model_orchestrator import ModelOrchestrator

# Legacy imports (for backward compatibility)
try:
    from .security_vision import SecurityVisionModel
    from .report_generator import SecurityReportGenerator
    LEGACY_AVAILABLE = True
except ImportError:
    LEGACY_AVAILABLE = False

__all__ = [
    "QwenVisionModel",
    "ModelOrchestrator",
]

if LEGACY_AVAILABLE:
    __all__.extend(["SecurityVisionModel", "SecurityReportGenerator"])
