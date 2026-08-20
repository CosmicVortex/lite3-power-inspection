#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3 12分钟演示流程脚本

该脚本实现了完整的12分钟演示流程，适用于国赛演示。
演示分为三个阶段：开场、检测演示、总结。

用法:
    python3 scripts/demo_12min.py [--mode simulation|real|hybrid] [--fast]
"""

import sys
import asyncio
import time
from pathlib import Path
from datetime import datetime
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.simulation_generator import SimulationDataGenerator
from src.gateway.websocket_client import WebSocketGateway
from src.gateway.ptz_controller import PtzController
from src.gateway.udp_controller import UDPMotionController
from src.perception.temperature_monitor import TemperatureMonitor
import numpy as np


class Demo12Min:
    """12分钟演示流程"""
    
    def __init__(self, mode="simulation"):
        self.mode = mode
        self.generator = SimulationDataGenerator(mode=mode)
        self.websocket = WebSocketGateway()
        self.ptz = PtzController()
        self.udp = UDPMotionController()
        self.temp_monitor = TemperatureMonitor()
        
        # 航点配置
        self.waypoints = [
            {"id": "WP001", "pos": [0.5, 0.5, 0.0], "ptz": (45, -30)},
            {"id": "WP002", "pos": [1.0, 0.5, 0.0], "ptz": (90, -25)},
            {"id": "WP003", "pos": [1.5, 0.5, 0.0], "ptz": (135, -45)},
            {"id": "WP004", "pos": [0.5, 1.0, 0.0], "ptz": (180, -45)},
            {"id": "WP005", "pos": [1.0, 1.0, 0.0], "ptz": (225, -45)},
        ]
        
    async def run(self, fast=False):
        """运行完整演示"""
        speed = 0.25 if fast else 1.0
        
        logger.info("=" * 70)
        logger.info("绝影Lite3 12分钟电力巡检演示")
        logger.info(f"模式: {self.mode}")
        logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 70)
        logger.info("")
        
        # 连接所有模块
        await self._connect_all()
        
        try:
            # 阶段一：开场（0-90秒）
            await self._phase1_opening(speed)
            
            # 阶段二：检测演示（90-570秒）
            await self._phase2_inspection(speed)
            
            # 阶段三：总结（570-720秒）
            await self._phase3_summary(speed)
            
            logger.info("")
            logger.info("=" * 70)
            logger.info("✅ 演示完成！")
            logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"演示过程中出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self._disconnect_all()
    
    async def _connect_all(self):
        """连接所有模块"""
        logger.info("连接各模块...")
        
        try:
            self.udp.connect()
            self.udp.start_heartbeat()
            logger.info("  ✓ UDP控制器已连接")
        except Exception as e:
            logger.warning(f"  ⚠ UDP连接失败: {e}（模拟模式继续）")
        
        try:
            self.ptz.login()
            logger.info("  ✓ 云台控制器已连接")
        except Exception as e:
            logger.warning(f"  ⚠ 云台连接失败: {e}（使用模拟数据）")
        
        try:
            await self.websocket.connect()
            logger.info("  ✓ WebSocket已连接")
        except Exception as e:
            logger.warning(f"  ⚠ WebSocket连接失败: {e}（仅本地演示）")
    
    async def _disconnect_all(self):
        """断开所有模块"""
        logger.info("断开各模块...")
        
        try:
            self.udp.stop_heartbeat()
        except:
            pass
        
        try:
            self.ptz.logout()
        except:
            pass
        
        try:
            await self.websocket.disconnect()
        except:
            pass
    
    async def _sleep(self, seconds, speed=1.0):
        """可调节速度的延时"""
        await asyncio.sleep(seconds / speed)
    
    async def _phase1_opening(self, speed):
        """阶段一：开场（0-90秒）"""
        logger.info("")
        logger.info("▶ 阶段一：开场介绍（0:00-1:30）")
        logger.info("-" * 70)
        
        # 0-30秒：待机亮相
        logger.info("[0:00] 机器狗待机亮相")
        await self._sleep(30, speed)
        
        # 30-60秒：自我介绍
        logger.info("[0:30] 播放开场介绍语音")
        await self._sleep(30, speed)
        
        # 60-90秒：设备自检
        logger.info("[1:00] 设备自检流程")
        await self._do_self_check(speed)
        
        logger.info("✓ 阶段一完成")
    
    async def _do_self_check(self, speed):
        """执行设备自检"""
        logger.info("  执行自检...")
        
        # 云台俯仰自检
        logger.info("  - 云台俯仰自检")
        for angle in range(-30, 31, 10):
            self.ptz.set_angle(pitch=angle)
            await self._sleep(0.5, speed)
        
        # 云台水平自检
        logger.info("  - 云台水平自检")
        for angle in range(-45, 46, 15):
            self.ptz.set_angle(yaw=angle)
            await self._sleep(0.3, speed)
        
        # 相机变焦自检
        logger.info("  - 相机变焦自检")
        for zoom in [1, 5, 10, 5, 1]:
            self.ptz.set_zoom(zoom)
            await self._sleep(0.5, speed)
        
        logger.info("  ✓ 自检完成")
        
        # 上报自检状态
        heartbeat = self.generator.generate_heartbeat()
        heartbeat["payload"]["self_check"] = True
        heartbeat["payload"]["self_check_status"] = "PASSED"
        await self.websocket.send_message(heartbeat["type"], heartbeat["payload"])
    
    async def _phase2_inspection(self, speed):
        """阶段二：检测演示（90-570秒）"""
        logger.info("")
        logger.info("▶ 阶段二：检测演示（1:30-9:30）")
        logger.info("-" * 70)
        
        # 裂缝检测（2:00-4:00）
        await self._inspect_crack(speed)
        
        # 蜂窝麻面检测（4:00-6:00）
        await self._inspect_honeycomb(speed)
        
        # 转场（6:00-6:30）
        await self._transition_to_temp(speed)
        
        # 温度监测（6:30-9:30）
        await self._inspect_temperature(speed)
    
    async def _inspect_crack(self, speed):
        """裂缝检测演示"""
        logger.info("")
        logger.info("  ▶ 裂缝检测演示（2:00-4:00）")
        logger.info("-" * 70)
        
        # 移动到裂缝检测区
        logger.info("  [2:00] 移动到裂缝检测区")
        await self._move_to_waypoint("WP001", speed)
        
        # 云台对准
        logger.info("  [2:15] 云台对准检测位置")
        self.ptz.set_angle(yaw=45, pitch=-30)
        await self._sleep(5, speed)
        
        # 广角扫描
        logger.info("  [2:20] 广角扫描发现目标")
        await self._sleep(10, speed)
        
        # 10倍变焦
        logger.info("  [2:30] 10倍变焦精细检测")
        self.ptz.set_zoom(10)
        await self._sleep(10, speed)
        
        # 检测并上报
        logger.info("  [2:40] 执行裂缝检测")
        crack_data = self.generator.generate_crack_detection("WP001")
        crack_data["payload"]["waypoint_id"] = "WP001"
        await self.websocket.send_message(crack_data["type"], crack_data["payload"])
        
        logger.info(f"  ✓ 检测到裂缝: {crack_data['payload']['measurements']['width_mm']}mm")
        
        # 停留展示
        logger.info("  [3:00] 停留展示检测结果")
        await self._sleep(30, speed)
        
        logger.info("  ✓ 裂缝检测演示完成")
    
    async def _inspect_honeycomb(self, speed):
        """蜂窝麻面检测演示"""
        logger.info("")
        logger.info("  ▶ 蜂窝麻面检测演示（4:00-6:00）")
        logger.info("-" * 70)
        
        # 移动到蜂窝麻面区
        logger.info("  [4:00] 移动到蜂窝麻面区")
        await self._move_to_waypoint("WP002", speed)
        
        # 云台对准
        logger.info("  [4:15] 云台对准检测位置")
        self.ptz.set_angle(yaw=90, pitch=-25)
        await self._sleep(5, speed)
        
        # 5倍变焦
        logger.info("  [4:20] 5倍变焦检测")
        self.ptz.set_zoom(5)
        await self._sleep(10, speed)
        
        # 检测并上报（使用裂缝数据作为示例）
        logger.info("  [4:30] 执行蜂窝麻面检测")
        crack_data = self.generator.generate_crack_detection("WP002")
        crack_data["type"] = "inspection_result"
        crack_data["payload"]["defect_type"] = "honeycomb"
        crack_data["payload"]["waypoint_id"] = "WP002"
        crack_data["payload"]["measurements"]["porosity"] = 12.5
        await self.websocket.send_message(crack_data["type"], crack_data["payload"])
        
        logger.info(f"  ✓ 检测到蜂窝麻面: 孔隙率12.5%")
        
        # 停留展示
        logger.info("  [5:00] 停留展示检测结果")
        await self._sleep(30, speed)
        
        logger.info("  ✓ 蜂窝麻面检测演示完成")
    
    async def _transition_to_temp(self, speed):
        """转到温升监测区"""
        logger.info("")
        logger.info("  ▶ 转场（6:00-6:30）")
        logger.info("-" * 70)
        
        logger.info("  [6:00] 移动到温升监测区")
        await self._move_to_waypoint("WP004", speed)
        
        logger.info("  ✓ 转场完成")
    
    async def _inspect_temperature(self, speed):
        """温度监测演示"""
        logger.info("")
        logger.info("  ▶ 温度监测演示（6:30-9:30）")
        logger.info("-" * 70)
        
        # 云台对准
        logger.info("  [6:30] 云台对准温升区")
        self.ptz.set_angle(yaw=135, pitch=-45)
        await self._sleep(5, speed)
        
        # 切换热成像
        logger.info("  [6:40] 切换热成像模式")
        await self._sleep(10, speed)
        
        # 模拟温度上升
        logger.info("  [6:50] 开始温度监测（模拟温度上升）")
        temperatures = [35, 38, 41, 44, 46, 48, 50, 52]
        
        for i, temp in enumerate(temperatures):
            # 生成温度数据
            frame = np.full((512, 640), float(temp), dtype=np.float32)
            result = self.temp_monitor.check_temperature(frame)
            
            # 上报温度数据
            temp_data = self.generator.generate_temperature_alert("WP004")
            temp_data["payload"]["temperature"]["max_c"] = temp
            temp_data["payload"]["temperature"]["mean_c"] = temp
            temp_data["payload"]["alert_level"] = result["status"]
            temp_data["payload"]["waypoint_id"] = "WP004"
            
            await self.websocket.send_message(temp_data["type"], temp_data["payload"])
            
            logger.info(f"  [6:50+{i*10}s] 温度: {temp}℃, 状态: {result['status']}")
            
            # 根据状态显示不同效果
            if result["status"] == "WARN":
                logger.info("    ⚠️  触发WARN预警（45℃）")
            elif result["status"] == "CRITICAL":
                logger.info("    🔴 触发CRITICAL告警（50℃）")
            
            await self._sleep(10, speed)
        
        logger.info("  ✓ 温度监测演示完成")
    
    async def _phase3_summary(self, speed):
        """阶段三：总结（9:30-12:00）"""
        logger.info("")
        logger.info("▶ 阶段三：总结致谢（9:30-12:00）")
        logger.info("-" * 70)
        
        # 轨迹回放
        logger.info("  [9:30] 轨迹回放展示")
        await self._show_trajectory(speed)
        
        # 数据汇总
        logger.info("  [10:30] 数据汇总展示")
        await self._show_summary(speed)
        
        # 返回起点
        logger.info("  [11:00] 返回起点")
        await self._move_to_waypoint("WP001", speed)
        
        # 待机谢幕
        logger.info("  [11:30] 待机谢幕")
        await self._sleep(30, speed)
        
        logger.info("✓ 阶段三完成")
    
    async def _show_trajectory(self, speed):
        """展示巡检轨迹"""
        logger.info("  展示巡检轨迹...")
        
        # 生成轨迹数据
        trajectory_data = {
            "type": "trajectory",
            "payload": {
                "waypoints_visited": ["WP001", "WP002", "WP004"],
                "total_distance": 3.5,
                "inspection_time": 540,
                "defects_found": 2,
                "alerts_triggered": 3
            }
        }
        
        await self.websocket.send_message(trajectory_data["type"], trajectory_data["payload"])
        logger.info("  ✓ 轨迹回放完成")
    
    async def _show_summary(self, speed):
        """展示数据汇总"""
        logger.info("  展示数据汇总...")
        
        # 生成汇总数据
        summary_data = {
            "type": "inspection_summary",
            "payload": {
                "total_waypoints": 5,
                "visited_waypoints": 3,
                "cracks_detected": 1,
                "honeycomb_detected": 1,
                "temperature_alerts": 2,
                "inspection_duration": 720,
                "battery_level": 85
            }
        }
        
        await self.websocket.send_message(summary_data["type"], summary_data["payload"])
        logger.info("  ✓ 数据汇总完成")
    
    async def _move_to_waypoint(self, waypoint_id, speed):
        """移动到指定航点"""
        waypoint = next((wp for wp in self.waypoints if wp["id"] == waypoint_id), None)
        if waypoint:
            logger.info(f"  移动到 {waypoint_id}: pos={waypoint['pos']}, ptz=({waypoint['ptz'][0]}°, {waypoint['ptz'][1]}°)")
            
            # 模拟移动
            try:
                self.udp.set_velocity(0.3, 0, 0)
                await self._sleep(3, speed)
                self.udp.set_velocity(0, 0, 0)
            except Exception as e:
                logger.warning(f"  ⚠ 运动控制失败: {e}（模拟模式继续）")
            
            # 设置云台角度
            try:
                self.ptz.set_angle(yaw=waypoint['ptz'][0], pitch=waypoint['ptz'][1])
                await self._sleep(2, speed)
            except Exception as e:
                logger.warning(f"  ⚠ 云台控制失败: {e}（模拟模式继续）")
        else:
            logger.warning(f"  ⚠ 未找到航点 {waypoint_id}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="绝影Lite3 12分钟演示流程")
    parser.add_argument(
        "--mode",
        choices=["simulation", "real", "hybrid"],
        default="simulation",
        help="演示模式"
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="快速演示（1/4速度）"
    )
    
    args = parser.parse_args()
    
    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )
    logger.add(
        "data/logs/demo_12min_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="00:00",
        retention="7 days"
    )
    
    # 运行演示
    demo = Demo12Min(mode=args.mode)
    asyncio.run(demo.run(fast=args.fast))


if __name__ == "__main__":
    main()
