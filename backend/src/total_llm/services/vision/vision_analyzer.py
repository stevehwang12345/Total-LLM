"""
Vision-Language 모델 기반 한국어 장면 분석 모듈

IBM Granite Vision 3.3 2B 모델을 사용하여 이미지를 분석하고
한국어로 장면 보고서를 생성합니다.

지원 모델:
- IBM Granite Vision 3.3 2B (기본, 안정적)
- 기타 Hugging Face Vision-Language 모델
"""

import torch
from PIL import Image
from transformers import (
    AutoProcessor,
    AutoModelForVision2Seq,
    BitsAndBytesConfig
)
from typing import Optional, Union, Dict, Any
from pathlib import Path
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GraniteVisionAnalyzer:
    """
    Vision-Language 모델을 사용한 이미지 분석 클래스

    Features:
        - 자동 GPU/CPU 감지 및 최적화
        - 한국어 장면 보고서 생성
        - 다양한 프롬프트 타입 지원
        - 배치 처리 지원

    지원 모델:
        - ibm-granite/granite-vision-3.3-2b (기본, 안정적)
        - 기타 Hugging Face Vision-Language 모델
    """

    def __init__(
        self,
        model_name: str = "ibm-granite/granite-vision-3.3-2b",
        device: Optional[str] = None,
        gpu_id: int = 1,
        cache_dir: Optional[str] = None,
        torch_dtype: Optional[torch.dtype] = None,
    ):
        """
        VisionAnalyzer 초기화

        Args:
            model_name: Hugging Face 모델 이름 (기본값: ibm-granite/granite-vision-3.3-2b)
            device: 사용할 디바이스 ("cuda", "cpu", 또는 None for auto)
            gpu_id: 사용할 GPU ID (기본값: 1)
            cache_dir: 모델 캐시 디렉토리 (None for default)
            torch_dtype: Torch 데이터 타입 (None for auto)
        """
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.gpu_id = gpu_id

        # 디바이스 자동 감지
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # GPU ID를 포함한 디바이스 설정
        if self.device == "cuda":
            # GPU ID 설정
            if torch.cuda.device_count() > gpu_id:
                self.device = f"cuda:{gpu_id}"
                torch.cuda.set_device(gpu_id)
            else:
                logger.warning(f"GPU {gpu_id} not available. Using cuda:0")
                self.device = "cuda:0"
                torch.cuda.set_device(0)

        # Torch dtype 자동 설정
        if torch_dtype is None:
            if "cuda" in str(self.device):
                # GPU: bfloat16 사용 (더 안정적)
                self.torch_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            else:
                # CPU: float32 사용
                self.torch_dtype = torch.float32
        else:
            self.torch_dtype = torch_dtype

        logger.info(f"🚀 Initializing Vision-Language Analyzer")
        logger.info(f"   Model: {self.model_name}")
        logger.info(f"   Device: {self.device}")
        if "cuda" in str(self.device):
            logger.info(f"   GPU ID: {self.gpu_id}")
        logger.info(f"   Dtype: {self.torch_dtype}")

        # 모델 및 프로세서 로드
        self._load_model()

    def _load_model(self):
        """모델과 프로세서를 로드합니다."""
        try:
            logger.info("📥 Loading processor...")
            self.processor = AutoProcessor.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir,
                trust_remote_code=True,
            )

            logger.info("📥 Loading model... (첫 실행 시 다운로드에 시간이 걸릴 수 있습니다)")

            # 모델 로드
            self.model = AutoModelForVision2Seq.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir,
                trust_remote_code=True,
                torch_dtype=self.torch_dtype,
                device_map=self.device if "cuda" in str(self.device) else None
            )

            # 디바이스로 이동
            if self.device == "cpu":
                self.model = self.model.to(self.device)
            elif "cuda" in str(self.device):
                self.model = self.model.to(self.device)

            self.model.eval()  # 평가 모드로 설정

            logger.info("✅ Model loaded successfully!")

            # GPU 정보 및 메모리 사용량 출력
            if "cuda" in str(self.device):
                gpu_memory = torch.cuda.get_device_properties(self.gpu_id).total_memory / 1024**3
                gpu_name = torch.cuda.get_device_name(self.gpu_id)
                gpu_allocated = torch.cuda.memory_allocated(self.gpu_id) / 1024**3
                logger.info(f"   GPU Name: {gpu_name}")
                logger.info(f"   GPU Memory: {gpu_memory:.2f} GB")
                logger.info(f"   Allocated: {gpu_allocated:.2f} GB")

        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise

    def load_image(self, image_path: Union[str, Path]) -> Image.Image:
        """
        이미지를 로드합니다.

        Args:
            image_path: 이미지 파일 경로

        Returns:
            PIL.Image: 로드된 이미지

        Raises:
            FileNotFoundError: 이미지 파일이 존재하지 않을 때
            ValueError: 지원하지 않는 이미지 형식일 때
        """
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        try:
            image = Image.open(image_path).convert("RGB")
            logger.info(f"✅ Image loaded: {image_path.name} ({image.size[0]}x{image.size[1]})")
            return image
        except Exception as e:
            raise ValueError(f"Failed to load image: {e}")

    def analyze(
        self,
        image: Union[str, Path, Image.Image],
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.3,
        top_p: float = 0.9,
        do_sample: bool = True,
        repetition_penalty: float = 1.5,
        no_repeat_ngram_size: int = 3,
        **generation_kwargs,
    ) -> str:
        """
        이미지를 분석하고 한국어 보고서를 생성합니다.

        Args:
            image: 이미지 파일 경로 또는 PIL Image 객체
            prompt: 분석 프롬프트 (한국어)
            max_new_tokens: 생성할 최대 토큰 수 (기본값 512, 권장 범위 256-1024)
            temperature: 샘플링 온도 (기본값 0.3, 권장 범위 0.2-0.5, 높을수록 창의적)
            top_p: Nucleus sampling 파라미터
            do_sample: 샘플링 사용 여부
            repetition_penalty: 반복 방지 패널티 (1.0~2.0, 기본값 1.5)
            no_repeat_ngram_size: 연속 n-gram 반복 방지 (기본값 3)
            **generation_kwargs: 추가 생성 파라미터

        Returns:
            str: 한국어로 생성된 분석 보고서

        Example:
            >>> analyzer = GraniteVisionAnalyzer()
            >>> result = analyzer.analyze("test.jpg", "이 이미지를 한국어로 설명해주세요.")
            >>> print(result)
        """
        # 이미지 로드
        if isinstance(image, (str, Path)):
            image = self.load_image(image)

        logger.info(f"🔍 Analyzing image with prompt: {prompt[:50]}...")

        try:
            # Granite Vision 방식: Chat template 사용
            conversation = [{
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": prompt}
                ]
            }]

            # apply_chat_template으로 텍스트 템플릿 생성
            prompt_text = self.processor.apply_chat_template(
                conversation,
                add_generation_prompt=True,
                tokenize=False
            )

            # processor의 __call__ 메서드로 이미지와 텍스트를 함께 처리
            inputs = self.processor(
                text=prompt_text,
                images=image,
                return_tensors="pt"
            )

            # 디바이스로 이동
            inputs = {k: v.to(self.device) if hasattr(v, 'to') else v for k, v in inputs.items()}

            # 생성 파라미터 설정
            generation_config = {
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "do_sample": do_sample,
                "repetition_penalty": repetition_penalty,
                "no_repeat_ngram_size": no_repeat_ngram_size,
                **generation_kwargs,
            }

            # 추론
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    **generation_config,
                )

            # 입력 토큰 길이 확인 (새로 생성된 부분만 디코딩하기 위해)
            input_length = inputs['input_ids'].shape[1]

            # 새로 생성된 토큰만 디코딩 (입력 프롬프트 제외)
            generated_tokens = outputs[0][input_length:]
            generated_text = self.processor.decode(
                generated_tokens,
                skip_special_tokens=True
            )

            logger.info("✅ Analysis completed!")

            return generated_text.strip()

        except Exception as e:
            logger.error(f"❌ Analysis failed: {e}")
            raise

    def analyze_with_metadata(
        self,
        image: Union[str, Path, Image.Image],
        prompt: str,
        **generation_kwargs,
    ) -> Dict[str, Any]:
        """
        이미지를 분석하고 메타데이터와 함께 결과를 반환합니다.

        Args:
            image: 이미지 파일 경로 또는 PIL Image 객체
            prompt: 분석 프롬프트
            **generation_kwargs: 생성 파라미터

        Returns:
            dict: 분석 결과 및 메타데이터
                - result: 분석 텍스트
                - image_size: 이미지 크기
                - prompt: 사용된 프롬프트
                - model: 모델 이름
                - device: 사용된 디바이스
        """
        # 이미지 로드
        if isinstance(image, (str, Path)):
            image_path = image
            image = self.load_image(image)
        else:
            image_path = "PIL Image"

        # 분석 실행
        result = self.analyze(image, prompt, **generation_kwargs)

        # 메타데이터 구성
        metadata = {
            "result": result,
            "image_path": str(image_path),
            "image_size": image.size,
            "prompt": prompt,
            "model": self.model_name,
            "device": self.device,
            "dtype": str(self.torch_dtype),
        }

        return metadata

    def batch_analyze(
        self,
        images: list,
        prompts: Union[str, list],
        **generation_kwargs,
    ) -> list:
        """
        여러 이미지를 배치로 분석합니다.

        Args:
            images: 이미지 경로 리스트
            prompts: 프롬프트 (단일 문자열 또는 리스트)
            **generation_kwargs: 생성 파라미터

        Returns:
            list: 각 이미지의 분석 결과 리스트

        Example:
            >>> results = analyzer.batch_analyze(
            ...     images=["img1.jpg", "img2.jpg"],
            ...     prompts="이미지를 한국어로 설명해주세요."
            ... )
        """
        # 프롬프트가 단일 문자열이면 리스트로 변환
        if isinstance(prompts, str):
            prompts = [prompts] * len(images)

        if len(images) != len(prompts):
            raise ValueError("Number of images and prompts must match")

        results = []
        for i, (image_path, prompt) in enumerate(zip(images, prompts), 1):
            logger.info(f"📊 Processing {i}/{len(images)}: {Path(image_path).name}")
            try:
                result = self.analyze_with_metadata(
                    image_path,
                    prompt,
                    **generation_kwargs
                )
                results.append(result)
            except Exception as e:
                logger.error(f"❌ Failed to process {image_path}: {e}")
                results.append({"error": str(e), "image_path": str(image_path)})

        logger.info(f"✅ Batch processing completed: {len(results)}/{len(images)} successful")
        return results

    def get_model_info(self) -> Dict[str, Any]:
        """
        모델 정보를 반환합니다.

        Returns:
            dict: 모델 정보
        """
        info = {
            "model_name": self.model_name,
            "device": self.device,
            "dtype": str(self.torch_dtype),
            "parameters": sum(p.numel() for p in self.model.parameters()) / 1e9,  # Billions
        }

        if self.device == "cuda":
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_memory_gb"] = torch.cuda.get_device_properties(0).total_memory / 1024**3

        return info

    def __repr__(self) -> str:
        return f"GraniteVisionAnalyzer(model={self.model_name}, device={self.device})"
