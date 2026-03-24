"""
보안 CCTV 분석용 Qwen2-VL-7B-Instruct 모델

Qwen2-VL은 Alibaba의 강력한 Vision-Language 모델로
멀티링구얼 지원과 뛰어난 이미지 이해 능력을 제공합니다.
"""

import torch
from PIL import Image
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor, AutoModelForVision2Seq
from typing import Optional, Union
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# QA 기반 분석 프롬프트
Q1_DETECTION = "Does this video contain any potentially violent or criminal activities?"
Q2_CLASSIFICATION = "What type of abnormal event is present in the video?"
Q3_SUBJECT = "Who is the main person involved in the unusual event?"
Q4_DESCRIPTION = "What is happening in the detected abnormal event, and can you describe the environment and actions taking place in the video?"


class QwenVisionModel:
    """
    보안 CCTV 분석용 Qwen2-VL 모델

    Features:
        - 상세한 이미지 분석
        - 한글 직접 생성 지원
        - 보안 사고 감지 및 보고서 작성
        - 단일 모델로 분석 + 보고서 생성
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
            model_name: Hugging Face 모델 이름
            device: 디바이스 ("cuda", "cpu", 또는 None for auto)
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

        logger.debug(f"🚀 Initializing Qwen2-VL Model")
        logger.debug(f"   Model: {self.model_name}")
        logger.debug(f"   Device: {self.device}")
        logger.debug(f"   Dtype: {self.torch_dtype}")

        self.model = None
        self.processor = None
        self.is_loaded = False

    def load_model(self):
        """모델과 프로세서를 로드합니다."""
        if self.is_loaded:
            logger.debug("✅ Model already loaded")
            return

        try:
            logger.debug("📥 Loading processor...")
            self.processor = AutoProcessor.from_pretrained(
                self.model_name,
                trust_remote_code=True,
            )

            logger.debug("📥 Loading model...")
            # Use AutoModelForVision2Seq (Qwen2-VL 지원)
            self.model = AutoModelForVision2Seq.from_pretrained(
                self.model_name,
                torch_dtype=self.torch_dtype,
                device_map=self.device if "cuda" in str(self.device) else "auto"
            )

            self.model.eval()
            self.is_loaded = True

            logger.debug("✅ Qwen2-VL Model loaded successfully!")

            if "cuda" in str(self.device):
                gpu_memory = torch.cuda.get_device_properties(self.gpu_id).total_memory / 1024**3
                gpu_allocated = torch.cuda.memory_allocated(self.gpu_id) / 1024**3
                logger.debug(f"   GPU Memory: {gpu_memory:.2f} GB")
                logger.debug(f"   Allocated: {gpu_allocated:.2f} GB")

        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise

    def unload_model(self):
        """모델을 메모리에서 언로드합니다."""
        if not self.is_loaded:
            return

        logger.debug("🔄 Unloading Qwen2-VL Model...")

        del self.model
        del self.processor
        self.model = None
        self.processor = None
        self.is_loaded = False

        if "cuda" in str(self.device):
            torch.cuda.empty_cache()

        logger.debug("✅ Model unloaded and memory cleared")

    def analyze_image(
        self,
        image: Union[str, Path, Image.Image],
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.3,
    ) -> str:
        """
        이미지를 분석합니다 (범용 메서드)

        Args:
            image: 이미지 경로 또는 PIL Image
            prompt: 분석 프롬프트
            max_new_tokens: 최대 생성 토큰 수
            temperature: 샘플링 온도

        Returns:
            str: 분석 결과
        """
        if not self.is_loaded:
            self.load_model()

        # 이미지 로드 - PIL Image로 변환
        if isinstance(image, (str, Path)):
            pil_image = Image.open(image).convert('RGB')
            logger.debug(f"✅ Image loaded from path: {pil_image.size}")
        elif isinstance(image, Image.Image):
            pil_image = image.convert('RGB')
            logger.debug(f"✅ PIL Image: {pil_image.size}")
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

        logger.debug(f"🔍 Analyzing image...")

        try:
            # Qwen2-VL 사용법: messages에 이미지 URL 또는 PIL Image
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_image},  # PIL Image 직접 전달
                    {"type": "text", "text": prompt}
                ]
            }]

            # Step 1: Chat template 적용 (텍스트 생성)
            text = self.processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )

            # Step 2: 프로세서로 이미지와 텍스트 함께 처리
            inputs = self.processor(
                text=[text],
                images=[pil_image],
                return_tensors="pt"
            )

            # 디바이스로 이동
            inputs = inputs.to(self.device)

            # 생성 (반복 방지 파라미터 추가)
            with torch.no_grad():
                generated_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    do_sample=True if temperature > 0 else False,
                    repetition_penalty=1.2,  # 반복 페널티 (1.0 = 없음, >1.0 = 반복 억제)
                    no_repeat_ngram_size=3,  # 3-gram 이상 반복 방지
                )

            # 디코딩 - input_ids 길이만큼 제거
            input_len = inputs.input_ids.shape[1]
            output_text = self.processor.batch_decode(
                generated_ids[:, input_len:],
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False
            )

            logger.debug("✅ Analysis completed!")

            return output_text[0].strip()

        except Exception as e:
            logger.error(f"❌ Analysis failed: {e}")
            raise

    def analyze_security_scene(
        self,
        image: Union[str, Path, Image.Image],
        location: str = "",
        timestamp: str = "",
        max_new_tokens: int = 512,
        temperature: float = 0.3,
    ) -> str:
        """
        보안 CCTV 영상을 상세 분석합니다 (Step 1)

        Args:
            image: 이미지 경로 또는 PIL Image
            location: 발생 장소
            timestamp: 발생 시간
            max_new_tokens: 최대 생성 토큰 수
            temperature: 샘플링 온도

        Returns:
            str: 상세 분석 결과
        """
        prompt = self._create_analysis_prompt(location, timestamp)
        return self.analyze_image(image, prompt, max_new_tokens, temperature)

    def generate_security_report(
        self,
        image: Union[str, Path, Image.Image],
        analysis: str,
        location: str,
        timestamp: str,
        incident_type: str,
        severity: str,
        max_new_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """
        분석 결과를 바탕으로 보안 보고서를 생성합니다 (Step 3)

        Args:
            image: 이미지 경로 또는 PIL Image
            analysis: Step 1의 분석 결과
            location: 발생 장소
            timestamp: 발생 시간
            incident_type: 감지된 사고 유형
            severity: 심각도
            max_new_tokens: 최대 생성 토큰 수
            temperature: 샘플링 온도

        Returns:
            str: 생성된 보안 보고서
        """
        prompt = self._create_report_prompt(
            analysis, location, timestamp, incident_type, severity
        )
        return self.analyze_image(image, prompt, max_new_tokens, temperature)

    def _create_analysis_prompt(self, location: str, timestamp: str) -> str:
        """
        상세 분석 프롬프트 생성 (Step 1)

        사용자 요구사항: "Explain the content in detail"
        """
        prompt = """Explain the content in detail. Focus on:

