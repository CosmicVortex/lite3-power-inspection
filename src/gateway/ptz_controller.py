#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云台控制器
"""

import time
import requests
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class PtzState:
    """云台状态"""
    yaw: float = 0.0           # 偏航角(°)
    pitch: float = 0.0         # 俯仰角(°)
    roll: float = 0.0          # 翻滚角(°)
    zoom: int = 1              # 变倍级别(1-10)
    is_enabled: bool = True    # 电机使能状态


class PtzController:
    """云台控制器
    
    封装数尔安防云台的MerlinSession HTTP协议。
    支持角度控制、变焦控制、状态查询等功能。
    """
    
    # 角度限制
    YAW_RANGE = (-180.0, 180.0)
    PITCH_RANGE = (-115.0, 40.0)
    ROLL_RANGE = (-30.0, 30.0)
    
    # Session有效期
    SESSION_EXPIRE_TIME = 30.0  # 秒
    
    def __init__(self, base_url: str = "http://192.168.1.108",
                 username: str = "admin",
                 password: str = "123456"):
        """
        Args:
            base_url: 云台IP地址
            username: 用户名
            password: 密码
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
        
        # 禁用代理
        import os
        os.environ['no_proxy'] = '*'
        
        self._session_token: Optional[str] = None
        self._last_heartbeat: float = 0
        self._state = PtzState()
        
        logger.info(f"初始化云台控制器: {self.base_url}")
    
    def login(self) -> bool:
        """登录云台，获取Session
        
        Returns:
            登录是否成功
        """
        try:
            url = f"{self.base_url}/merlin/Login.cgi"
            params = {"Type": "WEB", "Expires": "30"}
            resp = self.session.get(url, params=params, timeout=5)
            
            if resp.status_code == 200:
                self._session_token = resp.text.strip()
                self._last_heartbeat = time.time()
                logger.info("云台登录成功")
                return True
            else:
                logger.error(f"云台登录失败: HTTP {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"云台登录异常: {e}")
            return False
    
    def logout(self) -> bool:
        """登出云台
        
        Returns:
            登出是否成功
        """
        try:
            url = f"{self.base_url}/merlin/Logout.cgi"
            resp = self.session.get(url, timeout=5)
            self._session_token = None
            logger.info("云台登出成功")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"云台登出异常: {e}")
            return False
    
    def heartbeat(self) -> bool:
        """发送心跳，保持Session活跃
        
        Returns:
            心跳是否成功
        """
        # 检查是否需要重新登录
        if self._session_token is None or \
           time.time() - self._last_heartbeat > self.SESSION_EXPIRE_TIME:
            logger.warning("Session过期，重新登录")
            return self.login()
        
        try:
            url = f"{self.base_url}/merlin/Heartbeat.cgi"
            resp = self.session.get(url, timeout=5)
            self._last_heartbeat = time.time()
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"心跳发送失败: {e}")
            return False
    
    def set_angle(self, yaw: Optional[float] = None,
                  pitch: Optional[float] = None,
                  roll: Optional[float] = None) -> bool:
        """设置云台角度
        
        Args:
            yaw: 偏航角(-180°~180°)
            pitch: 俯仰角(-115°~40°)
            roll: 翻滚角(-30°~30°)
            
        Returns:
            设置是否成功
        """
        if not self._check_session():
            return False
        
        # 角度范围检查
        if yaw is not None:
            yaw = max(self.YAW_RANGE[0], min(self.YAW_RANGE[1], yaw))
        if pitch is not None:
            pitch = max(self.PITCH_RANGE[0], min(self.PITCH_RANGE[1], pitch))
        if roll is not None:
            roll = max(self.ROLL_RANGE[0], min(self.ROLL_RANGE[1], roll))
        
        try:
            url = f"{self.base_url}/merlin/SetPtzangle.cgi"
            data = {"Angle": {}}
            if yaw is not None:
                data["Angle"]["yaw"] = yaw
            if pitch is not None:
                data["Angle"]["pitch"] = pitch
            if roll is not None:
                data["Angle"]["roll"] = roll
            
            resp = self.session.post(url, json=data, timeout=5)
            
            if resp.status_code == 200:
                if yaw is not None:
                    self._state.yaw = yaw
                if pitch is not None:
                    self._state.pitch = pitch
                if roll is not None:
                    self._state.roll = roll
                logger.debug(f"云台角度设置成功: yaw={yaw}, pitch={pitch}, roll={roll}")
                return True
            else:
                logger.error(f"云台角度设置失败: HTTP {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"云台角度设置异常: {e}")
            return False
    
    def set_zoom(self, zoom: int) -> bool:
        """设置变倍级别
        
        Args:
            zoom: 变倍级别(1-10)
            
        Returns:
            设置是否成功
        """
        if not self._check_session():
            return False
        
        zoom = max(1, min(10, zoom))
        
        try:
            url = f"{self.base_url}/merlin/ZoomCtrl.cgi"
            params = {"zoom": zoom}
            resp = self.session.get(url, params=params, timeout=5)
            
            if resp.status_code == 200:
                self._state.zoom = zoom
                logger.debug(f"云台变倍设置成功: zoom={zoom}")
                return True
            else:
                logger.error(f"云台变倍设置失败: HTTP {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"云台变倍设置异常: {e}")
            return False
    
    def set_direction(self, direction: str, speed: int = 20) -> bool:
        """设置云台方向
        
        Args:
            direction: 方向 (up/down/left/right/up-left/up-right/down-left/down-right/stop)
            speed: 速度(1-100)
            
        Returns:
            设置是否成功
        """
        if not self._check_session():
            return False
        
        valid_directions = [
            "up", "down", "left", "right",
            "up-left", "up-right", "down-left", "down-right",
            "stop"
        ]
        
        if direction not in valid_directions:
            logger.error(f"无效的方向参数: {direction}")
            return False
        
        try:
            url = f"{self.base_url}/merlin/SetPtzDirection.cgi"
            data = {
                "Direction": {
                    "ptz_opt": direction,
                    "speed": speed
                }
            }
            resp = self.session.post(url, json=data, timeout=5)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"云台方向设置异常: {e}")
            return False
    
    def get_state(self) -> Optional[Dict]:
        """获取云台状态
        
        Returns:
            云台状态字典
        """
        if not self._check_session():
            return None
        
        try:
            url = f"{self.base_url}/merlin/GetFlyStateInfo.cgi"
            resp = self.session.get(url, timeout=5)
            
            if resp.status_code == 200:
                state = resp.json()
                self._state.yaw = state.get("Angle", {}).get("yaw", self._state.yaw)
                self._state.pitch = state.get("Angle", {}).get("pitch", self._state.pitch)
                self._state.zoom = state.get("Zoom", {}).get("zoom", self._state.zoom)
                return state
            else:
                logger.error(f"获取云台状态失败: HTTP {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"获取云台状态异常: {e}")
            return None
    
    def enable_motors(self, enable: bool = True) -> bool:
        """使能/禁用云台电机
        
        Args:
            enable: True=使能, False=禁用
            
        Returns:
            操作是否成功
        """
        if not self._check_session():
            return False
        
        enable_value = 1 if enable else 0
        
        try:
            url = f"{self.base_url}/merlin/SetPtzAbility.cgi"
            data = {"Motor": {"Enable": enable_value}}
            resp = self.session.post(url, json=data, timeout=5)
            
            if resp.status_code == 200:
                self._state.is_enabled = enable
                logger.debug(f"云台电机{'使能' if enable else '禁用'}成功")
                return True
            else:
                logger.error(f"云台电机控制失败: HTTP {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"云台电机控制异常: {e}")
            return False
    
    def take_snapshot(self, snapshot_id: str) -> Optional[str]:
        """拍摄快照
        
        Args:
            snapshot_id: 快照ID
            
        Returns:
            快照URL，失败返回None
        """
        if not self._check_session():
            return None
        
        try:
            url = f"{self.base_url}/merlin/Snapshot.cgi"
            params = {"id": snapshot_id}
            resp = self.session.get(url, params=params, timeout=10)
            
            if resp.status_code == 200:
                snapshot_url = f"{self.base_url}/snap/{snapshot_id}.jpg"
                logger.debug(f"快照拍摄成功: {snapshot_url}")
                return snapshot_url
            else:
                logger.error(f"快照拍摄失败: HTTP {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"快照拍摄异常: {e}")
            return None
    
    def _check_session(self) -> bool:
        """检查Session有效性"""
        return self._session_token is not None and \
               time.time() - self._last_heartbeat < self.SESSION_EXPIRE_TIME
    
    @property
    def state(self) -> PtzState:
        """获取云台状态"""
        return self._state


if __name__ == "__main__":
    # 测试代码
    ptz = PtzController()
    
    if ptz.login():
        print("登录成功")
        
        # 测试角度控制
        ptz.set_angle(yaw=45.0, pitch=-30.0)
        
        # 测试变焦
        ptz.set_zoom(10)
        
        # 获取状态
        state = ptz.get_state()
        print(f"云台状态: {state}")
        
        # 拍快照
        ptz.take_snapshot("TEST-001")
        
        ptz.logout()
        print("登出成功")
    else:
        print("登录失败")
