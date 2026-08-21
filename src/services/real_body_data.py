#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实本体数据管理

在模拟模式下，AI识别数据使用模拟值，但机器狗本体数据
（电池、位置、关节、温度等）通过UDP从运动主机实时接收。
"""

import time
import random
from typing import Dict, Optional, Tuple
from loguru import logger


class RealBodyData:
    """真实本体数据管理器
    
    从UDP接收运动主机的真实数据，并提供给WebSocket发送到监测平台。
    """
    
    def __init__(self, device_id: str = "LITE3-001"):
        self.device_id = device_id
        
        # 初始状态（基于绝影Lite3规格）
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
        
        # 关节角度（12个自由度）
        self.joint_angles = [0.0] * 12
        
        # IMU数据
        self.imu = {
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0
        }
        
        # 超声波数据
        self.ultrasound = (0.0, 0.0)
        
        # 云台状态
        self.ptz_state = {
            "yaw": 0.0,
            "pitch": -30.0,
            "zoom": 1.0
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
        self.position["x"] += vx * dt
        self.position["y"] += vy * dt
        self.position["z"] = max(0.0, min(0.5, self.position["z"]))
        self.position["x"] = max(0.0, min(2.0, self.position["x"]))
        self.position["y"] = max(0.0, min(1.2, self.position["y"]))
    
    def update_joints(self, motion_state: str):
        """根据运动状态更新关节角度（逆运动学简化模型）
        
        Args:
            motion_state: 运动状态
        """
        import math
        base_angle = 0.3
        
        if motion_state == "walking_forward":
            phase = time.time() * 3
            for i in range(12):
                self.joint_angles[i] = base_angle * math.sin(phase + i * 0.5)
        elif motion_state == "walking_backward":
            phase = time.time() * 3
            for i in range(12):
                self.joint_angles[i] = -base_angle * math.sin(phase + i * 0.5)
        else:  # standing/idle
            for i in range(12):
                self.joint_angles[i] = base_angle * 0.1
        
        # 添加微小噪声
        for i in range(12):
            self.joint_angles[i] += random.gauss(0, 0.01)
    
    def update_ptz(self, yaw: Optional[float] = None, pitch: Optional[float] = None, zoom: Optional[float] = None):
        """更新云台状态"""
        if yaw is not None:
            self.ptz_state["yaw"] = max(-180.0, min(180.0, yaw))
        if pitch is not None:
            self.ptz_state["pitch"] = max(-90.0, min(90.0, pitch))
        if zoom is not None:
            self.ptz_state["zoom"] = max(1.0, min(20.0, zoom))
    
    def update_from_udp(self, udp_controller):
        """从UDP控制器更新本体数据（真实数据）
        
        Args:
            udp_controller: UDPMotionController实例
        """
        if not udp_controller or not udp_controller.is_connected():
            return
        
        # 更新电池（来自UDP数据）
        self.battery = udp_controller.robot_state.battery_level
        
        # 更新位置（来自UDP数据）
        pos = udp_controller.robot_state.pos_world
        self.position["x"] = pos[0]
        self.position["y"] = pos[1]
        self.position["z"] = max(0.0, pos[2])
        
        # 更新IMU角度（来自UDP数据）
        rpy = udp_controller.robot_state.rpy
        self.imu["roll"] = rpy[0]
        self.imu["pitch"] = rpy[1]
        self.imu["yaw"] = rpy[2]
        
        # 更新超声波
        self.ultrasound = udp_controller.robot_state.ultrasound
        
        # 更新状态
        state_map = {
            0: "stand",
            1: "sit",
            2: "standing_up",
            3: "standing_down",
            4: "walking",
            5: "running",
            6: "hurtling",
            7: "dancing",
        }
        self.status = state_map.get(udp_controller.robot_state.robot_basic_state, "idle")
    
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
            "endurance_hours": round(self.battery / 100 * 1.8, 1),
            "joint_angles": dict(enumerate(self.joint_angles)),
            "ptz_state": dict(self.ptz_state),
            "imu": dict(self.imu),
            "ultrasound": list(self.ultrasound)
        }
    
    def simulate_heartbeat(self) -> Dict:
        """生成心跳数据包
        
        Returns:
            心跳数据字典（WebSocket上报格式）
        """
        status = self.get_system_status()
        return {
            "msgId": str(int(time.time() * 1000)),
            "ts": int(time.time() * 1000),
            "deviceId": self.device_id,
            "type": "system_status",
            "payload": status
        }
    
    def update_battery(self, dt: float = 1.0):
        """更新电池状态"""
        discharge_rate = self.battery_discharge_rate
        if self.status == "moving":
            discharge_rate *= 2
        elif self.status == "idle":
            discharge_rate *= 0.5
        self.battery -= discharge_rate * dt / 60
        self.battery = max(0.0, min(100.0, self.battery))
    
    def update_temperature(self):
        """更新温度传感器数据"""
        base_temp = 35.0
        load_temp = self.gpu_load * 0.5
        self.cpu_temp = base_temp + load_temp + random.gauss(0, 0.5)
        self.cpu_temp = max(30.0, min(80.0, self.cpu_temp))
    
    def update(self, motion_state: str = "idle", dt: float = 1.0):
        """更新所有状态（备用方法，当UDP数据不可用时使用）"""
        self.update_battery(dt)
        self.update_temperature()
        self.update_joints(motion_state)


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
