#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket数据上报网关
"""

import asyncio
import json
import uuid
import time
from typing import Dict, Optional, Callable
from datetime import datetime
from loguru import logger

try:
    import websockets
except ImportError:
    logger.warning("websockets未安装，WebSocket功能不可用")
    websockets = None


class WebSocketGateway:
    """WebSocket数据上报网关
    
    负责将检测结果、告警事件、系统状态上报至监测平台。
    支持断网缓存和网络恢复后的数据补传。
    """
    
    def __init__(self, server_url: str = "ws://192.168.1.103:8765/ws",
                 device_id: str = "LITE3-001",
                 reconnect_interval: float = 5.0):
        """
        Args:
            server_url: WebSocket服务端地址
            device_id: 设备ID
            reconnect_interval: 重连间隔（秒）
        """
        self.server_url = server_url
        self.device_id = device_id
        self.reconnect_interval = reconnect_interval
        
        self._ws = None
        self._running = False
        self._queue = []  # 断网缓存队列
        self._max_queue_size = 1000
        
        # 消息回调
        self._message_handlers: Dict[str, Callable] = {}
        
        logger.info(f"初始化WebSocket网关: {server_url}")
    
    async def connect(self):
        """建立WebSocket连接"""
        if websockets is None:
            logger.error("websockets库未安装")
            return False
        
        try:
            self._ws = await websockets.connect(
                self.server_url,
                ping_interval=30,
                ping_timeout=10
            )
            self._running = True
            logger.info("WebSocket连接成功")
            return True
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开WebSocket连接"""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
            logger.info("WebSocket已断开")
    
    async def send_message(self, msg_type: str, data: Dict):
        """发送消息
        
        Args:
            msg_type: 消息类型
            data: 消息数据
        """
        message = self._format_message(msg_type, data)
        
        if self._ws and self._running:
            try:
                await self._ws.send(json.dumps(message, ensure_ascii=False))
                logger.debug(f"发送消息: {msg_type}")
            except Exception as e:
                logger.error(f"消息发送失败: {e}")
                self._cache_message(message)
        else:
            # 断网时缓存
            self._cache_message(message)
            logger.warning(f"WebSocket未连接，消息已缓存: {msg_type}")
    
    async def send_inspection_result(self, result: Dict):
        """上报巡检结果
        
        Args:
            result: 检测结果
        """
        message = {
            "device_id": self.device_id,
            **result
        }
        await self.send_message("inspection_result", message)
    
    async def send_temperature_alert(self, alert: Dict):
        """上报温度告警
        
        Args:
            alert: 告警信息
        """
        await self.send_message("temperature_alert", alert)
    
    async def send_crack_alert(self, alert: Dict):
        """上报裂缝告警
        
        Args:
            alert: 告警信息
        """
        await self.send_message("crack_alert", alert)
    
    async def send_system_status(self, status: Dict):
        """上报系统状态
        
        Args:
            status: 状态信息
        """
        await self.send_message("system_status", status)
    
    def _format_message(self, msg_type: str, data: Dict) -> Dict:
        """格式化消息
        
        Args:
            msg_type: 消息类型
            data: 消息数据
            
        Returns:
            格式化后的消息
        """
        return {
            "msgId": str(uuid.uuid4()),
            "ts": int(time.time() * 1000),
            "deviceId": self.device_id,
            "type": msg_type,
            "payload": data
        }
    
    def _cache_message(self, message: Dict):
        """缓存消息
        
        Args:
            message: 消息字典
        """
        if len(self._queue) < self._max_queue_size:
            self._queue.append(message)
            logger.debug(f"消息已缓存，队列长度: {len(self._queue)}")
    
    def flush_queue(self):
        """刷新缓存队列，重发未发送消息"""
        if not self._queue:
            return

        logger.info(f"刷新缓存队列，共{len(self._queue)}条消息")
        self._flush_sync()

    def _flush_sync(self):
        """同步刷新缓存队列（线程安全）"""
        import asyncio as _asyncio
        loop = _asyncio.new_event_loop()
        try:
            _asyncio.set_event_loop(loop)

            async def _flush():
                for message in self._queue[:]:
                    try:
                        await self._ws.send(json.dumps(message, ensure_ascii=False))
                        self._queue.remove(message)
                        logger.debug("缓存消息重发成功")
                    except Exception as e:
                        logger.error(f"缓存消息重发失败: {e}")
                        break

            loop.run_until_complete(_flush())
        finally:
            loop.close()
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._ws is not None and self._running
    
    @property
    def queue_size(self) -> int:
        """缓存队列长度"""
        return len(self._queue)


if __name__ == "__main__":
    # 测试代码
    async def test():
        gateway = WebSocketGateway()
        
        if await gateway.connect():
            print("连接成功")
            
            # 测试发送消息
            await gateway.send_system_status({
                "battery": 95,
                "status": "ready"
            })
            
            await gateway.disconnect()
            print("测试完成")
        else:
            print("连接失败")
    
    asyncio.run(test())
