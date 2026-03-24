"""
보안 분석 시스템 메인 파이프라인 (QA 기반)

CCTV 이미지 → Qwen2-VL QA 분석 (4개 질문) → 사고 유형/심각도 추출 → Qwen2-VL 보고서 생성 → 내보내기
"""

import logging
from typing import Union, Optional, Dict
from pathlib import Path
from PIL import Image
from datetime import datetime

from .models import ModelOrchestrator
from .detection import IncidentDetector, IncidentType, SeverityLevel
from .templates import ReportTemplate, ReportMetadata

logger = logging.getLogger(__name__)


class SecurityAnalyzer:
    """
    보안 분석 통합 시스템 (Qwen2-VL 기반, QA 기반)

    Complete Pipeline:
        1. 이미지 입력
        2. Qwen2-VL로 QA 기반 구조화된 분석 (4개 질문)
        3. QA 결과로부터 사고 유형 및 심각도 자동 추출
        4. Qwen2-VL로 QA 결과 기반 한글 보고서 생성
        5. 표준 형식으로 포맷팅
        6. 내보내기 지원

    Features:
        - 단일 Qwen2-VL-7B 모델 사용
        - QA 기반 구조화된 분석 (패턴 매칭 제거)
        - 멀티링구얼 한글 지원
        - 엔드-투-엔드 파이프라인
        - 자동 사고 감지 (QA 결과 기반)
        - 보고서 ID 생성
        - 메타데이터 관리
        - 메모리 효율적 (14GB)
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2-VL-7B-Instruct",
        gpu_id: int = 1,
    ):
        """
        초기화

        Args:
            model_name: Qwen2-VL 모델 이름
            gpu_id: 사용할 GPU ID
        """
        logger.debug("🔧 Initializing Security Analyzer...")

        # 모델 오케스트레이터 (단일 Qwen 모델)
        self.orchestrator = ModelOrchestrator(
            model_name=model_name,
            gpu_id=gpu_id,
        )

        # 사고 감지기
        self.incident_detector = IncidentDetector()

        logger.debug("✅ Security Analyzer initialized successfully!")

    def analyze_cctv(
        self,
        image: Union[str, Path, Image.Image],
        location: str,
        timestamp: Optional[str] = None,
        qa_max_tokens: int = 256,
        qa_temperature: float = 0.3,
        report_max_tokens: int = 1024,
        report_temperature: float = 0.7,
    ) -> Dict:
        """
        CCTV 영상 전체 분석 파이프라인 (QA 기반)

        Pipeline:
            1. QA 기반 구조화된 분석 (4개 질문)
            2. QA 결과로부터 사고 유형 및 심각도 추출
            3. QA 결과 기반 한글 보고서 생성
            4. 표준 형식으로 포맷팅

        Args:
            image: CCTV 이미지 (경로 또는 PIL Image)
            location: 발생 장소
            timestamp: 발생 시간 (None이면 현재 시간)
            qa_max_tokens: QA 분석 최대 토큰
            qa_temperature: QA 분석 온도
            report_max_tokens: 보고서 생성 최대 토큰
            report_temperature: 보고서 생성 온도

        Returns:
            Dict: {
                "report_id": str,
                "qa_results": Dict,
                "incident_type": str,
                "severity": str,
                "raw_report": str,
                "formatted_report": str,
                "metadata": ReportMetadata,
            }
        """
        # 타임스탬프 설정
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"🔍 Analyzing CCTV (QA-based): {location} at {timestamp}")

        # Step 1: QA 기반 분석 (4개 질문)
        qa_results = self.orchestrator.analyze_qa_based(
            image=image,
            location=location,
            timestamp=timestamp,
            max_new_tokens=qa_max_tokens,
            temperature=qa_temperature,
        )

        # Step 2: QA 결과로부터 사고 유형 및 심각도 자동 판단
        incident_type, severity = self._extract_incident_from_qa(qa_results)

        logger.info(f"✅ Detection from QA: {incident_type} (심각도: {severity})")

        # Step 3: QA 결과 기반 한글 보고서 생성
        raw_report = self.orchestrator.generate_report_from_qa(
            image=image,
            qa_results=qa_results,
            location=location,
            timestamp=timestamp,
            max_new_tokens=report_max_tokens,
            temperature=report_temperature,
        )

        # 보고서 ID 생성
        report_id = ReportTemplate.generate_report_id(timestamp, location)

        # 표준 형식으로 포맷팅
        formatted_report = ReportTemplate.format_complete_report(
            location=location,
            timestamp=timestamp,
            incident_type=incident_type,
            severity=severity,
            vision_analysis="",  # QA 기반이므로 불필요
            generated_report=raw_report,
            report_id=report_id,
        )

        # 메타데이터 생성
        metadata = ReportMetadata(
            report_id=report_id,
            location=location,
            timestamp=timestamp,
            incident_type=incident_type,
            severity=severity,
            confidence=0.95,  # QA 기반은 높은 신뢰도
        )

        logger.info(f"✅ Complete: {report_id}")

        return {
            "report_id": report_id,
            "qa_results": qa_results,
            "incident_type": incident_type,
            "severity": severity,
            "raw_report": raw_report,
            "formatted_report": formatted_report,
            "metadata": metadata,
        }

    def _extract_incident_from_qa(self, qa_results: Dict) -> tuple[str, str]:
        """
        QA 결과로부터 사고 유형과 심각도를 추출

        Args:
            qa_results: QA 분석 결과

        Returns:
            tuple: (incident_type, severity)
        """
        q1_detection = qa_results.get("q1_detection", "").lower()
        q2_classification = qa_results.get("q2_classification", "").lower()

        # Q1: 폭력/범죄 활동 감지
        has_incident = any(
            keyword in q1_detection
            for keyword in ["yes", "violent", "criminal", "abnormal", "unusual"]
        )

        if not has_incident or "no" in q1_detection[:20]:
            # 정상 상황
            return "정상", "정보"

        # Q2: 사고 유형 분류
        incident_type = "비정상행동"  # 기본값
        severity = "중간"  # 기본값

        # 폭력/싸움
        if any(
            keyword in q2_classification
            for keyword in ["fight", "assault", "violence", "attack", "punch", "kick"]
        ):
            incident_type = "폭력"
            severity = "매우높음"

        # 낙상
        elif any(keyword in q2_classification for keyword in ["fall", "collapse", "slip"]):
            incident_type = "넘어짐/낙상"
            severity = "높음"

        # 침입
        elif any(
            keyword in q2_classification
            for keyword in ["intrusion", "trespass", "unauthorized", "break"]
        ):
            incident_type = "침입"
            severity = "높음"

        # 위협행위
        elif any(
            keyword in q2_classification for keyword in ["threat", "weapon", "suspicious"]
        ):
            incident_type = "위협행위"
            severity = "높음"

        # 기타 비정상
        elif any(
            keyword in q2_classification for keyword in ["abnormal", "unusual", "strange"]
        ):
            incident_type = "비정상행동"
            severity = "중간"

        return incident_type, severity

    def cleanup(self):
        """리소스 정리"""
        logger.debug("🧹 Cleaning up Security Analyzer resources...")
        self.orchestrator.cleanup()
        logger.debug("✅ Cleanup completed")

    def get_system_info(self) -> Dict:
        """시스템 정보 반환"""
        return {
            "pipeline_info": self.orchestrator.get_pipeline_info(),
            "detector_info": {
                "incident_types": [t.value for t in IncidentType],
                "severity_levels": [s.value for s in SeverityLevel],
            },
        }

    def __enter__(self):
        """Context manager 지원"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료 시 자동 정리"""
        self.cleanup()
        return False
