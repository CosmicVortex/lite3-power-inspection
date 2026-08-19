#!/usr/bin/env python3
"""
监测平台启动脚本
"""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor_platform.server import main

if __name__ == "__main__":
    print("=" * 50)
    print("绝影Lite3监测平台")
    print("=" * 50)
    print(f"Web界面: http://0.0.0.0:8000")
    print(f"WebSocket: ws://0.0.0.0:8765/ws")
    print("=" * 50)
    
    asyncio.run(main())
