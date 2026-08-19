#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速启动脚本

用法:
  ./scripts/quick_start.sh                # 启动演示
  ./scripts/quick_start.sh monitor        # 仅启动监测平台
  ./scripts/quick_start.sh both           # 启动全部（后台）
"""

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

case "${1:-demo}" in
    demo)
        echo "=========================================="
        echo "启动演示模式 (simulation)"
        echo "=========================================="
        python3 scripts/run_demo.py --mode simulation --log-level INFO
        ;;
    monitor)
        echo "=========================================="
        echo "启动监测平台"
        echo "=========================================="
        python3 scripts/start_monitor.py
        ;;
    both)
        echo "=========================================="
        echo "启动监测平台 (后台)"
        echo "=========================================="
        nohup python3 scripts/start_monitor.py > data/logs/monitor.log 2>&1 &
        MONITOR_PID=$!
        echo "监测平台PID: $MONITOR_PID"
        
        echo ""
        echo "=========================================="
        echo "启动演示模式"
        echo "=========================================="
        python3 scripts/run_demo.py --mode simulation --log-level INFO
        ;;
    *)
        echo "用法: $0 [demo|monitor|both]"
        echo ""
        echo "  demo     - 启动演示模式 (默认)"
        echo "  monitor  - 仅启动监测平台"
        echo "  both     - 同时启动监测平台和演示"
        exit 1
        ;;
esac
