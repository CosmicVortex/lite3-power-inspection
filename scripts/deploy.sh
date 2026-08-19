#!/bin/bash
# 绝影Lite3电力巡检系统部署脚本

set -e

REMOTE_HOST="admin@192.168.1.120"
PROJECT_DIR="/home/admin/lite3-power-inspection"
PYTHON_VENV="$PROJECT_DIR/venv"

echo "=========================================="
echo "绝影Lite3电力巡检系统部署"
echo "=========================================="

# 1. 检查网络连接
echo "[1/6] 检查网络连接..."
ping -c 2 $REMOTE_HOST > /dev/null 2>&1 || {
    echo "❌ 无法连接到 $REMOTE_HOST"
    echo "请确认："
    echo "  1. 机器狗主机已开机"
    echo "  2. WiFi网络连接正常"
    echo "  3. IP地址192.168.1.120正确"
    exit 1
}
echo "✅ 网络连接正常"

# 2. 创建项目目录
echo "[2/6] 创建项目目录..."
ssh $REMOTE_HOST "mkdir -p $PROJECT_DIR"

# 3. 同步代码文件
echo "[3/6] 同步代码文件..."
rsync -avz --progress \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='data/' \
    --exclude='*.db' \
    ./ $REMOTE_HOST:$PROJECT_DIR/
echo "✅ 代码同步完成"

# 4. 安装Python依赖
echo "[4/6] 安装Python依赖..."
ssh $REMOTE_HOST "cd $PROJECT_DIR && python3 -m venv $PYTHON_VENV && \
    source $PYTHON_VENV/bin/activate && \
    pip install -r requirements.txt --quiet"
echo "✅ 依赖安装完成"

# 5. 创建数据目录
echo "[5/6] 创建数据目录..."
ssh $REMOTE_HOST "mkdir -p $PROJECT_DIR/{data,logs,models,config}"
echo "✅ 数据目录创建完成"

# 6. 验证部署
echo "[6/6] 验证部署..."
ssh $REMOTE_HOST "cd $PROJECT_DIR && source $PYTHON_VENV/bin/activate && \
    python3 -c 'from src.perception.temperature_monitor import TemperatureMonitor; m = TemperatureMonitor(); print(\"✅ 温度监测模块加载成功\")'"
ssh $REMOTE_HOST "cd $PROJECT_DIR && source $PYTHON_VENV/bin/activate && \
    python3 -c 'from src.gateway.udp_controller import UDPMotionController; print(\"✅ UDP控制器加载成功\")'"
ssh $REMOTE_HOST "cd $PROJECT_DIR && source $PYTHON_VENV/bin/activate && \
    python3 -c 'from src.gateway.ptz_controller import PtzController; print(\"✅ 云台控制器加载成功\")'"
ssh $REMOTE_HOST "cd $PROJECT_DIR && source $PYTHON_VENV/bin/activate && \
    python3 -c 'from src.storage.sqlite_cache import SQLiteCache; c = SQLiteCache(); print(\"✅ SQLite缓存加载成功\")'"

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "SSH登录: ssh $REMOTE_HOST"
echo "项目目录: $PROJECT_DIR"
echo "Python环境: $PYTHON_VENV/bin/python3"
echo ""
echo "启动监测平台:"
echo "  cd $PROJECT_DIR && source $PYTHON_VENV/bin/activate && python3 src/app/monitor_platform.py"
echo ""
echo "访问地址: http://192.168.1.120:5000"
echo ""
echo "运行测试:"
echo "  cd $PROJECT_DIR && source $PYTHON_VENV/bin/activate && python3 scripts/test_all.py"
