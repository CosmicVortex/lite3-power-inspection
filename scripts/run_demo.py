#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示模式启动脚本 - 增强版

支持：
1. 启动前自动检查依赖
2. 多种演示模式（simulation/real/hybrid）
3. 自动生成诊断报告

用法:
  python3 scripts/run_demo.py                    # 默认模拟模式
  python3 scripts/run_demo.py --mode real        # 真实模式（需模型）
  python3 scripts/run_demo.py --mode hybrid      # 混合模式
  python3 scripts/run_demo.py --log-level DEBUG  # 详细日志
  python3 scripts/run_demo.py --diagnostic       # 启动前诊断
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
        "numpy": "数值计算",
        "cv2": "图像处理",
        "websockets": "WebSocket通信",
        "requests": "HTTP请求",
        "yaml": "配置解析",
    }
    
    optional = {
        "torch": "深度学习框架（真实模式）",
        "tensorrt": "GPU推理加速（真实模式）",
        "onnx": "模型格式（真实模式）",
    }
    
    missing = []
    for module, purpose in required.items():
        try:
            __import__(module)
            logger.debug(f"  ✓ {module} ({purpose})")
        except ImportError:
            logger.error(f"  ✗ {module} ({purpose}) - 缺失")
            missing.append(module)
    
    # 检查可选依赖
    gpu_available = True
    for module, purpose in optional.items():
        try:
            __import__(module)
            logger.debug(f"  ✓ {module} ({purpose})")
        except ImportError:
            logger.warning(f"  ⚠ {module} ({purpose}) - 未安装，将使用模拟模式")
            gpu_available = False
    
    if missing:
        logger.error(f"缺少必需依赖: {', '.join(missing)}")
        logger.info("请运行: pip install -r requirements.txt")
        return False, False
    
    return True, gpu_available


def check_models(gpu_available):
    """检查模型文件"""
    if not gpu_available:
        logger.info("GPU环境不可用，使用模拟模式")
        return "simulation"
    
    models_dir = Path("models")
    if not models_dir.exists():
        logger.warning("models目录不存在，使用模拟模式")
        return "simulation"
    
    trt_files = list(models_dir.glob("*.trt"))
    onnx_files = list(models_dir.glob("*.onnx"))
    
    if trt_files or onnx_files:
        logger.info(f"发现 {len(trt_files)} 个TRT模型和 {len(onnx_files)} 个ONNX模型")
        return "real"
    else:
        logger.warning("未找到模型文件，使用模拟模式")
        return "simulation"


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="绝影Lite3电力巡检演示")
    parser.add_argument(
        "--mode",
        choices=["real", "simulation", "hybrid"],
        default=None,
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
    parser.add_argument(
        "--diagnostic",
        action="store_true",
        help="启动前运行环境诊断"
    )
    parser.add_argument(
        "--ws-url",
        default=None,
        help="WebSocket服务器地址（覆盖配置文件）"
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
    logger.info("绝影Lite3 电力巡检演示系统")
    logger.info("=" * 60)
    
    # 运行诊断
    if args.diagnostic:
        logger.info("运行环境诊断...")
        from scripts.detect_environment import main as run_diagnostic
        run_diagnostic()
    
    # 检查依赖
    deps_ok, gpu_available = check_dependencies()
    if not deps_ok:
        logger.error("依赖检查失败，退出")
        sys.exit(1)
    
    # 确定演示模式
    if args.mode:
        demo_mode = args.mode
    else:
        demo_mode = check_models(gpu_available)
    
    logger.info(f"演示模式: {demo_mode}")
    logger.info("")
    
    # 运行演示
    from src.app.main import run_demo
    ws_url = args.ws_url if args.ws_url else None
    await run_demo(mode=demo_mode, ws_url=ws_url)


if __name__ == "__main__":
    asyncio.run(main())
