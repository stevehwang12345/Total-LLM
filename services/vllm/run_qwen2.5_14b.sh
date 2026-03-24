#!/bin/bash

# vLLM 서버 실행 스크립트 (GPU 0 또는 GPU 1 사용)
# Qwen2.5-14B-Instruct-AWQ 모델 서빙

set -e

# 환경변수 또는 기본값 사용
MODEL_PATH="${LLM_MODEL_PATH:-/home/sphwang/dev/vLLM/models/qwen2.5-14b-instruct}"
MODEL_NAME="${LLM_MODEL_NAME:-Qwen/Qwen2.5-14B-Instruct-AWQ}"  # 참조용 (볼륨 마운트로 실제 사용)
GPU_DEVICE="${LLM_GPU_DEVICE:-${1:-0}}"  # 환경변수 > 인자 > 기본값 0
PORT="${VLLM_PORT:-9000}"

echo "======================================"
echo "vLLM Server Configuration"
echo "======================================"
echo "Model: ${MODEL_NAME}"
echo "Path: ${MODEL_PATH}"
echo "GPU: ${GPU_DEVICE}"
echo "Port: ${PORT}"
echo "API: http://localhost:${PORT}/v1"
echo ""

# 모델 존재 확인
if [ ! -d "${MODEL_PATH}" ] || [ ! -f "${MODEL_PATH}/config.json" ]; then
    echo "ERROR: Model not found or incomplete at ${MODEL_PATH}"
    echo "Please wait for model download to complete"
    exit 1
fi

# GPU 확인
echo "Checking GPU ${GPU_DEVICE}..."
nvidia-smi -i ${GPU_DEVICE} --query-gpu=name,memory.total,memory.free --format=csv,noheader

echo ""
echo "Starting vLLM server with Qwen2.5-14B-Instruct-AWQ..."
echo "Press Ctrl+C to stop"
echo ""

# 기존 컨테이너 중지
docker stop vllm-gpt-oss-20b 2>/dev/null || true
docker stop vllm-qwen2.5-14b 2>/dev/null || true

# vLLM 서버 실행
docker run --rm \
    --gpus "\"device=${GPU_DEVICE}\"" \
    --name vllm-qwen2.5-14b \
    -v ${MODEL_PATH}:/model \
    -p ${PORT}:9000 \
    --ipc=host \
    vllm/vllm-openai:latest \
    --model /model \
    --quantization awq \
    --dtype auto \
    --gpu-memory-utilization 0.90 \
    --max-model-len 8192 \
    --port 9000 \
    --host 0.0.0.0 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes

# AWQ 양자화 모델이므로 --quantization awq 추가
# GPU memory utilization 0.90 = ~18GB / 20GB 사용 (AWQ는 메모리 효율적)
# max-model-len 8192 = Qwen2.5의 긴 컨텍스트 활용 (최대 32K까지 가능)
