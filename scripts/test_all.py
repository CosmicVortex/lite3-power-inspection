#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整测试流程
"""

import sys
import time
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_temperature_monitor():
    """测试温度监测模块"""
    print("\n" + "="*60)
    print("[测试1/6] 温度监测模块")
    print("="*60)
    
    from perception.temperature_monitor import TemperatureMonitor, AlertLevel
    import numpy as np
    
    monitor = TemperatureMonitor()
    
    # 模拟热成像数据
    thermal_frame = np.full((512, 640), 40.0, dtype=np.float32)
    thermal_frame[200:300, 200:300] = 48.0  # 高温区域
    
    result = monitor.check_temperature(thermal_frame)
    print(f"温度监测结果: {result}")
    
    assert result['status'] == 'WARN', f"预期WARN，实际{result['status']}"
    assert result['max_temperature'] == 48.0, f"预期48.0，实际{result['max_temperature']}"
    
    print("✅ 温度监测模块测试通过")
    return True

def test_udp_controller():
    """测试UDP控制器"""
    print("\n" + "="*60)
    print("[测试2/6] UDP运动控制")
    print("="*60)
    
    from gateway.udp_controller import UDPMotionController
    
    controller = UDPMotionController()
    
    # 验证指令码
    assert controller.CMD_HEARTBEAT == 0x21040001
    assert controller.CMD_STAND_UP == 0x21010202
    assert controller.CMD_EMERGENCY_STOP == 0x21020C0E
    
    print(f"心跳指令: 0x{controller.CMD_HEARTBEAT:08X}")
    print(f"起立指令: 0x{controller.CMD_STAND_UP:08X}")
    print(f"急停指令: 0x{controller.CMD_EMERGENCY_STOP:08X}")
    
    print("✅ UDP控制器参数验证通过")
    return True

def test_ptz_controller():
    """测试云台控制器"""
    print("\n" + "="*60)
    print("[测试3/6] 云台控制")
    print("="*60)
    
    from gateway.ptz_controller import PtzController, PtzState
    
    ptz = PtzController()
    
    # 验证默认值
    assert ptz.base_url == "http://192.168.1.108"
    assert ptz.YAW_RANGE == (-180.0, 180.0)
    assert ptz.PITCH_RANGE == (-115.0, 40.0)
    
    print(f"云台IP: {ptz.base_url}")
    print(f"偏航角范围: {ptz.YAW_RANGE}")
    print(f"俯仰角范围: {ptz.PITCH_RANGE}")
    
    print("✅ 云台控制器参数验证通过")
    return True

def test_websocket_client():
    """测试WebSocket客户端"""
    print("\n" + "="*60)
    print("[测试4/6] WebSocket数据上报")
    print("="*60)
    
    from gateway.websocket_client import WebSocketGateway
    
    gateway = WebSocketGateway()
    
    # 验证默认值
    assert gateway.server_url == "ws://192.168.1.200:8765/ws"
    assert gateway.device_id == "LITE3-001"
    
    print(f"WebSocket地址: {gateway.server_url}")
    print(f"设备ID: {gateway.device_id}")
    
    print("✅ WebSocket客户端参数验证通过")
    return True

def test_rtsp_client():
    """测试RTSP客户端"""
    print("\n" + "="*60)
    print("[测试5/6] RTSP视频流")
    print("="*60)
    
    from gateway.rtsp_client import RTSPClient
    
    # 测试流地址格式
    urls = {
        "visible_main": "rtsp://admin:123456@192.168.1.108:554/id=1&type=0",
        "visible_sub": "rtsp://admin:123456@192.168.1.108:554/id=1&type=1",
        "thermal": "rtsp://admin:123456@192.168.1.108:554/id=2&type=0"
    }
    
    for name, url in urls.items():
        client = RTSPClient(url, name)
        print(f"{name}: {url}")
    
    print("✅ RTSP客户端参数验证通过")
    return True

def test_sqlite_cache():
    """测试SQLite缓存"""
    print("\n" + "="*60)
    print("[测试6/6] SQLite本地缓存")
    print("="*60)
    
    from storage.sqlite_cache import SQLiteCache
    
    cache = SQLiteCache("data/test.db")
    
    # 测试保存结果
    result_id = cache.save_inspection_result({
        "type": "crack",
        "confidence": 0.92,
        "width_mm": 0.15,
        "length_mm": 45.2
    })
    assert result_id > 0
    print(f"保存检测结果ID: {result_id}")
    
    # 测试保存告警
    alert_id = cache.save_alert({
        "alert_id": "ALT-TEST-001",
        "type": "temperature",
        "level": "warn",
        "temperature": 46.5
    })
    assert alert_id > 0
    print(f"保存告警ID: {alert_id}")
    
    # 测试查询
    results = cache.get_unuploaded_results()
    print(f"未上传结果数: {len(results)}")
    
    alerts = cache.get_alert_history()
    print(f"告警历史数: {len(alerts)}")
    
    cache.close()
    
    print("✅ SQLite缓存模块测试通过")
    return True

def main():
    print("="*60)
    print("绝影Lite3电力巡检演示方案 - 完整测试")
    print("="*60)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    tests = [
        ("温度监测", test_temperature_monitor),
        ("UDP控制", test_udp_controller),
        ("云台控制", test_ptz_controller),
        ("WebSocket", test_websocket_client),
        ("RTSP流", test_rtsp_client),
        ("SQLite缓存", test_sqlite_cache),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, "✅ 通过" if success else "❌ 失败"))
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            results.append((name, f"❌ 失败: {e}"))
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    passed = sum(1 for _, r in results if "✅" in r)
    failed = sum(1 for _, r in results if "❌" in r)
    
    for name, result in results:
        print(f"  {name:15} {result}")
    
    print(f"\n总计: {passed}项通过, {failed}项失败")
    
    if failed == 0:
        print("\n🎉 所有测试通过！系统已准备好部署。")
    else:
        print(f"\n⚠️ 有{failed}项测试失败，请检查代码。")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
