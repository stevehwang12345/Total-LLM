#!/bin/bash

MODEL="Qwen/Qwen3.5-9B-Instruct"
PORT=9000
GPU_ID=${GPU_ID:-1}

CUDA_VISIBLE_DEVICES=$GPU_ID python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --served-model-name "$MODEL" \
    --host 0.0.0.0 \
    --port $PORT \
    --max-model-len 65536 \
    --gpu-memory-utilization 0.85 \
    --dtype auto \
    --trust-remote-code \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    --limit-mm-per-prompt image=4 \
    --chat-template-content-format openai \
    --reasoning-parser qwen3 \
    2>&1 | tee /tmp/vllm_qwen3.5_9b.log
