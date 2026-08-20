#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监测平台启动脚本 - 增强版

支持：
1. 启动前自动检查依赖
2. 启动监测平台服务
3. 生成诊断报告

用法:
  python3 scripts/start_monitor.py                    # 启动监测平台
  python3 scripts/start_monitor.py --diagnostic       # 先运行诊断
  python3 scripts/start_monitor.py --port 8080        # 指定端口
  python3 scripts/start_monitor.py --host 0.0.0.0     # 指定主机
"""

import sys
import asyncio
from pathlib import Path
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_dependencies():
    """检查必需依赖"""
    logger.info("检查Python依赖...")
    
    required = {
        "loguru": "日志管理",
        "fastapi": "Web框架",
        "uvicorn": "ASGI服务器",
        "websockets": "WebSocket通信",
        "pydantic": "数据验证",
        "requests": "HTTP请求",
        "yaml": "配置解析",
    }
    
    missing = []
    for module, purpose in required.items():
        try:
            __import__(module)
            logger.debug(f"  ✓ {module} ({purpose})")
        except ImportError:
            logger.error(f"  ✗ {module} ({purpose}) - 缺失")
            missing.append(module)
    
    if missing:
        logger.error(f"缺少依赖: {', '.join(missing)}")
        logger.info("请运行: pip install -r requirements.txt")
        return False
    
    logger.info("所有依赖检查通过")
    return True


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="绝影Lite3监测平台")
    parser.add_argument("--diagnostic", action="store_true", help="启动前运行环境诊断")
    parser.add_argument("--port", type=int, default=8000, help="HTTP端口 (默认: 8000)")
    parser.add_argument("--ws-port", type=int, default=8765, help="WebSocket端口 (默认: 8765)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    
    args = parser.parse_args()
    
    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    logger.add(
        "data/logs/monitor_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="00:00",
        retention="7 days"
    )
    
    logger.info("=" * 60)
    logger.info("绝影Lite3 监测平台启动")
    logger.info("=" * 60)
    
    # 运行诊断
    if args.diagnostic:
        logger.info("运行环境诊断...")
        from scripts.detect_environment import main as run_diagnostic
        run_diagnostic()
    
    # 检查依赖
    if not check_dependencies():
        logger.error("依赖检查失败，退出")
        sys.exit(1)
    
    # 启动服务
    from monitor_platform.server import app, monitor
    
    logger.info(f"HTTP服务: http://{args.host}:{args.port}")
    logger.info(f"WebSocket: ws://{args.host}:{args.ws_port}/ws")
    logger.info("")
    logger.info("按 Ctrl+C 停止服务")
    logger.info("=" * 60)
    
    import uvicorn
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        ws_port=args.ws_port,
        log_level="info"
    )


if __name__ == "__main__":
    asyncio.run(main())
