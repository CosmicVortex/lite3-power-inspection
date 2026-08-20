#!/bin/bash
# 绝影Lite3 机器狗环境信息采集脚本
# 用法: ./scripts/gather_info.sh [--output report.md]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "绝影Lite3 机器狗环境信息采集"
echo "=========================================="
echo ""
echo "采集时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "项目路径: $PROJECT_ROOT"
echo ""

# 检查Python
echo "[1/6] 检查Python环境..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo "  ✓ Python版本: $PYTHON_VERSION"
    PYTHON_PATH=$(which python3)
    echo "  ✓ Python路径: $PYTHON_PATH"
else
    echo "  ✗ 未找到python3"
    exit 1
fi
echo ""

# 检查虚拟环境
echo "[2/6] 检查虚拟环境..."
if [ -f "$PROJECT_ROOT/venv/bin/python" ]; then
    VENV_PYTHON="$PROJECT_ROOT/venv/bin/python"
    echo "  ✓ 虚拟环境: $PROJECT_ROOT/venv"
    VENV_ACTIVE="是的"
else
    VENV_PYTHON="python3"
    echo "  ⚠ 虚拟环境不存在，使用系统Python"
    VENV_ACTIVE="否"
fi
echo ""

# 系统信息
echo "[3/6] 采集系统信息..."
OS_NAME=$(uname -s)
OS_VERSION=$(uname -r)
ARCH=$(uname -m)
HOSTNAME=$(hostname)

echo "  操作系统: $OS_NAME"
echo "  内核版本: $OS_VERSION"
echo "  架构: $ARCH"
echo "  主机名: $HOSTNAME"
echo ""

# CPU信息
echo "  CPU信息:"
CPU_CORES=$(nproc 2>/dev/null || echo "N/A")
CPU_MODEL=$(grep 'model name' /proc/cpuinfo 2>/dev/null | head -1 | cut -d: -f2 | xargs || echo "N/A")
CPU_LOAD=$(cat /proc/loadavg 2>/dev/null | awk '{print $1, $2, $3}' || echo "N/A")
echo "    核心数: $CPU_CORES"
echo "    型号: $CPU_MODEL"
echo "    负载: $CPU_LOAD"
echo ""

# 内存信息
echo "  内存信息:"
MEMORY_INFO=$(free -h | grep Mem | awk '{print "总量: "$2", 已用: "$3", 可用: "$4}')
echo "    $MEMORY_INFO"
echo ""

# GPU信息
echo "[4/6] 检测GPU环境..."
if command -v nvidia-smi &> /dev/null; then
    echo "  ✓ NVIDIA GPU检测工具可用"
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -1)
    if [ -n "$GPU_INFO" ]; then
        echo "  ✓ 检测到GPU: $GPU_INFO"
        CUDA_VERSION=$(nvcc --version 2>/dev/null | grep release | awk '{print $NF}' || echo "N/A")
        echo "  ✓ CUDA版本: $CUDA_VERSION"
    else
        echo "  ⚠ 未检测到GPU"
    fi
else
    echo "  ℹ 未安装nvidia-smi，跳过GPU检测"
fi
echo ""

# Python依赖检查
echo "[5/6] 检查Python依赖..."
REQUIRED_PACKAGES=("loguru" "numpy" "cv2" "websockets" "requests" "yaml" "fastapi" "uvicorn" "pydantic")
INSTALLED_COUNT=0
MISSING_PACKAGES=()

for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if $VENV_PYTHON -c "import $pkg" 2>/dev/null; then
        VERSION=$($VENV_PYTHON -c "import $pkg; print(getattr($pkg, '__version__', 'unknown'))" 2>/dev/null)
        echo "  ✓ $pkg: $VERSION"
        INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
    else
        echo "  ✗ $pkg: 未安装"
        MISSING_PACKAGES+=("$pkg")
    fi
