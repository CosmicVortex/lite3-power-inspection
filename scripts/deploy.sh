#!/bin/bash
# 绝影Lite3 一键部署脚本（精简版）
# 用法: ./deploy.sh [simulation|real|hybrid]

set -e

MODE="${1:-simulation}"
PROJECT_DIR="/home/ysc/lite3-power-inspection"
VENV="$PROJECT_DIR/venv/bin/activate"

echo "=========================================="
echo "绝影Lite3 电力巡检系统 - 一键部署"
echo "=========================================="
echo ""

# 检查是否在正确目录
if [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "❌ 错误: 项目目录不存在"
    echo "   路径: $PROJECT_DIR"
    echo ""
    echo "请先解压部署包:"
    echo "  cd ~"
    echo "  unzip -q /mnt/usb/lite3-power-inspection.zip"
    exit 1
fi

cd "$PROJECT_DIR"

# 创建虚拟环境
if [ ! -f "$VENV" ]; then
    echo "[1/4] 创建Python虚拟环境..."
    python3 -m venv venv
    echo "   ✓ 虚拟环境已创建"
fi

# 激活环境并安装依赖
echo "[2/4] 安装Python依赖..."
source "$VENV"
pip install -q -r requirements.txt
echo "   ✓ 依赖安装完成"

# 创建必要目录
echo "[3/4] 创建数据目录..."
mkdir -p data/logs data/cache models
echo "   ✓ 目录创建完成"

# 验证核心模块
echo "[4/4] 验证核心模块..."
python3 -c "from src.perception.temperature_monitor import TemperatureMonitor; m = TemperatureMonitor(); print('   ✓ 温度监测模块OK')" 2>/dev/null || echo "   ⚠ 温度监测模块加载失败"
python3 -c "from src.gateway.udp_controller import UDPMotionController; print('   ✓ UDP控制器OK')" 2>/dev/null || echo "   ⚠ UDP控制器加载失败"
python3 -c "from src.gateway.ptz_controller import PtzController; print('   ✓ 云台控制器OK')" 2>/dev/null || echo "   ⚠ 云台控制器加载失败"
python3 -c "from src.storage.sqlite_cache import SQLiteCache; c = SQLiteCache(); print('   ✓ SQLite缓存OK')" 2>/dev/null || echo "   ⚠ SQLite缓存加载失败"

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "启动命令:"
echo "  # 启动监测平台（后台）"
echo "  source venv/bin/activate && nohup python3 scripts/start_monitor.py > data/logs/monitor.log 2>&1 &"
echo ""
echo "  # 运行演示"
echo "  source venv/bin/activate && python3 scripts/demo_12min.py --mode $MODE"
echo ""
echo "  # 访问监测平台"
echo "  http://192.168.1.103:8000"
echo ""
