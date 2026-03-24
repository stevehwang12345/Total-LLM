# LLM/VLM 모델 설정 가이드

## 개요

Total-LLM 프로젝트의 LLM/VLM 모델 설정을 중앙에서 관리하는 시스템입니다.
모든 모델 관련 설정은 `backend/config/model_config.py` 모듈을 통해 일관되게 관리됩니다.

## 설정 우선순위

```
1. 환경변수 (최우선)
2. config.yaml 설정값
3. 코드 내 기본값 (폴백)
```

## 환경변수

| 환경변수 | 설명 | 기본값 |
|----------|------|--------|
| `LLM_MODEL_NAME` | LLM 모델명 | `Qwen/Qwen2.5-14B-Instruct-AWQ` |
| `VLLM_BASE_URL` | vLLM API URL | `http://localhost:9000/v1` |
| `VLM_MODEL_NAME` | VLM(Vision) 모델명 | `Qwen/Qwen2-VL-7B-Instruct` |
| `VLM_BASE_URL` | VLM API URL | `http://localhost:9001/v1` |

### 사용 예시

```bash
# 다른 모델 사용
export LLM_MODEL_NAME="Qwen/Qwen2.5-7B-Instruct"
export VLLM_BASE_URL="http://192.168.1.100:9000/v1"

# 서버 시작
python -m uvicorn main:app --host 0.0.0.0 --port 9002
```

## 중앙 설정 모듈 API

### `backend/config/model_config.py`

```python
from config.model_config import (
    get_llm_model_name,
    get_llm_base_url,
    get_vlm_model_name,
    get_vlm_base_url,
    clear_config_cache,
)

# LLM 설정 가져오기
model = get_llm_model_name()  # "Qwen/Qwen2.5-14B-Instruct-AWQ"
url = get_llm_base_url()      # "http://localhost:9000/v1"

# VLM 설정 가져오기
vlm_model = get_vlm_model_name()  # "Qwen/Qwen2-VL-7B-Instruct"
vlm_url = get_vlm_base_url()      # "http://localhost:9001/v1"

# 설정 캐시 초기화 (테스트용)
clear_config_cache()
```

## 설정 파일

### `backend/config/config.yaml`

```yaml
# LLM Configuration (Text)
# 환경변수로 오버라이드 가능: LLM_MODEL_NAME, VLLM_BASE_URL
llm:
  provider: "vllm"
  base_url: "http://localhost:9000/v1"
  model_name: "Qwen/Qwen2.5-14B-Instruct-AWQ"
  temperature: 0.7
  max_tokens: 4096
  streaming: true

# VLM Configuration (Vision - Multimodal)
# 환경변수로 오버라이드 가능: VLM_MODEL_NAME, VLM_BASE_URL
vlm:
  provider: "vllm"
  base_url: "http://localhost:9001/v1"
  model_name: "Qwen/Qwen2-VL-7B-Instruct"
  temperature: 0.7
  max_tokens: 1024
```

## 적용된 파일 목록

### Backend API

| 파일 | 변경 내용 |
|------|----------|
| `api/security_chat_api.py` | `model=get_llm_model_name()` 사용 |
| `api/document_api.py` | `model=get_llm_model_name()` 사용 |
| `api/system_api.py` | Docker 명령어에 동적 모델명 적용 |
| `api/control_api.py` | SystemController 초기화 시 중앙 설정 사용 |

### Retrievers

| 파일 | 변경 내용 |
|------|----------|
| `retrievers/query_expander.py` | 기본값을 중앙 설정에서 가져옴 |

### Frontend

| 파일 | 변경 내용 |
|------|----------|
| `frontend/src/react_agent/graph.py` | 환경변수 `LLM_MODEL_NAME`, `VLLM_BASE_URL` 지원 |

### Shell Scripts

| 파일 | 변경 내용 |
|------|----------|
| `services/vllm/run_qwen2.5_14b.sh` | 환경변수로 설정 오버라이드 가능 |

## vLLM 서버 실행

### 스크립트 사용

```bash
# 기본 실행 (GPU 0)
./services/vllm/run_qwen2.5_14b.sh

# GPU 1에서 실행
./services/vllm/run_qwen2.5_14b.sh 1

# 환경변수로 설정 오버라이드
LLM_GPU_DEVICE=1 VLLM_PORT=9000 ./services/vllm/run_qwen2.5_14b.sh
```

### Docker 직접 실행

```bash
docker run -d \
    --gpus '"device=1"' \
    --name vllm-qwen2.5-14b \
    -v /home/sphwang/dev/vLLM/models/qwen2.5-14b-instruct:/model \
    -p 9000:9000 \
    --ipc=host \
    vllm/vllm-openai:v0.5.1 \
    --model /model \
    --quantization awq \
    --dtype auto \
    --gpu-memory-utilization 0.90 \
    --max-model-len 8192 \
    --port 9000 \
    --host 0.0.0.0 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes
```

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                      환경변수                                │
│  LLM_MODEL_NAME, VLLM_BASE_URL, VLM_MODEL_NAME, VLM_BASE_URL │
└─────────────────────────┬───────────────────────────────────┘
                          │ 우선
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 config/model_config.py                       │
│  get_llm_model_name(), get_llm_base_url()                   │
│  get_vlm_model_name(), get_vlm_base_url()                   │
└─────────────────────────┬───────────────────────────────────┘
                          │ 폴백
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   config/config.yaml                         │
│  llm.model_name, llm.base_url                               │
│  vlm.model_name, vlm.base_url                               │
└─────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │ Backend  │   │ Frontend │   │ Scripts  │
    │   APIs   │   │  Agent   │   │  vLLM    │
    └──────────┘   └──────────┘   └──────────┘
```

## 모델 변경 방법

### 1. 임시 변경 (세션 한정)

```bash
export LLM_MODEL_NAME="새로운/모델명"
# 서버 재시작
```

### 2. 영구 변경

`backend/config/config.yaml` 수정:

```yaml
llm:
  model_name: "새로운/모델명"
```

### 3. 다른 vLLM 서버 사용

```bash
export VLLM_BASE_URL="http://다른서버:9000/v1"
export LLM_MODEL_NAME="서버에_로드된_모델명"
```

## 주의사항

1. **vLLM 서버 모델과 일치**: `LLM_MODEL_NAME`은 실제 vLLM 서버에 로드된 모델명과 일치해야 합니다.

2. **로컬 모델 사용 시**: 볼륨 마운트된 모델을 사용하는 경우, vLLM은 `/model` 경로를 사용하지만 API 호출 시에는 실제 모델명을 사용합니다.

3. **캐시 주의**: `model_config.py`는 설정을 캐시합니다. 런타임 중 설정 변경 시 `clear_config_cache()`를 호출하세요.

## 관련 문서

- [vLLM 공식 문서](https://docs.vllm.ai/)
- [Qwen2.5 모델 카드](https://huggingface.co/Qwen/Qwen2.5-14B-Instruct-AWQ)
