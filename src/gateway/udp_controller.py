#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UDP运动控制器
"""

import struct
import socket
import time
from typing import Tuple, Optional
from loguru import logger


class UDPMotionController:
    """UDP运动控制器
    
    封装与RK3588运动主机的UDP通信。
    提供运动控制、状态查询等接口。
    """
    
    # UDP端口
    DEFAULT_PORT = 43893
    
    # 指令码定义（来自官方手册）
    CMD_HEARTBEAT = 0x21040001      # 心跳
    CMD_STAND_UP = 0x21010202       # 起立
    CMD_STAND_DOWN = 0x21010203     # 趴下（值=1）
    CMD_EMERGENCY_STOP = 0x21020C0E # 软急停
    CMD_HARD_STOP = 0x21020C0F      # 硬急停
    CMD_HOME = 0x21010C05           # 回零
    CMD_ENTER_AI_MODE = 0x21010528  # 进入AI模式
    CMD_EXIT_AI_MODE = 0x2101052B   # 退出AI模式
    
    # 速度控制指令码
    CMD_VELOCITY = 0x0103
    CMD_JOINT_ANGLE = 0x0104
    
    # 心跳间隔
    HEARTBEAT_INTERVAL = 0.4  # 秒（2.5Hz）
    
    def __init__(self, ip: str = "192.168.1.103", port: int = DEFAULT_PORT):
        """
        Args:
            ip: 运动主机IP地址
            port: UDP端口
        """
        self.target_addr = (ip, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(1.0)
        
        self._running = False
        self._heartbeat_task = None
        
        logger.info(f"初始化UDP控制器: {ip}:{port}")
    
    def connect(self) -> bool:
        """建立UDP连接（实际上是无状态连接）
        
        Returns:
            连接是否成功
        """
        try:
            # 发送一次心跳测试连接
            self.send_heartbeat()
            logger.info("UDP连接测试成功")
            return True
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
            self.sock.sendto(cmd, self.target_addr)
            return True
        except Exception as e:
            logger.error(f"心跳发送失败: {e}")
            return False
    
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
            self.sock.sendto(cmd, self.target_addr)
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
            self.sock.sendto(packet, self.target_addr)
            logger.debug(f"发送指令: 0x{cmd:08X}, value={value}")
            return True
        except Exception as e:
            logger.error(f"指令发送失败: {e}")
            return False
    
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
    
    def start_heartbeat(self):
        """启动心跳线程"""
        import threading
        self._heartbeat_task = threading.Thread(
            target=self.send_heartbeat_loop,
            daemon=True
        )
        self._heartbeat_task.start()
    
    def stop_heartbeat(self):
        """停止心跳线程"""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.join(timeout=2.0)
    
    def close(self):
        """关闭连接"""
        self.stop_heartbeat()
        self.sock.close()
        logger.info("UDP控制器已关闭")


if __name__ == "__main__":
    # 测试代码
    controller = UDPMotionController()
    
    if controller.connect():
        print("连接成功")
        
        # 发送心跳
        controller.send_heartbeat()
        time.sleep(1)
        
        # 进入AI模式
        controller.enter_ai_mode()
        
        # 设置速度
        controller.set_velocity(0.3, 0.0, 0.0)
        time.sleep(2)
        
        # 急停
        controller.emergency_stop()
        
        controller.close()
        print("测试完成")
    else:
        print("连接失败")
