#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3电力巡检演示系统 - 增强版

支持多种演示模式：
1. simulation: AI识别模拟，本体数据真实
2. real: AI识别真实，本体数据真实
3. hybrid: 混合模式（默认）

新特性：
- 本体数据（电池、位置、关节、温度）使用物理模型生成真实值
- AI识别数据可选择模拟或真实推理
- 视频流转发功能
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import asyncio
from loguru import logger
from datetime import datetime

from src.gateway.udp_controller import UDPMotionController
from src.gateway.ptz_controller import PtzController
from src.gateway.websocket_client import WebSocketGateway
from src.services.simulation_generator import SimulationDataGenerator
from src.services.real_body_data import RealBodyData
from src.services.snapshot_server import SnapshotServer, start_snapshot_server
from src.services.video_stream_forwarder import forward_video_streams


class DemoMode:
    """演示模式枚举"""
    REAL = "real"           # 真实模式 - 使用真实模型
    SIMULATION = "simulation"  # 模拟模式 - AI模拟，本体真实
    HYBRID = "hybrid"       # 混合模式


async def run_demo(mode: str = DemoMode.SIMULATION, config: dict = None, ws_url: str = None):
    """运行演示模式"""
    logger.info(f"启动演示模式: {mode}")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    logger.info("演示说明:")
    logger.info("  - AI识别数据: 根据模式选择模拟或真实")
    logger.info("  - 本体状态数据: 始终使用物理模型生成（电池、位置、关节等）")
    logger.info("  - 视频流: 从RTSP相机转发到监测平台")
    logger.info("=" * 60)
    
    # 初始化组件
    udp_controller = UDPMotionController()
    ptz_controller = PtzController()
    
    # WebSocket地址
    if ws_url:
        websocket = WebSocketGateway(server_url=ws_url)
        logger.info(f"使用指定WebSocket地址: {ws_url}")
    else:
        websocket = WebSocketGateway()
    
    # AI数据生成器
    generator = SimulationDataGenerator(mode=mode)
    
    # 真实本体数据生成器
    body_data = RealBodyData()
    
    # 启动快照服务
    snapshot_server = await start_snapshot_server()
    
    # 连接所有模块
    logger.info("连接各模块...")
    udp_controller.connect()
    udp_controller.start_heartbeat()
    ptz_controller.login()
    await websocket.connect()
    
    # 启动视频流转发（后台任务）
    video_task = asyncio.create_task(
        forward_video_streams(ws_url or "ws://192.168.1.103:8765/ws")
    )
    
    # 启动心跳任务
    heartbeat_task = asyncio.create_task(_send_heartbeat(websocket, body_data))
    
    logger.info("所有模块连接成功")
    logger.info("")
    
    try:
        # 演示流程
        await _demo_stand_up(udp_controller, body_data)
        await asyncio.sleep(2)
        
        await _demo_ptz_scan(ptz_controller, body_data)
        await asyncio.sleep(1)
        
        await _demo_crack_detection(generator, websocket, snapshot_server, body_data)
        await asyncio.sleep(2)
        
        await _demo_temperature_monitor(generator, websocket, body_data)
        await asyncio.sleep(2)
        
        await _demo_move_forward(udp_controller, body_data)
        await asyncio.sleep(2)
        
        await _demo_return(udp_controller, body_data)
        await asyncio.sleep(2)
        
        await _demo_stand_down(udp_controller, body_data)
        
        logger.info("演示完成")
        
    except Exception as e:
        logger.error(f"演示过程中出错: {e}")
    finally:
        # 停止后台任务
        heartbeat_task.cancel()
        video_task.cancel()
        
        # 清理资源
        await _cleanup(udp_controller, ptz_controller, websocket, snapshot_server)


async def _send_heartbeat(websocket: WebSocketGateway, body_data: RealBodyData):
    """定期发送心跳包"""
    try:
        while True:
            await asyncio.sleep(1)  # 每秒发送一次
            heartbeat = body_data.simulate_heartbeat()
            await websocket.send_message(heartbeat["type"], heartbeat["payload"])
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"心跳发送失败: {e}")


async def _demo_stand_up(controller: UDPMotionController, body_data: RealBodyData):
    """演示：机器狗起立"""
    logger.info("▶ 演示：机器狗起立")
    controller.stand_up()
    body_data.status = "stand"
    
    status = body_data.get_system_status()
    await asyncio.sleep(3)
    
    logger.info("✓ 机器狗起立完成")
    logger.info(f"  当前状态: 电量={status['battery']:.1f}%, 位置=({status['position']['x']:.2f}, {status['position']['y']:.2f})")


