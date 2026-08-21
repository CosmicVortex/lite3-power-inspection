#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频流转发服务

功能：
1. 从RTSP相机获取视频流
2. 将视频帧推送到监测平台
3. 支持可见光和热成像双路视频
"""

import asyncio
import cv2
import numpy as np
import base64
import io
import websockets
import json
import time
from typing import Optional, Dict
from loguru import logger


class VideoStreamForwarder:
    """视频流转发器
    
    从RTSP相机获取视频流，定期推送帧到监测平台
    """
    
    def __init__(self, rtsp_url: str, stream_name: str, ws_url: str = "ws://localhost:8765/ws"):
        """
        Args:
            rtsp_url: RTSP流地址
            stream_name: 流名称 (visible/thermal)
            ws_url: WebSocket服务器地址
        """
        self.rtsp_url = rtsp_url
        self.stream_name = stream_name
        self.ws_url = ws_url
        
        self.cap = None
        self.ws = None
        self.running = False
        self.frame_count = 0
        self.fps = 15  # 推送帧率
        
    async def connect(self):
        """连接WebSocket和RTSP流"""
        # 连接WebSocket
        try:
            self.ws = await websockets.connect(self.ws_url, ping_interval=None)
            logger.info(f"VideoStreamForwarder: 连接到 {self.ws_url}")
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            return False
        
        # 打开RTSP流
        try:
            self.cap = cv2.VideoCapture(self.rtsp_url)
            if not self.cap.isOpened():
                logger.error(f"无法打开RTSP流: {self.rtsp_url}")
                return False
            logger.info(f"VideoStreamForwarder: 已打开 {self.stream_name} 流")
        except Exception as e:
            logger.error(f"RTSP打开失败: {e}")
            return False
        
        self.running = True
        return True
    
    def _frame_to_base64(self, frame: np.ndarray, quality: int = 85) -> str:
        """将帧转换为Base64编码"""
        # 压缩为JPEG
        _, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        # 转换为Base64
        return base64.b64encode(encoded).decode('utf-8')
    
    async def send_frame(self, frame: np.ndarray):
        """发送单帧到监测平台"""
        if not self.ws or not self.running:
            return
        
        try:
            # 转换帧为Base64
            b64_frame = self._frame_to_base64(frame)
            
            # 发送消息
            message = {
                "msgId": str(int(time.time() * 1000)),
                "ts": int(time.time() * 1000),
                "deviceId": "LITE3-001",
                "type": "video_frame",
                "payload": {
                    "stream": self.stream_name,
                    "frame_id": self.frame_count,
                    "timestamp": int(time.time() * 1000),
                    "resolution": f"{frame.shape[1]}x{frame.shape[0]}",
                    "data": b64_frame
                }
            }
            
            await self.ws.send(json.dumps(message))
            self.frame_count += 1
            
        except Exception as e:
            logger.error(f"发送视频帧失败: {e}")
            self.running = False
    
    async def start(self):
        """开始转发视频流"""
        if not await self.connect():
            return
        
        logger.info(f"开始转发 {self.stream_name} 视频流")
        
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    logger.warning(f"无法读取帧，重连中...")
                    await asyncio.sleep(1)
                    continue
                
                # 发送帧
                await self.send_frame(frame)
                
                # 控制帧率
                await asyncio.sleep(1.0 / self.fps)
                
            except Exception as e:
                logger.error(f"视频流转发错误: {e}")
                await asyncio.sleep(1)
    
    async def stop(self):
        """停止转发"""
        self.running = False
        if self.cap:
            self.cap.release()
        if self.ws:
            await self.ws.close()
        logger.info(f"{self.stream_name} 视频流已停止")


async def forward_video_streams(ws_url: str):
    """启动所有视频流转发
    
    Args:
        ws_url: WebSocket服务器地址
    """
    # RTSP流配置（从配置文件读取）
    streams = [
        ("rtsp://admin:123456@192.168.1.108:554/id=1&type=0", "visible"),
        ("rtsp://admin:123456@192.168.1.108:554/id=2&type=0", "thermal"),
    ]
    
    forwarders = []
    
    for url, name in streams:
        forwarder = VideoStreamForwarder(url, name, ws_url)
        forwarders.append(forwarder)
        
        # 启动转发任务
        asyncio.create_task(forwarder.start())
    
    logger.info(f"启动 {len(forwarders)} 个视频流转发任务")
    
    # 保持运行
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("接收到停止信号")
    finally:
        for f in forwarders:
            await f.stop()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="视频流转发服务")
    parser.add_argument("--ws-url", default="ws://localhost:8765/ws", help="WebSocket服务器地址")
    args = parser.parse_args()
    
    logger.info("视频流转发服务启动")
    asyncio.run(forward_video_streams(args.ws_url))
