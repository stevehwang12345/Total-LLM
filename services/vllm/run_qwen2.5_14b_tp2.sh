#!/bin/bash

# vLLM 서버 실행 스크립트 - 텐서 병렬화 (TP=2)
# Qwen2.5-14B-Instruct-AWQ 모델 서빙 (GPU 0 + GPU 1)

set -e

MODEL_PATH="/home/sphwang/dev/vLLM/models/qwen2.5-14b-instruct"
PORT="9000"

echo "======================================"
echo "vLLM Server Configuration (TP=2)"
echo "======================================"
echo "Model: Qwen2.5-14B-Instruct-AWQ"
echo "Path: ${MODEL_PATH}"
echo "GPUs: 0 + 1 (Tensor Parallelism)"
echo "Port: ${PORT}"
echo "API: http://localhost:${PORT}/v1"
echo "Context Length: 16,384 tokens"
echo ""

# 모델 존재 확인
if [ ! -d "${MODEL_PATH}" ] || [ ! -f "${MODEL_PATH}/config.json" ]; then
    echo "ERROR: Model not found or incomplete at ${MODEL_PATH}"
    echo "Please wait for model download to complete"
    exit 1
fi

# GPU 확인
echo "Checking GPUs..."
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv,noheader

echo ""
echo "Starting vLLM server with Tensor Parallelism (TP=2)..."
echo "Memory will be distributed across both GPUs"
echo "Press Ctrl+C to stop"
echo ""

# 기존 컨테이너 중지
docker stop vllm-gpt-oss-20b 2>/dev/null || true
docker stop vllm-qwen2.5-14b 2>/dev/null || true
docker stop vllm-qwen-tp2 2>/dev/null || true

# vLLM 서버 실행 (TP=2)
docker run --rm \
    --gpus '"device=0,1"' \
    --name vllm-qwen-tp2 \
    -v ${MODEL_PATH}:/model \
    -p ${PORT}:9000 \
    --ipc=host \
    vllm/vllm-openai:latest \
    --model /model \
    --quantization awq \
    --tensor-parallel-size 2 \
    --dtype auto \
    --gpu-memory-utilization 0.90 \
    --max-model-len 16384 \
    --port 9000 \
    --host 0.0.0.0

# Tensor Parallelism 설정:
# - 모델을 2개 GPU에 분산 (각 GPU에 절반씩)
# - GPU 간 통신으로 협력하여 추론 수행
# - 메모리: 각 GPU 약 10GB 사용 (총 20GB)
# - 컨텍스트: 16K tokens (한국어 약 10,000자)
# - 레이턴시: 단일 GPU 대비 15-25% 증가
# - 처리량: 메모리 여유로 더 많은 동시 요청 가능