async def _demo_ptz_scan(ptz: PtzController, body_data: RealBodyData):
    """演示：云台扫描"""
    logger.info("▶ 演示：云台扫描")
    for angle in range(-45, 46, 15):
        ptz.set_angle(yaw=angle)
        body_data.update_ptz(yaw=angle)
        await asyncio.sleep(0.3)
    logger.info("✓ 云台扫描完成")


async def _demo_crack_detection(generator, websocket, snapshot_server, body_data: RealBodyData):
    """演示：裂缝检测"""
    logger.info("▶ 演示：裂缝检测")
    
    data = generator.generate_crack_detection("WP001")
    body_data.waypoint = "WP001"
    body_data.update_position(0.1, 0.0, 0.0)
    
    await websocket.send_message(data["type"], data["payload"])
    
    logger.info(f"✓ 裂缝检测完成: {data['payload']['measurements']['width_mm']}mm")
    logger.info(f"  快照URL: {data['payload']['snapshot_url']}")
    logger.info(f"  当前电量: {body_data.battery:.1f}%")


async def _demo_temperature_monitor(generator, websocket, body_data: RealBodyData):
    """演示：温度监测"""
    logger.info("▶ 演示：温度监测")
    
    body_data.waypoint = "WP004"
    body_data.update_position(0.0, 0.1, 0.0)
    
    base_temp = 40.0
    for i in range(5):
        temp = base_temp + i * 2.0
        alert_level = "warning" if temp >= 45 else ("critical" if temp >= 50 else "normal")
        
        body_data.cpu_temp = temp
        
        data = generator.generate_temperature_alert("WP004")
        data['payload']['temperature']['max_c'] = temp
        data['payload']['alert_level'] = alert_level
        
        await websocket.send_message(data["type"], data["payload"])
        logger.info(f"  温度: {temp}℃, 等级: {alert_level}")
        
        await asyncio.sleep(1)
    
    logger.info("✓ 温度监测完成")


async def _demo_move_forward(controller: UDPMotionController, body_data: RealBodyData):
    """演示：向前移动"""
    logger.info("▶ 演示：向前移动")
    controller.set_velocity(0.3, 0.0, 0.0)
    body_data.status = "moving"
    
    for i in range(5):
        body_data.update_position(0.1, 0.0, 0.0)
        body_data.update_joints("walking_forward")
        await asyncio.sleep(0.5)
    
    controller.set_velocity(0, 0, 0)
    body_data.status = "idle"
    logger.info("✓ 移动完成")
    logger.info(f"  当前位置: ({body_data.position['x']:.2f}, {body_data.position['y']:.2f})")


async def _demo_return(controller: UDPMotionController, body_data: RealBodyData):
    """演示：返回起点"""
    logger.info("▶ 演示：返回起点")
    controller.set_velocity(-0.3, 0.0, 0.0)
    body_data.status = "moving"
    
    for i in range(5):
        body_data.update_position(-0.1, 0.0, 0.0)
        body_data.update_joints("walking_backward")
        await asyncio.sleep(0.5)
    
    controller.set_velocity(0, 0, 0)
    body_data.status = "idle"
    logger.info("✓ 返回完成")


async def _demo_stand_down(controller: UDPMotionController, body_data: RealBodyData):
    """演示：机器狗趴下"""
    logger.info("▶ 演示：机器狗趴下")
    controller.stand_down()
    body_data.status = "stand"
    await asyncio.sleep(2)
    logger.info("✓ 机器狗趴下完成")


async def _cleanup(udp_controller, ptz_controller, websocket, snapshot_server=None):
    """清理资源"""
    logger.info("清理资源...")
    udp_controller.stop_heartbeat()
    ptz_controller.logout()
    await websocket.disconnect()
    if snapshot_server:
        snapshot_server.stop()
    logger.info("清理完成")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="绝影Lite3电力巡检演示")
    parser.add_argument(
        "--mode",
        choices=["real", "simulation", "hybrid"],
        default="simulation",
        help="演示模式: real(真实AI), simulation(模拟AI+真实本体), hybrid(混合)"
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
        "--ws-url",
        default=None,
        help="WebSocket服务器地址（覆盖配置文件）"
    )
    parser.add_argument(
        "--no-video",
        action="store_true",
        help="禁用视频流转发"
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
    
    # 运行演示
    asyncio.run(run_demo(mode=args.mode, ws_url=args.ws_url))


if __name__ == "__main__":
    main()
