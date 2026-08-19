#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示模式启动脚本

用法:
  python3 scripts/run_demo.py                    # 默认模拟模式
  python3 scripts/run_demo.py --mode real        # 真实模式（需模型）
  python3 scripts/run_demo.py --mode hybrid      # 混合模式
  python3 scripts/run_demo.py --log-level DEBUG  # 详细日志
"""

import sys
import asyncio
from pathlib import Path
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.main import run_demo, DemoMode


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="绝影Lite3电力巡检演示")
    parser.add_argument(
        "--mode", 
        choices=["real", "simulation", "hybrid"],
        default="simulation",
        help="演示模式: real(真实), simulation(模拟), hybrid(混合)"
    )
    parser.add_argument(
        "--config",
        default="config/inspection_config.yaml",
        help="配置文件路径"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别"
    )
    
    args = parser.parse_args()
    
    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        level=args.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    logger.add(
        "data/logs/demo_{time:YYYY-MM-DD}.log",
        level=args.log_level,
        rotation="00:00",
        retention="7 days"
    )
    
    logger.info("=" * 60)
    logger.info("绝影Lite3电力巡检演示系统")
    logger.info(f"演示模式: {args.mode}")
    logger.info("=" * 60)
    
    # 运行演示
    asyncio.run(run_demo(mode=args.mode))


if __name__ == "__main__":
    main()
