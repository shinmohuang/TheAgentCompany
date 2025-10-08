#!/bin/bash

# 启动 Qwen3-30B-A3B (非FP8版本，适配A100)
# 使用 32K 上下文，2个GPU

set -e

MODEL="Qwen/Qwen3-30B-A3B-Instruct-2507"
PORT=${1:-8000}
GPU_COUNT=${2:-2}
MAX_LEN=${3:-32768}

echo "================================================"
echo "🚀 启动 Qwen3-30B-A3B (A100专用配置)"
echo "================================================"
echo "模型: $MODEL"
echo "端口: $PORT"
echo "GPU数量: $GPU_COUNT"
echo "最大上下文: $MAX_LEN tokens ($(($MAX_LEN/1024))K)"
echo "================================================"

# 检查GPU
nvidia-smi --query-gpu=name,memory.free --format=csv,noheader

echo ""
echo "🔄 启动 vLLM 服务器..."
echo ""

vllm serve "$MODEL" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --trust-remote-code \
    --tensor-parallel-size "$GPU_COUNT" \
    --max-model-len "$MAX_LEN" \
    --gpu-memory-utilization 0.90

