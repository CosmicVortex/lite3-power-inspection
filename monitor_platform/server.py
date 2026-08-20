#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor Platform Server - Complete Version
Supports robot status monitoring, motion control, and inspection data receiving
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
WS_HOST = "0.0.0.0"
WS_PORT = 8765
HTTP_PORT = 8000

# UDP motion control configuration
MOTION_HOST = "192.168.1.103"
MOTION_PORT = 43893

# UDP command codes
CMD_STAND_UP = 0x21010202
CMD_STAND_DOWN = 0x21010203
CMD_EMERGENCY_STOP = 0x21020C0E
CMD_VELOCITY = 0x0103

# Create FastAPI app
app = FastAPI(title="绝影Lite3监测平台")

# Global data storage
connections: List[WebSocket] = []
inspections: List[Dict] = []
alerts: List[Dict] = []

# Robot status
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

# UDP socket
motion_sock = None


def send_udp_command(cmd: int, data: bytes = b''):
    """Send UDP motion control command"""
    global motion_sock
    try:
        if motion_sock is None:
            motion_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            motion_sock.settimeout(0.5)

        pkg = struct.pack('>I', cmd) + struct.pack('>H', len(data)) + data
        motion_sock.sendto(pkg, (MOTION_HOST, MOTION_PORT))
        logger.info(f"Sent UDP command: 0x{cmd:08X}")
    except Exception as e:
        logger.error(f"UDP send failed: {e}")


async def control_motion(direction: str, speed: float = 0.5):
    """Control robot motion"""
    vx, vy, vw = 0.0, 0.0, 0.0

    if direction == "forward":
        vy = -speed
    elif direction == "backward":
        vy = speed
    elif direction == "left":
        vx = -speed
    elif direction == "right":
        vx = speed
    elif direction == "rotate_left":
        vw = -speed
    elif direction == "rotate_right":
        vw = speed

    data = struct.pack('<fff', vx, vy, vw)
    send_udp_command(CMD_VELOCITY, data)
    robot_status["status"] = "moving"


