# 使用开源模型进行评测指南

本指南将帮助您部署开源模型并使用 TheAgentCompany 进行评测。

## 📋 目录

1. [模型部署方案](#模型部署方案)
2. [配置评测系统](#配置评测系统)
3. [运行评测](#运行评测)
4. [推荐的开源模型](#推荐的开源模型)
5. [故障排除](#故障排除)

## 🚀 模型部署方案

### 方案 1: vLLM（推荐用于大模型）

vLLM 是高性能的 LLM 推理引擎，支持大多数主流开源模型。

#### 安装和启动

```bash
# 1. 安装 vLLM
pip install vllm

# 2. 启动服务（以 Qwen2.5-72B-Instruct 为例）
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-72B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --trust-remote-code \
  --tensor-parallel-size 2  # 如果有多张 GPU，可以增加此值

# 3. 测试服务是否正常
curl http://localhost:8000/v1/models
```

#### 硬件要求

| 模型大小 | 推荐 GPU | 内存要求 |
|---------|---------|---------|
| 7B      | 1x RTX 3090/4090 | 24GB |
| 13B     | 1x A100 (40GB) | 40GB |
| 34B     | 2x A100 (40GB) | 80GB |
| 70B+    | 4x A100 (80GB) | 320GB |

### 方案 2: Ollama（推荐用于本地测试）

Ollama 是易于使用的本地 LLM 部署工具。

```bash
# 1. 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. 下载模型
ollama pull qwen2.5:72b
# 或其他模型：llama3.1:70b, deepseek-coder:33b 等

# 3. 启动服务（默认端口 11434）
ollama serve

# 4. 测试
curl http://localhost:11434/api/tags
```

### 方案 3: LM Studio（图形界面）

适合不熟悉命令行的用户。

1. 下载：https://lmstudio.ai/
2. 在应用中搜索并下载模型（如 Qwen2.5）
3. 点击 "Start Server"
4. 默认地址：`http://localhost:1234/v1`

### 方案 4: 云端 API 服务

如果本地硬件不足，可以使用这些提供开源模型 API 的云服务：

#### Together AI
```bash
# 注册: https://api.together.xyz/
# 支持: Llama 3.1, Qwen2.5, Mixtral 等
```

配置示例：
```toml
[llm.group1]
model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
base_url="https://api.together.xyz/v1"
api_key="your-together-api-key"
```

#### Groq（速度快）
```bash
# 注册: https://console.groq.com/
# 特点: 超快推理速度
```

配置示例：
```toml
[llm.group1]
model="llama-3.1-70b-versatile"
base_url="https://api.groq.com/openai/v1"
api_key="your-groq-api-key"
```

#### DeepInfra
```bash
# 注册: https://deepinfra.com/
# 支持大量开源模型
```

## ⚙️ 配置评测系统

### 1. 修改配置文件

编辑 `evaluation/config.toml`:

```toml
# Agent 使用的模型（执行任务的 AI Agent）
# ⚠️ 关键：使用本地 vLLM/Ollama 时，模型名前必须加 openai/ 前缀
[llm.group1]
model="openai/Qwen/Qwen2.5-72B-Instruct"
base_url="http://localhost:8000/v1"
api_key="EMPTY"

# 环境模型（NPC 角色扮演和任务评估）
# 建议使用强大的模型以确保评测质量
[llm.group2]
model="openai/Qwen/Qwen2.5-72B-Instruct"
base_url="http://localhost:8000/v1"
api_key="EMPTY"
```

### ⚠️ 重要：模型名前缀规则

| 部署方式 | 是否需要 `openai/` 前缀 | 示例 |
|---------|---------------------|------|
| vLLM (本地) | ✅ **必须** | `openai/Qwen/Qwen2.5-72B-Instruct` |
| Ollama (本地) | ✅ **必须** | `openai/qwen2.5:72b` |
| LM Studio (本地) | ✅ **必须** | `openai/model-name` |
| Together AI | ❌ 不需要 | `meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo` |
| Groq | ❌ 不需要 | `llama-3.1-70b-versatile` |
| OpenAI | ❌ 不需要 | `gpt-4o` |

**原因**：litellm 需要知道这是 OpenAI 兼容的 API，否则会报错：
```
litellm.BadRequestError: LLM Provider NOT provided
```

### 2. 重要说明

- **group1**: Agent 模型，用于执行任务
- **group2**: 环境模型，用于：
  - NPC（非玩家角色）对话
  - LLM-based 评估器评分
  
推荐 group2 使用强大模型（如 Claude 3.5 Sonnet 或 GPT-4o）以确保评测准确性。

### 3. 配置 NPC 和评估器的 LLM

编辑 `workspaces/base_image/Dockerfile`，确保环境变量正确：

```dockerfile
ENV LITELLM_API_KEY EMPTY
ENV LITELLM_BASE_URL http://host.docker.internal:8000/v1
ENV LITELLM_MODEL Qwen/Qwen2.5-72B-Instruct
```

注意：如果使用 vLLM，Docker 容器内需要使用 `host.docker.internal` 而不是 `localhost`。

## 🏃 运行评测

### 完整评测流程

```bash
# 1. 确保所有服务都在运行
# RocketChat 应该在 http://localhost:3002
# GitLab, Plane, OwnCloud 等其他服务也应该正常运行

# 2. 切换到 root 用户（评测需要）
sudo su

# 3. 进入评测目录
cd /home/hxm826/TheAgentCompany/evaluation

# 4. 运行评测
bash run_eval.sh \
  --agent-llm-config group1 \
  --env-llm-config group2 \
  --outputs-path outputs \
  --server-hostname localhost \
  --version 1.0.0

# 可选参数：
# --run-npc-tasks-only  # 只运行需要 NPC 的任务
```

### 单个任务测试

如果想先测试单个任务：

```bash
# 1. 启动任务容器
docker run --name test-task --network host -it \
  ghcr.io/theagentcompany/taskimage_hr-get-valid-password:1.0.0 \
  /bin/bash

# 2. 在容器内初始化环境
SERVER_HOSTNAME=localhost \
LITELLM_API_KEY=EMPTY \
LITELLM_BASE_URL=http://localhost:8000/v1 \
LITELLM_MODEL=Qwen/Qwen2.5-72B-Instruct \
bash /utils/init.sh

# 3. 查看任务说明
cat /instruction/task.md

# 4. 让你的 agent 执行任务...

# 5. 运行评估
LITELLM_API_KEY=EMPTY \
LITELLM_BASE_URL=http://localhost:8000/v1 \
LITELLM_MODEL=Qwen/Qwen2.5-72B-Instruct \
DECRYPTION_KEY='theagentcompany is all you need' \
python_default /utils/eval.py --output_path /workspace/result.json
```

### 查看评测结果

```bash
# 生成评测总结
poetry run python summarise_results.py outputs

# 结果包括：
# - outputs/traj/: 每个任务的轨迹
# - outputs/eval/: 评分结果
# - outputs/screenshots/: 浏览器截图
```

## 🎯 推荐的开源模型

根据任务复杂度和资源，这里是一些推荐：

### 高性能模型（70B+）
- **Qwen2.5-72B-Instruct**: 综合能力强，中英文都很好
- **Llama-3.1-70B-Instruct**: Meta 的旗舰模型
- **DeepSeek-V2**: 性价比高，MoE 架构

### 中等规模模型（30-40B）
- **Qwen2.5-32B-Instruct**: 性能接近 70B
- **Yi-34B-Chat**: 中文能力优秀
- **Mixtral-8x7B**: MoE 架构，效率高

### 轻量级模型（7-14B，用于测试）
- **Qwen2.5-14B-Instruct**: 小巧但能力不错
- **Llama-3.1-8B-Instruct**: 快速测试用
- **Phi-3-Medium**: Microsoft 出品

## 🔧 故障排除

### 问题 1: vLLM 启动失败

```bash
# 检查 CUDA 版本
nvidia-smi

# 重新安装对应版本的 vLLM
pip uninstall vllm
pip install vllm --no-build-isolation
```

### 问题 2: Docker 容器无法访问 localhost

如果使用 vLLM 在宿主机，Docker 容器内需要使用特殊地址：

- **Linux**: 使用 `--network host`
- **Mac/Windows**: 使用 `http://host.docker.internal:8000/v1`

更新 config.toml:
```toml
base_url="http://host.docker.internal:8000/v1"  # Mac/Windows
```

### 问题 3: 模型响应慢

1. 增加 GPU 数量（tensor parallelism）:
```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-72B-Instruct \
  --tensor-parallel-size 4
```

2. 使用量化版本:
```bash
# 使用 AWQ 4-bit 量化
ollama pull qwen2.5:72b-instruct-q4_0
```

### 问题 4: 内存不足

- 使用小一点的模型
- 使用量化版本（如 GPTQ, AWQ, GGUF）
- 启用 CPU offloading（速度会变慢）

### 问题 5: RocketChat 端口错误

确认 RocketChat 在正确的端口（3002）:
```bash
curl http://localhost:3002
```

### 问题 6: NPC 无法正常工作

检查环境变量是否正确传递：
```bash
docker exec -it <container_name> env | grep LITELLM
```

## 📊 性能基准参考

根据我们的测试（非官方）：

| 模型 | 成功率估计 | 推理速度 | 硬件需求 |
|------|----------|---------|---------|
| GPT-4o | ~35% | 快 | 云端 API |
| Claude 3.5 Sonnet | ~40% | 快 | 云端 API |
| Qwen2.5-72B | ~25-30% | 中等 | 4x A100 |
| Llama-3.1-70B | ~20-25% | 中等 | 4x A100 |
| Qwen2.5-32B | ~15-20% | 快 | 2x A100 |

注意：实际性能取决于具体配置和优化。

## 💡 优化建议

1. **混合使用模型**: Agent 用开源模型，NPC 用商业模型
2. **缓存优化**: vLLM 支持 KV cache，可以加速
3. **批处理**: 同时运行多个任务以提高 GPU 利用率
4. **提示工程**: 为开源模型优化系统提示词

## 📚 更多资源

- vLLM 文档: https://docs.vllm.ai/
- Ollama 文档: https://github.com/ollama/ollama
- TheAgentCompany 官网: https://the-agent-company.com/
- OpenHands: https://github.com/All-Hands-AI/OpenHands

## 🤝 社区支持

如有问题，可以：
- 提 Issue: https://github.com/TheAgentCompany/TheAgentCompany/issues
- 查看 Discussions
- 参考其他评测结果

祝评测顺利！🎉

