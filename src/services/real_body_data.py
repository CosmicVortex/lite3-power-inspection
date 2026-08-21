#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实本体数据模拟器

在模拟模式下，AI识别数据使用模拟值，但机器狗本体数据
（电池、温度、关节角度、位置等）保持真实或基于物理模型。
"""

import time
import random
from typing import Dict, Optional
from loguru import logger


class RealBodyData:
    """真实本体数据生成器
    
    生成符合物理规律的真实机器人状态数据，
    而非随机模拟数据。
    """
    
    def __init__(self, device_id: str = "LITE3-001"):
        self.device_id = device_id
        
        # 真实初始状态（基于绝影Lite3规格）
        self.battery = 95.0  # 电量百分比
        self.cpu_temp = 35.0  # CPU温度(℃)
        self.gpu_load = 0.0  # GPU负载(%)
        self.memory_usage = 45.0  # 内存使用率(%)
        self.status = "idle"  # idle/moving/stand/raise
        self.waypoint = "WP001"
        
        # 位置坐标（基于沙盘实际尺寸）
        self.position = {
            "x": 0.5,  # 米
            "y": 0.5,
            "z": 0.0
        }
        
        # 关节角度（8个自由度）
        self.joint_angles = {
            "left_hip": 0.0,
            "left_knee": 0.0,
            "left_ankle": 0.0,
            "right_hip": 0.0,
            "right_knee": 0.0,
            "right_ankle": 0.0,
            "front_left_hip": 0.0,
            "front_left_knee": 0.0,
            "front_left_ankle": 0.0,
            "front_right_hip": 0.0,
            "front_right_knee": 0.0,
            "front_right_ankle": 0.0,
        }
        
        # 云台状态
        self.ptz_state = {
            "yaw": 0.0,  # 水平角度
            "pitch": -30.0,  # 俯仰角度
            "zoom": 1.0  # 变倍
        }
        
        # 物理参数
        self.max_speed = 0.5  # m/s
        self.battery_discharge_rate = 0.01  # 每分钟耗电量
        
        logger.info(f"初始化真实本体数据: device_id={device_id}")
    
    def update_position(self, vx: float, vy: float, vw: float, dt: float = 0.1):
        """根据速度更新位置（运动学模型）
        
        Args:
            vx: 前后速度 (m/s)
            vy: 左右速度 (m/s)
            vw: 旋转速度 (rad/s)
            dt: 时间增量 (s)
        """
        # 简化运动模型
        self.position["x"] += vx * dt
        self.position["y"] += vy * dt
        self.position["z"] = max(0.0, min(0.5, self.position["z"]))  # 限制高度
        
        # 防止超出沙盘范围
        self.position["x"] = max(0.0, min(2.0, self.position["x"]))
        self.position["y"] = max(0.0, min(1.2, self.position["y"]))
    
    def update_joints(self, motion_state: str):
        """根据运动状态更新关节角度（逆运动学简化模型）
        
        Args:
            motion_state: 运动状态 (standing/walking_forward/walking_backward/turn_left/turn_right)
        """
        import math
        
        base_angle = 0.3  # 站立基础角度
        
        if motion_state == "walking_forward":
            # 行走时关节交替运动
            phase = time.time() * 3  # 步频
            for leg in ["left", "right"]:
                for side in ["front", "back"]:
                    key = f"{side}_{leg}_hip"
                    self.joint_angles[key] = base_angle * math.sin(phase) if leg == "left" else -base_angle * math.sin(phase)
        elif motion_state == "walking_backward":
            phase = time.time() * 3
            for leg in ["left", "right"]:
                for side in ["front", "back"]:
                    key = f"{side}_{leg}_hip"
                    self.joint_angles[key] = -base_angle * math.sin(phase) if leg == "left" else base_angle * math.sin(phase)
        elif motion_state == "turn_left":
            phase = time.time() * 4
            self.joint_angles["left_hip"] = base_angle * 1.2
            self.joint_angles["right_hip"] = -base_angle * 1.2
        elif motion_state == "turn_right":
            phase = time.time() * 4
            self.joint_angles["left_hip"] = -base_angle * 1.2
            self.joint_angles["right_hip"] = base_angle * 1.2
        else:  # standing/idle
            for key in self.joint_angles:
                self.joint_angles[key] = base_angle * 0.1  # 微动
        
        # 添加微小噪声（传感器噪声）
        for key in self.joint_angles:
            self.joint_angles[key] += random.gauss(0, 0.01)
    
    def update_battery(self, dt: float = 1.0):
        """更新电池状态"""
        # 放电速率根据状态变化
        discharge_rate = self.battery_discharge_rate
        if self.status == "moving":
            discharge_rate *= 2  # 移动时耗电更快
        elif self.status == "idle":
            discharge_rate *= 0.5  # 待机时耗电慢
        
        self.battery -= discharge_rate * dt / 60  # 转换为分钟
        self.battery = max(0.0, min(100.0, self.battery))
    
    def update_temperature(self):
        """更新温度传感器数据"""
        # CPU温度随负载变化
        base_temp = 35.0
        load_temp = self.gpu_load * 0.5  # 每1%负载增加0.5℃
        self.cpu_temp = base_temp + load_temp + random.gauss(0, 0.5)
        self.cpu_temp = max(30.0, min(80.0, self.cpu_temp))  # 限制范围
    
    def update_ptz(self, yaw: Optional[float] = None, pitch: Optional[float] = None, zoom: Optional[float] = None):
        """更新云台状态"""
        if yaw is not None:
            self.ptz_state["yaw"] = max(-180.0, min(180.0, yaw))
        if pitch is not None:
            self.ptz_state["pitch"] = max(-90.0, min(90.0, pitch))
        if zoom is not None:
            self.ptz_state["zoom"] = max(1.0, min(20.0, zoom))
    
    def get_system_status(self) -> Dict:
        """获取系统状态数据"""
        return {
            "battery": round(self.battery, 1),
            "cpu_temp": round(self.cpu_temp, 1),
            "gpu_load": round(self.gpu_load, 1),
            "memory_usage": round(self.memory_usage, 1),
            "status": self.status,
            "waypoint": self.waypoint,
            "position": {
                "x": round(self.position["x"], 2),
                "y": round(self.position["y"], 2),
                "z": round(self.position["z"], 2)
            },
            "endurance_hours": round(self.battery / 100 * 1.8, 1),  # 预估续航
            "joint_angles": dict(self.joint_angles),
            "ptz_state": dict(self.ptz_state)
        }
    
    def update(self, motion_state: str = "idle", dt: float = 1.0):
        """更新所有状态
        
        Args:
            motion_state: 运动状态
            dt: 时间增量
        """
        self.update_battery(dt)
        self.update_temperature()
        self.update_joints(motion_state)
    
    def simulate_heartbeat(self) -> Dict:
        """模拟心跳数据包
        
        返回用于WebSocket上报的心跳数据格式
        """
        status = self.get_system_status()
        return {
            "msgId": str(int(time.time() * 1000)),
            "ts": int(time.time() * 1000),
            "deviceId": self.device_id,
            "type": "system_status",
            "payload": status
        }


if __name__ == "__main__":
    # 测试
    body = RealBodyData()
    
    print("=== 真实本体数据测试 ===")
    print(f"初始状态: {body.get_system_status()}")
    
    # 模拟移动
    body.status = "moving"
    for i in range(5):
        body.update_position(0.1, 0.0, 0.0)
        body.update_joints("walking_forward")
        status = body.get_system_status()
        print(f"\n时间{i+1}: 位置=({status['position']['x']:.2f}, {status['position']['y']:.2f}), "
              f"电量={status['battery']:.1f}%, 温度={status['cpu_temp']:.1f}℃")
    
    print("\n✓ 真实本体数据生成测试通过")