@app.get("/", response_class=HTMLResponse)
async def root():
    """Home page"""
    return DASHBOARD_HTML


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint"""
    await websocket.accept()
    connections.append(websocket)
    logger.info(f"WebSocket client connected, online: {len(connections)}")

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await monitor.process_message(message, websocket)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in connections:
            connections.remove(websocket)


@app.post("/api/control/motion")
async def api_control_motion(direction: str, speed: float = 0.5):
    """Motion control API"""
    await control_motion(direction, speed)
    return {"status": "ok", "direction": direction, "speed": speed}


@app.post("/api/control/stand_up")
async def api_control_stand_up():
    """Stand up"""
    send_udp_command(CMD_STAND_UP)
    robot_status["status"] = "idle"
    return {"status": "ok", "action": "stand_up"}


@app.post("/api/control/stand_down")
async def api_control_stand_down():
    """Stand down"""
    send_udp_command(CMD_STAND_DOWN)
    robot_status["status"] = "idle"
    return {"status": "ok", "action": "stand_down"}


@app.post("/api/control/emergency_stop")
async def api_control_emergency_stop():
    """Emergency stop"""
    send_udp_command(CMD_EMERGENCY_STOP)
    robot_status["status"] = "idle"
    return {"status": "ok", "action": "emergency_stop"}


@app.post("/api/control/ptz")
async def api_control_ptz(yaw: Optional[float] = None, pitch: Optional[float] = None, zoom: Optional[int] = None):
    """PTZ control (reserved)"""
    return {"status": "ok", "yaw": yaw, "pitch": pitch, "zoom": zoom}


class MonitorServer:
    """Monitor platform server"""

    def __init__(self):
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)

    async def handle_client(self, websocket: WebSocket):
        """Handle client connection"""
        connections.append(websocket)
        logger.info(f"Client connected, online: {len(connections)}")

        await websocket.send_json({"type": "robot_status", "data": robot_status})

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.process_message(data, websocket)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "message": "Invalid JSON"})
        except WebSocketDisconnect:
            logger.info("Client disconnected")
        except Exception as e:
            logger.error(f"Client error: {e}")
        finally:
            if websocket in connections:
                connections.remove(websocket)

    async def process_message(self, data: Dict, websocket: WebSocket):
        """Process received message"""
        msg_type = data.get("type")
        timestamp = time.time()
        payload = data.get("payload", data.get("data", {}))
        device_id = data.get("deviceId", data.get("device_id", "LITE3-001"))

        if msg_type == "inspection_result":
            result = {
                "id": f"INS_{int(timestamp * 1000)}",
                "timestamp": timestamp,
                "datetime": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                "device_id": device_id,
                "data": payload
            }
            inspections.append(result)
            self.check_alerts(result)
            ui_data = self._convert_to_ui_format(result)
            await self.broadcast({"type": "inspection_result", "data": ui_data})
            logger.info(f"Received inspection: {result['id']}")

        elif msg_type == "temperature_alert":
            alert = {
                "id": f"ALT_{int(timestamp * 1000)}",
                "type": "temperature",
                "level": payload.get("alert_level", "WARN"),
                "timestamp": timestamp,
                "datetime": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                "device_id": device_id,
                "data": payload,
                "acknowledged": False
            }
            alerts.append(alert)
            await self.broadcast({"type": "temperature_alert", "data": alert})
            logger.warning(f"Temperature alert: {payload.get('alert_level')} - {payload.get('temperature', {}).get('max_c')}℃")

        elif msg_type == "heartbeat":
            robot_status["last_heartbeat"] = timestamp
            await websocket.send_json({"type": "heartbeat_ack", "timestamp": timestamp})

        elif msg_type == "crack_alert":
            alert = {
                "id": f"CRACK_ALT_{int(timestamp * 1000)}",
                "type": "crack",
                "level": "WARNING",
                "timestamp": timestamp,
                "datetime": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                "device_id": device_id,
                "data": payload,
                "acknowledged": False
            }
            alerts.append(alert)
            await self.broadcast({"type": "crack_alert", "data": alert})
            logger.warning(f"Crack alert: {payload.get('width_mm')}mm")

        elif msg_type == "system_status":
            status_data = payload
            for key in ["battery", "cpu_temp", "gpu_load", "memory_usage", "status", "waypoint", "position"]:
                if key in status_data:
                    robot_status[key] = status_data[key]
            await self.broadcast({"type": "robot_status", "data": robot_status})
            logger.debug(f"System status: {status_data.get('status', 'unknown')}")

        else:
            await websocket.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})

    def _convert_to_ui_format(self, result: Dict) -> Dict:
        """Convert internal data format to UI format"""
        payload = result.get("data", {})
        crack_data = {"detected": False, "count": 0, "details": []}

        if payload.get("defect_type") == "crack":
            crack_data["detected"] = True
            crack_data["count"] = 1
            crack_data["details"].append({
                "id": f"CRACK_{int(result['timestamp'] * 1000)}",
                "width_mm": payload.get("measurements", {}).get("width_mm", 0),
                "length_mm": payload.get("measurements", {}).get("length_mm", 0),
                "confidence": payload.get("confidence", 0),
                "location": payload.get("location", {})
            })

        temp_data = payload.get("temperature", {})
        return {
            "crack": crack_data,
            "temperature": {
                "status": payload.get("alert_level", "NORMAL"),
                "value": temp_data.get("max_c", 0) if temp_data else 0
            }
        }

    def check_alerts(self, result: Dict):
        """Check and generate alerts"""
        data = result.get("data", {})
        temp_data = data.get("temperature", {})

        if temp_data.get("status") in ["WARN", "CRITICAL"]:
            alert = {
                "id": f"ALERT_{int(time.time() * 1000)}",
                "type": "temperature",
                "level": temp_data.get("status"),
                "value": temp_data.get("value"),
                "timestamp": result["timestamp"],
                "datetime": result["datetime"],
                "device_id": result["device_id"],
                "acknowledged": False
            }
            alerts.append(alert)
            logger.warning(f"Temperature alert: {alert['value']}℃")

        crack_data = data.get("crack", {})
        if crack_data.get("detected") and crack_data.get("count", 0) > 0:
            for detail in crack_data.get("details", []):
                if detail.get("confidence", 0) > 0.8 and detail.get("width_mm", 0) >= 0.1:
                    alert = {
                        "id": f"ALERT_{int(time.time() * 1000)}",
                        "type": "crack",
                        "level": "WARNING",
                        "crack_id": detail.get("id"),
                        "size_mm": detail.get("size_mm"),
                        "confidence": detail.get("confidence"),
                        "timestamp": result["timestamp"],
                        "datetime": result["datetime"],
                        "device_id": result["device_id"],
                        "acknowledged": False
                    }
                    alerts.append(alert)
                    logger.warning(f"Crack alert: {detail.get('id')}")

    async def broadcast(self, message: Dict):
        """Broadcast message to all connected clients"""
        if not connections:
            return

        disconnected = []
        for conn in connections:
            try:
                await conn.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast failed: {e}")
                disconnected.append(conn)

        for conn in disconnected:
            if conn in connections:
                connections.remove(conn)

    def get_stats(self) -> Dict:
        """Get statistics"""
        return {
            "connected_clients": len(connections),
            "total_inspections": len(inspections),
            "pending_alerts": len([a for a in alerts if not a.get("acknowledged")]),
            "total_alerts": len(alerts),
            "inspections_last_minute": len([i for i in inspections if time.time() - i["timestamp"] < 60])
        }

    def get_robot_status(self) -> Dict:
        """Get robot status"""
        return robot_status


# Create monitor instance
monitor = MonitorServer()


@app.get("/api/status")
async def get_status():
    """System status"""
    return monitor.get_stats()


@app.get("/api/robot/status")
async def get_robot_status():
    """Robot status"""
    return monitor.get_robot_status()


@app.get("/api/inspections")
async def get_inspections(limit: int = 100):
    """Get inspection records"""
    return JSONResponse(inspections[-limit:])


@app.get("/api/alerts")
async def get_alerts(unacknowledged: bool = True):
    """Get alerts"""
    if unacknowledged:
        return JSONResponse([a for a in alerts if not a.get("acknowledged")])
    return JSONResponse(alerts)


@app.post("/api/alert/ack")
async def acknowledge_alert(alert_id: str):
    """Acknowledge alert"""
    for alert in alerts:
        if alert.get("id") == alert_id:
            alert["acknowledged"] = True
            return {"status": "ok", "alert_id": alert_id}
    raise HTTPException(status_code=404, detail="Alert not found")


@app.post("/api/demo/send")
async def send_demo():
    """Send demo data"""
    import random

    demo_data = {
        "type": "inspection_result",
        "deviceId": "LITE3-001",
        "payload": {
            "defect_type": "crack" if random.random() > 0.3 else None,
            "subtype": "longitudinal" if random.random() > 0.5 else "transverse",
            "location": {
                "image_x": random.randint(100, 500),
                "image_y": random.randint(100, 400),
                "world_x": round(random.uniform(0.5, 2.0), 2),
                "world_y": round(random.uniform(0.3, 1.5), 2),
                "world_theta": round(random.uniform(0, 3.14), 2)
            },
            "measurements": {
                "width_mm": round(random.uniform(0.1, 1.0), 2) if random.random() > 0.3 else 0,
                "length_mm": round(random.uniform(5.0, 50.0), 1),
                "pixel_precision": 0.019,
                "zoom_level": random.choice([5, 10, 15])
            },
            "confidence": round(random.uniform(0.7, 0.98), 2),
            "snapshot_url": f"http://192.168.1.103:8080/snap/CRACK-WP{random.randint(1,5)}-{int(time.time()*1000)}.jpg",
            "waypoint_id": f"WP{random.randint(1,5):03d}",
            "ptz_state": {
                "yaw": round(random.uniform(-280, 280), 1),
                "pitch": round(random.uniform(-115, 40), 1),
                "zoom": random.choice([5, 10, 15])
            },
            "temperature": {
                "status": random.choice(["NORMAL", "NORMAL", "WARN", "CRITICAL"]),
                "max_c": round(random.uniform(25.0, 55.0), 1),
                "avg_c": round(random.uniform(25.0, 45.0), 1),
                "min_c": round(random.uniform(20.0, 35.0), 1)
            }
        }
    }

    class DummyWS:
        pass

    dummy_ws = DummyWS()
    await monitor.process_message(demo_data, dummy_ws)

    status_data = {
        "type": "system_status",
        "deviceId": "LITE3-001",
        "payload": {
            "battery": random.randint(60, 95),
            "cpu_temp": round(random.uniform(35.0, 55.0), 1),
            "gpu_load": random.randint(20, 80),
            "memory_usage": random.randint(40, 70),
            "status": "inspecting",
            "waypoint": f"WP{random.randint(1,5):03d}",
            "total_waypoints": 5,
            "completed_waypoints": random.randint(1, 4),
            "uptime_seconds": random.randint(1800, 7200)
        }
    }
    await monitor.process_message(status_data, dummy_ws)

    return {"status": "ok", "message": "Demo data sent"}


@app.post("/api/demo/send_status")
async def send_demo_status():
    """Send demo status data"""
    import random

    status_data = {
        "type": "system_status",
        "deviceId": "LITE3-001",
        "payload": {
            "battery": random.randint(60, 95),
            "cpu_temp": round(random.uniform(35.0, 55.0), 1),
            "gpu_load": random.randint(20, 80),
            "memory_usage": random.randint(40, 70),
            "status": random.choice(["idle", "moving", "inspecting"]),
            "waypoint": f"WP{random.randint(1,5):03d}",
            "total_waypoints": 5,
            "completed_waypoints": random.randint(1, 4),
            "uptime_seconds": random.randint(1800, 7200)
        }
    }

    class DummyWS:
        pass

    dummy_ws = DummyWS()
    await monitor.process_message(status_data, dummy_ws)

    return {"status": "ok", "message": "Status updated"}


# Dashboard HTML
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>绝影Lite3 监测平台</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; }
        .header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 22px; }
        .status-bar { display: flex; gap: 20px; align-items: center; }
        .status-item { display: flex; align-items: center; gap: 8px; font-size: 14px; }
        .dot { width: 10px; height: 10px; border-radius: 50%; background: #ccc; }
        .dot.connected { background: #22c55e; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 20px 30px; max-width: 1800px; margin: 0 auto; }
        .panel { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .panel h2 { font-size: 16px; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #e5e7eb; display: flex; justify-content: space-between; align-items: center; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 12px; text-align: center; }
        .stat-card:nth-child(2) { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
        .stat-card:nth-child(3) { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
        .stat-card:nth-child(4) { background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); }
        .stat-value { font-size: 28px; font-weight: bold; }
        .stat-label { font-size: 12px; opacity: 0.9; margin-top: 5px; }
        .robot-status { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; }
        .status-item-detail { background: #f8fafc; padding: 12px; border-radius: 8px; }
        .status-item-detail label { font-size: 12px; color: #64748b; display: block; margin-bottom: 5px; }
        .status-item-detail .value { font-size: 18px; font-weight: 600; color: #1e293b; }
        .status-item-detail .value.warning { color: #f59e0b; }
        .status-item-detail .value.danger { color: #ef4444; }
        .progress-bar { height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; margin-top: 8px; }
        .progress-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
        .progress-fill.battery { background: linear-gradient(90deg, #22c55e, #16a34a); }
        .progress-fill.battery.low { background: linear-gradient(90deg, #ef4444, #dc2626); }
        .progress-fill.temp { background: linear-gradient(90deg, #3b82f6, #8b5cf6); }
        .progress-fill.temp.high { background: linear-gradient(90deg, #f59e0b, #ef4444); }
        .control-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 15px; }
        .control-btn { padding: 15px; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; transition: all 0.2s; font-weight: 600; }
        .control-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        .btn-forward { background: #3b82f6; color: white; grid-column: 2; }
        .btn-backward { background: #3b82f6; color: white; grid-column: 2; grid-row: 3; }
        .btn-left { background: #3b82f6; color: white; grid-column: 1; grid-row: 2; }
        .btn-right { background: #3b82f6; color: white; grid-column: 3; grid-row: 2; }
        .btn-rotate-left { background: #8b5cf6; color: white; grid-column: 1; grid-row: 1; }
        .btn-rotate-right { background: #8b5cf6; color: white; grid-column: 3; grid-row: 1; }
        .btn-stand-up { background: #22c55e; color: white; grid-column: 1 / 4; margin-top: 10px; }
        .btn-stand-down { background: #f59e0b; color: white; grid-column: 1 / 4; }
        .btn-emergency { background: #ef4444; color: white; grid-column: 1 / 4; margin-top: 10px; }
        .demo-section { display: flex; gap: 10px; margin-top: 15px; }
        .btn-demo { flex: 1; padding: 12px; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; font-weight: 600; transition: all 0.2s; }
        .btn-demo:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        .btn-inspection { background: #6366f1; color: white; }
        .btn-status { background: #10b981; color: white; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #e5e7eb; font-size: 13px; }
        th { background: #f8fafc; font-weight: 600; color: #475569; }
        tr:hover { background: #f8fafc; }
        .badge { padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; }
        .badge-success { background: #dcfce7; color: #166534; }
        .badge-warning { background: #fef3c7; color: #92400e; }
        .badge-danger { background: #fee2e2; color: #991b1b; }
        .alert-item { padding: 12px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .alert-item.warn { background: #fef3c7; border-left: 4px solid #f59e0b; }
        .alert-item.critical { background: #fee2e2; border-left: 4px solid #ef4444; }
        .alert-item.crack { background: #fce7f3; border-left: 4px solid #ec4899; }
        .alert-info { font-size: 13px; }
        .alert-time { font-size: 11px; color: #64748b; }
        .btn-ack { padding: 5px 12px; border: none; border-radius: 5px; background: #e2e8f0; cursor: pointer; font-size: 12px; }
        .btn-ack:hover { background: #cbd5e1; }
        .empty { color: #94a3b8; text-align: center; padding: 30px; font-size: 14px; }
        .video-placeholder { background: #1e293b; color: #94a3b8; padding: 40px; text-align: center; border-radius: 8px; margin-bottom: 15px; }
        .waypoint-progress { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
        .waypoint-dots { display: flex; gap: 5px; }
        .waypoint-dot { width: 12px; height: 12px; border-radius: 50%; background: #e2e8f0; }
        .waypoint-dot.active { background: #3b82f6; }
        .waypoint-dot.completed { background: #22c55e; }
    </style>
</head>
<body>
    <div class="header">
        <h1>绝影Lite3 监测平台</h1>
        <div class="status-bar">
            <div class="status-item"><div class="dot" id="connDot"></div><span id="connStatus">未连接</span></div>
            <div class="status-item">📡 <span id="clientCount">0</span> 设备在线</div>
            <div class="status-item">🕐 <span id="currentTime">--:--:--</span></div>
        </div>
    </div>

    <div class="container">
        <div class="left">
            <div class="stats">
                <div class="stat-card"><div class="stat-value" id="totalInspections">0</div><div class="stat-label">总巡检次数</div></div>
                <div class="stat-card"><div class="stat-value" id="normalCount">0</div><div class="stat-label">正常检测</div></div>
                <div class="stat-card"><div class="stat-value" id="crackCount">0</div><div class="stat-label">裂缝检测</div></div>
                <div class="stat-card"><div class="stat-value" id="alertCount">0</div><div class="stat-label">待处理告警</div></div>
            </div>

            <div class="panel">
                <h2>最近巡检记录 <span style="font-size:12px;color:#64748b;font-weight:normal" id="inspectionTime">--</span></h2>
                <table>
                    <thead><tr><th>时间</th><th>设备</th><th>航点</th><th>裂缝数</th><th>温度</th><th>状态</th></tr></thead>
                    <tbody id="inspectionTable"><tr><td colspan="6" class="empty">暂无数据</td></tr></tbody>
                </table>
            </div>

            <div class="panel" style="margin-top:20px">
                <h2>实时视频流</h2>
                <div class="video-placeholder">
                    <div>📹 视频流暂未连接</div>
                    <div style="font-size:12px;margin-top:5px">RTSP: rtsp://192.168.1.108:554/id=1&type=0</div>
                </div>
            </div>
        </div>

        <div class="right">
            <div class="panel">
                <h2>机器狗状态</h2>
                <div class="robot-status">
                    <div class="status-item-detail">
                        <label>电量</label>
                        <div class="value" id="batteryValue">100%</div>
                        <div class="progress-bar"><div class="progress-fill battery" id="batteryBar" style="width:100%"></div></div>
                    </div>
                    <div class="status-item-detail">
                        <label>CPU温度</label>
                        <div class="value" id="cpuTempValue">35.0℃</div>
                        <div class="progress-bar"><div class="progress-fill temp" id="cpuTempBar" style="width:35%"></div></div>
                    </div>
                    <div class="status-item-detail">
                        <label>GPU负载</label>
                        <div class="value" id="gpuLoadValue">0%</div>
                        <div class="progress-bar"><div class="progress-fill" id="gpuLoadBar" style="width:0%;background:#3b82f6"></div></div>
                    </div>
                    <div class="status-item-detail">
                        <label>内存使用</label>
                        <div class="value" id="memValue">45%</div>
                        <div class="progress-bar"><div class="progress-fill" id="memBar" style="width:45%;background:#8b5cf6"></div></div>
                    </div>
                    <div class="status-item-detail">
                        <label>运行状态</label>
                        <div class="value" id="robotStatusValue">待机</div>
                    </div>
                    <div class="status-item-detail">
                        <label>当前位置</label>
                        <div class="value" id="positionValue">(0.0, 0.0)</div>
                    </div>
                </div>

                <div style="margin-top:15px">
                    <label style="font-size:12px;color:#64748b">巡检进度</label>
                    <div class="waypoint-progress">
                        <div class="waypoint-dots" id="waypointDots">
                            <div class="waypoint-dot active"></div>
                            <div class="waypoint-dot"></div>
                            <div class="waypoint-dot"></div>
                            <div class="waypoint-dot"></div>
                            <div class="waypoint-dot"></div>
                        </div>
                        <span style="font-size:12px;color:#64748b" id="waypointText">WP001/005</span>
                    </div>
                </div>
            </div>

            <div class="panel" style="margin-top:20px">
                <h2>运动控制</h2>
                <div class="control-grid">
                    <button class="control-btn btn-rotate-left" onclick="sendControl('rotate_left')">↰ 左转</button>
                    <button class="control-btn btn-forward" onclick="sendControl('forward')">↑ 前</button>
                    <button class="control-btn btn-rotate-right" onclick="sendControl('rotate_right')">↱ 右转</button>
                    <button class="control-btn btn-left" onclick="sendControl('left')">← 左</button>
                    <div style="background:#f1f5f9;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:12px;color:#64748b">停止</div>
                    <button class="control-btn btn-right" onclick="sendControl('right')">右 →</button>
                    <button class="control-btn btn-backward" onclick="sendControl('backward')">↓ 后</button>
                </div>
                <button class="control-btn btn-stand-up" onclick="sendControl('stand_up')">⬆ 起立</button>
                <button class="control-btn btn-stand-down" onclick="sendControl('stand_down')">⬇ 趴下</button>
                <button class="control-btn btn-emergency" onclick="sendControl('emergency_stop')">🛑 急停</button>
            </div>

            <div class="panel" style="margin-top:20px">
                <h2>演示控制</h2>
                <div class="demo-section">
                    <button class="btn-demo btn-inspection" onclick="sendDemo()">发送巡检数据</button>
                    <button class="btn-demo btn-status" onclick="sendDemoStatus()">更新状态</button>
                </div>
                <p style="color:#64748b;font-size:12px;margin-top:10px;text-align:center">点击按钮模拟巡检数据上报</p>
            </div>

            <div class="panel" style="margin-top:20px">
                <h2>实时告警 <span style="font-size:12px;color:#ef4444;font-weight:normal" id="alertBadge">0</span></h2>
                <div id="alertList"><p class="empty">暂无告警</p></div>
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
                if (msg.type === 'inspection_result') {
                    addInspection(msg.data);
                } else if (msg.type === 'temperature_alert' || msg.type === 'crack_alert') {
                    addAlert(msg.data);
                } else if (msg.type === 'robot_status') {
                    updateRobotStatus(msg.data);
                } else if (msg.type === 'stats') {
                    document.getElementById('clientCount').textContent = msg.data.connected_clients;
                }
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
                tbody.innerHTML = '<tr><td colspan="6" class="empty">暂无数据</td></tr>';
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
                container.innerHTML = '<p class="empty">暂无告警</p>';
                return;
            }

            container.innerHTML = alerts.map(a => {
                const cls = a.level === 'CRITICAL' ? 'critical' : a.level === 'WARN' ? 'warn' : 'crack';
                const typeIcon = a.type === 'temperature' ? '🌡️' : '🔍';
                return `<div class="alert-item ${cls}">
                    <div class="alert-info">${typeIcon} ${a.value}${a.unit} (${a.level})</div>
                    <div style="text-align:right">
                        <div class="alert-time">${a.time}</div>
                        <button class="btn-ack" onclick="ackAlert(${a.id})">确认</button>
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
            batteryEl.className = 'value' + (data.battery < 20 ? ' danger' : data.battery < 50 ? ' warning' : '');
            batteryBar.className = 'progress-fill battery' + (data.battery < 20 ? ' low' : '');

            const cpuTempEl = document.getElementById('cpuTempValue');
            const cpuTempBar = document.getElementById('cpuTempBar');
            cpuTempEl.textContent = data.cpu_temp + '℃';
            cpuTempBar.style.width = Math.min(data.cpu_temp / 100 * 100, 100) + '%';
            cpuTempEl.className = 'value' + (data.cpu_temp > 60 ? ' danger' : data.cpu_temp > 50 ? ' warning' : '');
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
                console.log('Control sent:', data);
            } catch (e) {
                console.error('Control failed:', e);
                alert('控制发送失败，请检查网络连接');
            }
        }

        async function sendDemo() {
            try {
                const resp = await fetch('/api/demo/send', {method: 'POST'});
                const data = await resp.json();
                console.log('Demo data sent:', data);
            } catch (e) {
                console.error('Demo failed:', e);
            }
        }

        async function sendDemoStatus() {
            try {
                const resp = await fetch('/api/demo/send_status', {method: 'POST'});
                const data = await resp.json();
                console.log('Status updated:', data);
            } catch (e) {
                console.error('Status update failed:', e);
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
    """Main function"""
    config = uvicorn.Config(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
    server = uvicorn.Server(config)

    ws_server = await asyncio.create_task(
        asyncio.to_thread(uvicorn.run, app, host=WS_HOST, port=WS_PORT, log_level="info")
    )

    logger.info("=" * 60)
    logger.info("绝影Lite3 监测平台启动")
    logger.info("=" * 60)
    logger.info(f"HTTP界面:   http://0.0.0.0:{HTTP_PORT}")
    logger.info(f"WebSocket:  ws://0.0.0.0:{WS_PORT}/ws")
    logger.info("=" * 60)

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
