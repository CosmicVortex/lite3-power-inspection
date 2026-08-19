#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3电力巡检演示系统 - 增强版

支持无模型环境下的完整演示流程：
1. 模拟模式：使用模拟数据生成器进行演示
2. 真实模式：使用真实模型进行推理（需模型文件）
3. 混合模式：部分模块使用模拟数据，部分使用真实数据
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path
from loguru import logger
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.gateway.udp_controller import UDPMotionController
from src.gateway.ptz_controller import PtzController
from src.gateway.websocket_client import WebSocketGateway
from src.perception.yolo_detector import YOLODetector
from src.perception.unet_segmentor import UNetSegmentor
from src.perception.temperature_monitor import TemperatureMonitor
from src.services.simulation_generator import SimulationDataGenerator
from src.services.snapshot_server import SnapshotServer, start_snapshot_server


class DemoMode:
    """演示模式枚举"""
    REAL = "real"           # 真实模式 - 使用真实模型
    SIMULATION = "simulation"  # 模拟模式 - 使用模拟数据
    HYBRID = "hybrid"       # 混合模式 - 部分模拟


async def run_demo(mode: str = DemoMode.SIMULATION, config: dict = None):
    """运行演示模式
    
    Args:
        mode: 演示模式 (real/simulation/hybrid)
        config: 配置字典
    """
    logger.info(f"启动演示模式: {mode}")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 初始化组件
    udp_controller = UDPMotionController()
    ptz_controller = PtzController()
    websocket = WebSocketGateway()
    generator = SimulationDataGenerator(mode=mode)
    
    # 启动快照服务
    snapshot_server = await start_snapshot_server()
    
    # 连接所有模块
    logger.info("连接各模块...")
    udp_controller.connect()
    udp_controller.start_heartbeat()
    ptz_controller.login()
    await websocket.connect()
    
    logger.info("所有模块连接成功")
    
    try:
        # 演示流程
        await _demo_stand_up(udp_controller)
        await asyncio.sleep(2)
        
        await _demo_ptz_scan(ptz_controller)
        await asyncio.sleep(1)
        
        await _demo_crack_detection(generator, websocket, snapshot_server)
        await asyncio.sleep(2)
        
        await _demo_temperature_monitor(generator, websocket)
        await asyncio.sleep(2)
        
        await _demo_move_forward(udp_controller)
        await asyncio.sleep(2)
        
        await _demo_return(udp_controller)
        await asyncio.sleep(2)
        
        await _demo_stand_down(udp_controller)
        
        logger.info("演示完成")
        
    except Exception as e:
        logger.error(f"演示过程中出错: {e}")
    finally:
        # 清理资源
        await _cleanup(udp_controller, ptz_controller, websocket)


async def _demo_stand_up(controller: UDPMotionController):
    """演示：机器狗起立"""
    logger.info("▶ 演示：机器狗起立")
    controller.stand_up()
    await asyncio.sleep(3)
    logger.info("✓ 机器狗起立完成")


async def _demo_ptz_scan(ptz: PtzController):
    """演示：云台扫描"""
    logger.info("▶ 演示：云台扫描")
    for angle in range(-45, 46, 15):
        ptz.set_angle(yaw=angle)
        await asyncio.sleep(0.3)
    logger.info("✓ 云台扫描完成")


async def _demo_crack_detection(generator, websocket, snapshot_server):
    """演示：裂缝检测"""
    logger.info("▶ 演示：裂缝检测")
    
    # 生成模拟数据
    data = generator.generate_crack_detection("WP001")
    
    # 上报数据
    await websocket.send_message(data["type"], data["payload"])
    
    logger.info(f"✓ 裂缝检测完成: {data['payload']['measurements']['width_mm']}mm")
    logger.info(f"  快照URL: {data['payload']['snapshot_url']}")


async def _demo_temperature_monitor(generator, websocket):
    """演示：温度监测"""
    logger.info("▶ 演示：温度监测")
    
    # 生成模拟数据（模拟温度上升）
    for i in range(5):
        data = generator.generate_temperature_alert("WP004")
        level = data['payload']['alert_level']
        temp = data['payload']['temperature']['max_c']
        
        await websocket.send_message(data["type"], data["payload"])
        logger.info(f"  温度: {temp}℃, 等级: {level}")
        
        await asyncio.sleep(1)
    
    logger.info("✓ 温度监测完成")


async def _demo_move_forward(controller: UDPMotionController):
    """演示：向前移动"""
    logger.info("▶ 演示：向前移动")
    controller.set_velocity(0.3, 0.0, 0.0)
    await asyncio.sleep(2)
    controller.set_velocity(0, 0, 0)
    logger.info("✓ 移动完成")


async def _demo_return(controller: UDPMotionController):
    """演示：返回起点"""
    logger.info("▶ 演示：返回起点")
    controller.set_velocity(-0.3, 0.0, 0.0)
    await asyncio.sleep(2)
    controller.set_velocity(0, 0, 0)
    logger.info("✓ 返回完成")


async def _demo_stand_down(controller: UDPMotionController):
    """演示：机器狗趴下"""
    logger.info("▶ 演示：机器狗趴下")
    controller.stand_down()
    await asyncio.sleep(2)
    logger.info("✓ 机器狗趴下完成")


async def _cleanup(udp_controller, ptz_controller, websocket):
    """清理资源"""
    logger.info("清理资源...")
    udp_controller.stop_heartbeat()
    ptz_controller.logout()
    await websocket.disconnect()
    logger.info("✓ 清理完成")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="绝影Lite3电力巡检演示系统")
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
        "data/logs/app_{time:YYYY-MM-DD}.log",
        level=args.log_level,
        rotation="00:00",
        retention="7 days"
    )
    
    logger.info("=" * 60)
    logger.info("绝影Lite3电力巡检演示系统")
    logger.info(f"演示模式: {args.mode}")
    logger.info("=" * 60)
    
    # 检查模型文件
    model_path = "models/yolov8s-crack.trt"
    if args.mode == "real" and not Path(model_path).exists():
        logger.warning(f"模型文件不存在: {model_path}")
        logger.warning("自动切换到模拟模式")
        args.mode = "simulation"
    
    # 运行演示
    asyncio.run(run_demo(mode=args.mode))


if __name__ == "__main__":
    main()
