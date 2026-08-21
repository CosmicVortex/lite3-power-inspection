#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UDP运动控制器 - 增强版

支持接收运动主机的实时数据上报：
- 机器人状态（电池、IMU、位置等）
- 关节角度
- 关节角速度
"""

import struct
import socket
import time
import threading
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class RobotState:
    """机器人状态数据类"""
    # 基本状态
    robot_basic_state: int = 0        # 基本运动状态
    robot_gait_state: int = 0         # 当前步态
    robot_policy_state: int = 0       # AI步态状态
    robot_motion_state: int = 0       # 动作状态
    
    # IMU数据
    rpy: Tuple[float, float, float] = (0.0, 0.0, 0.0)      # 欧拉角 {roll, pitch, yaw}
    rpy_vel: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # 角速度
    xyz_acc: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # 加速度
    
    # 位置和速度
    pos_world: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # 世界坐标 {x, y, yaw}
    vel_world: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # 世界速度
    vel_body: Tuple[float, float, float] = (0.0, 0.0, 0.0)   # 身体速度
    
    # 电池和状态标志
    battery_level: float = 100.0          # 电量百分比
    is_charging: bool = False             # 充电状态
    is_robot_need_move: bool = False      # 需要移动保持平衡
    zero_position_flag: bool = False      # 回零标志
    is_after_first_start: bool = False    # 首次启动标志
    is_voice_ctrl_enable: bool = False    # 语音控制使能
    
    # 超声波
    ultrasound: Tuple[float, float] = (0.0, 0.0)  # {前, 后}


@dataclass
class JointData:
    """关节数据类"""
    angles: Tuple[float, ...] = tuple([0.0] * 12)   # 关节角度
    velocities: Tuple[float, ...] = tuple([0.0] * 12)  # 关节角速度


class UDPMotionController:
    """UDP运动控制器
    
    封装与RK3588运动主机的UDP通信。
    提供运动控制、状态查询、实时数据接收等接口。
    """
    
    # UDP端口
    DEFAULT_PORT = 43893
    RECEIVE_PORT = 43894  # 接收数据端口（运动主机默认发送到此端口）
    
    # 指令码定义（来自官方手册）
    CMD_HEARTBEAT = 0x21040001      # 心跳
    CMD_STAND_UP = 0x21010202       # 起立
    CMD_STAND_DOWN = 0x21010203     # 趴下
    CMD_EMERGENCY_STOP = 0x21020C0E # 软急停
    CMD_HARD_STOP = 0x21020C0F      # 硬急停
    CMD_HOME = 0x21010C05           # 回零
    CMD_ENTER_AI_MODE = 0x21010528  # 进入AI模式
    CMD_EXIT_AI_MODE = 0x2101052B   # 退出AI模式
    
    # 数据接收指令码
    CMD_ROBOT_STATE = 0x0901        # 机器人状态上报
    CMD_JOINT_ANGLE = 0x0902        # 关节角度上报
    CMD_JOINT_VEL = 0x0903          # 关节角速度上报
    
    # 心跳间隔
    HEARTBEAT_INTERVAL = 0.4  # 秒（2.5Hz）
    
    def __init__(self, ip: str = "192.168.1.103", port: int = DEFAULT_PORT):
        """
        Args:
            ip: 运动主机IP地址
            port: UDP端口
        """
        self.target_addr = (ip, port)
        self.local_addr = ("0.0.0.0", RECEIVE_PORT)
        
        # 发送socket
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_sock.settimeout(1.0)
        
        # 接收socket
        self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.recv_sock.bind(self.local_addr)
        self.recv_sock.settimeout(0.01)  # 非阻塞接收
        
        self._running = False
        self._heartbeat_task = None
        self._receive_task = None
        
        # 最新数据
        self.robot_state = RobotState()
        self.joint_data = JointData()
        
        # 统计信息
        self._packet_count = 0
        self._last_recv_time = 0
        
        logger.info(f"初始化UDP控制器: {ip}:{port}")
        logger.info(f"接收端口: {RECEIVE_PORT}")
    
    def connect(self) -> bool:
        """建立UDP连接（实际上是无状态连接）
        
        Returns:
            连接是否成功
        """
        try:
            # 发送一次心跳测试连接
            self.send_heartbeat()
            time.sleep(0.1)  # 等待响应
            
            # 尝试接收数据
            data, addr = self.recv_sock.recvfrom(1024)
            if data:
                logger.info(f"UDP连接测试成功，收到{len(data)}字节")
                self._parse_packet(data)
                return True
            else:
                logger.warning("UDP连接测试：未收到响应")
                return False
        except socket.timeout:
            logger.warning("UDP连接测试：超时（可能运动主机未发送数据）")
            return True  # UDP无连接，不强制要求响应
        except Exception as e:
            logger.error(f"UDP连接失败: {e}")
            return False
    
    def send_heartbeat(self) -> bool:
        """发送心跳包
        
        Returns:
            发送是否成功
        """
        try:
            cmd = struct.pack('<III', self.CMD_HEARTBEAT, 0, 0)
            self.send_sock.sendto(cmd, self.target_addr)
            return True
        except Exception as e:
            logger.error(f"心跳发送失败: {e}")
            return False
    
    def _parse_packet(self, data: bytes):
        """解析UDP数据包
        
        Args:
            data: 原始数据包
        """
        try:
            if len(data) < 12:
                return
            
            # 解析CommandHead
            code, paramters_size, type_ = struct.unpack('<III', data[:12])
            
            self._packet_count += 1
            self._last_recv_time = time.time()
            
            # 根据指令码解析数据
            if code == self.CMD_ROBOT_STATE:
                self._parse_robot_state(data[12:])
            elif code == self.CMD_JOINT_ANGLE:
                self._parse_joint_angles(data[12:])
            elif code == self.CMD_JOINT_VEL:
                self._parse_joint_velocities(data[12:])
                
        except Exception as e:
            logger.debug(f"解析数据包失败: {e}")
    
    def _parse_robot_state(self, data: bytes):
        """解析机器人状态数据
        
        结构体RobotStateUpload字段布局：
        - robot_basic_state: int (4字节)
        - robot_gait_state: int (4字节)
        - robot_policy_state: int (4字节)
        - rpy: double[3] (24字节)
        - rpy_vel: double[3] (24字节)
        - xyz_acc: double[3] (24字节)
        - pos_world: double[3] (24字节)
        - vel_world: double[3] (24字节)
        - vel_body: double[3] (24字节)
        - touch_down_and_stair_trot: unsigned (4字节)
        - is_charging: bool (1字节)
        - error_state: unsigned (4字节)
        - robot_motion_state: int (4字节)
        - battery_level: double (8字节)
        - task_state: int (4字节)
        - is_robot_need_move: bool (1字节)
        - zero_position_flag: bool (1字节)
        - is_after_first_start: bool (1字节)
        - is_voice_ctrl_enable: bool (1字节)
        - ultrasound: double[2] (16字节)
        """
        try:
            offset = 0
            
            # 基本状态
            self.robot_state.robot_basic_state = struct.unpack_from('<i', data, offset)[0]
            offset += 4
            self.robot_state.robot_gait_state = struct.unpack_from('<i', data, offset)[0]
            offset += 4
            self.robot_state.robot_policy_state = struct.unpack_from('<i', data, offset)[0]
            offset += 4
            
            # IMU数据
            self.robot_state.rpy = struct.unpack_from('<ddd', data, offset)
            offset += 24
            self.robot_state.rpy_vel = struct.unpack_from('<ddd', data, offset)
            offset += 24
            self.robot_state.xyz_acc = struct.unpack_from('<ddd', data, offset)
            offset += 24
            
            # 位置速度
            self.robot_state.pos_world = struct.unpack_from('<ddd', data, offset)
            offset += 24
            self.robot_state.vel_world = struct.unpack_from('<ddd', data, offset)
            offset += 24
            self.robot_state.vel_body = struct.unpack_from('<ddd', data, offset)
            offset += 24
            
            # 其他状态
            offset += 4  # touch_down_and_stair_trot (跳过)
            self.robot_state.is_charging = struct.unpack_from('<?', data, offset)[0]
            offset += 1
            offset += 4  # error_state (跳过)
            self.robot_state.robot_motion_state = struct.unpack_from('<i', data, offset)[0]
            offset += 4
            self.robot_state.battery_level = struct.unpack_from('<d', data, offset)[0] * 100  # 转为百分比
            offset += 8
            offset += 4  # task_state (跳过)
            self.robot_state.is_robot_need_move = struct.unpack_from('<?', data, offset)[0]
            offset += 1
            self.robot_state.zero_position_flag = struct.unpack_from('<?', data, offset)[0]
            offset += 1
            self.robot_state.is_after_first_start = struct.unpack_from('<?', data, offset)[0]
            offset += 1
            self.robot_state.is_voice_ctrl_enable = struct.unpack_from('<?', data, offset)[0]
            offset += 1
            self.robot_state.ultrasound = struct.unpack_from('<dd', data, offset)
            
        except Exception as e:
            logger.debug(f"解析机器人状态失败: {e}")
    
    def _parse_joint_angles(self, data: bytes):
        """解析关节角度数据
        
        12个关节角度，每个double (8字节)，共96字节
        """
        try:
            self.joint_data.angles = struct.unpack_from('<12d', data, 0)
        except Exception as e:
            logger.debug(f"解析关节角度失败: {e}")
    
    def _parse_joint_velocities(self, data: bytes):
        """解析关节角速度数据
        
        12个关节角速度，每个double (8字节)，共96字节
        """
        try:
            self.joint_data.velocities = struct.unpack_from('<12d', data, 0)
        except Exception as e:
            logger.debug(f"解析关节角速度失败: {e}")
    
    def stand_up(self) -> bool:
        """命令机器狗起立
        
        Returns:
            发送是否成功
        """
        return self._send_command(self.CMD_STAND_UP, 0)
    
    def stand_down(self) -> bool:
        """命令机器狗趴下
        
        Returns:
            发送是否成功
        """
        return self._send_command(self.CMD_STAND_DOWN, 1)
    
    def emergency_stop(self) -> bool:
        """软急停
        
        Returns:
            发送是否成功
        """
        return self._send_command(self.CMD_EMERGENCY_STOP, 0)
    
    def hard_stop(self) -> bool:
        """硬急停
        
        Returns:
            发送是否成功
        """
        return self._send_command(self.CMD_HARD_STOP, 0)
    
    def go_home(self) -> bool:
        """回零
        
        Returns:
            发送是否成功
        """
        return self._send_command(self.CMD_HOME, 0)
    
    def enter_ai_mode(self) -> bool:
        """进入AI模式
        
        Returns:
            发送是否成功
        """
        return self._send_command(self.CMD_ENTER_AI_MODE, 0)
    
    def exit_ai_mode(self) -> bool:
        """退出AI模式
        
        Returns:
            发送是否成功
        """
        return self._send_command(self.CMD_EXIT_AI_MODE, 0)
    
    def set_velocity(self, vx: float, vy: float, vw: float) -> bool:
        """设置运动速度
        
        Args:
            vx: 前后速度 (-1.0 ~ 1.0 m/s)
            vy: 左右速度 (-1.0 ~ 1.0 m/s)
            vw: 旋转速度 (-1.0 ~ 1.0 rad/s)
            
        Returns:
            发送是否成功
        """
        try:
            cmd = struct.pack('<IIIfff', self.CMD_VELOCITY, 0, 0, vx, vy, vw)
            self.send_sock.sendto(cmd, self.target_addr)
            return True
        except Exception as e:
            logger.error(f"速度设置失败: {e}")
            return False
    
    def set_joint_angles(self, angles: Tuple[float, ...]) -> bool:
        """设置关节角度
        
        Args:
            angles: 12个关节角度 (q1~q12)
            
        Returns:
            发送是否成功
        """
        try:
            if len(angles) != 12:
                logger.error(f"关节角度数量错误: 期望12，实际{len(angles)}")
                return False
            
            # 构造指令: [cmd][0][0][q1...q12]
            payload = struct.pack('<III', self.CMD_JOINT_ANGLE, 0, 0)
            payload += struct.pack('f' * 12, *angles)
            
            self.sock.sendto(payload, self.target_addr)
            return True
        except Exception as e:
            logger.error(f"关节角度设置失败: {e}")
            return False
    
    def _send_command(self, cmd: int, value: int) -> bool:
        """发送简单指令
        
        Args:
            cmd: 指令码
            value: 指令值
            
        Returns:
            发送是否成功
        """
        try:
            packet = struct.pack('<III', cmd, value, 0)
            self.send_sock.sendto(packet, self.target_addr)
            logger.debug(f"发送指令: 0x{cmd:08X}, value={value}")
            return True
        except Exception as e:
            logger.error(f"指令发送失败: {e}")
            return False
    
    def get_last_packet_time(self) -> float:
        """获取最后收到数据包的时间戳
        
        Returns:
            时间戳（秒）
        """
        return self._last_recv_time
    
    def is_connected(self) -> bool:
        """检查连接状态
        
        Returns:
            是否在最近1秒内收到数据
        """
        return time.time() - self._last_recv_time < 1.0
    
    def get_state_dict(self) -> Dict:
        """获取当前机器人状态字典
        
        Returns:
            状态数据字典
        """
        return {
            "battery": round(self.robot_state.battery_level, 1),
            "status": self.robot_state.robot_basic_state,
            "gait": self.robot_state.robot_gait_state,
            "rpy": list(self.robot_state.rpy),
            "position": list(self.robot_state.pos_world),
            "velocity": list(self.robot_state.vel_body),
            "is_charging": self.robot_state.is_charging,
            "ultrasound": list(self.robot_state.ultrasound),
        }
    
    def get_joint_dict(self) -> Dict:
        """获取关节数据字典
        
        Returns:
            关节数据字典
        """
        return {
            "angles": list(self.joint_data.angles),
            "velocities": list(self.joint_data.velocities),
        }
    
    def send_heartbeat_loop(self, interval: float = HEARTBEAT_INTERVAL):
        """持续发送心跳（在独立线程中运行）
        
        Args:
            interval: 心跳间隔（秒）
        """
        self._running = True
        logger.info(f"启动心跳循环: 间隔={interval}s")
        
        while self._running:
            self.send_heartbeat()
            time.sleep(interval)
        
        logger.info("心跳循环已停止")
    
    def receive_loop(self):
        """持续接收数据（在独立线程中运行）"""
        logger.info("启动数据接收循环")
        
        while self._running:
            try:
                data, addr = self.recv_sock.recvfrom(1024)
                if data:
                    self._parse_packet(data)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"接收数据失败: {e}")
    
    def start_heartbeat(self):
        """启动心跳线程"""
        self._running = True
        self._heartbeat_task = threading.Thread(
            target=self.send_heartbeat_loop,
            daemon=True
        )
        self._heartbeat_task.start()
        
        # 启动数据接收线程
        self._receive_task = threading.Thread(
            target=self.receive_loop,
            daemon=True
        )
        self._receive_task.start()
        
        logger.info("心跳和数据接收已启动")
    
    def stop_heartbeat(self):
        """停止心跳线程"""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.join(timeout=2.0)
        if self._receive_task:
            self._receive_task.join(timeout=2.0)
    
    def close(self):
        """关闭连接"""
        self.stop_heartbeat()
        self.send_sock.close()
        self.recv_sock.close()
        logger.info("UDP控制器已关闭")


if __name__ == "__main__":
    # 测试代码
    controller = UDPMotionController()
    
    if controller.connect():
        print("连接成功")
        
        # 启动心跳和接收
        controller.start_heartbeat()
        
        # 等待接收数据
        print("等待运动主机数据...")
        for i in range(10):
            time.sleep(1)
            if controller.is_connected():
                state = controller.get_state_dict()
                print(f"\n收到数据 (包数: {controller._packet_count}):")
                print(f"  电量: {state['battery']}%")
                print(f"  位置: {state['position']}")
                print(f"  超声波: {state['ultrasound']}")
            else:
                print(f"\n未收到数据 (包数: {controller._packet_count})")
        
        controller.stop_heartbeat()
        print("\n测试完成")
    else:
        print("连接失败")
