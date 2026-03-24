#!/usr/bin/env python3
"""
QwenVLM Analyzer Service

QwenVLM을 사용한 보안 알람 이미지 분석 서비스

통합 기능 (granite-vision-korean-poc):
    - 4단계 QA 기반 구조화 분석
    - 9가지 사고 유형 분류
    - 5단계 심각도 평가
    - 6섹션 마크다운 보고서 생성
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import base64
import asyncio
import io
from openai import AsyncOpenAI
from PIL import Image

# Vision 모듈 통합 (granite-vision-korean-poc 포팅)
try:
    from .vision.detection.incident_detector import IncidentDetector, IncidentType, SeverityLevel
    from .vision.korean_prompts import (
        SECURITY_QA_PROMPTS,
        create_security_prompt,
        create_structured_security_prompt,
        get_prompt,
    )
    from .vision.templates.report_template import ReportTemplate, ReportMetadata
    VISION_MODULE_AVAILABLE = True
except ImportError:
    VISION_MODULE_AVAILABLE = False

logger = logging.getLogger(__name__)


class VLMAnalyzer:
    """
    QwenVLM 이미지 분석기

    역할:
    1. 보안 알람 이미지 분석
    2. 다중 이미지 종합 분석
    3. 보고서 요약 생성
    """

    def __init__(
        self,
        base_url: str = "http://localhost:9000/v1",
        model_name: str = "qwen-vl",
        max_tokens: int = 2048,
        temperature: float = 0.7
    ):
        """
        Args:
            base_url: vLLM 서버 URL
            model_name: VLM 모델 이름
            max_tokens: 최대 토큰 수
            temperature: 생성 온도
        """
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="dummy"  # vLLM doesn't require API key
        )
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature

        logger.info(f"✅ VLMAnalyzer initialized (model={model_name})")

    # ============================================
    # 단일 이미지 분석
    # ============================================

    async def analyze_image(
        self,
        image_path: str,
        prompt: str = "이 보안 알람 이미지에서 무엇이 감지되었는지 상세히 분석해주세요.",
        language: str = "ko"
    ) -> str:
        """
        단일 이미지 분석

        Args:
            image_path: 이미지 파일 경로
            prompt: 분석 프롬프트
            language: 응답 언어 (ko, en)

        Returns:
            분석 결과 텍스트
        """
        logger.info(f"🔍 Analyzing image: {image_path}")

        try:
            # 이미지를 base64로 인코딩
            image_base64 = self._encode_image(image_path)

            # VLM 호출
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": f"당신은 보안 이미지 분석 전문가입니다. {language}로 답변하세요."
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
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            analysis = response.choices[0].message.content
            logger.info(f"✅ Analysis complete ({len(analysis)} chars)")

            return analysis

        except Exception as e:
            logger.error(f"❌ Image analysis failed: {e}", exc_info=True)
            raise

    # ============================================
    # 다중 이미지 분석
    # ============================================

    async def analyze_multiple_images(
        self,
        image_analyses: List[Dict[str, Any]],
        base_prompt: str = "다음 보안 알람 이미지들을 분석한 결과입니다. 공통 패턴과 주요 위협을 요약해주세요."
    ) -> str:
        """
        다중 이미지 분석 결과 종합

        Args:
            image_analyses: [{"alarm_id": "...", "analysis": "..."}, ...]
            base_prompt: 종합 분석 프롬프트

        Returns:
            종합 분석 결과
        """
        logger.info(f"📊 Analyzing {len(image_analyses)} images collectively")

        try:
            # 개별 분석 결과를 텍스트로 구성
            analysis_text = ""
            for i, item in enumerate(image_analyses, 1):
                alarm_id = item.get("alarm_id", f"ALARM-{i}")
                analysis = item.get("analysis", "분석 없음")
                analysis_text += f"\n\n### {alarm_id}\n{analysis}"

            # VLM 호출 (텍스트 전용)
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 보안 분석 전문가입니다. 여러 알람을 종합하여 보고서를 작성합니다."
                    },
                    {
                        "role": "user",
                        "content": f"{base_prompt}\n\n{analysis_text}"
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            summary = response.choices[0].message.content
            logger.info(f"✅ Collective analysis complete ({len(summary)} chars)")

            return summary

        except Exception as e:
            logger.error(f"❌ Collective analysis failed: {e}", exc_info=True)
            raise

    # ============================================
    # 보고서 요약 생성
    # ============================================

    async def generate_summary(
        self,
        analyses: List[Dict[str, Any]],
        summary_prompt: str
    ) -> str:
        """
        보고서 요약 생성

        Args:
            analyses: 개별 분석 결과 리스트
            summary_prompt: 요약 프롬프트

        Returns:
            요약 텍스트
        """
        logger.info(f"📝 Generating summary for {len(analyses)} analyses")

        try:
            return await self.analyze_multiple_images(
                image_analyses=analyses,
                base_prompt=summary_prompt
            )

        except Exception as e:
            logger.error(f"❌ Summary generation failed: {e}", exc_info=True)
            raise

    # ============================================
    # 보안 특화 분석
    # ============================================

    async def analyze_security_alarm(
        self,
        image_path: str,
        alarm_type: str,
        location: str,
        severity: str
    ) -> Dict[str, Any]:
        """
        보안 알람 특화 분석

        Args:
            image_path: 이미지 경로
            alarm_type: 알람 유형
            location: 발생 위치
            severity: 심각도

        Returns:
            {
                "threat_detected": bool,
                "threat_level": str,
                "description": str,
                "recommended_actions": List[str],
                "confidence": float
            }
        """
        logger.info(f"🚨 Security-specific analysis: {alarm_type} @ {location}")

        # 보안 특화 프롬프트
        prompt = f"""이 이미지는 {location}에서 발생한 {alarm_type} 알람입니다 (심각도: {severity}).

