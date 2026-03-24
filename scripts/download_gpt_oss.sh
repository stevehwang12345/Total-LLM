#!/bin/bash

# GPT-OSS-20B 모델 다운로드 스크립트
# Target: /home/sphwang/dev/vLLM/models/gpt-oss-20b

set -e

MODEL_DIR="/home/sphwang/dev/vLLM/models/gpt-oss-20b"
MODEL_ID="openai/gpt-oss-20b"

echo "======================================"
echo "GPT-OSS-20B 모델 다운로드"
echo "======================================"
echo "Model: ${MODEL_ID}"
echo "Target: ${MODEL_DIR}"
echo ""

# huggingface-cli 설치 확인
if ! command -v huggingface-cli &> /dev/null; then
    echo "huggingface-cli not found. Installing..."
    pip install -U huggingface_hub
fi

# 디렉토리 생성
mkdir -p "${MODEL_DIR}"

echo "Starting download..."
echo "This will take 1-2 hours depending on network speed (~40-50GB)"
echo ""

# 모델 다운로드
huggingface-cli download "${MODEL_ID}" \
    --local-dir "${MODEL_DIR}" \
    --local-dir-use-symlinks False

echo ""
echo "======================================"
echo "Download completed!"
echo "======================================"
echo "Model location: ${MODEL_DIR}"
echo ""

# 다운로드 확인
echo "Verifying download..."
ls -lh "${MODEL_DIR}"

echo ""
echo "Next step: Run vLLM server with:"
echo "  cd /home/sphwang/dev/vLLM/services/vllm"
echo "  ./run_vllm.sh"
