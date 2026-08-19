#!/usr/bin/env python3
"""
主入口：绝影Lite3电力巡检演示
"""

import argparse
import asyncio
import sys
from pathlib import Path
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="绝影Lite3电力巡检演示系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行演示模式
  python3 main.py --demo
  
  # 运行测试模式
  python3 main.py --test
  
  # 指定配置文件
  python3 main.py --config config/inspection_config.yaml
        """
    )
    
    parser.add_argument(
        "--demo", 
        action="store_true", 
        help="运行演示模式"
    )
    parser.add_argument(
        "--test", 
        action="store_true", 
        help="运行测试模式"
    )
    parser.add_argument(
        "--config", 
        type=str,
        default="config/inspection_config.yaml",
        help="配置文件路径"
    )
    parser.add_argument(
        "--log-level", 
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别"
    )
    
    return parser.parse_args()


async def run_demo(config: dict):
    """运行演示模式"""
    logger.info("启动演示模式")
    
    # TODO: 实现演示流程
    # 1. 连接云台
    # 2. 执行巡检流程
    # 3. 上报数据
    # 4. 结束演示
    
    logger.info("演示完成")


async def run_test(config: dict):
    """运行测试模式"""
    logger.info("启动测试模式")
    
    # TODO: 实现测试流程
    # 1. 单元测试
    # 2. 集成测试
    # 3. 性能测试
    
    logger.info("测试完成")


def main():
    """主函数"""
    args = parse_args()
    
    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        level=args.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    logger.add(
        "data/logs/app_{time:YYYY-MM-DD}.log",
        level=args.log_level,
        rotation="00:00",
        retention="7 days"
    )
    
    logger.info("="*50)
    logger.info("绝影Lite3电力巡检演示系统")
    logger.info("="*50)
    
    # 加载配置
    try:
        import yaml
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"配置文件加载成功: {args.config}")
    except Exception as e:
        logger.error(f"配置文件加载失败: {e}")
        sys.exit(1)
    
    # 运行模式
    if args.demo:
        asyncio.run(run_demo(config))
    elif args.test:
        asyncio.run(run_test(config))
    else:
        print("请使用 --demo 或 --test 参数运行")
        sys.exit(1)


if __name__ == "__main__":
    main()
