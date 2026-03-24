"""
단일 모델 관리자

Qwen2-VL-7B-Instruct 모델을 사용하여 CCTV 분석과 보고서 생성을 통합 처리합니다.

Workflow:
1. Qwen2-VL 모델 로드 (14GB)
2. Step 1: 상세 분석
3. Step 2: 사고 감지
4. Step 3: 보고서 생성
5. 모델 언로드 (선택적)

Peak Memory: 14GB (RTX 4000 Ada 20GB 내)
"""

import torch
from typing import Union, Optional
from pathlib import Path
from PIL import Image
import logging

from .qwen_vision import QwenVisionModel

logger = logging.getLogger(__name__)


class ModelOrchestrator:
    """
    단일 모델 관리자

    Features:
        - Qwen2-VL-7B-Instruct 단일 모델 관리
        - 분석 + 보고서 생성 통합 파이프라인
        - 메모리 효율적 (모델 전환 불필요)
        - 간소화된 API
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2-VL-7B-Instruct",
        device: Optional[str] = None,
        gpu_id: int = 1,
        torch_dtype: Optional[torch.dtype] = None,
    ):
        """
        초기화

        Args:
            model_name: Qwen2-VL 모델 이름
            device: 디바이스 (자동 감지 시 None)
            gpu_id: 사용할 GPU ID
            torch_dtype: Torch 데이터 타입
        """
        self.model_name = model_name
        self.gpu_id = gpu_id

        # 디바이스 설정
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        if self.device == "cuda" and torch.cuda.device_count() > gpu_id:
            self.device = f"cuda:{gpu_id}"
            torch.cuda.set_device(gpu_id)

        # Dtype 설정
        if torch_dtype is None:
            self.torch_dtype = torch.bfloat16 if "cuda" in str(self.device) else torch.float32
        else:
            self.torch_dtype = torch_dtype

        logger.debug(f"🎯 Initializing Model Orchestrator")
        logger.debug(f"   Model: {self.model_name}")
        logger.debug(f"   Device: {self.device}")
        logger.debug(f"   Dtype: {self.torch_dtype}")

        # Qwen2-VL 모델 인스턴스
        self.qwen_model = QwenVisionModel(
            model_name=self.model_name,
            device=self.device,
            gpu_id=self.gpu_id,
            torch_dtype=self.torch_dtype,
        )

    def _log_gpu_memory(self, stage: str):
        """GPU 메모리 사용량 로깅"""
        if "cuda" in str(self.device):
            allocated = torch.cuda.memory_allocated(self.gpu_id) / 1024**3
            reserved = torch.cuda.memory_reserved(self.gpu_id) / 1024**3
            logger.debug(f"   [{stage}] GPU Memory - Allocated: {allocated:.2f}GB, Reserved: {reserved:.2f}GB")

    def analyze_vision_only(
        self,
        image: Union[str, Path, Image.Image],
        location: str,
        timestamp: str,
        max_new_tokens: int = 512,
        temperature: float = 0.3,
    ) -> str:
        """
        Vision 분석만 수행 (Step 1)

        Args:
            image: 분석할 이미지 (경로 또는 PIL Image)
            location: 발생 장소
            timestamp: 발생 시간
            max_new_tokens: 최대 토큰 수
            temperature: 샘플링 온도

        Returns:
            str: 상세 분석 결과
        """
        logger.debug("=" * 60)
        logger.debug("📹 Vision Analysis (Qwen2-VL)")
        logger.debug("=" * 60)

        try:
            # Qwen 모델 로드
            logger.debug("📥 Loading Qwen2-VL Model...")
            self._log_gpu_memory("Before Load")

            self.qwen_model.load_model()

            self._log_gpu_memory("After Load")

            # CCTV 장면 분석
            logger.info("🔍 Analyzing...")
            vision_analysis = self.qwen_model.analyze_security_scene(
                image=image,
                location=location,
                timestamp=timestamp,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
            )

            logger.debug(f"   Analysis length: {len(vision_analysis)} characters")

            return vision_analysis

        except Exception as e:
            logger.error(f"❌ Vision analysis failed: {e}")
            raise

    def generate_report_only(
        self,
        image: Union[str, Path, Image.Image],
        vision_analysis: str,
        location: str,
        timestamp: str,
        incident_type: str,
        severity: str,
        max_new_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """
        보고서 생성만 수행 (Step 3)

        Args:
            image: 분석할 이미지
            vision_analysis: Step 1의 분석 결과
            location: 발생 장소
            timestamp: 발생 시간
            incident_type: 감지된 사고 유형
            severity: 평가된 심각도
            max_new_tokens: 최대 토큰 수
            temperature: 샘플링 온도

        Returns:
            str: 생성된 보안 보고서
        """
        logger.debug("=" * 60)
        logger.debug("📝 Report Generation (Qwen2-VL)")
        logger.debug("=" * 60)

        try:
            # 모델이 이미 로드되어 있어야 함
            if not self.qwen_model.is_loaded:
                logger.debug("📥 Loading Qwen2-VL Model...")
                self.qwen_model.load_model()

            self._log_gpu_memory("Before Report Generation")

            # 보안 보고서 생성
            logger.info("📝 Generating report...")
            security_report = self.qwen_model.generate_security_report(
                image=image,
                analysis=vision_analysis,
                location=location,
                timestamp=timestamp,
                incident_type=incident_type,
                severity=severity,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
            )

            logger.debug(f"   Report length: {len(security_report)} characters")

            self._log_gpu_memory("After Report Generation")

            return security_report

        except Exception as e:
            logger.error(f"❌ Report generation failed: {e}")
            raise

    def analyze_and_report(
        self,
        image: Union[str, Path, Image.Image],
        location: str,
        timestamp: str,
        incident_type: str = "미확인",
        severity: str = "중간",
        vision_max_tokens: int = 512,
        vision_temperature: float = 0.3,
        report_max_tokens: int = 1024,
        report_temperature: float = 0.7,
    ) -> tuple[str, str]:
        """
        전체 파이프라인 실행: CCTV 분석 → 보고서 생성

        Args:
            image: 분석할 이미지 (경로 또는 PIL Image)
            location: 발생 장소
            timestamp: 발생 시간
            incident_type: 사고 유형 (Step 2에서 갱신됨)
            severity: 심각도 (Step 2에서 갱신됨)
            vision_max_tokens: Vision 분석 최대 토큰
            vision_temperature: Vision 분석 온도
            report_max_tokens: 보고서 생성 최대 토큰
            report_temperature: 보고서 생성 온도

        Returns:
            tuple[str, str]: (vision_analysis, security_report)
        """
        logger.debug("=" * 60)
        logger.debug("🚀 Starting Security Analysis Pipeline (Qwen2-VL)")
        logger.debug("=" * 60)

        try:
            # Qwen 모델 로드
            logger.debug("📥 Loading Qwen2-VL Model...")
            self._log_gpu_memory("Before Load")

            self.qwen_model.load_model()

            self._log_gpu_memory("After Load")

            # Step 1: Vision 분석
            logger.debug("\n📹 Step 1: CCTV Scene Analysis")
            logger.debug("-" * 60)

            vision_analysis = self.qwen_model.analyze_security_scene(
                image=image,
                location=location,
                timestamp=timestamp,
                max_new_tokens=vision_max_tokens,
                temperature=vision_temperature,
            )

            logger.debug("✅ Vision analysis completed!")
            logger.debug(f"   Analysis length: {len(vision_analysis)} characters")

            # Step 2는 호출자(SecurityAnalyzer)에서 처리
            # Step 3: 보고서 생성
            logger.debug("\n📝 Step 3: Security Report Generation")
            logger.debug("-" * 60)

            security_report = self.qwen_model.generate_security_report(
                image=image,
                analysis=vision_analysis,
                location=location,
                timestamp=timestamp,
                incident_type=incident_type,
                severity=severity,
                max_new_tokens=report_max_tokens,
                temperature=report_temperature,
            )

            logger.debug("✅ Security report generated!")
            logger.debug(f"   Report length: {len(security_report)} characters")

            logger.debug("\n" + "=" * 60)
            logger.debug("✅ Security Analysis Pipeline Completed!")
            logger.debug("=" * 60)

            return vision_analysis, security_report

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}")
            raise

    def analyze_qa_based(
        self,
        image: Union[str, Path, Image.Image],
        location: str,
        timestamp: str,
        max_new_tokens: int = 256,
        temperature: float = 0.3,
    ) -> dict:
        """
        QA 기반 구조화된 CCTV 분석 (Step 1)

        4개의 질문을 순차적으로 실행하여 구조화된 정보 추출:
        1. Detection: 폭력/범죄 활동 감지
        2. Classification: 비정상 사건 유형
        3. Subject: 주요 인물
        4. Description: 상황 설명

        Args:
            image: 분석할 이미지 (경로 또는 PIL Image)
            location: 발생 장소
            timestamp: 발생 시간
            max_new_tokens: 최대 토큰 수
            temperature: 샘플링 온도

        Returns:
            dict: QA 결과 {'q1_detection', 'q2_classification', 'q3_subject', 'q4_description'}
        """
        logger.debug("=" * 60)
        logger.debug("📹 QA-Based Analysis (Qwen2-VL)")
        logger.debug("=" * 60)

        try:
            # Qwen 모델 로드
            if not self.qwen_model.is_loaded:
                logger.debug("📥 Loading Qwen2-VL Model...")
                self._log_gpu_memory("Before Load")
                self.qwen_model.load_model()
                self._log_gpu_memory("After Load")

            # QA 기반 분석 실행
            logger.info("🔍 Running QA-based analysis (4 questions)...")
            qa_results = self.qwen_model.analyze_qa_based(
                image=image,
                location=location,
                timestamp=timestamp,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
            )

            logger.debug("✅ QA analysis completed!")
            for key, value in qa_results.items():
                logger.debug(f"   {key}: {len(value)} characters")

            return qa_results

        except Exception as e:
            logger.error(f"❌ QA analysis failed: {e}")
            raise

    def generate_report_from_qa(
        self,
        image: Union[str, Path, Image.Image],
        qa_results: dict,
        location: str,
        timestamp: str,
        max_new_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """
        QA 결과를 바탕으로 한글 보안 보고서 생성 (Step 3)

        Args:
            image: 분석할 이미지
            qa_results: analyze_qa_based()의 결과
            location: 발생 장소
            timestamp: 발생 시간
            max_new_tokens: 최대 토큰 수
            temperature: 샘플링 온도

        Returns:
            str: 생성된 한글 보안 보고서
        """
        logger.debug("=" * 60)
        logger.debug("📝 Report Generation from QA (Qwen2-VL)")
        logger.debug("=" * 60)

        try:
            # 모델이 이미 로드되어 있어야 함
            if not self.qwen_model.is_loaded:
                logger.debug("📥 Loading Qwen2-VL Model...")
                self.qwen_model.load_model()

            self._log_gpu_memory("Before Report Generation")

            # QA 기반 보고서 생성
            logger.info("📝 Generating report from QA results...")
            security_report = self.qwen_model.generate_report_from_qa(
                image=image,
                qa_results=qa_results,
                location=location,
                timestamp=timestamp,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
            )

            logger.debug(f"   Report length: {len(security_report)} characters")

            self._log_gpu_memory("After Report Generation")

            return security_report

        except Exception as e:
            logger.error(f"❌ Report generation from QA failed: {e}")
            raise

    def cleanup(self):
        """모든 모델 리소스 정리"""
        logger.debug("🧹 Cleaning up model resources...")

        try:
            self.qwen_model.unload_model()
        except Exception as e:
            logger.warning(f"Model cleanup warning: {e}")

        if "cuda" in str(self.device):
            torch.cuda.empty_cache()

        logger.debug("✅ Cleanup completed")

    def get_pipeline_info(self) -> dict:
        """파이프라인 정보 반환"""
        info = {
            "qwen_model": self.qwen_model.get_model_info(),
            "device": str(self.device),
            "dtype": str(self.torch_dtype),
        }

        if "cuda" in str(self.device):
            info["gpu_memory_total"] = f"{torch.cuda.get_device_properties(self.gpu_id).total_memory / 1024**3:.2f}GB"
            info["gpu_memory_allocated"] = f"{torch.cuda.memory_allocated(self.gpu_id) / 1024**3:.2f}GB"
            info["gpu_memory_reserved"] = f"{torch.cuda.memory_reserved(self.gpu_id) / 1024**3:.2f}GB"

        return info

    def __enter__(self):
        """Context manager 지원"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료 시 자동 정리"""
        self.cleanup()
        return False
