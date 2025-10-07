#!/bin/bash

# 使用开源模型快速评测脚本
# 使用方法: bash quick_eval_opensource.sh

set -e

echo "================================================"
echo "🤖 TheAgentCompany 开源模型评测"
echo "================================================"
echo ""

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  警告: 建议使用 root 权限运行评测"
    echo "请使用: sudo bash $0"
    read -p "是否继续? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 检查配置文件
CONFIG_FILE="evaluation/config.toml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 错误: 配置文件不存在: $CONFIG_FILE"
    echo "请先配置 evaluation/config.toml"
    exit 1
fi

echo "📋 当前配置:"
cat "$CONFIG_FILE"
echo ""

# 询问是否继续
read -p "配置正确吗? 按 Enter 继续，Ctrl+C 取消..."

# 检查服务
echo ""
echo "🔍 检查服务状态..."

SERVICES=(
    "RocketChat:http://localhost:3002"
    "GitLab:http://localhost:8929"
    "Plane:http://localhost:8091"
    "OwnCloud:http://localhost:8092"
)

for service in "${SERVICES[@]}"; do
    IFS=':' read -r name url <<< "$service"
    if curl -s -f "$url" > /dev/null 2>&1; then
        echo "✅ $name: $url"
    else
        echo "❌ $name 不可访问: $url"
        echo "   请先启动所有服务"
        exit 1
    fi
done

echo ""
echo "✅ 所有服务正常"
echo ""

# 询问评测模式
echo "📊 选择评测模式:"
echo "1) 完整评测 (175 个任务，可能需要数天)"
echo "2) 仅 NPC 任务 (约 60 个任务)"
echo "3) 单个任务测试"
read -p "请选择 (1/2/3): " mode

case $mode in
    1)
        echo "开始完整评测..."
        cd evaluation
        bash run_eval.sh \
            --agent-llm-config group1 \
            --env-llm-config group2 \
            --outputs-path outputs \
            --server-hostname localhost \
            --version 1.0.0
        ;;
    2)
        echo "开始 NPC 任务评测..."
        cd evaluation
        bash run_eval.sh \
            --agent-llm-config group1 \
            --env-llm-config group2 \
            --outputs-path outputs \
            --server-hostname localhost \
            --version 1.0.0 \
            --run-npc-tasks-only
        ;;
    3)
        echo "可用任务示例:"
        echo "- hr-get-valid-password"
        echo "- pm-send-notification-to-corresponding-user"
        echo "- sde-debug-crashed-server"
        read -p "请输入任务名称: " task_name
        
        echo "启动任务容器..."
        docker run --name test-$task_name --network host -it \
            ghcr.io/theagentcompany/taskimage_$task_name:1.0.0 \
            /bin/bash
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac

echo ""
echo "================================================"
echo "✅ 评测完成!"
echo "================================================"
echo ""
echo "查看结果:"
echo "  poetry run python evaluation/summarise_results.py outputs"
echo ""