다음 항목을 분석해주세요:
1. 실제 위협이 감지되었는가?
2. 위협 수준은? (CRITICAL, HIGH, MEDIUM, LOW, FALSE_POSITIVE)
3. 무엇이 보이는가? (사람, 물체, 행동 등)
4. 권장 조치 사항 (최대 3개)
5. 분석 신뢰도 (0.0-1.0)

JSON 형식으로 답변하세요:
{{
  "threat_detected": true/false,
  "threat_level": "CRITICAL/HIGH/MEDIUM/LOW/FALSE_POSITIVE",
  "description": "상세 설명",
  "recommended_actions": ["조치1", "조치2", "조치3"],
  "confidence": 0.95
}}
"""

        try:
            # 이미지 분석
            analysis_text = await self.analyze_image(
                image_path=image_path,
                prompt=prompt
            )

            # JSON 파싱 시도
            import json
            import re

            # JSON 블록 추출 (```json ... ``` 또는 { ... })
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', analysis_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
                json_str = json_match.group(0) if json_match else analysis_text

            try:
                result = json.loads(json_str)
                logger.info(f"✅ Structured analysis: threat={result.get('threat_detected')}")
                return result
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 기본 응답
                logger.warning("⚠️ Failed to parse JSON, returning text analysis")
                return {
                    "threat_detected": severity in ["CRITICAL", "HIGH"],
                    "threat_level": severity,
                    "description": analysis_text,
                    "recommended_actions": ["이미지 검토 필요", "담당자 확인"],
                    "confidence": 0.7
                }

        except Exception as e:
            logger.error(f"❌ Security analysis failed: {e}", exc_info=True)
            raise

    # ============================================
    # 이미지 인코딩
    # ============================================

    def _resize_image_base64(self, image_base64: str, max_size: int = 512) -> str:
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

    def _encode_image(self, image_path: str, max_size: int = 512) -> str:
        """
        이미지를 base64로 인코딩하고 리사이즈

        Args:
            image_path: 이미지 파일 경로
            max_size: 최대 이미지 크기 (픽셀)

        Returns:
            base64 인코딩된 문자열
        """
        path = Path(image_path)

        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(path, "rb") as f:
            image_bytes = f.read()
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # 이미지 리사이즈
        resized_base64 = self._resize_image_base64(image_base64, max_size)

        logger.debug(f"   Encoded image: {len(resized_base64)} bytes (resized to max {max_size}px)")
        return resized_base64

    # ============================================
    # 배치 분석 (병렬 처리)
    # ============================================

    async def analyze_batch(
        self,
        image_paths: List[str],
        prompts: Optional[List[str]] = None,
        max_concurrent: int = 5
    ) -> List[str]:
        """
        다중 이미지 병렬 분석

        Args:
            image_paths: 이미지 경로 리스트
            prompts: 각 이미지별 프롬프트 (None이면 기본 프롬프트)
            max_concurrent: 최대 동시 처리 수

        Returns:
            분석 결과 리스트
        """
        logger.info(f"🔄 Batch analyzing {len(image_paths)} images (concurrent={max_concurrent})")

        if prompts is None:
            prompts = ["이 보안 이미지를 분석해주세요."] * len(image_paths)

        if len(prompts) != len(image_paths):
            raise ValueError("prompts 개수와 image_paths 개수가 일치하지 않습니다.")

        # Semaphore로 동시 실행 수 제한
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_semaphore(image_path: str, prompt: str):
            async with semaphore:
                return await self.analyze_image(image_path, prompt)

        # 병렬 실행
        tasks = [
            analyze_with_semaphore(img, prompt)
            for img, prompt in zip(image_paths, prompts)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 에러 처리
        analyzed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Failed to analyze {image_paths[i]}: {result}")
                analyzed.append(f"분석 실패: {str(result)}")
            else:
                analyzed.append(result)

        logger.info(f"✅ Batch analysis complete: {len(analyzed)} results")
        return analyzed

    # ============================================
    # QA 기반 구조화 분석 (granite-vision-korean-poc 통합)
    # ============================================

    async def analyze_qa_based(
        self,
        image_path: Optional[str] = None,
        location: str = "미지정",
        timestamp: Optional[str] = None,
        max_tokens: int = 256,
        temperature: float = 0.3,
        image_base64: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        4단계 QA 기반 구조화 분석

        Args:
            image_path: 이미지 파일 경로 (image_base64가 없을 때 사용)
            location: 발생 장소
            timestamp: 발생 시간 (None이면 현재 시간)
            max_tokens: 각 QA별 최대 토큰
            temperature: 생성 온도
            image_base64: Base64 인코딩된 이미지 (우선 사용)

        Returns:
            {
                "qa_results": {
                    "q1_detection": str,    # 폭력/범죄 감지 결과
                    "q2_classification": str,  # 사고 유형 분류
                    "q3_subject": str,      # 관련 인물 설명
                    "q4_description": str,  # 상황 설명
                },
                "incident_type": str,
                "severity": str,
                "confidence": float,
            }
        """
        if not VISION_MODULE_AVAILABLE:
            logger.warning("⚠️ Vision module not available, using fallback")
            return {
                "qa_results": {
                    "q1_detection": "N/A - Vision module not available",
                    "q2_classification": "N/A",
                    "q3_subject": "N/A",
                    "q4_description": "N/A",
                },
                "incident_type": "NORMAL",
                "severity": "INFO",
                "confidence": 0.5,
            }

        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"🔍 QA-based analysis: {location} at {timestamp}")

        qa_results = {}

        # Base64 이미지 처리 (API에서 직접 전달받거나 파일에서 인코딩)
        if image_base64 is None:
            if image_path is None:
                raise ValueError("Either image_path or image_base64 must be provided")
            image_base64 = self._encode_image(image_path)
        else:
            # API에서 받은 이미지도 리사이즈
            image_base64 = self._resize_image_base64(image_base64, max_size=512)

        for qa_key, qa_prompt in SECURITY_QA_PROMPTS.items():
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a security expert analyzing CCTV footage. Answer concisely."
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": qa_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                                }
                            ]
                        }
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                qa_results[qa_key] = response.choices[0].message.content
                logger.debug(f"   {qa_key}: {qa_results[qa_key][:50]}...")

            except Exception as e:
                logger.error(f"❌ QA {qa_key} failed: {e}")
                qa_results[qa_key] = f"Error: {str(e)}"

        # QA 결과에서 사고 유형 및 심각도 추출
        incident_type, severity = self._extract_incident_from_qa(qa_results)

        logger.info(f"✅ QA-based analysis complete: {incident_type} ({severity})")
        return {
            "qa_results": qa_results,
            "incident_type": incident_type,
            "severity": severity,
            "confidence": 0.85,
        }

    async def analyze_with_incident_detection(
        self,
        image_path: str,
        location: str,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        이미지 분석 + 사고 유형/심각도 자동 감지

        Returns:
            {
                "analysis": str,
                "incident_type": str,
                "severity": str,
                "confidence": float,
                "all_incidents": List,
            }
        """
        if not VISION_MODULE_AVAILABLE:
            # 기본 분석으로 폴백
            analysis = await self.analyze_image(image_path)
            return {
                "analysis": analysis,
                "incident_type": "Unknown",
                "severity": "Unknown",
                "confidence": 0.0,
                "all_incidents": [],
            }

        # 이미지 분석
        analysis = await self.analyze_image(image_path)

        # 사고 감지
        detector = IncidentDetector()
        detection_result = detector.analyze_incident(analysis)

        primary_incident = detection_result["primary_incident"]
        incident_type, confidence = primary_incident

        return {
            "analysis": analysis,
            "incident_type": incident_type.value,
            "severity": detection_result["severity"].value,
            "confidence": confidence,
            "all_incidents": [
                (inc[0].value, inc[1]) for inc in detection_result["all_incidents"]
            ],
        }

    async def generate_security_report(
        self,
        image_path: Optional[str] = None,
        location: str = "미지정",
        timestamp: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        image_base64: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        전체 보안 분석 파이프라인: QA 분석 → 사고 감지 → 보고서 생성

        Args:
            image_path: 이미지 파일 경로 (image_base64가 없을 때 사용)
            location: 발생 장소
            timestamp: 발생 시간 (None이면 현재 시간)
            max_tokens: 보고서 생성 최대 토큰
            temperature: 생성 온도
            image_base64: Base64 인코딩된 이미지 (우선 사용)

        Returns:
            {
                "report_id": str,
                "qa_results": Dict,
                "incident_type": str,
                "severity": str,
                "markdown_report": str,
                "metadata": Dict,
            }
        """
        if not VISION_MODULE_AVAILABLE:
            logger.warning("⚠️ Vision module not available")
            return {"error": "Vision module not available"}

        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Base64 이미지 처리 (리사이즈 포함)
        if image_base64 is None:
            if image_path is None:
                raise ValueError("Either image_path or image_base64 must be provided")
            image_base64 = self._encode_image(image_path)
        else:
            # API에서 받은 이미지도 리사이즈
            image_base64 = self._resize_image_base64(image_base64, max_size=512)

        logger.info(f"📋 Generating security report: {location} at {timestamp}")

        # Step 1: QA 기반 분석
        qa_result = await self.analyze_qa_based(
            image_base64=image_base64,
            location=location,
            timestamp=timestamp,
        )

        # Step 2: QA 결과 추출
        qa_results = qa_result.get("qa_results", {})
        incident_type = qa_result.get("incident_type", "NORMAL")
        severity = qa_result.get("severity", "INFO")

        # Step 3: 보고서 생성 프롬프트
        report_prompt = create_security_prompt(
            location=location,
            timestamp=timestamp,
            qa_results=qa_results,
        )

        # Step 4: 보고서 생성
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional security report writer. Write reports in Korean."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": report_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                            }
                        ]
                    }
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            raw_report = response.choices[0].message.content
        except Exception as e:
            logger.error(f"❌ Report generation VLM call failed: {e}")
            # VLM 호출 실패 시 QA 결과 기반 기본 보고서 생성
            raw_report = f"""## 보안 사고 보고서 (자동 생성)

### 1. 사고 개요
QA 분석 결과를 기반으로 생성된 보고서입니다.
- 폭력/범죄 감지: {qa_results.get('q1_detection', 'N/A')[:100]}

### 2. 인물 및 행동 분석
{qa_results.get('q3_subject', '정보 없음')[:200]}

### 3. 환경 및 상황 분석
- 위치: {location}
- 시간: {timestamp}
- 상황: {qa_results.get('q4_description', '정보 없음')[:200]}

### 4. 사고 유형 및 심각도 판단
- 유형: {incident_type}
- 심각도: {severity}

### 5. 권장 조치
- 담당자 확인 필요
- 상황 모니터링 지속

### 6. 종합 의견
VLM 서버 연결 오류로 자동 보고서가 생성되었습니다. 수동 검토를 권장합니다.
"""

        # Step 5: 보고서 포맷팅
        report_id = ReportTemplate.generate_report_id(timestamp, location)
        formatted_report = ReportTemplate.format_complete_report(
            location=location,
            timestamp=timestamp,
            incident_type=incident_type,
            severity=severity,
            vision_analysis="",
            generated_report=raw_report,
            report_id=report_id,
        )

        # Step 6: 메타데이터
        metadata = ReportMetadata(
            report_id=report_id,
            location=location,
            timestamp=timestamp,
            incident_type=incident_type,
            severity=severity,
            confidence=0.95,
        )

        logger.info(f"✅ Security report generated: {report_id}")

        return {
            "report_id": report_id,
            "qa_results": qa_results,
            "incident_type": incident_type,
            "severity": severity,
            "raw_report": raw_report,
            "markdown_report": formatted_report,
            "metadata": metadata.to_dict(),
        }

    def _extract_incident_from_qa(self, qa_results: Dict[str, str]) -> tuple:
        """QA 결과로부터 사고 유형과 심각도 추출"""
        q1_detection = qa_results.get("q1_detection", "").lower()
        q2_classification = qa_results.get("q2_classification", "").lower()

        # Q1: 폭력/범죄 활동 감지
        has_incident = any(
            keyword in q1_detection
            for keyword in ["yes", "violent", "criminal", "abnormal", "unusual"]
        )

        if not has_incident or "no" in q1_detection[:20]:
            return ("정상", "정보")

        # Q2: 사고 유형 분류
        incident_type = "비정상행동"
        severity = "중간"

        if any(kw in q2_classification for kw in ["fight", "assault", "violence", "attack"]):
            incident_type = "폭력"
            severity = "매우높음"
        elif any(kw in q2_classification for kw in ["fall", "collapse", "slip"]):
            incident_type = "넘어짐/낙상"
            severity = "높음"
        elif any(kw in q2_classification for kw in ["intrusion", "trespass", "unauthorized"]):
            incident_type = "침입"
            severity = "높음"
        elif any(kw in q2_classification for kw in ["threat", "weapon", "suspicious"]):
            incident_type = "위협행위"
            severity = "높음"
        elif any(kw in q2_classification for kw in ["abnormal", "unusual", "strange"]):
            incident_type = "비정상행동"
            severity = "중간"

        return (incident_type, severity)


# ============================================
# Standalone 테스트
# ============================================

async def test_vlm_analyzer():
    """VLM Analyzer 테스트"""
    analyzer = VLMAnalyzer()

    # 테스트 이미지 경로
    test_image = "/home/sphwang/dev/vLLM/data/alarms/test_alarm.jpg"

    # 단일 이미지 분석
    print("=== Single Image Analysis ===")
    analysis = await analyzer.analyze_image(
        image_path=test_image,
        prompt="이 보안 이미지에서 무엇이 보이나요?"
    )
    print(analysis)

    # 보안 특화 분석
    print("\n=== Security-Specific Analysis ===")
    security_result = await analyzer.analyze_security_alarm(
        image_path=test_image,
        alarm_type="침입 감지",
        location="A동 3층 복도",
        severity="CRITICAL"
    )
    print(security_result)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    asyncio.run(test_vlm_analyzer())