done
echo ""
echo "  核心依赖: $INSTALLED_COUNT/${#REQUIRED_PACKAGES[@]} 已安装"
echo ""

# 网络连接检查
echo "[6/6] 检查网络连接..."
TARGETS=("192.168.1.103:运动主机" "192.168.1.108:云台相机" "192.168.1.200:监测平台")
REACHABLE=0

for target in "${TARGETS[@]}"; do
    IP=$(echo $target | cut -d: -f1)
    NAME=$(echo $target | cut -d: -f2)
    
    if ping -c 1 -W 1 $IP &> /dev/null; then
        echo "  ✓ $NAME ($IP): 可达"
        REACHABLE=$((REACHABLE + 1))
    else
        echo "  ✗ $NAME ($IP): 不可达"
    fi
done
echo ""
echo "  可达设备: $REACHABLE/${#TARGETS[@]}"
echo ""

# 生成报告
echo "=========================================="
echo "生成环境信息报告"
echo "=========================================="
echo ""

REPORT_FILE="$PROJECT_ROOT/data/system_info_report.md"
mkdir -p "$PROJECT_ROOT/data"

cat > "$REPORT_FILE" << EOF
# 绝影Lite3 机器狗环境信息采集报告

> **采集时间**: $(date '+%Y-%m-%d %H:%M:%S')
> **主机名**: $HOSTNAME
> **项目路径**: $PROJECT_ROOT

---

## 一、系统信息

| 项目 | 值 |
|------|-----|
| 操作系统 | $OS_NAME |
| 内核版本 | $OS_VERSION |
| 架构 | $ARCH |
| 主机名 | $HOSTNAME |

## 二、Python环境

| 项目 | 值 |
|------|-----|
| Python版本 | $PYTHON_VERSION |
| Python路径 | $PYTHON_PATH |
| 虚拟环境 | $VENV_ACTIVE |

## 三、硬件信息

### CPU
- 核心数: $CPU_CORES
- 型号: $CPU_MODEL
- 负载: $CPU_LOAD

