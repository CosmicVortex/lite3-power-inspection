#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监测平台启动脚本 - 增强版

支持独立运行，无需机器人端
"""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor_platform.server import main

if __name__ == "__main__":
    print("=" * 60)
    print("绝影Lite3监测平台")
    print("=" * 60)
    print(f"\nWeb界面: http://0.0.0.0:8000")
    print(f"WebSocket: ws://0.0.0.0:8765/ws")
    print(f"\n按 Ctrl+C 停止服务\n")
    print("=" * 60)
    
    asyncio.run(main())
