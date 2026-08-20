#!/bin/bash
# 绝影Lite3 环境诊断脚本
# 用法: ./scripts/run_diagnostic.sh [选项]
#
# 选项:
#   --deps      仅检查依赖
#   --network   仅检查网络
#   --full      完整诊断（默认）
#   --output    指定输出路径
#   --help      显示帮助

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "绝影Lite3 环境诊断工具"
echo "=========================================="
echo "项目路径: $PROJECT_ROOT"
echo "诊断时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# 检查Python是否可用
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到python3"
    echo "请先安装Python 3.8+:"
    echo "  Ubuntu: sudo apt-get install python3 python3-pip"
    echo "  macOS:  brew install python3"
    exit 1
fi

echo "✓ Python版本: $(python3 --version)"
echo ""

# 检查虚拟环境
if [ -f "$PROJECT_ROOT/venv/bin/python" ]; then
    PYTHON="$PROJECT_ROOT/venv/bin/python"
    echo "✓ 使用虚拟环境: $PROJECT_ROOT/venv"
else
    PYTHON="python3"
    echo "ℹ 使用系统Python"
fi
echo ""

# 检查必需依赖
echo "[检查依赖]"
REQUIRED_PACKAGES=("loguru" "numpy" "cv2" "websockets" "requests" "yaml" "fastapi" "uvicorn" "pydantic")
MISSING_PACKAGES=()

for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if $PYTHON -c "import $pkg" 2>/dev/null; then
        echo "  ✓ $pkg"
    else
        echo "  ✗ $pkg (缺失)"
        MISSING_PACKAGES+=("$pkg")
    fi
done
echo ""

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo "⚠️  缺少依赖包: ${MISSING_PACKAGES[*]}"
    echo "请运行以下命令安装:"
    echo "  pip install -r requirements.txt"
    echo ""
fi

# 检查GPU依赖（可选）
echo "[检查GPU环境]"
if $PYTHON -c "import torch" 2>/dev/null; then
    echo "  ✓ PyTorch已安装"
    if $PYTHON -c "import torch; print(torch.cuda.is_available())" 2>/dev/null | grep -q True; then
        echo "  ✓ CUDA可用"
    else
        echo "  ⚠️  CUDA不可用（将使用模拟模式）"
    fi
else
    echo "  ℹ  PyTorch未安装（将使用模拟模式）"
fi
echo ""

# 检查网络连接
echo "[检查网络连接]"
TARGETS=("192.168.1.103:43893" "192.168.1.108:80" "192.168.1.108:554" "192.168.1.200:8765")
UNREACHABLE=()

for target in "${TARGETS[@]}"; do
    IP=$(echo $target | cut -d: -f1)
    PORT=$(echo $target | cut -d: -f2)
    
    if timeout 2 bash -c "echo > /dev/tcp/$IP/$PORT" 2>/dev/null; then
        echo "  ✓ $target (可达)"
    else
        echo "  ⚠️  $target (超时或不可达)"
        UNREACHABLE+=("$target")
    fi
done
echo ""

if [ ${#UNREACHABLE[@]} -gt 0 ]; then
    echo "ℹ️  注意: 当前可能在云端环境，无法访问内网设备"
    echo "   这是正常的，系统会自动降级到模拟模式"
    echo ""
fi

# 检查配置文件
echo "[检查配置文件]"
if [ -f "$PROJECT_ROOT/config/inspection_config.yaml" ]; then
    echo "  ✓ inspection_config.yaml"
else
    echo "  ✗ inspection_config.yaml (缺失)"
fi
echo ""

# 检查模型文件
echo "[检查模型文件]"
if [ -d "$PROJECT_ROOT/models" ]; then
    MODEL_COUNT=$(find "$PROJECT_ROOT/models" -name "*.trt" -o -name "*.onnx" 2>/dev/null | wc -l)
    if [ "$MODEL_COUNT" -gt 0 ]; then
        echo "  ✓ 发现 $MODEL_COUNT 个模型文件"
    else
        echo "  ⚠️  未找到模型文件（将使用模拟模式）"
    fi
else
    echo "  ℹ  models目录不存在（模拟模式不需要）"
fi
echo ""

# 运行完整诊断脚本
echo "[运行完整诊断]"
if [ -f "$PROJECT_ROOT/scripts/detect_environment.py" ]; then
    echo "  正在生成详细诊断报告..."
    $PYTHON "$PROJECT_ROOT/scripts/detect_environment.py" --full --output "$PROJECT_ROOT/data/diagnostic_report"
    echo ""
    echo "✓ 诊断报告已生成:"
    echo "  - HTML: $PROJECT_ROOT/data/diagnostic_report.html"
    echo "  - JSON: $PROJECT_ROOT/data/diagnostic_report.json"
    echo "  - MD:   $PROJECT_ROOT/data/diagnostic_report.md"
else
    echo "  ⚠️  detect_environment.py未找到"
fi
echo ""

# 诊断结论
echo "=========================================="
echo "诊断结论"
echo "=========================================="

if [ ${#MISSING_PACKAGES[@]} -eq 0 ] && [ ${#UNREACHABLE[@]} -eq 0 ]; then
    echo "✅ 环境检查通过，可以运行演示"
    echo ""
    echo "启动命令:"
    echo "  python3 scripts/start_monitor.py    # 启动监测平台"
    echo "  python3 scripts/run_demo.py --mode simulation  # 运行演示"
elif [ ${#MISSING_PACKAGES[@]} -eq 0 ]; then
    echo "⚠️  部分网络目标不可达，但可以运行模拟模式"
    echo ""
    echo "说明: 当前环境无法访问硬件设备，系统将自动降级到模拟模式"
    echo ""
    echo "启动命令:"
    echo "  python3 scripts/start_monitor.py    # 启动监测平台"
    echo "  python3 scripts/run_demo.py --mode simulation  # 运行演示"
else
    echo "❌ 缺少必需依赖，请先安装依赖"
    echo ""
    echo "安装命令:"
    echo "  pip install -r requirements.txt"
    echo ""
    echo "或使用国内镜像:"
    echo "  pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"
fi

echo ""
echo "=========================================="
echo "诊断完成"
echo "=========================================="
