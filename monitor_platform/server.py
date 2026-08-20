#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3 监测平台 - 科幻科技版
"""

import asyncio, json, time, logging, struct, socket
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
WS_PORT, HTTP_PORT = 8765, 8000
MOTION_HOST, MOTION_PORT = "192.168.1.103", 43893
CMD_STAND_UP, CMD_STAND_DOWN = 0x21010202, 0x21010203
CMD_EMERGENCY_STOP, CMD_VELOCITY = 0x21020C0E, 0x0103

connections: List[WebSocket] = []
inspections: List[Dict] = []
alerts: List[Dict] = []
robot_status = {"battery": 100, "cpu_temp": 35.0, "gpu_load": 0, "memory_usage": 45,
                "status": "idle", "position": {"x": 0.0, "y": 0.0},
                "waypoint": "WP001", "total_waypoints": 5, "completed_waypoints": 0}
motion_sock = None

def send_udp(cmd: int, data: bytes = b''):
    global motion_sock
    try:
        if motion_sock is None:
            motion_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            motion_sock.settimeout(0.5)
        motion_sock.sendto(struct.pack('>I', cmd) + struct.pack('>H', len(data)) + data, (MOTION_HOST, MOTION_PORT))
    except: pass

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    connections.append(ws)
    await ws.send_json({"type": "robot_status", "data": robot_status})
    try:
        async for msg in ws:
            try: await monitor.process(json.loads(msg), ws)
            except: pass
    finally:
        connections.remove(ws) if ws in connections else None

@app.post("/api/control/{action}")
async def control(action: str):
    if action == "stand_up": send_udp(CMD_STAND_UP); robot_status["status"] = "idle"
    elif action == "stand_down": send_udp(CMD_STAND_DOWN); robot_status["status"] = "idle"
    elif action == "emergency_stop": send_udp(CMD_EMERGENCY_STOP); robot_status["status"] = "idle"
    else:
        vx, vy, vw = 0.0, 0.0, 0.0
        if action == "forward": vy = -0.5
        elif action == "backward": vy = 0.5
        elif action == "left": vx = -0.5
        elif action == "right": vx = 0.5
        elif action == "rotate_left": vw = -0.5
        elif action == "rotate_right": vw = 0.5
        send_udp(CMD_VELOCITY, struct.pack('<fff', vx, vy, vw))
        robot_status["status"] = "moving"
    return {"status": "ok"}

@app.get("/")
async def root(): return HTMLResponse(DASHBOARD_HTML)

@app.get("/api/status")
async def status():
    return {"clients": len(connections), "inspections": len(inspections),
            "alerts": len([a for a in alerts if not a.get("ack")])}

@app.get("/api/robot")
async def get_robot(): return robot_status

@app.get("/api/inspections")
async def get_inspections(limit: int = 50): return inspections[-limit:]

@app.post("/api/demo")
async def demo():
    import random
    inspections.append({"time": datetime.now().strftime("%H:%M:%S"), "cracks": random.randint(0,3),
                       "temp": round(random.uniform(25, 55), 1), "status": random.choice(["NORMAL","WARN","CRITICAL"])})
    robot_status.update({"battery": random.randint(60,95), "cpu_temp": round(random.uniform(35,55),1),
                        "gpu_load": random.randint(20,80), "waypoint": f"WP{random.randint(1,5):03d}",
                        "completed_waypoints": random.randint(1,4), "status": "inspecting"})
    for ws in connections:
        await ws.send_json({"type": "inspection", "data": inspections[-1]})
        await ws.send_json({"type": "robot_status", "data": robot_status})
    return {"status": "ok"}

class Monitor:
    async def process(self, data: Dict, ws: WebSocket):
        t = time.time()
        p = data.get("payload", data.get("data", {}))
        if data.get("type") == "system_status":
            for k in ["battery","cpu_temp","gpu_load","memory_usage","status","waypoint","position"]:
                if k in p: robot_status[k] = p[k]
            await ws.send_json({"type": "robot_status", "data": robot_status})

monitor = Monitor()


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>绝影Lite3 监测平台 | YUEYING MONITOR</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;500;600;700&display=swap');

:root {
    --neon-blue: #00f3ff;
    --neon-purple: #bc13fe;
    --neon-green: #0aff0a;
    --neon-orange: #ff6b00;
    --neon-red: #ff003c;
    --dark-bg: #050810;
    --panel-bg: rgba(10, 20, 40, 0.85);
    --border-glow: rgba(0, 243, 255, 0.3);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    background: var(--dark-bg);
    color: #e0e8f0;
    font-family: 'Rajdhani', monospace;
    overflow-x: hidden;
    min-height: 100vh;
}

/* 扫描线效果 */
body::before {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: repeating-linear-gradient(
        0deg,
        transparent,
        transparent 2px,
        rgba(0, 243, 255, 0.015) 2px,
        rgba(0, 243, 255, 0.015) 4px
    );
    pointer-events: none;
    z-index: 9999;
}

/* 网格背景 */
body::after {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background-image: 
        linear-gradient(rgba(0, 243, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0, 243, 255, 0.03) 1px, transparent 1px);
    background-size: 50px 50px;
    pointer-events: none;
    z-index: -1;
}

/* Header - 科技感顶栏 */
.header {
    background: linear-gradient(180deg, rgba(0,20,40,0.95) 0%, rgba(5,8,16,0.9) 100%);
    border-bottom: 2px solid var(--neon-blue);
    padding: 15px 30px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: relative;
    box-shadow: 0 0 30px rgba(0, 243, 255, 0.2);
}

.header::after {
    content: '';
    position: absolute;
    bottom: -2px;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
    animation: scan 3s linear infinite;
}

@keyframes scan {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}

.logo {
    display: flex;
    align-items: center;
    gap: 15px;
}

.logo-icon {
    width: 45px;
    height: 45px;
    background: linear-gradient(135deg, var(--neon-blue), var(--neon-purple));
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    box-shadow: 0 0 20px rgba(0, 243, 255, 0.5);
    animation: pulse-glow 2s ease-in-out infinite;
}

@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 20px rgba(0, 243, 255, 0.5); }
    50% { box-shadow: 0 0 40px rgba(0, 243, 255, 0.8); }
}

.logo h1 {
    font-family: 'Orbitron', sans-serif;
    font-size: 24px;
    font-weight: 700;
    background: linear-gradient(90deg, var(--neon-blue), var(--neon-purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-shadow: 0 0 30px rgba(0, 243, 255, 0.5);
    letter-spacing: 3px;
}

.logo .subtitle {
    font-size: 11px;
    color: var(--neon-blue);
    letter-spacing: 5px;
    opacity: 0.7;
}

.header-status {
    display: flex;
    gap: 30px;
    align-items: center;
}

.status-item {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 14px;
    color: #8892b0;
}

.status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #333;
    border: 2px solid #555;
    transition: all 0.3s;
}

.status-dot.connected {
    background: var(--neon-green);
    border-color: var(--neon-green);
    box-shadow: 0 0 15px var(--neon-green);
    animation: blink 1.5s infinite;
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

/* 主布局 */
.main-container {
    display: grid;
    grid-template-columns: 1fr 420px;
    gap: 20px;
    padding: 20px;
    max-width: 1800px;
    margin: 0 auto;
}

/* 面板样式 - 全息效果 */
.panel {
    background: var(--panel-bg);
    border: 1px solid var(--border-glow);
    border-radius: 4px;
    position: relative;
    overflow: hidden;
}

.panel::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
}

.panel::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(135deg, rgba(0,243,255,0.02) 0%, transparent 50%, rgba(188,19,254,0.02) 100%);
    pointer-events: none;
}

.panel-header {
    padding: 12px 16px;
    border-bottom: 1px solid rgba(0, 243, 255, 0.2);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(0, 20, 40, 0.5);
}

.panel-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 12px;
    font-weight: 600;
    color: var(--neon-blue);
    letter-spacing: 2px;
    text-transform: uppercase;
}

.panel-body {
    padding: 16px;
}

/* 统计卡片 - 全息仪表 */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 15px;
    margin-bottom: 20px;
}

.stat-card {
    background: linear-gradient(135deg, rgba(0,20,40,0.9), rgba(10,30,50,0.9));
    border: 1px solid var(--border-glow);
    border-radius: 4px;
    padding: 18px;
    position: relative;
    overflow: hidden;
    transition: all 0.3s;
}

.stat-card:hover {
    border-color: var(--neon-blue);
    box-shadow: 0 0 25px rgba(0, 243, 255, 0.3);
    transform: translateY(-2px);
}

.stat-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
}

.stat-card:nth-child(1)::before { background: linear-gradient(90deg, var(--neon-blue), transparent); }
.stat-card:nth-child(2)::before { background: linear-gradient(90deg, var(--neon-green), transparent); }
.stat-card:nth-child(3)::before { background: linear-gradient(90deg, var(--neon-purple), transparent); }
.stat-card:nth-child(4)::before { background: linear-gradient(90deg, var(--neon-orange), transparent); }

.stat-icon {
    font-size: 20px;
    margin-bottom: 8px;
    opacity: 0.8;
}

.stat-value {
    font-family: 'Orbitron', sans-serif;
    font-size: 32px;
    font-weight: 700;
    color: #fff;
    text-shadow: 0 0 20px currentColor;
    line-height: 1;
}

.stat-label {
    font-size: 11px;
    color: #8892b0;
    margin-top: 6px;
    letter-spacing: 1px;
    text-transform: uppercase;
}

/* 表格样式 - 数据流 */
.table-container {
    max-height: 320px;
    overflow-y: auto;
}

.table-container::-webkit-scrollbar {
    width: 4px;
}

.table-container::-webkit-scrollbar-thumb {
    background: var(--neon-blue);
    border-radius: 2px;
}

table {
    width: 100%;
    border-collapse: collapse;
}

th {
    background: rgba(0, 243, 255, 0.1);
    padding: 10px 12px;
    text-align: left;
    font-size: 10px;
    font-weight: 600;
    color: var(--neon-blue);
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1px solid rgba(0, 243, 255, 0.3);
    position: sticky;
    top: 0;
}

td {
    padding: 10px 12px;
    font-size: 13px;
    color: #b0b8c8;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

tr:hover td {
    background: rgba(0, 243, 255, 0.05);
    color: #fff;
}

.badge {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 2px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
}

.badge-success { background: rgba(10, 255, 10, 0.15); color: var(--neon-green); border: 1px solid rgba(10, 255, 10, 0.3); }
.badge-warning { background: rgba(255, 107, 0, 0.15); color: var(--neon-orange); border: 1px solid rgba(255, 107, 0, 0.3); }
.badge-danger { background: rgba(255, 0, 60, 0.15); color: var(--neon-red); border: 1px solid rgba(255, 0, 60, 0.3); }

/* 视频区域 */
.video-section {
    margin-top: 20px;
}

.video-placeholder {
    background: linear-gradient(135deg, rgba(0,10,20,0.9), rgba(5,15,30,0.9));
    border: 1px dashed rgba(0, 243, 255, 0.3);
    border-radius: 4px;
    padding: 30px;
    text-align: center;
    position: relative;
    overflow: hidden;
}

.video-placeholder::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 60px;
    height: 60px;
    border: 2px solid var(--neon-blue);
    border-radius: 50%;
    animation: radar 2s linear infinite;
}

@keyframes radar {
    0% { width: 60px; height: 60px; opacity: 1; }
    100% { width: 150px; height: 150px; opacity: 0; }
}

.video-placeholder .icon {
    font-size: 32px;
    margin-bottom: 10px;
    opacity: 0.6;
}

.video-placeholder .info {
    font-size: 11px;
    color: #555;
    font-family: monospace;
}

/* 右侧面板 */
.right-panel {
    display: flex;
    flex-direction: column;
    gap: 15px;
}

/* 机器人状态 - 仪表盘 */
.status-dashboard {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
}

.status-module {
    background: rgba(0, 15, 30, 0.6);
    border: 1px solid rgba(0, 243, 255, 0.15);
    border-radius: 4px;
    padding: 12px;
    position: relative;
}

.status-module::after {
    content: '';
    position: absolute;
    top: 0;
    right: 0;
    width: 20px;
    height: 20px;
    border-left: 2px solid var(--neon-blue);
    border-bottom: 2px solid var(--neon-blue);
    opacity: 0.5;
}

.module-label {
    font-size: 9px;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 6px;
}

.module-value {
    font-family: 'Orbitron', sans-serif;
    font-size: 20px;
    font-weight: 700;
    color: var(--neon-blue);
    text-shadow: 0 0 15px rgba(0, 243, 255, 0.5);
}

.module-value.warning { color: var(--neon-orange); text-shadow: 0 0 15px rgba(255, 107, 0, 0.5); }
.module-value.danger { color: var(--neon-red); text-shadow: 0 0 15px rgba(255, 0, 60, 0.5); }

.progress-track {
    height: 3px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 2px;
    margin-top: 8px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--neon-blue), var(--neon-purple));
    border-radius: 2px;
    transition: width 0.5s ease;
    box-shadow: 0 0 10px currentColor;
}

.progress-fill.green { background: linear-gradient(90deg, var(--neon-green), #00ff88); }
.progress-fill.orange { background: linear-gradient(90deg, var(--neon-orange), #ffaa00); }
.progress-fill.red { background: linear-gradient(90deg, var(--neon-red), #ff4444); }

/* 航点进度 - 轨道显示 */
.waypoint-track {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 15px;
    padding-top: 15px;
    border-top: 1px solid rgba(0, 243, 255, 0.15);
}

.waypoint-line {
    flex: 1;
    height: 2px;
    background: rgba(255, 255, 255, 0.1);
    position: relative;
}

.waypoint-line::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    background: var(--neon-green);
    box-shadow: 0 0 10px var(--neon-green);
    transition: width 0.5s;
}

.waypoint-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.2);
    border: 2px solid rgba(255, 255, 255, 0.3);
    position: relative;
    z-index: 1;
}

.waypoint-dot.active {
    background: var(--neon-blue);
    border-color: var(--neon-blue);
    box-shadow: 0 0 10px var(--neon-blue);
}

.waypoint-dot.completed {
    background: var(--neon-green);
    border-color: var(--neon-green);
    box-shadow: 0 0 10px var(--neon-green);
}

.waypoint-info {
    font-family: 'Orbitron', sans-serif;
    font-size: 11px;
    color: var(--neon-blue);
}

/* 控制面板 */
.control-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 12px;
}

.ctrl-btn {
    padding: 14px 8px;
    background: rgba(0, 20, 40, 0.6);
    border: 1px solid rgba(0, 243, 255, 0.2);
    border-radius: 4px;
    color: var(--neon-blue);
    font-size: 18px;
    cursor: pointer;
    transition: all 0.2s;
    text-align: center;
    position: relative;
    overflow: hidden;
}

.ctrl-btn::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(0, 243, 255, 0.2), transparent);
    transition: left 0.5s;
}

.ctrl-btn:hover::before {
    left: 100%;
}

.ctrl-btn:hover {
    background: rgba(0, 243, 255, 0.15);
    border-color: var(--neon-blue);
    box-shadow: 0 0 15px rgba(0, 243, 255, 0.3);
    transform: scale(1.05);
}

.ctrl-btn:active {
    transform: scale(0.95);
}

.ctrl-btn .label {
    display: block;
    font-size: 9px;
    color: #555;
    margin-top: 4px;
    letter-spacing: 1px;
}

.ctrl-btn.primary {
    background: rgba(0, 243, 255, 0.1);
    border-color: rgba(0, 243, 255, 0.4);
}

.ctrl-btn.danger {
    color: var(--neon-red);
    border-color: rgba(255, 0, 60, 0.3);
}

.ctrl-btn.danger:hover {
    background: rgba(255, 0, 60, 0.15);
    border-color: var(--neon-red);
    box-shadow: 0 0 15px rgba(255, 0, 60, 0.3);
}

.action-buttons {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.action-btn {
    padding: 10px;
    background: rgba(0, 15, 30, 0.6);
    border: 1px solid rgba(0, 243, 255, 0.2);
    border-radius: 4px;
    color: #b0b8c8;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
    text-align: left;
    display: flex;
    align-items: center;
    gap: 10px;
}

.action-btn:hover {
    background: rgba(0, 243, 255, 0.1);
    border-color: var(--neon-blue);
    color: var(--neon-blue);
}

.action-btn.up { border-left: 3px solid var(--neon-green); }
.action-btn.down { border-left: 3px solid var(--neon-orange); }
.action-btn.emergency { border-left: 3px solid var(--neon-red); color: var(--neon-red); }
.action-btn.emergency:hover { background: rgba(255, 0, 60, 0.15); border-color: var(--neon-red); }

/* 演示控制 */
.demo-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}

.demo-btn {
    padding: 12px;
    background: rgba(188, 19, 254, 0.1);
    border: 1px solid rgba(188, 19, 254, 0.3);
    border-radius: 4px;
    color: var(--neon-purple);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
    text-align: center;
}

.demo-btn:hover {
    background: rgba(188, 19, 254, 0.2);
    border-color: var(--neon-purple);
    box-shadow: 0 0 15px rgba(188, 19, 254, 0.3);
}

/* 告警列表 */
.alert-list {
    max-height: 200px;
    overflow-y: auto;
}

.alert-item {
    padding: 10px 12px;
    margin-bottom: 6px;
    border-radius: 4px;
    border-left: 3px solid;
    background: rgba(0, 15, 30, 0.5);
    animation: slideIn 0.3s ease;
}

@keyframes slideIn {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}

.alert-item.warn { border-color: var(--neon-orange); }
.alert-item.critical { border-color: var(--neon-red); }
.alert-item.crack { border-color: var(--neon-purple); }

.alert-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.alert-text {
    font-size: 12px;
    color: #b0b8c8;
}

.alert-time {
    font-size: 10px;
    color: #555;
    font-family: monospace;
}

.alert-action {
    padding: 4px 10px;
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 2px;
    color: #888;
    font-size: 10px;
    cursor: pointer;
    transition: all 0.2s;
}

.alert-action:hover {
    background: rgba(0, 243, 255, 0.1);
    border-color: var(--neon-blue);
    color: var(--neon-blue);
}

/* 空状态 */
.empty-state {
    text-align: center;
    padding: 30px;
    color: #333;
}

.empty-state .icon {
    font-size: 32px;
    margin-bottom: 10px;
    opacity: 0.4;
}

/* 装饰角标 */
.corner-decor {
    position: absolute;
    width: 10px;
    height: 10px;
}

.corner-decor.tl { top: -1px; left: -1px; border-top: 2px solid var(--neon-blue); border-left: 2px solid var(--neon-blue); }
.corner-decor.tr { top: -1px; right: -1px; border-top: 2px solid var(--neon-blue); border-right: 2px solid var(--neon-blue); }
.corner-decor.bl { bottom: -1px; left: -1px; border-bottom: 2px solid var(--neon-blue); border-left: 2px solid var(--neon-blue); }
.corner-decor.br { bottom: -1px; right: -1px; border-bottom: 2px solid var(--neon-blue); border-right: 2px solid var(--neon-blue); }

/* 响应式 */
@media (max-width: 1200px) {
    .main-container {
        grid-template-columns: 1fr;
    }
    .right-panel {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
    }
}
</style>
</head>
<body>
    <!-- Header -->
    <div class="header">
        <div class="logo">
            <div class="logo-icon">🤖</div>
            <div>
                <h1>绝影LITE3</h1>
                <div class="subtitle">INSPECTION MONITOR SYSTEM v1.7</div>
            </div>
        </div>
        <div class="header-status">
            <div class="status-item">
                <div class="status-dot" id="connDot"></div>
                <span id="connStatus">SYSTEM OFFLINE</span>
            </div>
            <div class="status-item">
                <span style="color:var(--neon-blue)">◉</span>
                <span id="clientCount">0</span> DEVICES
            </div>
            <div class="status-item">
                <span style="color:var(--neon-blue)">⏱</span>
                <span id="currentTime">--:--:--</span>
            </div>
        </div>
    </div>

    <!-- Main Content -->
    <div class="main-container">
        <!-- Left Column -->
        <div class="left-column">
            <!-- Stats Dashboard -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon">📊</div>
                    <div class="stat-value" id="totalInspections">000</div>
                    <div class="stat-label">TOTAL INSPECTIONS</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">✅</div>
                    <div class="stat-value" id="normalCount" style="color:var(--neon-green)">000</div>
                    <div class="stat-label">NORMAL READINGS</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">🔍</div>
                    <div class="stat-value" id="crackCount" style="color:var(--neon-purple)">000</div>
                    <div class="stat-label">CRACK DETECTED</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">⚠️</div>
                    <div class="stat-value" id="alertCount" style="color:var(--neon-orange)">000</div>
                    <div class="stat-label">PENDING ALERTS</div>
                </div>
            </div>

            <!-- Inspection Records -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">◈ INSPECTION LOG</div>
                    <div style="font-size:10px;color:#555" id="inspectionTime">--:--:--</div>
                </div>
                <div class="panel-body">
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>TIME</th>
                                    <th>DEVICE</th>
                                    <th>WAYPOINT</th>
                                    <th>CRACKS</th>
                                    <th>TEMP</th>
                                    <th>STATUS</th>
                                </tr>
                            </thead>
                            <tbody id="inspectionTable">
                                <tr><td colspan="6"><div class="empty-state"><div class="icon">📭</div>NO DATA</div></td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Video Section -->
            <div class="panel video-section">
                <div class="panel-header">
                    <div class="panel-title">◈ LIVE FEED</div>
                    <div style="font-size:10px;color:var(--neon-green)">● RECORDING</div>
                </div>
                <div class="panel-body">
                    <div class="video-placeholder">
                        <div class="icon">📹</div>
                        <div style="color:var(--neon-blue);margin-bottom:8px">VIDEO STREAM UNAVAILABLE</div>
                        <div class="info">RTSP: rtsp://192.168.1.108:554/id=1&type=0</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Right Column -->
        <div class="right-panel">
            <!-- Robot Status -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">◈ ROBOT STATUS</div>
                    <div style="font-size:10px;color:var(--neon-green)">● ONLINE</div>
                </div>
                <div class="panel-body">
                    <div class="status-dashboard">
                        <div class="status-module">
                            <div class="module-label">BATTERY</div>
                            <div class="module-value" id="batteryValue">100%</div>
                            <div class="progress-track"><div class="progress-fill green" id="batteryBar" style="width:100%"></div></div>
                        </div>
                        <div class="status-module">
                            <div class="module-label">CPU TEMP</div>
                            <div class="module-value" id="cpuTempValue">35.0°C</div>
                            <div class="progress-track"><div class="progress-fill" id="cpuTempBar" style="width:35%"></div></div>
                        </div>
                        <div class="status-module">
                            <div class="module-label">GPU LOAD</div>
                            <div class="module-value" id="gpuLoadValue">0%</div>
                            <div class="progress-track"><div class="progress-fill" id="gpuLoadBar" style="width:0%"></div></div>
                        </div>
                        <div class="status-module">
                            <div class="module-label">MEMORY</div>
                            <div class="module-value" id="memValue">45%</div>
                            <div class="progress-track"><div class="progress-fill" id="memBar" style="width:45%"></div></div>
                        </div>
                        <div class="status-module">
                            <div class="module-label">STATUS</div>
                            <div class="module-value" id="robotStatusValue" style="font-size:16px">IDLE</div>
                        </div>
                        <div class="status-module">
                            <div class="module-label">POSITION</div>
                            <div class="module-value" id="positionValue" style="font-size:14px">(0.0, 0.0)</div>
                        </div>
                    </div>
                    
                    <div class="waypoint-track">
                        <div class="waypoint-line" id="waypointLine"></div>
                        <div class="waypoint-dot active" id="wp1"></div>
                        <div class="waypoint-dot" id="wp2"></div>
                        <div class="waypoint-dot" id="wp3"></div>
                        <div class="waypoint-dot" id="wp4"></div>
                        <div class="waypoint-dot" id="wp5"></div>
                        <div class="waypoint-info" id="waypointText">WP001/005</div>
                    </div>
                </div>
            </div>

            <!-- Motion Control -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">◈ MOTION CONTROL</div>
                </div>
                <div class="panel-body">
                    <div class="control-grid">
                        <button class="ctrl-btn" onclick="sendCmd('rotate_left')">↰<span class="label">LEFT</span></button>
                        <button class="ctrl-btn primary" onclick="sendCmd('forward')">↑<span class="label">FORWARD</span></button>
                        <button class="ctrl-btn" onclick="sendCmd('rotate_right')">↱<span class="label">RIGHT</span></button>
                        <button class="ctrl-btn" onclick="sendCmd('left')">←<span class="label">LEFT</span></button>
                        <button class="ctrl-btn" style="opacity:0.3;cursor:default">⏹<span class="label">STOP</span></button>
                        <button class="ctrl-btn" onclick="sendCmd('right')">→<span class="label">RIGHT</span></button>
                        <button class="ctrl-btn" onclick="sendCmd('backward')">↓<span class="label">BACK</span></button>
                    </div>
                    <div class="action-buttons">
                        <button class="action-btn up" onclick="sendCmd('stand_up')">⬆ STAND UP</button>
                        <button class="action-btn down" onclick="sendCmd('stand_down')">⬇ STAND DOWN</button>
                        <button class="action-btn emergency" onclick="sendCmd('emergency_stop')">🛑 EMERGENCY STOP</button>
                    </div>
                </div>
            </div>

            <!-- Demo Control -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">◈ DEMO MODE</div>
                </div>
                <div class="panel-body">
                    <div class="demo-grid">
                        <button class="demo-btn" onclick="sendDemo()">📊 SEND INSPECTION DATA</button>
                        <button class="demo-btn" onclick="sendDemoStatus()">🔄 UPDATE STATUS</button>
                    </div>
                </div>
            </div>

            <!-- Alerts -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">◈ ACTIVE ALERTS <span style="color:var(--neon-red)" id="alertBadge">0</span></div>
                </div>
                <div class="panel-body">
                    <div class="alert-list" id="alertList">
                        <div class="empty-state"><div class="icon">🔕</div>NO ALERTS</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let ws = null, inspections = [], alerts = [];
        let robot = { battery: 100, cpu_temp: 35, gpu_load: 0, memory_usage: 45, status: 'idle', waypoint: 'WP001', completed: 0 };
        
        function connect() {
            ws = new WebSocket('ws://' + location.host + ':8765/ws');
            ws.onopen = () => {
                document.getElementById('connDot').className = 'status-dot connected';
                document.getElementById('connStatus').textContent = 'SYSTEM ONLINE';
                document.getElementById('connStatus').style.color = 'var(--neon-green)';
            };
            ws.onmessage = (e) => {
                const m = JSON.parse(e.data);
                if (m.type === 'inspection') { addInspection(m.data); }
                else if (m.type === 'robot_status') updateRobot(m.data);
            };
            ws.onclose = () => {
                document.getElementById('connDot').className = 'status-dot';
                document.getElementById('connStatus').textContent = 'SYSTEM OFFLINE';
                setTimeout(connect, 3000);
            };
        }
        
        function addInspection(d) {
            inspections.unshift({ time: new Date().toLocaleTimeString(), cracks: Math.floor(Math.random()*3), temp: d.temperature?.value || 35, status: d.temperature?.status || 'NORMAL' });
            if (inspections.length > 20) inspections.pop();
            renderTable();
            document.getElementById('totalInspections').textContent = String(inspections.length).padStart(3,'0');
            document.getElementById('crackCount').textContent = String(inspections.filter(i=>i.cracks>0).length).padStart(3,'0');
            document.getElementById('inspectionTime').textContent = inspections[0]?.time || '--:--:--';
        }
        
        function renderTable() {
            const tb = document.getElementById('inspectionTable');
            if (!inspections.length) { tb.innerHTML = '<tr><td colspan="6"><div class="empty-state"><div class="icon">📭</div>NO DATA</div></td></tr>'; return; }
            tb.innerHTML = inspections.map(i => {
                const c = i.status === 'NORMAL' ? 'success' : i.status === 'WARN' ? 'warning' : 'danger';
                return `<tr><td>${i.time}</td><td>LITE3-001</td><td>WP00${Math.floor(Math.random()*5)+1}</td><td>${i.cracks}</td><td>${i.temp}°C</td><td><span class="badge badge-${c}">${i.status}</span></td></tr>`;
            }).join('');
        }
        
        function updateRobot(d) {
            robot = d;
            document.getElementById('batteryValue').textContent = d.battery + '%';
            document.getElementById('batteryBar').style.width = d.battery + '%';
            document.getElementById('batteryValue').className = 'module-value' + (d.battery < 20 ? ' danger' : d.battery < 50 ? ' warning' : '');
            
            document.getElementById('cpuTempValue').textContent = d.cpu_temp + '°C';
            document.getElementById('cpuTempBar').style.width = Math.min(d.cpu_temp, 100) + '%';
            document.getElementById('cpuTempValue').className = 'module-value' + (d.cpu_temp > 60 ? ' danger' : d.cpu_temp > 50 ? ' warning' : '');
            
            document.getElementById('gpuLoadValue').textContent = d.gpu_load + '%';
            document.getElementById('gpuLoadBar').style.width = d.gpu_load + '%';
            document.getElementById('memValue').textContent = d.memory_usage + '%';
            document.getElementById('memBar').style.width = d.memory_usage + '%';
            
            const sm = { 'idle': 'IDLE', 'moving': 'MOVING', 'inspecting': 'INSPECTING' };
            document.getElementById('robotStatusValue').textContent = sm[d.status] || d.status;
            
            if (d.position) document.getElementById('positionValue').textContent = `(${d.position.x.toFixed(1)}, ${d.position.y.toFixed(1)})`;
            
            if (d.waypoint) {
                document.getElementById('waypointText').textContent = d.waypoint + '/005';
                const completed = d.completed_waypoints || 0;
                document.querySelectorAll('.waypoint-dot').forEach((dot, i) => {
                    dot.className = 'waypoint-dot' + (i < completed ? ' completed' : i === completed ? ' active' : '');
                });
                document.getElementById('waypointLine').style.cssText = `width:${completed*20}%`;
            }
        }
        
        async function sendCmd(c) {
            try { await fetch('/api/control/' + c, {method: 'POST'}); } catch(e) { console.error(e); }
        }
        
        async function sendDemo() {
            try { await fetch('/api/demo', {method: 'POST'}); document.getElementById('alertCount').textContent = String(Math.floor(Math.random()*5)+1).padStart(3,'0'); } catch(e) {}
        }
        
        async function sendDemoStatus() {
            try { await fetch('/api/demo', {method: 'POST'}); } catch(e) {}
        }
        
        setInterval(() => document.getElementById('currentTime').textContent = new Date().toLocaleTimeString(), 1000);
        setInterval(() => fetch('/api/status').then(r => r.json()).then(d => {
            document.getElementById('clientCount').textContent = d.clients;
            document.getElementById('alertCount').textContent = String(d.alerts).padStart(3,'0');
        }), 2000);
        
        connect();
    </script>
</body>
</html>"""


async def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
    server = uvicorn.Server(config)
    logger.info(f"YUEYING MONITOR v1.7 | http://0.0.0.0:{HTTP_PORT} | WS: ws://0.0.0.0:{WS_PORT}/ws")
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
