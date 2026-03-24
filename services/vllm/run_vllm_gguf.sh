#!/bin/bash

# vLLM 서버 실행 스크립트 (GPU 1 사용)
# GPT-OSS-20B Function Calling GGUF 모델 서빙

set -e

GGUF_MODEL_PATH="/home/sphwang/dev/vLLM/models/gpt-oss-20b-fc-gguf/gpt-oss-20b-function-calling.Q4_K_M.gguf"
TOKENIZER="openai/gpt-oss-20b"  # Base model tokenizer
GPU_DEVICE="1"  # GPU 1 사용
PORT="8000"

echo "======================================"
echo "vLLM GGUF Server Configuration"
echo "======================================"
echo "GGUF Model: ${GGUF_MODEL_PATH}"
echo "Tokenizer: ${TOKENIZER}"
echo "GPU: ${GPU_DEVICE} (RTX 4000 Ada #2)"
echo "Port: ${PORT}"
echo "API: http://localhost:${PORT}/v1"
echo ""

# GGUF 모델 존재 확인
if [ ! -f "${GGUF_MODEL_PATH}" ]; then
    echo "ERROR: GGUF model not found at ${GGUF_MODEL_PATH}"
    exit 1
fi

# GPU 1 확인
echo "Checking GPU 1..."
nvidia-smi -i 1 --query-gpu=name,memory.total,memory.free --format=csv,noheader

echo ""
echo "Starting vLLM GGUF server..."
echo "Note: GGUF support is experimental in vLLM 0.11.0"
echo "Press Ctrl+C to stop"
echo ""

# vLLM 서버 실행 (GGUF 모델)
docker run --rm \
    --gpus '"device=1"' \
    --name vllm-gpt-oss-20b-fc \
    -v $(dirname ${GGUF_MODEL_PATH}):/gguf_models \
    -p ${PORT}:8000 \
    --ipc=host \
    vllm/vllm-openai:latest \
    --model /gguf_models/$(basename ${GGUF_MODEL_PATH}) \
    --tokenizer ${TOKENIZER} \
    --gpu-memory-utilization 0.85 \
    --max-model-len 8192 \
    --port 8000 \
    --host 0.0.0.0

# GGUF Q4_K_M quantization = ~16GB VRAM
# max-model-len 8192 = 더 긴 컨텍스트 지원 (GGUF 메모리 효율)
# tokenizer는 base model 사용 (GGUF tokenizer 변환 불안정)
