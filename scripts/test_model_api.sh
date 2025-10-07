#!/bin/bash

# 测试模型 API 是否正常工作
# 使用方法: bash test_model_api.sh [base_url] [model_name]

BASE_URL=${1:-"http://localhost:8000"}
MODEL=${2:-"Qwen/Qwen2.5-7B-Instruct"}

echo "================================================"
echo "🧪 测试模型 API"
echo "================================================"
echo "Base URL: $BASE_URL"
echo "Model: $MODEL"
echo "================================================"
echo ""

# 测试 1: 检查服务是否可访问
echo "📡 测试 1: 检查服务可访问性..."
if curl -s -f "$BASE_URL/v1/models" > /dev/null; then
    echo "✅ 服务可访问"
else
    echo "❌ 服务不可访问，请检查服务是否启动"
    exit 1
fi

echo ""

# 测试 2: 列出可用模型
echo "📋 测试 2: 列出可用模型..."
MODELS=$(curl -s "$BASE_URL/v1/models" | python -m json.tool)
echo "$MODELS"

echo ""

# 测试 3: 发送简单的补全请求
echo "💬 测试 3: 测试聊天补全..."
RESPONSE=$(curl -s "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL\",
    \"messages\": [
      {\"role\": \"user\", \"content\": \"Hello! Please respond with 'API is working'\"}
    ],
    \"max_tokens\": 50,
    \"temperature\": 0
  }")

echo "$RESPONSE" | python -m json.tool

# 提取响应内容
CONTENT=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin)['choices'][0]['message']['content'])" 2>/dev/null || echo "解析失败")

echo ""
echo "================================================"
if [ "$CONTENT" != "解析失败" ]; then
    echo "✅ API 测试成功!"
    echo "模型响应: $CONTENT"
else
    echo "❌ API 测试失败，请检查响应"
fi
echo "================================================"