### 内存
\`\`\`
$MEMORY_INFO
\`\`\`

### GPU
EOF

if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
    if [ -n "$GPU_INFO" ]; then
        echo "| 状态 | 型号 | 显存 |" >> "$REPORT_FILE"
        echo "|------|------|------|" >> "$REPORT_FILE"
        echo "| ✓ 已检测 | $(echo $GPU_INFO | cut -d',' -f1 | xargs) | $(echo $GPU_INFO | cut -d',' -f2 | xargs) |" >> "$REPORT_FILE"
        CUDA_VERSION=$(nvcc --version 2>/dev/null | grep release | awk '{print $NF}' || echo "N/A")
        echo "" >> "$REPORT_FILE"
        echo "CUDA版本: $CUDA_VERSION" >> "$REPORT_FILE"
    else
        echo "| 状态 | 说明 |" >> "$REPORT_FILE"
        echo "|------|------|" >> "$REPORT_FILE"
        echo "| ✗ 未检测到 | 将使用模拟模式 |" >> "$REPORT_FILE"
    fi
else
    echo "| 状态 | 说明 |" >> "$REPORT_FILE"
    echo "|------|------|" >> "$REPORT_FILE"
    echo "| ℹ 未安装nvidia-smi | 跳过GPU检测 |" >> "$REPORT_FILE"
fi

cat >> "$REPORT_FILE" << EOF

## 四、网络信息

### IP地址
\`\`\`
\$(ip addr show | grep 'inet ' | awk '{print \$2}')
\`\`\`

### 设备连通性
| 设备 | IP地址 | 状态 |
|------|--------|------|
EOF

for target in "${TARGETS[@]}"; do
    IP=$(echo $target | cut -d: -f1)
    NAME=$(echo $target | cut -d: -f2)
    
    if ping -c 1 -W 1 $IP &> /dev/null; then
        echo "| $NAME | $IP | ✓ 可达 |" >> "$REPORT_FILE"
    else
        echo "| $NAME | $IP | ✗ 不可达 |" >> "$REPORT_FILE"
    fi
done

cat >> "$REPORT_FILE" << EOF

## 五、Python依赖

### 核心依赖
| 包名 | 状态 | 版本 |
|------|------|------|
EOF

for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if $VENV_PYTHON -c "import $pkg" 2>/dev/null; then
        VERSION=$($VENV_PYTHON -c "import $pkg; print(getattr($pkg, '__version__', 'unknown'))" 2>/dev/null)
        echo "| $pkg | ✓ 已安装 | $VERSION |" >> "$REPORT_FILE"
    else
        echo "| $pkg | ✗ 未安装 | - |" >> "$REPORT_FILE"
    fi
done

cat >> "$REPORT_FILE" << EOF

## 六、诊断结论

### 部署就绪性评估
EOF

if [ ${#MISSING_PACKAGES[@]} -eq 0 ] && [[ $PYTHON_VERSION == *"3."* ]] && [[ $(echo $PYTHON_VERSION | cut -d. -f2) -ge 8 ]]; then
    echo "| 检查项 | 状态 | 说明 |" >> "$REPORT_FILE"
    echo "|--------|------|------|" >> "$REPORT_FILE"
    echo "| Python版本 | ✓ 通过 | >= 3.8 |" >> "$REPORT_FILE"
    echo "| 核心依赖 | ✓ 通过 | 全部安装 |" >> "$REPORT_FILE"
    if [ $REACHABLE -eq ${#TARGETS[@]} ]; then
        echo "| 网络连接 | ✓ 通过 | 全部可达 |" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
        echo "**结论**: ✅ 系统具备完整部署条件" >> "$REPORT_FILE"
    else
        echo "| 网络连接 | ⚠ 部分可达 | $REACHABLE/${#TARGETS[@]} 设备可达 |" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
        echo "**结论**: ⚠️ 系统基本可用，网络问题不影响模拟模式" >> "$REPORT_FILE"
    fi
else
    echo "| 检查项 | 状态 | 说明 |" >> "$REPORT_FILE"
    echo "|--------|------|------|" >> "$REPORT_FILE"
    if [[ $PYTHON_VERSION != *"3.8"* ]] && [[ $PYTHON_VERSION != *"3.9"* ]] && [[ $PYTHON_VERSION != *"3.10"* ]] && [[ $PYTHON_VERSION != *"3.11"* ]] && [[ $PYTHON_VERSION != *"3.12"* ]] && [[ $PYTHON_VERSION != *"3.13"* ]]; then
        echo "| Python版本 | ✗ 失败 | < 3.8 |" >> "$REPORT_FILE"
    else
        echo "| Python版本 | ✓ 通过 | >= 3.8 |" >> "$REPORT_FILE"
    fi
    if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
        echo "| 核心依赖 | ✗ 失败 | 缺少: ${MISSING_PACKAGES[*]} |" >> "$REPORT_FILE"
    else
        echo "| 核心依赖 | ✓ 通过 | 全部安装 |" >> "$REPORT_FILE"
    fi
    echo "" >> "$REPORT_FILE"
    echo "**结论**: ❌ 系统不具备部署条件，请修复上述问题" >> "$REPORT_FILE"
fi

cat >> "$REPORT_FILE" << EOF

---

*报告生成时间: $(date '+%Y-%m-%d %H:%M:%S')*
EOF

echo "✓ 报告已生成: $REPORT_FILE"
echo ""

# 输出摘要
echo "=========================================="
echo "采集完成"
echo "=========================================="
echo ""
echo "报告文件: $REPORT_FILE"
echo ""
echo "下一步操作:"
echo "  1. 查看报告: cat $REPORT_FILE"
echo "  2. 修复问题（如有）"
echo "  3. 将报告反馈给技术支持"
echo ""
echo "=========================================="
