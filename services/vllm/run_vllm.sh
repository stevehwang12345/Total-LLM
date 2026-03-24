#!/bin/bash

# vLLM 서버 실행 스크립트 (GPU 1 사용)
# GPT-OSS-20B 모델 서빙

set -e

MODEL_PATH="/home/sphwang/dev/vLLM/models/gpt-oss-20b"
GPU_DEVICE="1"  # GPU 1 사용
PORT="9000"

echo "======================================"
echo "vLLM Server Configuration"
echo "======================================"
echo "Model: ${MODEL_PATH}"
echo "GPU: ${GPU_DEVICE} (RTX 4000 Ada #2)"
echo "Port: ${PORT}"
echo "API: http://localhost:${PORT}/v1"
echo ""

# 모델 존재 확인
if [ ! -d "${MODEL_PATH}" ]; then
    echo "ERROR: Model not found at ${MODEL_PATH}"
    echo "Please run: /home/sphwang/dev/vLLM/scripts/download_gpt_oss.sh"
    exit 1
fi

# GPU 1 확인
echo "Checking GPU 1..."
nvidia-smi -i 1 --query-gpu=name,memory.total,memory.free --format=csv,noheader

echo ""
echo "Starting vLLM server..."
echo "Press Ctrl+C to stop"
echo ""

# vLLM 서버 실행 (GPU 1)
docker run --rm \
    --gpus '"device=1"' \
    --name vllm-gpt-oss-20b \
    -v ${MODEL_PATH}:/model \
    -p ${PORT}:9000 \
    --ipc=host \
    vllm/vllm-openai:latest \
    --model /model \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.85 \
    --max-model-len 4096 \
    --port 9000 \
    --host 0.0.0.0

# GPU memory utilization 0.85 = ~17GB / 20GB 사용
# max-model-len 4096 = 컨텍스트 길이 제한 (필요시 증가 가능)
