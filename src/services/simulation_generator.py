#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟数据生成器

用于在无模型时生成符合规范的测试数据，支持多种模式：
1. 随机模式：生成随机但符合规范的测试数据
2. 脚本模式：按预设脚本执行演示流程
3. 真实模式：使用真实模型推理（当模型可用时）
"""

import random
import time
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger


class SimulationDataGenerator:
    """模拟数据生成器"""
    
    def __init__(self, mode: str = "random"):
        """
        Args:
            mode: 生成模式 ('random', 'scripted', 'real')
        """
        self.mode = mode
        self._step = 0
        
        # 预设脚本数据
        self.scripted_data = {
            "crack_detection": [
                {"waypoint": "WP001", "confidence": 0.92, "width_mm": 0.12, "length_mm": 23.4},
                {"waypoint": "WP002", "confidence": 0.87, "width_mm": 0.15, "length_mm": 45.2},
                {"waypoint": "WP003", "confidence": 0.95, "width_mm": 0.18, "length_mm": 67.8},
            ],
            "temperature": [
                {"waypoint": "WP004", "base_temp": 40.0, "target_temp": 52.0, "rate": 3.2},
                {"waypoint": "WP005", "base_temp": 38.0, "target_temp": 48.0, "rate": 2.5},
            ]
        }
        
        logger.info(f"初始化模拟数据生成器: mode={mode}")
    
    def generate_crack_detection(self, waypoint_id: str = "WP001") -> Dict:
        """生成裂缝检测数据
        
        Args:
            waypoint_id: 航点ID
            
        Returns:
            检测结果字典
        """
        if self.mode == "scripted":
            data = self._get_scripted_crack(waypoint_id)
        else:
            data = self._generate_random_crack()
        
        return {
            "msgId": str(int(time.time() * 1000)),
            "ts": int(time.time() * 1000),
            "deviceId": "LITE3-001",
            "type": "inspection_result",
            "payload": {
                "defect_type": "crack",
                "subtype": random.choice(["longitudinal", "transverse", "network"]),
                "location": {
                    "image_x": random.randint(100, 500),
                    "image_y": random.randint(100, 400),
                    "world_x": round(random.uniform(0.5, 1.5), 2),
                    "world_y": round(random.uniform(0.5, 1.5), 2),
                },
                "measurements": {
                    "width_mm": data["width_mm"],
                    "length_mm": data["length_mm"],
                    "pixel_precision": 0.019,
                    "zoom_level": 10
                },
                "confidence": data["confidence"],
                "snapshot_url": f"http://192.168.1.103:8080/snap/CRACK-{waypoint_id}-{int(time.time())}",
                "waypoint_id": waypoint_id,
                "ptz_state": {
                    "yaw": 45.0,
                    "pitch": -30.0,
                    "zoom": 10
                }
            }
        }
    
    def generate_temperature_alert(self, waypoint_id: str = "WP004") -> Dict:
        """生成温度告警数据
        
        Args:
            waypoint_id: 航点ID
            
        Returns:
            告警数据字典
        """
        if self.mode == "scripted":
            base_temp = self._get_scripted_temp(waypoint_id)
        else:
            base_temp = random.uniform(38, 44)
        
        # 模拟温度变化
        current_temp = base_temp + random.uniform(0, 3)
        
        if current_temp >= 50:
            level = "CRITICAL"
        elif current_temp >= 45:
            level = "WARN"
        else:
            level = "NORMAL"
        
        return {
            "msgId": str(int(time.time() * 1000)),
            "ts": int(time.time() * 1000),
            "deviceId": "LITE3-001",
            "type": "temperature_alert",
            "payload": {
                "alert_level": level,
                "alert_id": f"ALT-{datetime.now().strftime('%Y%m%d')}-{random.randint(1, 999):03d}",
                "temperature": {
                    "max_c": round(current_temp, 1),
                    "avg_c": round(current_temp - 2, 1),
                    "min_c": round(current_temp - 5, 1)
                },
                "roi": {
                    "image_x": random.randint(100, 300),
                    "image_y": random.randint(100, 300),
                    "width": 50,
                    "height": 50
                },
                "thresholds": {
                    "warn": 45.0,
                    "critical": 50.0
                },
                "hotspot_ratio": round(random.uniform(0.05, 0.15), 2),
                "temperature_rate": round(random.uniform(2.0, 4.0), 1),
                "thermal_snapshot_url": f"http://192.168.1.103:8080/thermal/TEMP-{waypoint_id}-{int(time.time())}",
                "ptz_state": {
                    "yaw": 135.0,
                    "pitch": -45.0,
                    "zoom": 5
                }
            }
        }
    
    def generate_heartbeat(self) -> Dict:
        """生成心跳数据
        
        Returns:
            心跳数据字典
        """
        return {
            "msgId": str(int(time.time() * 1000)),
            "ts": int(time.time() * 1000),
            "deviceId": "LITE3-001",
            "type": "heartbeat",
            "payload": {
                "battery": random.randint(80, 95),
                "cpu_temp": round(random.uniform(45, 55), 1),
                "gpu_load": random.randint(30, 60),
                "memory_usage": random.randint(50, 70),
                "fps": random.randint(12, 18),
                "network_latency": random.randint(2, 5)
            }
        }
    
    def _get_scripted_crack(self, waypoint_id: str) -> Dict:
        """获取预设裂缝数据"""
        for data in self.scripted_data["crack_detection"]:
            if data["waypoint"] == waypoint_id:
                return data
        # 默认返回第一个
        return self.scripted_data["crack_detection"][0]
    
    def _get_scripted_temp(self, waypoint_id: str) -> float:
        """获取预设温度数据"""
        for data in self.scripted_data["temperature"]:
            if data["waypoint"] == waypoint_id:
                return data["base_temp"]
        return 40.0
    
    def _generate_random_crack(self) -> Dict:
        """生成随机裂缝数据"""
        return {
            "confidence": round(random.uniform(0.7, 0.95), 2),
            "width_mm": round(random.uniform(0.1, 0.5), 2),
            "length_mm": round(random.uniform(10, 100), 1)
        }
    
    def reset(self):
        """重置状态"""
        self._step = 0
        logger.info("模拟数据生成器已重置")


# 全局单例
_generator = None


def get_generator(mode: str = "random") -> SimulationDataGenerator:
    """获取全局模拟数据生成器实例"""
    global _generator
    if _generator is None or _generator.mode != mode:
        _generator = SimulationDataGenerator(mode=mode)
    return _generator


if __name__ == "__main__":
    # 测试代码
    gen = SimulationDataGenerator(mode="scripted")
    
    print("=== 裂缝检测数据 ===")
    crack_data = gen.generate_crack_detection("WP001")
    print(f"Type: {crack_data['type']}")
    print(f"Payload keys: {list(crack_data['payload'].keys())}")
    print(f"Weight: {crack_data['payload']['measurements']['width_mm']}mm")
    
    print("\n=== 温度告警数据 ===")
    temp_data = gen.generate_temperature_alert("WP004")
    print(f"Type: {temp_data['type']}")
    print(f"Level: {temp_data['payload']['alert_level']}")
    print(f"Max Temp: {temp_data['payload']['temperature']['max_c']}℃")
    
    print("\n=== 心跳数据 ===")
    hb_data = gen.generate_heartbeat()
    print(f"Type: {hb_data['type']}")
    print(f"Battery: {hb_data['payload']['battery']}%")
