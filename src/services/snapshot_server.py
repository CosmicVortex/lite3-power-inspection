#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快照HTTP服务

提供告警快照图片的HTTP访问接口
使用Python标准库实现，无需额外依赖
"""

import os
import asyncio
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import json
from loguru import logger


class SnapshotHandler(BaseHTTPRequestHandler):
    """快照请求处理器"""
    
    snapshot_dir = None
    
    def do_GET(self):
        """处理GET请求"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # 只允许访问/snap/路径
        if not path.startswith('/snap/'):
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
            return
        
        # 提取快照文件名
        snapshot_id = path[6:]  # 移除/snap/前缀
        
        # 构建完整路径
        if SnapshotHandler.snapshot_dir is None:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Snapshot directory not configured"}).encode())
            return
        
        file_path = Path(SnapshotHandler.snapshot_dir) / f"{snapshot_id}.jpg"
        
        if not file_path.exists():
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Snapshot not found"}).encode())
            return
        
        # 读取并返回文件
        try:
            with open(file_path, 'rb') as f:
                image_data = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', len(image_data))
            self.end_headers()
            self.wfile.write(image_data)
            
        except Exception as e:
            logger.error(f"读取快照文件失败: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        logger.debug(f"[SnapshotServer] {args[0]}")


class SnapshotServer:
    """快照HTTP服务
    
    提供静态文件服务，用于访问告警快照图片。
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8080, snapshot_dir: str = "data/snapshots"):
        self.host = host
        self.port = port
        self.snapshot_dir = snapshot_dir
        self.server = None
        self.thread = None
        self.running = False
        
        # 配置处理器
        SnapshotHandler.snapshot_dir = snapshot_dir
        
        logger.info(f"快照服务初始化: {host}:{port}, 目录={snapshot_dir}")
    
    def start(self):
        """启动服务器（后台线程）"""
        def run_server():
            try:
                self.server = HTTPServer((self.host, self.port), SnapshotHandler)
                logger.info(f"快照服务启动: http://{self.host}:{self.port}")
                self.server.serve_forever()
            except Exception as e:
                logger.error(f"快照服务启动失败: {e}")
        
        self.thread = threading.Thread(target=run_server, daemon=True)
        self.thread.start()
        self.running = True
        return self
    
    def stop(self):
        """停止服务器"""
        if self.server:
            self.server.shutdown()
            self.running = False
            logger.info("快照服务已停止")
    
    def get_snapshot_url(self, snapshot_id: str) -> str:
        """获取快照URL"""
        return f"http://{self.host}:{self.port}/snap/{snapshot_id}"


async def start_snapshot_server(snapshot_dir: str = "data/snapshots") -> SnapshotServer:
    """启动快照服务
    
    Returns:
        SnapshotServer实例
    """
    server = SnapshotServer(snapshot_dir=snapshot_dir)
    server.start()
    await asyncio.sleep(0.5)  # 等待服务器启动
    return server


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="快照HTTP服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--dir", default="data/snapshots")
    args = parser.parse_args()
    
    server = SnapshotServer(host=args.host, port=args.port, snapshot_dir=args.dir)
    server.start()
    
    try:
        while True:
            asyncio.run(asyncio.sleep(1))
    except KeyboardInterrupt:
        server.stop()
