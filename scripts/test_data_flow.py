#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据流测试脚本
验证感知主机到监测平台的数据推送功能
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_websocket_server():
    """测试WebSocket服务器"""
    import websockets
    
    # 连接监测平台WebSocket
    uri = "ws://localhost:8765/ws"
    print(f"连接到 {uri}...")
    
    try:
        async with websockets.connect(uri, ping_interval=None) as ws:
            print("✓ WebSocket连接成功")
            
            # 接收初始状态
            msg = await asyncio.wait_for(ws.recv(), timeout=2)
            data = json.loads(msg)
            print(f"✓ 收到初始状态: {data['type']}")
            
            # 发送模拟巡检数据
            test_data = {
                "msgId": "test-001",
                "ts": 1234567890,
                "deviceId": "LITE3-001",
                "type": "inspection_result",
                "payload": {
                    "waypoint_id": "WP001",
                    "defect_type": "crack",
                    "confidence": 0.92,
                    "measurements": {"width_mm": 0.15, "length_mm": 23.4}
                }
            }
            await ws.send(json.dumps(test_data))
            print("✓ 发送巡检数据")
            
            # 等待服务器响应
            msg = await asyncio.wait_for(ws.recv(), timeout=2)
            response = json.loads(msg)
            print(f"✓ 收到响应: {response['type']}")
            
            # 发送告警数据
            alert_data = {
                "msgId": "test-002",
                "ts": 1234567891,
                "deviceId": "LITE3-001",
                "type": "temperature_alert",
                "payload": {
                    "waypoint_id": "WP002",
                    "level": "warning",
                    "value": 48.5
                }
            }
            await ws.send(json.dumps(alert_data))
            print("✓ 发送温度告警")
            
            msg = await asyncio.wait_for(ws.recv(), timeout=2)
            response = json.loads(msg)
            print(f"✓ 收到告警响应: {response['type']}")
            
            print("\n✅ 数据流测试通过")
            return True
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    # 检查服务器是否运行
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:8000/api/status", timeout=1)
        print("监测平台正在运行")
    except:
        print("警告: 监测平台未运行，先启动服务器...")
        import subprocess
        subprocess.Popen([sys.executable, "monitor_platform/server.py"], 
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        asyncio.sleep(2)
    
    success = asyncio.run(test_websocket_server())
    sys.exit(0 if success else 1)