1. **People**: How many people are in the image? Where are they located?
2. **Postures**: What posture is each person in? (standing, sitting, lying, fallen, crouching)
3. **Actions**: What is each person doing? Be specific.
4. **States**: What is the physical/mental state of each person? (normal, injured, dangerous, suspicious)
5. **Security Incidents**: Are there any of the following?
   - Violence or attack
   - Fighting or physical altercation
   - Falling or injury
   - Intrusion or trespassing
   - Threatening behavior

Describe everything you observe clearly and objectively."""

        if location:
            prompt += f"\n\nLocation: {location}"
        if timestamp:
            prompt += f"\nTimestamp: {timestamp}"

        return prompt

    def _create_report_prompt(
        self,
        analysis: str,
        location: str,
        timestamp: str,
        incident_type: str,
        severity: str
    ) -> str:
        """
        보고서 생성 프롬프트 (Step 3)

        분석 결과를 한글 보고서로 변환
        """
        return f"""당신은 물리보안 전문가입니다. 다음 CCTV 분석 결과를 바탕으로 한글 보안 보고서를 작성하세요.

**CCTV 분석 결과:**
{analysis}

**사고 정보:**
- 장소: {location}
- 시간: {timestamp}
- 사고 유형: {incident_type}
- 심각도: {severity}

다음 형식으로 자연스러운 한글 보고서를 작성하세요:

## 보안 사고 보고서

**1. 사고 개요**
[분석 결과를 바탕으로 무슨 일이 발생했는지 명확히 서술]

**2. 인원 상황**
[각 사람의 위치, 자세, 행동, 상태를 자연스럽게 설명]

**3. 행동 분석**
[관찰된 행동들을 종합하여 상황 분석]

**4. 긴급도 평가**
[심각도를 바탕으로 즉시 대응이 필요한지 평가]

**5. 권장 조치**
[상황에 맞는 구체적 조치사항 제시]

**6. 종합 의견**
[전체 상황을 종합적으로 평가]

