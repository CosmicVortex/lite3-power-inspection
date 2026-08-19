#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快照HTTP服务

提供告警快照图片的HTTP访问接口
"""

import os
import asyncio
from pathlib import Path
from loguru import logger


class SnapshotServer:
    """快照HTTP服务
    
    提供静态文件服务，用于访问告警快照图片。
    """
    
    def __init__(self, snapshot_dir: str = "data/snapshots", host: str = "0.0.0.0", port: int = 8080):
        """
        Args:
            snapshot_dir: 快照文件存储目录
            host: HTTP服务监听地址
            port: HTTP服务端口
        """
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.host = host
        self.port = port
        self._server = None
        
        logger.info(f"初始化快照服务: {self.snapshot_dir} (port={port})")
    
    async def start(self):
        """启动HTTP服务"""
        from aiohttp import web
        
        app = web.Application()
        app.router.add_get('/snap/{filename}', self._handle_snap_request)
        app.router.add_get('/thermal/{filename}', self._handle_thermal_request)
        
        self._server = await asyncio.get_running_loop().create_server(
            web.AppRunner(app).setup(),
            self.host,
            self.port
        )
        
        logger.info(f"快照服务已启动: http://{self.host}:{self.port}")
        return self._server
    
    async def _handle_snap_request(self, request: web.Request) -> web.Response:
        """处理快照请求"""
        filename = request.match_info['filename']
        filepath = self.snapshot_dir / f"{filename}.jpg"
        
        if filepath.exists():
            return web.FileResponse(filepath)
        else:
            # 返回模拟图片
            return await self._generate_mock_image(request)
    
    async def _handle_thermal_request(self, request: web.Request) -> web.Response:
        """处理热成像请求"""
        filename = request.match_info['filename']
        filepath = self.snapshot_dir / f"thermal_{filename}.jpg"
        
        if filepath.exists():
            return web.FileResponse(filepath)
        else:
            return await self._generate_mock_image(request)
    
    async def _generate_mock_image(self, request: web.Request) -> web.Response:
        """生成模拟图片（开发测试用）"""
        import io
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # 创建模拟图片
            img = Image.new('RGB', (640, 480), color=(30, 30, 30))
            draw = ImageDraw.Draw(img)
            
            # 添加文字
            draw.text((200, 200), "SNAPSHOT", fill=(255, 255, 255))
            draw.text((180, 250), "TEST MODE", fill=(255, 255, 0))
            
            # 保存到内存
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG')
            buffer.seek(0)
            
            return web.Response(body=buffer.read(), content_type='image/jpeg')
        except ImportError:
            return web.Response(text="PIL not installed", status=500)
    
    def save_snapshot(self, snapshot_id: str, image_data: bytes):
        """保存快照图片
        
        Args:
            snapshot_id: 快照ID
            image_data: 图片数据
        """
        filepath = self.snapshot_dir / f"{snapshot_id}.jpg"
        with open(filepath, 'wb') as f:
            f.write(image_data)
        logger.info(f"快照已保存: {filepath}")
    
    def get_snapshot_url(self, snapshot_id: str) -> str:
        """获取快照URL
        
        Args:
            snapshot_id: 快照ID
            
        Returns:
            快照访问URL
        """
        return f"http://{self.host}:{self.port}/snap/{snapshot_id}"


# 全局单例
_loop = None
_snapshot_server = None


def get_snapshot_server() -> SnapshotServer:
    """获取全局快照服务实例"""
    global _snapshot_server
    if _snapshot_server is None:
        _snapshot_server = SnapshotServer()
    return _snapshot_server


async def start_snapshot_server():
    """启动快照服务"""
    global _snapshot_server
    if _snapshot_server is None:
        _snapshot_server = SnapshotServer()
    
    await _snapshot_server.start()
    return _snapshot_server


if __name__ == "__main__":
    # 测试代码
    async def test():
        server = await start_snapshot_server()
        logger.info(f"快照服务测试: http://localhost:8080/snap/TEST-001")
        
        # 保持运行
        await asyncio.sleep(3600)
    
    asyncio.run(test())
