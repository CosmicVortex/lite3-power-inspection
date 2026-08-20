#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3 监测平台 - 增强版
支持机器狗状态监控、运动控制和巡检数据接收
"""

import asyncio
import json
import time
import logging
import struct
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WS_HOST = "0.0.0.0"
WS_PORT = 8765
HTTP_PORT = 8000
MOTION_HOST = "192.168.1.103"
MOTION_PORT = 43893

CMD_STAND_UP = 0x21010202
CMD_STAND_DOWN = 0x21010203
CMD_EMERGENCY_STOP = 0x21020C0E
CMD_VELOCITY = 0x0103

app = FastAPI(title="绝影Lite3监测平台")

connections: List[WebSocket] = []
inspections: List[Dict] = []
alerts: List[Dict] = []

robot_status = {
    "battery": 100,
    "cpu_temp": 35.0,
    "gpu_load": 0,
    "memory_usage": 45,
    "status": "idle",
    "position": {"x": 0.0, "y": 0.0, "theta": 0.0},
    "yaw": 0.0,
    "pitch": 0.0,
    "zoom": 1,
    "mode": "manual",
    "waypoint": "WP001",
    "total_waypoints": 5,
    "completed_waypoints": 0,
    "uptime_seconds": 0,
    "last_heartbeat": 0
}

motion_sock = None


def send_udp_command(cmd: int, data: bytes = b''):
    global motion_sock
    try:
        if motion_sock is None:
            motion_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            motion_sock.settimeout(0.5)
        pkg = struct.pack('>I', cmd) + struct.pack('>H', len(data)) + data
        motion_sock.sendto(pkg, (MOTION_HOST, MOTION_PORT))
        logger.info(f"UDP: 0x{cmd:08X}")
    except Exception as e:
        logger.error(f"UDP失败: {e}")


async def control_motion(direction: str, speed: float = 0.5):
    vx, vy, vw = 0.0, 0.0, 0.0
    if direction == "forward": vy = -speed
    elif direction == "backward": vy = speed
    elif direction == "left": vx = -speed
    elif direction == "right": vx = speed
    elif direction == "rotate_left": vw = -speed
    elif direction == "rotate_right": vw = speed
    send_udp_command(CMD_VELOCITY, struct.pack('<fff', vx, vy, vw))
    robot_status["status"] = "moving"


@app.get("/", response_class=HTMLResponse)
async def root():
    return DASHBOARD_HTML


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)
    await websocket.send_json({"type": "robot_status", "data": robot_status})
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                await monitor.process_message(data, websocket)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in connections:
            connections.remove(websocket)


@app.post("/api/control/motion")
async def api_control_motion(direction: str, speed: float = 0.5):
    await control_motion(direction, speed)
    return {"status": "ok", "direction": direction}


@app.post("/api/control/stand_up")
async def api_control_stand_up():
    send_udp_command(CMD_STAND_UP)
    robot_status["status"] = "idle"
    return {"status": "ok"}


@app.post("/api/control/stand_down")
async def api_control_stand_down():
    send_udp_command(CMD_STAND_DOWN)
    robot_status["status"] = "idle"
    return {"status": "ok"}


@app.post("/api/control/emergency_stop")
async def api_control_emergency_stop():
    send_udp_command(CMD_EMERGENCY_STOP)
    robot_status["status"] = "idle"
    return {"status": "ok"}


class MonitorServer:
    def __init__(self):
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)

    async def handle_client(self, websocket: WebSocket):
        connections.append(websocket)
        await websocket.send_json({"type": "robot_status", "data": robot_status})
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.process_message(data, websocket)
        except Exception:
            pass
        finally:
            if websocket in connections:
                connections.remove(websocket)

    async def process_message(self, data: Dict, websocket: WebSocket):
        msg_type = data.get("type")
        timestamp = time.time()
        payload = data.get("payload", data.get("data", {}))
        device_id = data.get("deviceId", "LITE3-001")

        if msg_type == "inspection_result":
            result = {"id": f"INS_{int(timestamp*1000)}", "timestamp": timestamp,
                      "datetime": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                      "device_id": device_id, "data": payload}
            inspections.append(result)
            self.check_alerts(result)
            ui_data = self._convert_to_ui_format(result)
            await self.broadcast({"type": "inspection_result", "data": ui_data})

        elif msg_type == "temperature_alert":
            alert = {"id": f"ALT_{int(timestamp*1000)}", "type": "temperature",
                     "level": payload.get("alert_level", "WARN"), "timestamp": timestamp,
                     "datetime": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                     "device_id": device_id, "data": payload, "acknowledged": False}
            alerts.append(alert)
            await self.broadcast({"type": "temperature_alert", "data": alert})

        elif msg_type == "heartbeat":
            robot_status["last_heartbeat"] = timestamp
            await websocket.send_json({"type": "heartbeat_ack", "timestamp": timestamp})

        elif msg_type == "crack_alert":
            alert = {"id": f"CRACK_{int(timestamp*1000)}", "type": "crack",
                     "level": "WARNING", "timestamp": timestamp,
                     "datetime": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                     "device_id": device_id, "data": payload, "acknowledged": False}
            alerts.append(alert)
            await self.broadcast({"type": "crack_alert", "data": alert})

        elif msg_type == "system_status":
            for key in ["battery", "cpu_temp", "gpu_load", "memory_usage", "status", "waypoint", "position"]:
                if key in payload:
                    robot_status[key] = payload[key]
            await self.broadcast({"type": "robot_status", "data": robot_status})

    def _convert_to_ui_format(self, result: Dict) -> Dict:
        payload = result.get("data", {})
        crack_data = {"detected": False, "count": 0, "details": []}
        if payload.get("defect_type") == "crack":
            crack_data["detected"] = True
            crack_data["count"] = 1
        temp_data = payload.get("temperature", {})
        return {"crack": crack_data, "temperature": {"status": payload.get("alert_level", "NORMAL"),
                      "value": temp_data.get("max_c", 0) if temp_data else 0}}

    def check_alerts(self, result: Dict):
        data = result.get("data", {})
        temp_data = data.get("temperature", {})
        if temp_data.get("status") in ["WARN", "CRITICAL"]:
            alerts.append({"id": f"ALERT_{int(time.time()*1000)}", "type": "temperature",
                          "level": temp_data.get("status"), "value": temp_data.get("value"),
                          "timestamp": result["timestamp"], "datetime": result["datetime"],
                          "device_id": result["device_id"], "acknowledged": False})

    async def broadcast(self, message: Dict):
        if not connections: return
        for conn in connections[:]:
            try: await conn.send_json(message)
            except: connections.remove(conn)

    def get_stats(self) -> Dict:
        return {"connected_clients": len(connections), "total_inspections": len(inspections),
                "pending_alerts": len([a for a in alerts if not a.get("acknowledged")]),
                "total_alerts": len(alerts)}

    def get_robot_status(self) -> Dict:
        return robot_status

monitor = MonitorServer()

@app.get("/api/status")
async def get_status(): return monitor.get_stats()

@app.get("/api/robot/status")
async def get_robot_status(): return monitor.get_robot_status()

@app.get("/api/inspections")
async def get_inspections(limit: int = 100): return JSONResponse(inspections[-limit:])

@app.get("/api/alerts")
async def get_alerts(unacknowledged: bool = True):
    return JSONResponse([a for a in alerts if not a.get("acknowledged")] if unacknowledged else alerts)

@app.post("/api/alert/ack")
async def acknowledge_alert(alert_id: str):
    for alert in alerts:
        if alert.get("id") == alert_id:
            alert["acknowledged"] = True
            return {"status": "ok"}
    raise HTTPException(status_code=404)

@app.post("/api/demo/send")
async def send_demo():
    import random
    demo_data = {
        "type": "inspection_result", "deviceId": "LITE3-001",
        "payload": {
            "defect_type": "crack" if random.random() > 0.3 else None,
            "location": {"image_x": random.randint(100,500), "image_y": random.randint(100,400),
                        "world_x": round(random.uniform(0.5,2.0),2), "world_y": round(random.uniform(0.3,1.5),2)},
            "measurements": {"width_mm": round(random.uniform(0.1,1.0),2) if random.random()>0.3 else 0,
                            "length_mm": round(random.uniform(5.0,50.0),1), "pixel_precision": 0.019},
            "confidence": round(random.uniform(0.7,0.98),2),
            "temperature": {"status": random.choice(["NORMAL","NORMAL","WARN","CRITICAL"]),
                           "max_c": round(random.uniform(25.0,55.0),1)}
        }
    }
    class DummyWS: pass
    await monitor.process_message(demo_data, DummyWS())
    await monitor.process_message({
        "type": "system_status", "deviceId": "LITE3-001",
        "payload": {"battery": random.randint(60,95), "cpu_temp": round(random.uniform(35,55),1),
                   "gpu_load": random.randint(20,80), "memory_usage": random.randint(40,70),
                   "status": "inspecting", "waypoint": f"WP{random.randint(1,5):03d}",
                   "total_waypoints": 5, "completed_waypoints": random.randint(1,4)}
    }, DummyWS())
    return {"status": "ok"}

@app.post("/api/demo/send_status")
async def send_demo_status():
    import random
    status_data = {
        "type": "system_status", "deviceId": "LITE3-001",
        "payload": {"battery": random.randint(60,95), "cpu_temp": round(random.uniform(35,55),1),
                   "gpu_load": random.randint(20,80), "memory_usage": random.randint(40,70),
                   "status": random.choice(["idle","moving","inspecting"]),
                   "waypoint": f"WP{random.randint(1,5):03d}", "total_waypoints": 5,
                   "completed_waypoints": random.randint(1,4)}
    }
    class DummyWS: pass
    await monitor.process_message(status_data, DummyWS())
    return {"status": "ok"}


# ==================== 现代化UI设计 ====================
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>绝影Lite3 监测平台</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: rgba(30, 41, 59, 0.7);
            --bg-glass: rgba(255, 255, 255, 0.05);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --accent-cyan: #06b6d4;
            --accent-green: #10b981;
            --accent-orange: #f59e0b;
            --accent-red: #ef4444;
            --border-color: rgba(255, 255, 255, 0.1);
            --shadow-lg: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            --shadow-glow: 0 0 40px rgba(59, 130, 246, 0.15);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        /* 背景装饰 */
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: 
                radial-gradient(ellipse at 20% 20%, rgba(59, 130, 246, 0.15) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(139, 92, 246, 0.1) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, rgba(6, 182, 212, 0.05) 0%, transparent 70%);
            pointer-events: none;
            z-index: 0;
        }
        
        /* Header */
        .header {
            position: relative;
            z-index: 10;
            background: var(--bg-glass);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border-color);
            padding: 16px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header-left {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        
        .logo {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.4);
        }
        
        .header h1 {
            font-size: 20px;
            font-weight: 600;
            background: linear-gradient(135deg, var(--text-primary), var(--accent-cyan));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .header-status {
            display: flex;
            align-items: center;
            gap: 24px;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: var(--text-secondary);
        }
        
        .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--text-muted);
            transition: all 0.3s;
        }
        
        .dot.connected {
            background: var(--accent-green);
            box-shadow: 0 0 10px var(--accent-green);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.2); }
        }
        
        /* 主容器 */
        .container {
            position: relative;
            z-index: 1;
            display: grid;
            grid-template-columns: 1fr 400px;
            gap: 24px;
            padding: 24px 32px;
            max-width: 1920px;
            margin: 0 auto;
        }
        
        /* 卡片样式 */
        .panel {
            background: var(--bg-card);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 24px;
            box-shadow: var(--shadow-lg);
            transition: all 0.3s ease;
        }
        
        .panel:hover {
            border-color: rgba(59, 130, 246, 0.3);
            box-shadow: var(--shadow-glow);
        }
        
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .panel-title {
            font-size: 15px;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .panel-badge {
            font-size: 11px;
            padding: 4px 10px;
            border-radius: 20px;
            background: rgba(59, 130, 246, 0.2);
            color: var(--accent-blue);
        }
        
        /* 统计卡片网格 */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }
        
        .stat-card {
            background: var(--bg-card);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 20px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            border-radius: 16px 16px 0 0;
        }
        
        .stat-card:nth-child(1)::before { background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan)); }
        .stat-card:nth-child(2)::before { background: linear-gradient(90deg, var(--accent-green), var(--accent-cyan)); }
        .stat-card:nth-child(3)::before { background: linear-gradient(90deg, var(--accent-purple), var(--accent-pink)); }
        .stat-card:nth-child(4)::before { background: linear-gradient(90deg, var(--accent-orange), var(--accent-red)); }
        
        .stat-card:hover {
            transform: translateY(-4px);
            border-color: rgba(59, 130, 246, 0.3);
        }
        
        .stat-icon {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            margin-bottom: 12px;
        }
        
        .stat-card:nth-child(1) .stat-icon { background: rgba(59, 130, 246, 0.2); }
        .stat-card:nth-child(2) .stat-icon { background: rgba(16, 185, 129, 0.2); }
        .stat-card:nth-child(3) .stat-icon { background: rgba(139, 92, 246, 0.2); }
        .stat-card:nth-child(4) .stat-icon { background: rgba(245, 158, 11, 0.2); }
        
        .stat-value {
            font-size: 32px;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1;
            margin-bottom: 4px;
        }
        
        .stat-label {
            font-size: 12px;
            color: var(--text-secondary);
            font-weight: 500;
        }
        
        /* 表格样式 */
        .table-container {
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th {
            text-align: left;
            padding: 12px 16px;
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border-color);
        }
        
        td {
            padding: 14px 16px;
            font-size: 13px;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--border-color);
        }
        
        tr:hover td {
            background: rgba(255, 255, 255, 0.02);
            color: var(--text-primary);
        }
        
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 500;
            gap: 4px;
        }
        
        .badge-success { background: rgba(16, 185, 129, 0.15); color: var(--accent-green); }
        .badge-warning { background: rgba(245, 158, 11, 0.15); color: var(--accent-orange); }
        .badge-danger { background: rgba(239, 68, 68, 0.15); color: var(--accent-red); }
        
        /* 右侧面板布局 */
        .right-panel {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        /* 机器狗状态 */
        .robot-status-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }
        
        .status-item-box {
            background: var(--bg-glass);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 14px;
            transition: all 0.3s;
        }
        
        .status-item-box:hover {
            border-color: rgba(59, 130, 246, 0.3);
            background: rgba(59, 130, 246, 0.05);
        }
        
        .status-label {
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }
        
        .status-value {
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .status-value.warning { color: var(--accent-orange); }
        .status-value.danger { color: var(--accent-red); }
        
        .progress-bar {
            height: 4px;
            background: var(--border-color);
            border-radius: 2px;
            margin-top: 8px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            border-radius: 2px;
            transition: width 0.5s ease;
        }
        
        .progress-fill.battery { background: linear-gradient(90deg, var(--accent-green), var(--accent-cyan)); }
        .progress-fill.battery.low { background: linear-gradient(90deg, var(--accent-red), var(--accent-orange)); }
        .progress-fill.temp { background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple)); }
        .progress-fill.temp.high { background: linear-gradient(90deg, var(--accent-orange), var(--accent-red)); }
        
        /* 航点进度 */
        .waypoint-progress {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid var(--border-color);
        }
        
        .waypoint-dots {
            display: flex;
            gap: 8px;
            flex: 1;
        }
        
        .waypoint-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--border-color);
            transition: all 0.3s;
        }
        
        .waypoint-dot.active { background: var(--accent-blue); box-shadow: 0 0 10px var(--accent-blue); }
        .waypoint-dot.completed { background: var(--accent-green); }
        
        .waypoint-text {
            font-size: 12px;
            color: var(--text-secondary);
            white-space: nowrap;
        }
        
        /* 运动控制 */
        .control-pad {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 16px;
        }
        
        .control-btn {
            padding: 16px 8px;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            background: var(--bg-glass);
            color: var(--text-primary);
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
        }
        
        .control-btn:hover {
            background: rgba(59, 130, 246, 0.15);
            border-color: var(--accent-blue);
            transform: translateY(-2px);
        }
        
        .control-btn:active {
            transform: translateY(0);
        }
        
        .control-btn .icon { font-size: 18px; }
        .control-btn .label { font-size: 11px; color: var(--text-secondary); }
        
        .control-btn.primary {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(139, 92, 246, 0.2));
            border-color: rgba(59, 130, 246, 0.4);
        }
        
        .control-btn.danger {
            background: rgba(239, 68, 68, 0.1);
            border-color: rgba(239, 68, 68, 0.3);
            color: var(--accent-red);
        }
        
        .control-btn.danger:hover {
            background: rgba(239, 68, 68, 0.2);
            border-color: var(--accent-red);
        }
        
        .control-actions {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .action-btn {
            width: 100%;
            padding: 12px;
            border: 1px solid var(--border-color);
            border-radius: 10px;
            background: var(--bg-glass);
            color: var(--text-primary);
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .action-btn:hover {
            background: rgba(255, 255, 255, 0.05);
            border-color: rgba(255, 255, 255, 0.2);
        }
        
        .action-btn.stand-up { border-color: rgba(16, 185, 129, 0.3); color: var(--accent-green); }
        .action-btn.stand-up:hover { background: rgba(16, 185, 129, 0.1); }
        
        .action-btn.stand-down { border-color: rgba(245, 158, 11, 0.3); color: var(--accent-orange); }
        .action-btn.stand-down:hover { background: rgba(245, 158, 11, 0.1); }
        
        .action-btn.emergency { border-color: rgba(239, 68, 68, 0.3); color: var(--accent-red); }
        .action-btn.emergency:hover { background: rgba(239, 68, 68, 0.15); }
        
        /* 演示控制 */
        .demo-controls {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        
        .demo-btn {
            padding: 14px;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            background: var(--bg-glass);
            color: var(--text-primary);
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .demo-btn:hover {
            background: rgba(99, 102, 241, 0.15);
            border-color: rgba(99, 102, 241, 0.4);
        }
        
        .demo-btn.secondary:hover {
            background: rgba(16, 185, 129, 0.15);
            border-color: rgba(16, 185, 129, 0.4);
        }
        
        /* 告警列表 */
        .alert-list {
            max-height: 300px;
            overflow-y: auto;
        }
        
        .alert-item {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            padding: 12px;
            border-radius: 10px;
            margin-bottom: 8px;
            border-left: 3px solid;
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(-10px); }
            to { opacity: 1; transform: translateX(0); }
        }
        
        .alert-item.warn { background: rgba(245, 158, 11, 0.1); border-color: var(--accent-orange); }
        .alert-item.critical { background: rgba(239, 68, 68, 0.1); border-color: var(--accent-red); }
        .alert-item.crack { background: rgba(139, 92, 246, 0.1); border-color: var(--accent-purple); }
        
        .alert-info { flex: 1; }
        .alert-title { font-size: 13px; font-weight: 500; color: var(--text-primary); margin-bottom: 2px; }
        .alert-time { font-size: 11px; color: var(--text-muted); }
        .alert-action { margin-left: 12px; }
        
        .ack-btn {
            padding: 4px 10px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background: transparent;
            color: var(--text-secondary);
            font-size: 11px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .ack-btn:hover { background: var(--bg-glass); color: var(--text-primary); }
        
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-muted);
            font-size: 13px;
        }
        
        .empty-state .icon { font-size: 32px; margin-bottom: 12px; opacity: 0.5; }
        
        /* 视频占位 */
        .video-placeholder {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.8), rgba(30, 41, 59, 0.8));
            border: 1px dashed var(--border-color);
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            color: var(--text-muted);
        }
        
        .video-placeholder .icon { font-size: 40px; margin-bottom: 12px; opacity: 0.5; }
        .video-placeholder .info { font-size: 12px; }
        
        /* 滚动条 */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <div class="logo">🤖</div>
            <h1>绝影Lite3 监测平台</h1>
        </div>
        <div class="header-status">
            <div class="status-item">
                <div class="dot" id="connDot"></div>
                <span id="connStatus">未连接</span>
            </div>
            <div class="status-item">📡 <span id="clientCount">0</span> 在线</div>
            <div class="status-item">🕐 <span id="currentTime">--:--:--</span></div>
        </div>
    </div>
    
    <div class="container">
        <!-- 左侧主内容 -->
        <div class="left-panel">
            <!-- 统计卡片 -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon">📊</div>
                    <div class="stat-value" id="totalInspections">0</div>
                    <div class="stat-label">总巡检次数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">✅</div>
                    <div class="stat-value" id="normalCount">0</div>
                    <div class="stat-label">正常检测</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">🔍</div>
                    <div class="stat-value" id="crackCount">0</div>
                    <div class="stat-label">裂缝检测</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">⚠️</div>
                    <div class="stat-value" id="alertCount">0</div>
                    <div class="stat-label">待处理告警</div>
                </div>
            </div>
            
            <!-- 巡检记录 -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">📋 最近巡检记录 <span class="panel-badge" id="inspectionTime">--</span></div>
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>时间</th>
                                <th>设备</th>
                                <th>航点</th>
                                <th>裂缝数</th>
                                <th>温度状态</th>
                                <th>温度值</th>
                            </tr>
                        </thead>
                        <tbody id="inspectionTable">
                            <tr><td colspan="6" class="empty-state"><div class="icon">📭</div>暂无数据</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- 视频流 -->
            <div class="panel" style="margin-top:20px">
                <div class="panel-header">
                    <div class="panel-title">📹 实时视频流</div>
                </div>
                <div class="video-placeholder">
                    <div class="icon">🎥</div>
                    <div>视频流暂未连接</div>
                    <div class="info" style="margin-top:8px">RTSP: rtsp://192.168.1.108:554/id=1&type=0</div>
                </div>
            </div>
        </div>
        
        <!-- 右侧控制面板 -->
        <div class="right-panel">
            <!-- 机器狗状态 -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">🤖 机器狗状态</div>
                </div>
                <div class="robot-status-grid">
                    <div class="status-item-box">
                        <div class="status-label">电量</div>
                        <div class="status-value" id="batteryValue">100%</div>
                        <div class="progress-bar"><div class="progress-fill battery" id="batteryBar" style="width:100%"></div></div>
                    </div>
                    <div class="status-item-box">
                        <div class="status-label">CPU温度</div>
                        <div class="status-value" id="cpuTempValue">35.0℃</div>
                        <div class="progress-bar"><div class="progress-fill temp" id="cpuTempBar" style="width:35%"></div></div>
                    </div>
                    <div class="status-item-box">
                        <div class="status-label">GPU负载</div>
                        <div class="status-value" id="gpuLoadValue">0%</div>
                        <div class="progress-bar"><div class="progress-fill" id="gpuLoadBar" style="width:0%;background:linear-gradient(90deg,#3b82f6,#8b5cf6)"></div></div>
                    </div>
                    <div class="status-item-box">
                        <div class="status-label">内存使用</div>
                        <div class="status-value" id="memValue">45%</div>
                        <div class="progress-bar"><div class="progress-fill" id="memBar" style="width:45%;background:linear-gradient(90deg,#8b5cf6,#ec4899)"></div></div>
                    </div>
                    <div class="status-item-box">
                        <div class="status-label">运行状态</div>
                        <div class="status-value" id="robotStatusValue">待机</div>
                    </div>
                    <div class="status-item-box">
                        <div class="status-label">当前位置</div>
                        <div class="status-value" id="positionValue" style="font-size:14px">(0.0, 0.0)</div>
                    </div>
                </div>
                
                <div class="waypoint-progress">
                    <div class="waypoint-dots" id="waypointDots">
                        <div class="waypoint-dot active"></div>
                        <div class="waypoint-dot"></div>
                        <div class="waypoint-dot"></div>
                        <div class="waypoint-dot"></div>
                        <div class="waypoint-dot"></div>
                    </div>
                    <div class="waypoint-text" id="waypointText">WP001/005</div>
                </div>
            </div>
            
            <!-- 运动控制 -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">🎮 运动控制</div>
                </div>
                <div class="control-pad">
                    <button class="control-btn" onclick="sendControl('rotate_left')">
                        <span class="icon">↰</span>
                        <span class="label">左转</span>
                    </button>
                    <button class="control-btn primary" onclick="sendControl('forward')">
                        <span class="icon">↑</span>
                        <span class="label">前进</span>
                    </button>
                    <button class="control-btn" onclick="sendControl('rotate_right')">
                        <span class="icon">↱</span>
                        <span class="label">右转</span>
                    </button>
                    <button class="control-btn" onclick="sendControl('left')">
                        <span class="icon">←</span>
                        <span class="label">左移</span>
                    </button>
                    <div class="control-btn" style="cursor:default;opacity:0.5">
                        <span class="icon">⏹</span>
                        <span class="label">停止</span>
                    </div>
                    <button class="control-btn" onclick="sendControl('right')">
                        <span class="icon">→</span>
                        <span class="label">右移</span>
                    </button>
                    <button class="control-btn" onclick="sendControl('backward')">
                        <span class="icon">↓</span>
                        <span class="label">后退</span>
                    </button>
                </div>
                <div class="control-actions">
                    <button class="action-btn stand-up" onclick="sendControl('stand_up')">⬆ 起立</button>
                    <button class="action-btn stand-down" onclick="sendControl('stand_down')">⬇ 趴下</button>
                    <button class="action-btn emergency" onclick="sendControl('emergency_stop')">🛑 急停</button>
                </div>
            </div>
            
            <!-- 演示控制 -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">🎬 演示控制</div>
                </div>
                <div class="demo-controls">
                    <button class="demo-btn" onclick="sendDemo()">📊 发送巡检数据</button>
                    <button class="demo-btn secondary" onclick="sendDemoStatus()">🔄 更新状态</button>
                </div>
                <p style="font-size:11px;color:var(--text-muted);margin-top:12px;text-align:center">点击按钮模拟数据上报</p>
            </div>
            
            <!-- 实时告警 -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">🔔 实时告警 <span style="color:var(--accent-red);font-size:12px" id="alertBadge">0</span></div>
                </div>
                <div class="alert-list" id="alertList">
                    <div class="empty-state"><div class="icon">🔕</div>暂无告警</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let ws = null;
        let inspections = [];
        let alerts = [];
        let robotStatus = { battery: 100, cpu_temp: 35, gpu_load: 0, memory_usage: 45, status: 'idle', waypoint: 'WP001' };
        
        function connect() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(protocol + '//' + location.host + ':8765/ws');
            
            ws.onopen = () => {
                document.getElementById('connDot').className = 'dot connected';
                document.getElementById('connStatus').textContent = '已连接';
            };
            
            ws.onmessage = (e) => {
                const msg = JSON.parse(e.data);
                if (msg.type === 'inspection_result') addInspection(msg.data);
                else if (msg.type === 'temperature_alert' || msg.type === 'crack_alert') addAlert(msg.data);
                else if (msg.type === 'robot_status') updateRobotStatus(msg.data);
                else if (msg.type === 'stats') document.getElementById('clientCount').textContent = msg.data.connected_clients;
            };
            
            ws.onclose = () => {
                document.getElementById('connDot').className = 'dot';
                document.getElementById('connStatus').textContent = '已断开';
                setTimeout(connect, 3000);
            };
        }
        
        function addInspection(data) {
            const now = new Date().toLocaleString();
            const crackCount = data.crack?.details?.length || 0;
            const tempStatus = data.temperature?.status || 'NORMAL';
            const tempValue = (data.temperature?.value || 0).toFixed(1);
            
            inspections.unshift({ time: now, crackCount, tempStatus, tempValue, waypoint: 'WP001' });
            if (inspections.length > 20) inspections.pop();
            updateTable();
            updateStats();
        }
        
        function updateTable() {
            const tbody = document.getElementById('inspectionTable');
            if (!inspections.length) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><div class="icon">📭</div>暂无数据</td></tr>';
                return;
            }
            tbody.innerHTML = inspections.map(i => {
                const cls = i.tempStatus === 'NORMAL' ? 'badge-success' : i.tempStatus === 'WARN' ? 'badge-warning' : 'badge-danger';
                return `<tr><td>${i.time}</td><td>LITE3-001</td><td>${i.waypoint}</td><td>${i.crackCount}</td><td><span class="badge ${cls}">${i.tempStatus}</span></td><td>${i.tempValue}℃</td></tr>`;
            }).join('');
        }
        
        function updateStats() {
            document.getElementById('totalInspections').textContent = inspections.length;
            document.getElementById('crackCount').textContent = inspections.filter(i => i.crackCount > 0).length;
            document.getElementById('inspectionTime').textContent = inspections.length > 0 ? inspections[0].time : '--';
        }
        
        function addAlert(data) {
            const now = new Date().toLocaleString();
            const type = data.type || 'temperature';
            const level = data.level || 'WARN';
            const value = data.data?.temperature?.max_c || data.data?.width_mm || '--';
            const unit = type === 'temperature' ? '℃' : 'mm';
            
            alerts.unshift({ time: now, type, level, value, unit, id: data.id || Date.now() });
            if (alerts.length > 10) alerts.pop();
            updateAlerts();
        }
        
        function updateAlerts() {
            const container = document.getElementById('alertList');
            const badge = document.getElementById('alertBadge');
            const pending = alerts.filter(a => !a.acknowledged);
            badge.textContent = pending.length;
            
            if (!alerts.length) {
                container.innerHTML = '<div class="empty-state"><div class="icon">🔕</div>暂无告警</div>';
                return;
            }
            
            container.innerHTML = alerts.map(a => {
                const cls = a.level === 'CRITICAL' ? 'critical' : a.level === 'WARN' ? 'warn' : 'crack';
                const typeIcon = a.type === 'temperature' ? '🌡️' : '🔍';
                return `<div class="alert-item ${cls}">
                    <div class="alert-info">
                        <div class="alert-title">${typeIcon} ${a.value}${a.unit} (${a.level})</div>
                        <div class="alert-time">${a.time}</div>
                    </div>
                    <div class="alert-action">
                        <button class="ack-btn" onclick="ackAlert(${a.id})">确认</button>
                    </div>
                </div>`;
            }).join('');
        }
        
        function ackAlert(id) {
            fetch('/api/alert/ack?alert_id=' + id, {method: 'POST'})
                .then(r => r.json())
                .then(() => updateAlerts());
        }
        
        function updateRobotStatus(data) {
            robotStatus = data;
            
            const batteryEl = document.getElementById('batteryValue');
            const batteryBar = document.getElementById('batteryBar');
            batteryEl.textContent = data.battery + '%';
            batteryBar.style.width = data.battery + '%';
            batteryEl.className = 'status-value' + (data.battery < 20 ? ' danger' : data.battery < 50 ? ' warning' : '');
            batteryBar.className = 'progress-fill battery' + (data.battery < 20 ? ' low' : '');
            
            const cpuTempEl = document.getElementById('cpuTempValue');
            const cpuTempBar = document.getElementById('cpuTempBar');
            cpuTempEl.textContent = data.cpu_temp + '℃';
            cpuTempBar.style.width = Math.min(data.cpu_temp / 100 * 100, 100) + '%';
            cpuTempEl.className = 'status-value' + (data.cpu_temp > 60 ? ' danger' : data.cpu_temp > 50 ? ' warning' : '');
            cpuTempBar.className = 'progress-fill temp' + (data.cpu_temp > 60 ? ' high' : '');
            
            document.getElementById('gpuLoadValue').textContent = data.gpu_load + '%';
            document.getElementById('gpuLoadBar').style.width = data.gpu_load + '%';
            
            document.getElementById('memValue').textContent = data.memory_usage + '%';
            document.getElementById('memBar').style.width = data.memory_usage + '%';
            
            const statusMap = { 'idle': '待机', 'moving': '运动中', 'inspecting': '巡检中', 'charging': '充电中' };
            document.getElementById('robotStatusValue').textContent = statusMap[data.status] || data.status;
            
            if (data.position) {
                document.getElementById('positionValue').textContent = `(${data.position.x.toFixed(1)}, ${data.position.y.toFixed(1)})`;
            }
            
            if (data.waypoint) {
                document.getElementById('waypointText').textContent = data.waypoint + '/' + (data.total_waypoints || 5);
                updateWaypointDots(data.completed_waypoints || 0);
            }
        }
        
        function updateWaypointDots(completed) {
            const dots = document.querySelectorAll('.waypoint-dot');
            dots.forEach((dot, i) => {
                dot.className = 'waypoint-dot';
                if (i < completed) dot.classList.add('completed');
                else if (i === completed) dot.classList.add('active');
            });
        }
        
        async function sendControl(direction) {
            try {
                const resp = await fetch('/api/control/motion?direction=' + direction, {method: 'POST'});
                const data = await resp.json();
                console.log('控制发送:', data);
            } catch (e) {
                console.error('控制失败:', e);
                alert('控制发送失败，请检查网络连接');
            }
        }
        
        async function sendDemo() {
            try {
                const resp = await fetch('/api/demo/send', {method: 'POST'});
                const data = await resp.json();
                console.log('演示数据发送:', data);
            } catch (e) {
                console.error('演示失败:', e);
            }
        }
        
        async function sendDemoStatus() {
            try {
                const resp = await fetch('/api/demo/send_status', {method: 'POST'});
                const data = await resp.json();
                console.log('状态更新:', data);
            } catch (e) {
                console.error('状态更新失败:', e);
            }
        }
        
        setInterval(() => {
            document.getElementById('currentTime').textContent = new Date().toLocaleTimeString();
        }, 1000);
        
        setInterval(() => {
            fetch('/api/robot/status')
                .then(r => r.json())
                .then(d => updateRobotStatus(d))
                .catch(() => {});
        }, 2000);
        
        setInterval(() => fetch('/api/status').then(r => r.json()).then(d => {
            document.getElementById('alertCount').textContent = d.pending_alerts;
        }), 2000);
        
        connect();
    </script>
</body>
</html>"""


async def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
    server = uvicorn.Server(config)
    
    logger.info("=" * 60)
    logger.info("绝影Lite3 监测平台启动")
    logger.info("=" * 60)
    logger.info(f"HTTP:   http://0.0.0.0:{HTTP_PORT}")
    logger.info(f"WS:     ws://0.0.0.0:{WS_PORT}/ws")
    logger.info("=" * 60)
    
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