**작성 원칙:**
- 관찰된 사실만 기술
- 자연스럽고 명확한 한글
- 간결하되 핵심 정보 누락 없이"""

    def get_model_info(self) -> dict:
        """모델 정보를 반환합니다."""
        info = {
            "model_name": self.model_name,
            "device": str(self.device),
            "dtype": str(self.torch_dtype),
            "is_loaded": self.is_loaded,
        }

        if self.is_loaded and self.model is not None:
            param_count = sum(p.numel() for p in self.model.parameters()) / 1e9
            info["parameters"] = f"{param_count:.2f}B"

        return info

    def analyze_qa_based(
        self,
        image: Union[str, Path, Image.Image],
        location: str,
        timestamp: str,
        max_new_tokens: int = 256,
        temperature: float = 0.3,
    ) -> dict:
        """
        QA 기반 구조화된 CCTV 분석

        4개의 질문을 순차적으로 실행하여 구조화된 정보 추출:
        1. Detection: 폭력/범죄 활동 감지
        2. Classification: 비정상 사건 유형
        3. Subject: 주요 인물
        4. Description: 상황 및 환경 설명

        Args:
            image: CCTV 이미지
            location: 발생 장소
            timestamp: 발생 시간
            max_new_tokens: 각 질문당 최대 토큰 수
            temperature: 샘플링 온도

        Returns:
            dict: {
                'q1_detection': str,
                'q2_classification': str,
                'q3_subject': str,
                'q4_description': str
            }
        """
        logger.info("🔍 QA-based analysis started (4 questions)")

        qa_results = {}

        # Q1: Detection
        logger.debug("  Q1: Detection...")
        qa_results['q1_detection'] = self.analyze_image(
            image, Q1_DETECTION, max_new_tokens, temperature
        )

        # Q2: Classification
        logger.debug("  Q2: Classification...")
        qa_results['q2_classification'] = self.analyze_image(
            image, Q2_CLASSIFICATION, max_new_tokens, temperature
        )

        # Q3: Subject
        logger.debug("  Q3: Subject...")
        qa_results['q3_subject'] = self.analyze_image(
            image, Q3_SUBJECT, max_new_tokens, temperature
        )

        # Q4: Description
        logger.debug("  Q4: Description...")
        qa_results['q4_description'] = self.analyze_image(
            image, Q4_DESCRIPTION, max_new_tokens, temperature
        )

        logger.info("✅ QA-based analysis completed")

        return qa_results

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
        QA 결과를 바탕으로 한글 보안 보고서 생성

        Args:
            image: CCTV 이미지 (컨텍스트용)
            qa_results: QA 분석 결과
            location: 발생 장소
            timestamp: 발생 시간
            max_new_tokens: 최대 토큰 수
            temperature: 샘플링 온도

        Returns:
            str: 생성된 한글 보안 보고서
        """
        prompt = f"""You are a physical security expert. Write a concise Korean security report based on the following CCTV analysis Q&A results.

**Location**: {location}
**Time**: {timestamp}

**Q1. Violence/Crime Detection**
{qa_results['q1_detection']}

**Q2. Abnormal Event Type**
{qa_results['q2_classification']}

**Q3. Main Person**
{qa_results['q3_subject']}

**Q4. Situation Description**
{qa_results['q4_description']}

Write a natural Korean report in this format (STRICT: Each section must be 2-3 sentences maximum):

## 보안 사고 보고서

**1. 사고 개요**
[Summarize what happened based on Q2 and Q4 in 2-3 sentences]

**2. 인물 및 행동 분석**
[Describe the person's location, actions, and state based on Q3 and Q4 in 2-3 sentences]

**3. 환경 및 상황 분석**
[Describe environment (lighting, location, facilities) based on Q4 in 2-3 sentences]

**4. 사고 유형 및 심각도 판단**
[Determine incident type and severity (매우높음/높음/중간/낮음/정보) based on Q1 and Q2 in 2-3 sentences]

**5. 권장 조치**
[Provide specific action recommendations in 2-3 sentences]

**6. 종합 의견**
[Provide overall assessment in 2-3 sentences - DO NOT repeat previous sections]

**IMPORTANT RULES:**
- Each section: MAXIMUM 2-3 sentences
- Use DIFFERENT wording in each section - DO NOT repeat the same phrases
- State only observed facts
- Natural and clear Korean
- If Q1 says "No" or "정상", write accordingly
- Section 6 must provide NEW insights, not repeat sections 1-5"""

        return self.analyze_image(image, prompt, max_new_tokens, temperature)
