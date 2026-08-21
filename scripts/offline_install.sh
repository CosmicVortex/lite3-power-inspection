#!/bin/bash
# 绝影Lite3 离线安装脚本
# 
# 功能：从本地wheel包目录安装Python依赖（无需网络）
# 
# 用法：
#   ./scripts/offline_install.sh sensors    # 安装感知主机依赖
#   ./scripts/offline_install.sh monitor    # 安装监测平台依赖
#   ./scripts/offline_install.sh all        # 安装全部依赖

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OFFLINE_DIR="$PROJECT_ROOT/offline-deploy"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info() { echo -e "${CYAN}ℹ️   $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }

usage() {
    echo "用法: $0 [sensors|monitor|all]"
    echo ""
    echo "参数:"
    echo "  sensors  - 安装感知主机依赖 (numpy, opencv, etc.)"
    echo "  monitor  - 安装监测平台依赖 (fastapi, uvicorn, etc.)"
    echo "  all      - 安装全部依赖"
    echo ""
    echo "示例:"
    echo "  $0 sensors"
    echo "  $0 monitor"
    exit 1
}

install_packages() {
    local package_type="$1"
    local wheel_dir="$OFFLINE_DIR/$package_type"
    
    if [ ! -d "$wheel_dir" ]; then
        log_error "离线包目录不存在: $wheel_dir"
        exit 1
    fi
    
    local whl_count=$(find "$wheel_dir" -name "*.whl" | wc -l)
    if [ "$whl_count" -eq 0 ]; then
        log_error "未找到wheel包: $wheel_dir"
        exit 1
    fi
    
    log_info "找到 $whl_count 个wheel包: $wheel_dir"
    
    # 检查Python环境
    if ! command -v python3 &> /dev/null; then
        log_error "未找到python3"
        exit 1
    fi
    
    PYTHON=$(command -v python3)
    PIP="$PYTHON -m pip"
    
    log_info "使用Python: $PYTHON"
    log_info "开始安装..."
    
    # 创建虚拟环境（如不存在）
    if [ ! -d "$PROJECT_ROOT/venv" ]; then
        log_info "创建虚拟环境..."
        $PYTHON -m venv "$PROJECT_ROOT/venv"
    fi
    
    source "$PROJECT_ROOT/venv/bin/activate"
    
    # 离线安装
    $PIP install --no-index --find-links="$wheel_dir" "$wheel_dir"/*.whl -q
    
    log_success "$package_type 依赖安装完成"
}

# 主程序
if [ $# -eq 0 ]; then
    usage
fi

case "$1" in
    sensors)
        install_packages "sensors"
        ;;
    monitor)
        install_packages "monitor"
        ;;
    all)
        install_packages "sensors"
        install_packages "monitor"
        ;;
    *)
        log_error "未知参数: $1"
        usage
        ;;
esac
