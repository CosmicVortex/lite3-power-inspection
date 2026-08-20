#!/bin/bash
# 绝影Lite3 一键部署脚本 (Shell版本)
# 
# 功能：
# 1. 检测运行环境（Python版本、系统依赖、GPU环境）
# 2. 检查缺失的Python包，自动安装（优先使用离线包）
# 3. 创建必要目录结构
# 4. 启动监测平台和演示程序
# 5. 提供清晰的状态提示和故障原因说明
#
# 用法：
#   ./scripts/deploy_oneclick.sh              # 完整部署流程
#   ./scripts/deploy_oneclick.sh --check      # 仅检查环境
#   ./scripts/deploy_oneclick.sh --install    # 仅安装依赖
#   ./scripts/deploy_oneclick.sh --start      # 仅启动服务
#   ./scripts/deploy_oneclick.sh --offline-dir DIR  # 指定离线包目录
#

set -e

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${CYAN}ℹ️   $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_step() {
    echo -e "\n${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}📋 $1${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

# 默认参数
ACTION="full"
OFFLINE_DIR=""
FORCE=false
SKIP_CHECK=false
SKIP_INSTALL=false
NO_START=false
DEMO_MODE=""

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --check)
            ACTION="check"
            shift
            ;;
        --install)
            ACTION="install"
            shift
            ;;
        --start)
            ACTION="start"
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --skip-check)
            SKIP_CHECK=true
            shift
            ;;
        --skip-install)
            SKIP_INSTALL=true
            shift
            ;;
        --no-start)
            NO_START=true
            shift
            ;;
        --offline-dir)
            OFFLINE_DIR="$2"
            shift 2
            ;;
        --demo-mode)
            DEMO_MODE="$2"
            shift 2
            ;;
        --help)
            head -25 "$0" | grep "^#" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# 记录开始时间
START_TIME=$(date +%s)

# ==================== 环境检测 ====================

check_python_version() {
    log_step "步骤1/5: 检查Python版本"
    
    if ! command -v python3 &> /dev/null; then
        log_error "未找到python3命令"
        log_info "请安装Python 3.8+: sudo apt-get install python3 python3-pip"
        return 1
    fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
        log_success "Python版本: $PYTHON_VERSION (满足要求 >= 3.8)"
        return 0
    else
        log_error "Python版本过低: $PYTHON_VERSION (需要 >= 3.8)"
        log_info "请升级Python版本"
        return 1
    fi
}

