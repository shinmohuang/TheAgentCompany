#!/bin/bash

# vLLM 快速启动脚本
# 使用方法: bash start_vllm.sh [model_name] [port] [gpu_count] [max_context_length]
# 例如: bash start_vllm.sh "Qwen/Qwen2.5-7B-Instruct" 8000 1 32768

set -e

# 默认参数
MODEL=${1:-"Qwen/Qwen2.5-72B-Instruct"}
PORT=${2:-8000}
GPU_COUNT=${3:-1}

echo "================================================"
echo "🚀 启动 vLLM 服务"
echo "================================================"
echo "模型: $MODEL"
echo "端口: $PORT"
echo "GPU 数量: $GPU_COUNT"
echo "================================================"

# 提高文件描述符限制
echo ""
echo "📊 设置系统限制..."
CURRENT_ULIMIT=$(ulimit -n)
echo "当前 ulimit: $CURRENT_ULIMIT"

if [ "$CURRENT_ULIMIT" -lt 65535 ]; then
    echo "尝试提高 ulimit 到 65535..."
    ulimit -n 65535 2>/dev/null || echo "⚠️  警告: 无法自动提高 ulimit，如遇到 'Too many open files' 错误，请手动运行: ulimit -n 65535"
    echo "新的 ulimit: $(ulimit -n)"
fi

# 检查 GPU
if ! command -v nvidia-smi &> /dev/null; then
    echo "❌ 错误: 未检测到 NVIDIA GPU 或驱动"
    echo "请确保已安装 NVIDIA 驱动和 CUDA"
    exit 1
fi

echo ""
echo "📊 GPU 信息:"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# 检查 GPU 数量
AVAILABLE_GPUS=$(nvidia-smi --list-gpus | wc -l)
echo "可用 GPU 数量: $AVAILABLE_GPUS"

if [ "$GPU_COUNT" -gt "$AVAILABLE_GPUS" ]; then
    echo "❌ 错误: 请求使用 $GPU_COUNT 个 GPU，但只有 $AVAILABLE_GPUS 个可用"
    exit 1
fi

# 提示 tensor parallel 要求
echo ""
echo "💡 注意: tensor parallel size 必须能整除模型的注意力头数量"
echo "   - Qwen2.5-72B: 40 个头 (使用 1, 2, 4, 5, 8, 10, 20 或 40 个 GPU)"
echo "   - Llama-3.1-70B: 64 个头 (使用 1, 2, 4, 8, 16, 32 或 64 个 GPU)"
echo "   - 当前使用: $GPU_COUNT 个 GPU"

# 检查 vLLM 是否安装
if ! python -c "import vllm" 2>/dev/null; then
    echo ""
    echo "📦 vLLM 未安装，正在安装..."
    pip install vllm
fi

echo ""
echo "🔄 启动 vLLM 服务器..."
echo "提示: 首次运行会下载模型，可能需要较长时间"
echo ""

# 默认最大上下文长度
MAX_MODEL_LEN=${4:-32768}  # 默认 32K，可以通过第4个参数修改

echo "最大上下文长度: $MAX_MODEL_LEN tokens"
echo ""

# 启动 vLLM
python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --trust-remote-code \
    --tensor-parallel-size "$GPU_COUNT" \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization 0.85

# 如果需要后台运行，可以使用:
# nohup python -m vllm.entrypoints.openai.api_server \
#     --model "$MODEL" \
#     --host 0.0.0.0 \
#     --port "$PORT" \
#     --trust-remote-code \
#     --tensor-parallel-size "$GPU_COUNT" \
#     > vllm.log 2>&1 &
# 
# echo "✅ vLLM 已在后台启动"
# echo "日志文件: vllm.log"
# echo "进程 PID: $!"

