#!/bin/bash
# 绝影Lite3 系统部署就绪检查脚本
# 用法: ./scripts/check_deployment.sh

set -e

echo "=========================================="
echo "绝影Lite3 部署就绪检查"
echo "=========================================="
echo ""

PASS=0
FAIL=0
WARN=0

# 检查Python版本
echo "[1/8] 检查Python版本..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
    echo "  ✓ Python $PYTHON_VERSION"
    PASS=$((PASS+1))
else
    echo "  ✗ Python版本过低，需要 >= 3.8"
    FAIL=$((FAIL+1))
fi

# 检查虚拟环境
echo ""
echo "[2/8] 检查虚拟环境..."
if [ -f "venv/bin/python" ]; then
    echo "  ✓ 虚拟环境存在"
    PASS=$((PASS+1))
else
    echo "  ⚠ 虚拟环境不存在，建议使用venv"
    WARN=$((WARN+1))
fi

# 检查核心依赖
echo ""
echo "[3/8] 检查核心依赖..."
REQUIRED_PACKAGES=("loguru" "numpy" "cv2" "websockets" "requests" "yaml" "fastapi" "uvicorn" "pydantic")
MISSING_PACKAGES=()

for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if python3 -c "import $pkg" 2>/dev/null; then
        echo "  ✓ $pkg"
    else
        echo "  ✗ $pkg (缺失)"
        MISSING_PACKAGES+=("$pkg")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -eq 0 ]; then
    PASS=$((PASS+1))
else
    echo "  请运行: pip install -r requirements.txt"
    FAIL=$((FAIL+1))
fi

# 检查配置文件
echo ""
echo "[4/8] 检查配置文件..."
if [ -f "config/inspection_config.yaml" ]; then
    echo "  ✓ inspection_config.yaml 存在"
    PASS=$((PASS+1))
else
    echo "  ✗ 配置文件不存在"
    FAIL=$((FAIL+1))
fi

# 检查关键脚本
echo ""
echo "[5/8] 检查关键脚本..."
SCRIPTS=("scripts/run_demo.py" "scripts/start_monitor.py" "scripts/demo_12min.py" "scripts/run_diagnostic.sh")
MISSING_SCRIPTS=()

for script in "${SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        echo "  ✓ $script"
    else
        echo "  ✗ $script (缺失)"
        MISSING_SCRIPTS+=("$script")
    fi
done

if [ ${#MISSING_SCRIPTS[@]} -eq 0 ]; then
    PASS=$((PASS+1))
else
    FAIL=$((FAIL+1))
fi

# 检查GPU环境（可选）
echo ""
echo "[6/8] 检查GPU环境..."
if python3 -c "import torch" 2>/dev/null; then
    CUDA_AVAILABLE=$(python3 -c "import torch; print(torch.cuda.is_available())")
    if [ "$CUDA_AVAILABLE" = "True" ]; then
        echo "  ✓ CUDA可用（真实模式可用）"
        PASS=$((PASS+1))
    else
        echo "  ⚠ CUDA不可用（将使用模拟模式）"
        WARN=$((WARN+1))
    fi
else
    echo "  ℹ PyTorch未安装（将使用模拟模式）"
    WARN=$((WARN+1))
fi

# 检查模型文件（可选）
echo ""
echo "[7/8] 检查模型文件..."
if [ -d "models" ]; then
    MODEL_COUNT=$(find models -name "*.trt" -o -name "*.onnx" 2>/dev/null | wc -l)
    if [ "$MODEL_COUNT" -gt 0 ]; then
        echo "  ✓ 发现 $MODEL_COUNT 个模型文件"
        PASS=$((PASS+1))
    else
        echo "  ℹ 未找到模型文件（将使用模拟模式）"
        WARN=$((WARN+1))
    fi
else
    echo "  ℹ models目录不存在（将使用模拟模式）"
    WARN=$((WARN+1))
fi

# 检查数据目录
echo ""
echo "[8/8] 检查数据目录..."
if [ -d "data/logs" ]; then
    echo "  ✓ 日志目录存在"
    PASS=$((PASS+1))
else
    mkdir -p data/logs
    echo "  ✓ 日志目录已创建"
    PASS=$((PASS+1))
fi

# 总结
echo ""
echo "=========================================="
echo "检查结果"
echo "=========================================="
echo "  ✓ 通过: $PASS"
echo "  ⚠ 警告: $WARN"
echo "  ✗ 失败: $FAIL"
echo "=========================================="

if [ $FAIL -eq 0 ]; then
    echo ""
    echo "✅ 系统具备部署条件"
    echo ""
    echo "启动命令:"
    echo "  ./scripts/run_diagnostic.sh     # 运行诊断"
    echo "  python3 scripts/start_monitor.py  # 启动监测平台"
    echo "  python3 scripts/demo_12min.py   # 运行12分钟演示"
    echo ""
    exit 0
else
    echo ""
    echo "❌ 系统不具备部署条件，请修复上述问题"
    echo ""
    exit 1
fi