check_system_dependencies() {
    log_step "步骤2/5: 检查系统依赖"
    
    local missing=()
    
    # 检查必需命令
    local commands=("python3" "pip3" "rsync" "ssh" "git")
    local descriptions=("Python解释器" "Python包管理器" "文件同步工具" "SSH客户端" "Git版本控制")
    
    for i in "${!commands[@]}"; do
        cmd="${commands[$i]}"
        desc="${descriptions[$i]}"
        
        if command -v "$cmd" &> /dev/null; then
            log_success "$desc: 已安装"
        else
            log_warn "$desc: 未安装 ($cmd)"
            log_info "请安装: sudo apt-get install $cmd"
            missing+=("$cmd")
        fi
    done
    
    if [ ${#missing[@]} -eq 0 ]; then
        return 0
    else
        log_warn "缺少 ${#missing[@]} 个系统依赖"
        return 1
    fi
}

check_gpu_environment() {
    log_step "步骤3/5: 检查GPU环境"
    
    if command -v nvidia-smi &> /dev/null; then
        GPU_MODEL=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
        log_success "GPU型号: $GPU_MODEL"
        
        # 检查CUDA
        if [ -f "/usr/local/cuda/bin/nvcc" ]; then
            CUDA_VERSION=$(nvcc --version 2>/dev/null | grep "release" | sed 's/.*release //;s/,.*//')
            log_success "CUDA版本: $CUDA_VERSION"
        fi
    else
        log_warn "未检测到NVIDIA GPU"
        log_info "系统将使用模拟模式运行"
    fi
}

check_project_structure() {
    log_step "检查项目结构"
    
    local required_dirs=("src" "scripts" "docs" "config" "monitor_platform")
    local required_files=("requirements.txt" "README.md")
    
    for d in "${required_dirs[@]}"; do
        if [ -d "$PROJECT_ROOT/$d" ]; then
            log_success "目录: $d/"
        else
            log_warn "目录缺失: $d/"
        fi
    done
    
    for f in "${required_files[@]}"; do
        if [ -f "$PROJECT_ROOT/$f" ]; then
            log_success "文件: $f"
        else
            log_error "文件缺失: $f"
        fi
    done
}

check_config_file() {
    log_step "检查配置文件"
    
    local config_path="$PROJECT_ROOT/config/inspection_config.yaml"
    
    if [ -f "$config_path" ]; then
        log_success "配置文件存在: $(basename $config_path)"
        
        # 检查必要字段
        if grep -q "udp:" "$config_path" && grep -q "websocket:" "$config_path" && \
           grep -q "ptz:" "$config_path" && grep -q "temperature:" "$config_path"; then
            log_success "配置文件结构完整"
        else
            log_warn "配置文件可能缺少必要字段"
        fi
    else
        log_error "配置文件缺失: $config_path"
        return 1
    fi
}

# ==================== 依赖安装 ====================

check_offline_packages() {
    if [ -z "$OFFLINE_DIR" ]; then
        log_info "未指定离线包目录"
        return 1
    fi
    
    local offline_path="$PROJECT_ROOT/$OFFLINE_DIR"
    if [ ! -d "$offline_path" ]; then
        log_warn "离线包目录不存在: $offline_path"
        return 1
    fi
    
    # 查找wheel包
    local whl_count=$(find "$offline_path" -name "*.whl" | wc -l)
    if [ "$whl_count" -gt 0 ]; then
        log_success "找到 $whl_count 个离线安装包"
        return 0
    else
        log_warn "离线目录中未找到wheel包"
        return 1
    fi
}

create_virtual_environment() {
    log_step "创建虚拟环境"
    
    local venv_path="$PROJECT_ROOT/venv"
    if [ -f "$venv_path/bin/python" ]; then
        log_success "虚拟环境已存在: $venv_path"
        return 0
    fi
    
    log_info "创建虚拟环境..."
    python3 -m venv "$venv_path"
    
    if [ -f "$venv_path/bin/python" ]; then
        log_success "虚拟环境创建成功"
        return 0
    else
        log_error "虚拟环境创建失败"
        return 1
    fi
}

install_dependencies() {
    log_step "安装Python依赖"
    
    local venv_path="$PROJECT_ROOT/venv"
    local pip_path="$venv_path/bin/pip"
    
    # 检查是否需要安装
    local missing_packages=()
    local required_packages=("loguru" "numpy" "cv2" "websockets" "requests" "yaml" "fastapi" "uvicorn" "pydantic")
    
    for pkg in "${required_packages[@]}"; do
        if ! $venv_path/bin/python -c "import $pkg" 2>/dev/null; then
            missing_packages+=("$pkg")
        fi
    done
    
    if [ ${#missing_packages[@]} -eq 0 ]; then
        log_success "所有依赖已安装"
        return 0
    fi
    
    log_info "需要安装 ${#missing_packages[@]} 个包: ${missing_packages[*]}"
    
    # 检查离线包
    local install_success=false
    
    if check_offline_packages; then
        log_info "使用离线包安装..."
        local offline_path="$PROJECT_ROOT/$OFFLINE_DIR"
        
        # 使用--no-index和--find-links安装
        if $pip_path install --no-index --find-links="$offline_path" -r "$PROJECT_ROOT/requirements.txt" -q; then
            install_success=true
        fi
    fi
    
    # 如果离线安装失败，尝试网络安装
    if [ "$install_success" = false ] && [ -z "$OFFLINE_DIR" ]; then
        log_warn "尝试从网络安装..."
        if $pip_path install -r "$PROJECT_ROOT/requirements.txt" -q; then
            install_success=true
        fi
    fi
    
    if [ "$install_success" = true ]; then
        log_success "依赖安装成功"
    else
        log_error "依赖安装失败"
        log_info "请手动安装: pip install -r requirements.txt"
        return 1
    fi
}

# ==================== 目录创建 ====================

create_directories() {
    log_step "创建必要目录"
    
    local dirs=("data/logs" "data/cache" "models" "config")
    
    for d in "${dirs[@]}"; do
        mkdir -p "$PROJECT_ROOT/$d"
        log_success "目录: $d/"
    done
}

# ==================== 服务启动 ====================

start_monitor_platform() {
    log_step "启动监测平台"
    
    local monitor_script="$PROJECT_ROOT/scripts/start_monitor.py"
    if [ ! -f "$monitor_script" ]; then
        log_error "启动脚本不存在: $monitor_script"
        return 1
    fi
    
    local venv_python="$PROJECT_ROOT/venv/bin/python"
    if [ ! -f "$venv_python" ]; then
        venv_python="python3"
    fi
    
    log_info "启动监测平台服务 (http://192.168.1.103:8000)..."
    
    # 后台启动
    nohup $venv_python "$monitor_script" > "$PROJECT_ROOT/data/logs/monitor.log" 2>&1 &
    local pid=$!
    
    # 等待服务启动
    sleep 2
    
    # 验证服务
    if curl -s http://192.168.1.103:8000/api/status > /dev/null 2>&1; then
        log_success "监测平台启动成功 (PID: $pid)"
        echo "  访问地址: http://192.168.1.103:8000"
        echo "  查看日志: tail -f $PROJECT_ROOT/data/logs/monitor.log"
        return 0
    else
        log_warn "服务可能正在启动，请稍后检查"
        log_info "日志文件: $PROJECT_ROOT/data/logs/monitor.log"
        return 0
    fi
}

run_demo() {
    if [ -z "$DEMO_MODE" ]; then
        return 0
    fi
    
    log_step "运行演示程序"
    
    local demo_script="$PROJECT_ROOT/scripts/demo_12min.py"
    if [ ! -f "$demo_script" ]; then
        log_error "演示脚本不存在: $demo_script"
        return 1
    fi
    
    local venv_python="$PROJECT_ROOT/venv/bin/python"
    if [ ! -f "$venv_python" ]; then
        venv_python="python3"
    fi
    
    log_info "启动演示程序 (模式: $DEMO_MODE)..."
    $venv_python "$demo_script" --mode "$DEMO_MODE"
    
    if [ $? -eq 0 ]; then
        log_success "演示程序执行完成"
    else
        log_error "演示程序执行失败"
        return 1
    fi
}

# ==================== 主流程 ====================

main() {
    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}绝影Lite3 一键部署工具${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}部署时间: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${CYAN}项目路径: $PROJECT_ROOT${NC}"
    echo ""
    
    case $ACTION in
        "check")
            check_python_version
            check_system_dependencies
            check_gpu_environment
            check_project_structure
            check_config_file
            ;;
        "install")
            create_virtual_environment
            install_dependencies
            create_directories
            ;;
        "start")
            start_monitor_platform
            run_demo
            ;;
        "full")
            # 步骤1: 环境检测
            if [ "$SKIP_CHECK" = false ]; then
                check_python_version || {
                    if [ "$FORCE" = true ]; then
                        log_warn "环境检测失败，强制继续..."
                    else
                        log_error "环境检测未通过，请先解决上述问题"
                        log_info "使用 --force 参数可强制继续部署"
                        exit 1
                    fi
                }
                
                check_system_dependencies || log_warn "部分系统依赖缺失，可能影响功能"
                check_gpu_environment
                check_project_structure
                check_config_file || {
                    log_error "配置文件检查失败"
                    exit 1
                }
            fi
            
            # 步骤2: 创建目录
            if [ "$SKIP_INSTALL" = false ]; then
                create_directories
            fi
            
            # 步骤3: 安装依赖
            if [ "$SKIP_INSTALL" = false ]; then
                create_virtual_environment
                install_dependencies || {
                    if [ "$FORCE" = true ]; then
                        log_warn "依赖安装失败，强制继续..."
                    else
                        log_error "依赖安装失败，请检查网络或离线包"
                        exit 1
                    fi
                }
            fi
            
            # 步骤4: 验证安装
            if [ "$SKIP_CHECK" = false ]; then
                log_step "验证安装"
                local venv_python="$PROJECT_ROOT/venv/bin/python"
                if [ -f "$venv_python" ]; then
                    if $venv_python -c "import loguru, numpy, cv2, websockets, requests, yaml, fastapi, uvicorn, pydantic" 2>/dev/null; then
                        log_success "所有核心依赖验证通过"
                    else
                        log_error "依赖验证失败"
                        exit 1
                    fi
                fi
            fi
            
            # 步骤5: 启动服务
            if [ "$NO_START" = false ]; then
                start_monitor_platform
                run_demo
            fi
            
            # 计算耗时
            END_TIME=$(date +%s)
            ELAPSED=$((END_TIME - START_TIME))
            
            # 完成
            echo ""
            echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${GREEN}✅ 部署完成${NC}"
            echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo ""
            echo -e "${CYAN}访问地址: http://192.168.1.103:8000${NC}"
            echo -e "${CYAN}查看日志: tail -f $PROJECT_ROOT/data/logs/monitor.log${NC}"
            echo -e "${CYAN}停止服务: pkill -f start_monitor.py${NC}"
            echo ""
            echo -e "部署耗时: ${ELAPSED} 秒"
            echo ""
            ;;
    esac
}

# 执行主函数
main
