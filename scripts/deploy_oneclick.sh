#!/bin/bash
# 绝影Lite3监测平台 - 一键部署脚本 (Linux/Mac)

echo ""
echo "============================================"
echo " 绝影Lite3监测平台 - 一键部署"
echo "============================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found"
    exit 1
fi

echo "[1/4] Python检查通过"
python3 --version
echo ""

# Build Frontend (optional)
if command -v pnpm &> /dev/null; then
    echo "[2/4] 构建前端..."
    cd frontend
    pnpm install --no-frozen-lockfile 2>/dev/null || pnpm install
    pnpm build
    cd ..
    echo "✓ 前端构建完成"
else
    echo "[2/4] 跳过前端构建 (pnpm未安装)"
fi
echo ""

# Install Python dependencies
echo "[3/4] 安装Python依赖..."
if [ -f requirements.txt ]; then
    pip3 install -q -r requirements.txt
fi
if [ -f monitor_platform/requirements.txt ]; then
    pip3 install -q -r monitor_platform/requirements.txt
fi
echo "✓ 依赖安装完成"
echo ""

# Start Server
echo "[4/4] 启动服务..."
echo ""
echo "============================================"
echo " 监测平台启动成功"
echo "============================================"
echo ""
echo "   Web界面:   http://localhost:8000"
echo "   API文档:   http://localhost:8000/docs"
echo "   WebSocket: ws://localhost:8765/ws"
echo ""
echo "   按 Ctrl+C 停止服务"
echo ""

exec python3 monitor_platform/server.py
