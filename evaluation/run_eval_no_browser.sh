#!/bin/bash

# 评测脚本 - 跳过浏览器预登录
# 适用于：自动登录失败但服务都正常运行的情况

# 设置临时目录为用户有权限的位置
export TMPDIR=/home/hxm826/tmp_eval
export TEMP=$TMPDIR
export TMP=$TMPDIR

# 确保临时目录存在
mkdir -p "$TMPDIR"

# 设置目录权限，确保容器可以写入
chmod 777 "$TMPDIR"

echo "使用临时目录: $TMPDIR"
echo "⚠️  注意: 跳过浏览器预登录步骤"
echo "确保所有服务都已正常运行："
echo "  - RocketChat: http://localhost:3002"
echo "  - GitLab: http://localhost:8929"
echo "  - Plane: http://localhost:8091"
echo "  - OwnCloud: http://localhost:8092"
echo ""

# 设置环境变量跳过预登录
export SKIP_PRE_LOGIN=1

# 设置正确的服务端口
export ROCKETCHAT_PORT=3002

# 调用原始的评测脚本
bash "$(dirname "$0")/run_eval.sh" "$@"


