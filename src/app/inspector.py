#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
巡检主控制器
"""

import asyncio
import yaml
import time
from typing import Dict, List, Optional
from pathlib import Path
from loguru import logger

from .perception.yolo_detector import YOLODetector
from .perception.unet_segmentor import UNetSegmentor
from .perception.temperature_monitor import TemperatureMonitor
from .gateway.ptz_controller import PtzController
from .gateway.udp_controller import UDPMotionController
from .gateway.websocket_client import WebSocketGateway
from .gateway.rtsp_client import RTSPClient
from .storage.sqlite_cache import SQLiteCache


class Inspector:
    """巡检主控制器
    
    协调视觉检测、运动控制、数据上报的完整巡检流程。
    """
    
    def __init__(self, config_path: str = "config/inspection_config.yaml"):
        """
        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        
        # 初始化各模块
        self._init_modules()
        
        logger.info("巡检控制器初始化完成")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            配置字典
        """
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
            return self._default_config()
        
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    
    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            "robot": {
                "motion_host_ip": "192.168.1.103",
                "motion_host_port": 43893,
                "heartbeat_interval": 0.4
            },
            "ptz": {
                "base_url": "http://192.168.1.108",
                "username": "admin",
                "password": "123456",
                "heartbeat_interval": 10.0
            },
            "rtsp": {
                "visible_light_main": "rtsp://admin:123456@192.168.1.108:554/id=1&type=0",
                "visible_light_sub": "rtsp://admin:123456@192.168.1.108:554/id=1&type=1",
                "thermal": "rtsp://admin:123456@192.168.1.108:554/id=2&type=0"
            },
            "detection": {
                "crack": {
                    "yolo_model": "models/yolov8s-crack.trt",
                    "unet_model": "models/unet-crack.onnx",
                    "confidence_threshold": 0.5,
                    "min_width_mm": 0.1
                },
                "temperature": {
                    "warn_threshold": 45.0,
                    "critical_threshold": 50.0,
                    "filter_window": 3
                }
            },
            "communication": {
                "websocket": {
                    "server_url": "ws://MONITOR_HOST:8765/ws",
                    "reconnect_interval": 5.0
                }
            }
        }
    
    def _init_modules(self):
        """初始化各模块"""
        cfg = self.config
        
        # 感知模块
        self.crack_detector = YOLODetector(
            model_path=cfg['detection']['crack']['yolo_model'],
            confidence_threshold=cfg['detection']['crack']['confidence_threshold']
        )
        self.crack_segmentor = UNetSegmentor(
            model_path=cfg['detection']['crack']['unet_model']
        )
        self.temp_monitor = TemperatureMonitor(
            warn_threshold=cfg['detection']['temperature']['warn_threshold'],
            critical_threshold=cfg['detection']['temperature']['critical_threshold']
        )
        
        # 网关模块
        self.udp_controller = UDPMotionController(
            ip=cfg['robot']['motion_host_ip'],
            port=cfg['robot']['motion_host_port']
        )
        self.ptz_controller = PtzController(
            base_url=cfg['ptz']['base_url'],
            username=cfg['ptz']['username'],
            password=cfg['ptz']['password']
        )
        self.websocket = WebSocketGateway(
            server_url=cfg['communication']['websocket']['server_url']
        )
        
        # 视频流
        self.rtsp_visible = RTSPClient(cfg['rtsp']['visible_light_main'], "visible")
        self.rtsp_thermal = RTSPClient(cfg['rtsp']['thermal'], "thermal")
        
        # 存储
        self.cache = SQLiteCache("data/inspection.db")
    
    async def start_inspection(self):
        """启动巡检任务"""
        logger.info("启动巡检任务")
        
        # 连接各模块
        await self._connect_all()
        
        # 进入AI模式
        self.udp_controller.enter_ai_mode()
        
        try:
            # 执行巡检流程
            await self._run_inspection_loop()
        finally:
            # 清理资源
            await self._disconnect_all()
    
    async def _connect_all(self):
        """连接所有模块"""
        # UDP连接
        self.udp_controller.connect()
        self.udp_controller.start_heartbeat()
        
        # 云台登录
        self.ptz_controller.login()
        
        # WebSocket连接
        await self.websocket.connect()
        
        # RTSP流启动
        self.rtsp_visible.start()
        self.rtsp_thermal.start()
        
        logger.info("所有模块连接成功")
    
    async def _disconnect_all(self):
        """断开所有模块"""
        # 停止心跳
        self.udp_controller.stop_heartbeat()
        
        # 退出AI模式
        self.udp_controller.exit_ai_mode()
        
        # 云台登出
        self.ptz_controller.logout()
        
        # 断开WebSocket
        await self.websocket.disconnect()
        
        # 停止RTSP流
        self.rtsp_visible.stop()
        self.rtsp_thermal.stop()
        
        logger.info("所有模块已断开")
    
    async def _run_inspection_loop(self):
        """巡检主循环"""
        logger.info("开始巡检流程")
        
        # 获取航点配置
        waypoints = self.cache.get_waypoints()
        
        if not waypoints:
            logger.warning("未配置航点，使用默认航点")
            waypoints = self._get_default_waypoints()
        
        # 执行每个航点
        for waypoint in waypoints:
            await self._execute_waypoint(waypoint)
            await asyncio.sleep(waypoint.get('wait_time', 1.0))
    
    def _get_default_waypoints(self) -> List[Dict]:
        """获取默认航点配置"""
        return [
            {"id": "WP001", "x": 0.5, "y": 0.0, "theta": 0.0, 
             "type": "CRACK_INSPECTION", "ptz_yaw": 45.0, "ptz_pitch": -30.0, "zoom_level": 10},
            {"id": "WP002", "x": 1.0, "y": 0.0, "theta": 90.0,
             "type": "TEMPERATURE_MONITOR", "ptz_yaw": 135.0, "ptz_pitch": -45.0},
        ]
    
    async def _execute_waypoint(self, waypoint: Dict):
        """执行单航点检测任务
        
        Args:
            waypoint: 航点配置
        """
        wp_id = waypoint['id']
        wp_type = waypoint['type']
        
        logger.info(f"执行航点: {wp_id} ({wp_type})")
        
        # 移动至航点位置
        await self._move_to_waypoint(waypoint)
        
        # 设置云台角度
        self.ptz_controller.set_angle(
            yaw=waypoint.get('ptz_yaw'),
            pitch=waypoint.get('ptz_pitch')
        )
        
        # 根据航点类型执行检测
        if wp_type == "CRACK_INSPECTION":
            await self._inspect_crack(waypoint)
        elif wp_type == "TEMPERATURE_MONITOR":
            await self._monitor_temperature(waypoint)
    
    async def _move_to_waypoint(self, waypoint: Dict):
        """移动到航点位置
        
        Args:
            waypoint: 航点配置
        """
        # 移动至航点位置（模拟模式下不实际运动）
        # TODO: 实现实际运动控制逻辑，需在真实硬件环境下测试
        x = waypoint.get('x', 0)
        y = waypoint.get('y', 0)
        self.udp_controller.set_velocity(x * 0.3, y * 0.3, 0)
        await asyncio.sleep(1)
        self.udp_controller.set_velocity(0, 0, 0)
    
    async def _inspect_crack(self, waypoint: Dict):
        """执行裂缝检测
        
        Args:
            waypoint: 航点配置
        """
        # 获取可见光图像
        frame = self.rtsp_visible.get_frame()
        if frame is None:
            logger.warning("可见光图像获取失败")
            return
        
        # 设置变焦
        zoom_level = waypoint.get('zoom_level', 10)
        self.ptz_controller.set_zoom(zoom_level)
        await asyncio.sleep(0.5)  # 等待变焦稳定
        
        # 执行检测
        results = self.crack_detector.detect(frame)
        
        for result in results:
            # 精细化测量
            measurement = self.crack_segmentor.process_detection(frame, result)
            
            if measurement and measurement.width_mm >= 0.1:
                # 保存结果
                result_id = self.cache.save_inspection_result({
                    "type": "crack",
                    "waypoint_id": waypoint['id'],
                    "confidence": result.confidence,
                    "width_mm": measurement.width_mm,
                    "length_mm": measurement.length_mm,
                    "snapshot_url": self.ptz_controller.take_snapshot(f"CRACK-{waypoint['id']}")
                })
                
                # 上报告警
                await self.websocket.send_crack_alert({
                    "alert_id": f"CRACK-{waypoint['id']}-{result_id}",
                    "waypoint_id": waypoint['id'],
                    "width_mm": measurement.width_mm,
                    "length_mm": measurement.length_mm,
                    "confidence": result.confidence
                })
    
    async def _monitor_temperature(self, waypoint: Dict):
        """执行温度监测
        
        Args:
            waypoint: 航点配置
        """
        # 获取热成像帧
        frame = self.rtsp_thermal.get_frame()
        if frame is None:
            logger.warning("热成像帧获取失败")
            return
        
        # 检查温度
        result = self.temp_monitor.check_temperature(frame)
        
        # 根据告警等级处理
        if result['status'] != "NORMAL":
            alert_id = self.cache.save_alert({
                "alert_id": result['alert_id'],
                "type": "temperature",
                "level": result['status'].lower(),
                "temperature": result['max_temperature'],
                "waypoint_id": waypoint['id'],
                "details": result
            })
            
            await self.websocket.send_temperature_alert({
                "alert_id": result['alert_id'],
                "waypoint_id": waypoint['id'],
                "temperature": result['temperature'],
                "max_temperature": result['max_temperature'],
                "level": result['status'].lower()
            })
    
    async def run_demo(self):
        """运行演示模式"""
        logger.info("启动演示模式")
        
        # 执行预设的演示流程
        demo_steps = [
            {"action": "stand_up", "delay": 3},
            {"action": "move_forward", "distance": 0.5, "delay": 2},
            {"action": "ptz_scan", "delay": 3},
            {"action": "crack_detection", "waypoint": "WP001", "delay": 5},
            {"action": "temperature_monitor", "waypoint": "WP002", "delay": 10},
            {"action": "return_start", "delay": 3},
            {"action": "stand_down", "delay": 2},
        ]
        
        for step in demo_steps:
            action = step['action']
            delay = step.get('delay', 1)
            
            logger.info(f"执行演示步骤: {action}")
            
            if action == "stand_up":
                self.udp_controller.stand_up()
            elif action == "move_forward":
                distance = step.get('distance', 0.5)
                self.udp_controller.set_velocity(distance, 0, 0)
            elif action == "ptz_scan":
                for angle in range(-45, 46, 15):
                    self.ptz_controller.set_angle(yaw=angle)
                    await asyncio.sleep(0.3)
            elif action == "crack_detection":
                waypoint = self.cache.get_waypoints()
                if waypoint:
                    await self._inspect_crack(waypoint[0])
            elif action == "temperature_monitor":
                waypoint = self.cache.get_waypoints()
                if waypoint:
                    await self._monitor_temperature(waypoint[0])
            elif action == "return_start":
                self.udp_controller.set_velocity(-0.5, 0, 0)
            elif action == "stand_down":
                self.udp_controller.stand_down()
            
            await asyncio.sleep(delay)
        
        logger.info("演示模式完成")


if __name__ == "__main__":
    # 测试代码
    inspector = Inspector()
    
    async def main():
        await inspector.run_demo()
    
    asyncio.run(main())
