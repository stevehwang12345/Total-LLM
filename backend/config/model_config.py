"""LLM/VLM 모델 설정 중앙 관리 모듈

모든 LLM/VLM 관련 설정을 중앙에서 관리합니다.
환경변수가 설정되어 있으면 환경변수 값을 우선 사용합니다.
"""
import os
from pathlib import Path
from typing import Optional
import yaml

_config_cache: Optional[dict] = None


def _load_config() -> dict:
    """config.yaml 파일을 로드하고 캐시합니다."""
    global _config_cache
    if _config_cache is None:
        config_path = Path(__file__).parent / "config.yaml"
        if config_path.exists():
            with open(config_path, encoding='utf-8') as f:
                _config_cache = yaml.safe_load(f)
        else:
            _config_cache = {}
    return _config_cache


def get_llm_model_name() -> str:
    """LLM 모델명 반환 (환경변수 우선)

    우선순위:
    1. LLM_MODEL_NAME 환경변수
    2. config.yaml의 llm.model_name
    3. 기본값: 'Qwen/Qwen2.5-14B-Instruct-AWQ'
    """
    env_model = os.environ.get("LLM_MODEL_NAME")
    if env_model:
        return env_model
    config = _load_config()
    return config.get('llm', {}).get('model_name', 'Qwen/Qwen2.5-14B-Instruct-AWQ')


def get_llm_base_url() -> str:
    """LLM base URL 반환 (환경변수 우선)

    우선순위:
    1. VLLM_BASE_URL 환경변수
    2. config.yaml의 llm.base_url
    3. 기본값: 'http://localhost:9000/v1'
    """
    env_url = os.environ.get("VLLM_BASE_URL")
    if env_url:
        return env_url
    config = _load_config()
    return config.get('llm', {}).get('base_url', 'http://localhost:9000/v1')


def get_vlm_model_name() -> str:
    """VLM 모델명 반환 (환경변수 우선)

    우선순위:
    1. VLM_MODEL_NAME 환경변수
    2. config.yaml의 vlm.model_name
    3. 기본값: 'Qwen/Qwen2-VL-7B-Instruct'
    """
    env_model = os.environ.get("VLM_MODEL_NAME")
    if env_model:
        return env_model
    config = _load_config()
    return config.get('vlm', {}).get('model_name', 'Qwen/Qwen2-VL-7B-Instruct')


def get_vlm_base_url() -> str:
    """VLM base URL 반환 (환경변수 우선)

    우선순위:
    1. VLM_BASE_URL 환경변수
    2. config.yaml의 vlm.base_url
    3. 기본값: 'http://localhost:9001/v1'
    """
    env_url = os.environ.get("VLM_BASE_URL")
    if env_url:
        return env_url
    config = _load_config()
    return config.get('vlm', {}).get('base_url', 'http://localhost:9001/v1')


def clear_config_cache() -> None:
    """설정 캐시를 초기화합니다. 테스트 또는 설정 재로드 시 사용."""
    global _config_cache
    _config_cache = None
