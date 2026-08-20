#!/bin/bash
# 绝影Lite3 环境自动配置脚本
# 用法: ./scripts/auto_configure.sh

set -e

echo "=========================================="
echo "绝影Lite3 环境自动配置"
echo "=========================================="
echo ""

# 检查Python版本
echo "[1/5] 检查Python版本..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
    echo "  ✓ Python $PYTHON_VERSION 满足要求"
else
    echo "  ✗ Python $PYTHON_VERSION 不满足要求（需要 >= 3.8）"
    echo "  请升级Python版本: sudo apt-get install python3.8"
    exit 1
fi
echo ""

# 检查虚拟环境
echo "[2/5] 检查虚拟环境..."
if [ ! -f "venv/bin/python" ]; then
    echo "  ℹ 创建虚拟环境..."
    python3 -m venv venv
    echo "  ✓ 虚拟环境已创建"
else
    echo "  ✓ 虚拟环境已存在"
fi
echo ""

# 激活虚拟环境
echo "  激活虚拟环境..."
source venv/bin/activate
echo "  ✓ 虚拟环境已激活"
echo ""

# 安装依赖
echo "[3/5] 安装核心依赖..."
MISSING_PACKAGES=()
REQUIRED_PACKAGES=("loguru" "numpy" "opencv-python" "websockets" "requests" "yaml" "fastapi" "uvicorn" "pydantic")

for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if ! $PYTHON -c "import $pkg" 2>/dev/null; then
        echo "  安装 $pkg..."
        pip install "$pkg" -q
    fi
done

echo "  ✓ 核心依赖安装完成"
echo ""

# 检测GPU
echo "[4/5] 检测GPU环境..."
if command -v nvidia-smi &> /dev/null; then
    echo "  ✓ 检测到NVIDIA GPU"
    GPU_MODEL=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    echo "    GPU型号: $GPU_MODEL"
    
    # 询问是否安装GPU依赖
    read -p "  是否安装GPU依赖以支持真实模式？(y/N): " install_gpu
    if [ "$install_gpu" = "y" ] || [ "$install_gpu" = "Y" ]; then
        echo "  安装GPU依赖..."
        pip install -r requirements-gpu.txt -q
        echo "  ✓ GPU依赖安装完成"
    else
        echo "  ℹ 跳过GPU依赖安装，将使用模拟模式"
    fi
else
    echo "  ℹ 未检测到NVIDIA GPU，将使用模拟模式"
fi
echo ""

# 创建目录
echo "[5/5] 创建必要目录..."
mkdir -p data/logs data/cache models
chmod +x scripts/*.sh scripts/*.py
echo "  ✓ 目录创建完成"
echo ""

# 总结
echo "=========================================="
echo "配置完成"
echo "=========================================="
echo ""
echo "下一步操作:"
echo "  1. 运行环境诊断: ./scripts/gather_info.sh"
echo "  2. 检查部署就绪: ./scripts/check_deployment.sh"
echo "  3. 启动演示: python3 scripts/demo_12min.py --mode simulation"
echo ""
echo "=========================================="
