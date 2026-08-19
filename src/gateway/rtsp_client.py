#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTSP视频流客户端
"""

import cv2
import threading
import time
from typing import Optional, Tuple, Dict
from collections import deque
from loguru import logger


class RTSPClient:
    """RTSP视频流客户端
    
    封装OpenCV的RTSP流拉取功能。
    支持可见光和热成像双流并行。
    """
    
    def __init__(self, url: str, name: str = "default"):
        """
        Args:
            url: RTSP流地址
            name: 流名称（用于日志区分）
        """
        self.url = url
        self.name = name
        self._cap = None
        self._running = False
        self._thread = None
        self._frame_queue = deque(maxlen=10)
        self._last_frame = None
        self._lock = threading.Lock()
        
        logger.info(f"初始化RTSP客户端: {name} -> {url}")
    
    def start(self):
        """启动流拉取"""
        self._running = True
        self._thread = threading.Thread(target=self._pull_loop, daemon=True)
        self._thread.start()
        logger.info(f"RTSP流启动: {self.name}")
    
    def stop(self):
        """停止流拉取"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._cap:
            self._cap.release()
        logger.info(f"RTSP流停止: {self.name}")
    
    def _pull_loop(self):
        """拉取循环"""
        self._cap = cv2.VideoCapture(self.url)
        
        if not self._cap.isOpened():
            logger.error(f"无法打开RTSP流: {self.url}")
            return
        
        # 设置缓冲区大小为1（获取最新帧）
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        logger.info(f"RTSP流已打开: {self.name}")
        
        while self._running:
            ret, frame = self._cap.read()
            
            if ret and frame is not None:
                with self._lock:
                    self._last_frame = frame.copy()
                    self._frame_queue.append(frame.copy())
            else:
                logger.warning(f"RTSP流读取失败: {self.name}")
                time.sleep(0.1)
        
        self._cap.release()
        logger.info(f"RTSP流已关闭: {self.name}")
    
    def get_frame(self) -> Optional[np.ndarray]:
        """获取最新帧
        
        Returns:
            最新帧(BGR格式)，失败返回None
        """
        with self._lock:
            return self._last_frame.copy() if self._last_frame is not None else None
    
    def get_frames(self, count: int = 1) -> list:
        """获取多帧
        
        Args:
            count: 获取帧数
            
        Returns:
            帧列表
        """
        with self._lock:
            return list(self._frame_queue)[-count:]
    
    @property
    def is_opened(self) -> bool:
        """流是否已打开"""
        return self._cap is not None and self._cap.isOpened()
    
    @property
    def last_frame_time(self) -> float:
        """最后一帧时间戳"""
        return time.time()
    
    def read_direct(self) -> Tuple[bool, Optional[np.ndarray]]:
        """直接读取一帧（非阻塞）
        
        Returns:
            (success, frame)
        """
        if self._cap and self._cap.isOpened():
            return self._cap.read()
        return False, None


if __name__ == "__main__":
    # 测试代码
    # RTSP流地址示例
    urls = {
        "visible_main": "rtsp://admin:123456@192.168.1.108:554/id=1&type=0",
        "visible_sub": "rtsp://admin:123456@192.168.1.108:554/id=1&type=1",
        "thermal": "rtsp://admin:123456@192.168.1.108:554/id=2&type=0"
    }
    
    clients = {}
    for name, url in urls.items():
        clients[name] = RTSPClient(url, name)
        clients[name].start()
    
    # 读取帧
    time.sleep(5)
    
    for name, client in clients.items():
        frame = client.get_frame()
        if frame is not None:
            print(f"{name}: 帧尺寸={frame.shape}")
        client.stop()
    
    print("测试完成")
