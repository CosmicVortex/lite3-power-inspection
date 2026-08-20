#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3 监测平台 - 实时数据面板版
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
robot_status = {"battery": 68, "cpu_temp": 35.0, "gpu_load": 0, "memory_usage": 45,
                "status": "idle", "position": {"x": 0.0, "y": 0.0},
                "waypoint": "WP001", "total_waypoints": 5, "completed_waypoints": 0,
                "endurance_hours": 1.8}
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
        if ws in connections: connections.remove(ws)

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
    robot_status.update({
        "battery": random.randint(60, 95),
        "cpu_temp": round(random.uniform(35, 55), 1),
        "gpu_load": random.randint(20, 80),
        "memory_usage": random.randint(40, 70),
        "waypoint": f"WP{random.randint(1,5):03d}",
        "completed_waypoints": random.randint(1, 4),
        "endurance_hours": round(random.uniform(1.5, 2.5), 1),
        "status": "inspecting"
    })
    inspections.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "cracks": random.randint(0, 3),
        "temp": round(random.uniform(25, 55), 1),
        "status": random.choice(["NORMAL", "WARN", "CRITICAL"])
    })
    for ws in connections:
        await ws.send_json({"type": "inspection", "data": inspections[-1]})
        await ws.send_json({"type": "robot_status", "data": robot_status})
    return {"status": "ok"}

class Monitor:
    async def process(self, data: Dict, ws: WebSocket):
        t = time.time()
        p = data.get("payload", data.get("data", {}))
        if data.get("type") == "system_status":
            for k in ["battery","cpu_temp","gpu_load","memory_usage","status","waypoint","position","endurance_hours"]:
                if k in p: robot_status[k] = p[k]
            await ws.send_json({"type": "robot_status", "data": robot_status})

monitor = Monitor()


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>绝影Lite3 监测平台</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f5f7fa;
    color: #333;
    min-height: 100vh;
}

/* 顶部导航 */
.navbar {
    background: #fff;
    border-bottom: 1px solid #e5e7eb;
    padding: 0 24px;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.navbar-brand {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 18px;
    font-weight: 600;
    color: #111827;
}

.navbar-brand .logo {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 16px;
}

.navbar-status {
    display: flex;
    align-items: center;
    gap: 20px;
    font-size: 13px;
    color: #6b7280;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #d1d5db;
    transition: all 0.3s;
}

.status-dot.connected {
    background: #10b981;
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
}

/* 主内容区 */
.main-content {
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px;
}

/* 实时数据面板标题 */
.section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
}

.section-title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 16px;
    font-weight: 600;
    color: #111827;
}

.section-title::before {
    content: '';
    width: 4px;
    height: 20px;
    background: linear-gradient(180deg, #3b82f6, #8b5cf6);
    border-radius: 2px;
}

.refresh-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    font-size: 13px;
    color: #6b7280;
    cursor: pointer;
    transition: all 0.2s;
}

.refresh-btn:hover {
    background: #e5e7eb;
    color: #374151;
}

/* 机器人卡片 */
.robot-card {
    background: #fff;
    border-radius: 12px;
    border: 1px solid #e5e7eb;
    overflow: hidden;
    margin-bottom: 24px;
}

.robot-card-header {
    padding: 16px 20px;
    border-bottom: 1px solid #f3f4f6;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.robot-name {
    font-size: 15px;
    font-weight: 600;
    color: #111827;
}

.status-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: #dcfce7;
    color: #166534;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
}

.status-badge.offline {
    background: #fee2e2;
    color: #991b1b;
}

.robot-card-body {
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: 0;
}

.robot-image {
    width: 120px;
    height: 120px;
    background: linear-gradient(135deg, #f3f4f6, #e5e7eb);
    display: flex;
    align-items: center;
    justify-content: center;
    border-right: 1px solid #f3f4f6;
}

.robot-image img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
}

.robot-image .placeholder {
    font-size: 48px;
    opacity: 0.3;
}

.robot-info {
    padding: 20px;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
}

.info-item {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.info-label {
    font-size: 12px;
    color: #6b7280;
    font-weight: 500;
}

.info-value {
    display: flex;
    align-items: center;
    gap: 8px;
}

.battery-icon {
    width: 20px;
    height: 12px;
    border: 2px solid #10b981;
    border-radius: 2px;
    position: relative;
    display: flex;
    align-items: center;
    padding: 1px;
}

.battery-icon::after {
    content: '';
    position: absolute;
    right: -4px;
    width: 3px;
    height: 6px;
    background: #10b981;
    border-radius: 0 1px 1px 0;
}

.battery-fill {
    height: 100%;
    background: #10b981;
    border-radius: 1px;
    transition: width 0.5s;
}

.info-number {
    font-size: 20px;
    font-weight: 600;
    color: #111827;
}

.info-unit {
    font-size: 13px;
    color: #6b7280;
}

/* 统计卡片 */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}

.stat-card {
    background: #fff;
    border-radius: 12px;
    border: 1px solid #e5e7eb;
    padding: 20px;
    transition: all 0.2s;
}

.stat-card:hover {
    border-color: #3b82f6;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
}

.stat-icon {
    font-size: 24px;
    margin-bottom: 12px;
}

.stat-value {
    font-size: 28px;
    font-weight: 700;
    color: #111827;
    line-height: 1;
}

.stat-label {
    font-size: 13px;
    color: #6b7280;
    margin-top: 8px;
}

/* 表格 */
.table-card {
    background: #fff;
    border-radius: 12px;
    border: 1px solid #e5e7eb;
    overflow: hidden;
}

.table-header {
    padding: 16px 20px;
    border-bottom: 1px solid #f3f4f6;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.table-title {
    font-size: 15px;
    font-weight: 600;
    color: #111827;
}

.table-wrap {
    max-height: 320px;
    overflow-y: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
}

th {
    background: #f9fafb;
    padding: 12px 16px;
    text-align: left;
    font-size: 12px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #e5e7eb;
}

td {
    padding: 12px 16px;
    font-size: 13px;
    color: #374151;
    border-bottom: 1px solid #f3f4f6;
}

tr:hover td {
    background: #f9fafb;
}

.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
}

.badge-success { background: #dcfce7; color: #166534; }
.badge-warning { background: #fef3c7; color: #92400e; }
.badge-danger { background: #fee2e2; color: #991b1b; }

/* 空状态 */
.empty-state {
    text-align: center;
    padding: 40px;
    color: #9ca3af;
}

/* 右侧控制面板 */
.right-panel {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.control-panel {
    background: #fff;
    border-radius: 12px;
    border: 1px solid #e5e7eb;
    overflow: hidden;
}

.panel-header {
    padding: 14px 16px;
    border-bottom: 1px solid #f3f4f6;
    font-size: 14px;
    font-weight: 600;
    color: #111827;
}

.panel-body {
    padding: 16px;
}

/* 控制按钮网格 */
.control-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 12px;
}

.ctrl-btn {
    padding: 12px 8px;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    text-align: center;
}

.ctrl-btn:hover {
    background: #e5e7eb;
    border-color: #d1d5db;
}

.ctrl-btn .icon {
    font-size: 18px;
    display: block;
    margin-bottom: 4px;
}

.ctrl-btn .label {
    font-size: 10px;
    color: #6b7280;
}

.ctrl-btn.primary {
    background: #3b82f6;
    border-color: #3b82f6;
    color: white;
}

.ctrl-btn.primary:hover {
    background: #2563eb;
}

.ctrl-btn.danger {
    background: #ef4444;
    border-color: #ef4444;
    color: white;
}

.ctrl-btn.danger:hover {
    background: #dc2626;
}

.action-btns {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.action-btn {
    padding: 10px 12px;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    color: #374151;
    text-align: left;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 8px;
}

.action-btn:hover {
    background: #e5e7eb;
}

.action-btn.up { border-left: 3px solid #10b981; }
.action-btn.down { border-left: 3px solid #f59e0b; }
.action-btn.emergency { border-left: 3px solid #ef4444; color: #ef4444; }

/* 演示按钮 */
.demo-btns {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}

.demo-btn {
    padding: 10px;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    cursor: pointer;
    font-size: 12px;
    color: #374151;
    transition: all 0.2s;
}

.demo-btn:hover {
    background: #e5e7eb;
}

/* 告警列表 */
.alert-list {
    max-height: 180px;
    overflow-y: auto;
}

.alert-item {
    padding: 10px 12px;
    border-radius: 6px;
    margin-bottom: 6px;
    border-left: 3px solid;
    background: #f9fafb;
}

.alert-item.warn { border-color: #f59e0b; }
.alert-item.critical { border-color: #ef4444; }
.alert-item.crack { border-color: #8b5cf6; }

.alert-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
}

.alert-text { color: #374151; }
.alert-time { color: #9ca3af; }

/* 布局 */
.layout {
    display: grid;
    grid-template-columns: 1fr 360px;
    gap: 24px;
}

@media (max-width: 1200px) {
    .layout { grid-template-columns: 1fr; }
    .robot-card-body { grid-template-columns: 1fr; }
    .robot-image { width: 100%; height: 160px; border-right: none; border-bottom: 1px solid #f3f4f6; }
}
</style>
</head>
<body>
    <!-- 导航栏 -->
    <nav class="navbar">
        <div class="navbar-brand">
            <div class="logo">🤖</div>
            <span>绝影Lite3 监测平台</span>
        </div>
        <div class="navbar-status">
            <div class="status-item">
                <div class="status-dot" id="connDot"></div>
                <span id="connStatus">未连接</span>
            </div>
            <div class="status-item">📡 <span id="clientCount">0</span> 在线</div>
            <div class="status-item">🕐 <span id="currentTime">--:--:--</span></div>
        </div>
    </nav>

    <!-- 主内容 -->
    <div class="main-content">
        <!-- 实时数据标题 -->
        <div class="section-header">
            <div class="section-title">实时数据</div>
            <button class="refresh-btn" onclick="refreshData()">
                <span>↻</span> 刷新
            </button>
        </div>

        <div class="layout">
            <!-- 左侧 -->
            <div class="left-column">
                <!-- 机器人卡片 -->
                <div class="robot-card">
                    <div class="robot-card-header">
                        <div class="robot-name">机器狗 #02</div>
                        <div class="status-badge" id="onlineBadge">
                            <span>●</span> 在线
                        </div>
                    </div>
                    <div class="robot-card-body">
                        <div class="robot-image">
                            <div class="placeholder">🤖</div>
                        </div>
                        <div class="robot-info">
                            <div class="info-item">
                                <div class="info-label">电量</div>
                                <div class="info-value">
                                    <div class="battery-icon">
                                        <div class="battery-fill" id="batteryFill" style="width:68%"></div>
                                    </div>
                                    <span class="info-number" id="batteryValue">68%</span>
                                </div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">预估续航</div>
                                <div class="info-value">
                                    <span class="info-number" id="enduranceValue">1.8</span>
                                    <span class="info-unit">h</span>
                                </div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">CPU温度</div>
                                <div class="info-value">
                                    <span class="info-number" id="cpuTempValue">35.0</span>
                                    <span class="info-unit">℃</span>
                                </div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">GPU负载</div>
                                <div class="info-value">
                                    <span class="info-number" id="gpuLoadValue">0</span>
                                    <span class="info-unit">%</span>
                                </div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">运行状态</div>
                                <div class="info-value">
                                    <span class="info-number" id="statusValue" style="font-size:16px">待机</span>
                                </div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">当前位置</div>
                                <div class="info-value">
                                    <span class="info-number" id="positionValue" style="font-size:14px">(0.0, 0.0)</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

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

                <!-- 巡检记录表格 -->
                <div class="table-card">
                    <div class="table-header">
                        <div class="table-title">最近巡检记录</div>
                        <span style="font-size:12px;color:#6b7280" id="inspectionTime">--:--:--</span>
                    </div>
                    <div class="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>时间</th>
                                    <th>设备</th>
                                    <th>航点</th>
                                    <th>裂缝数</th>
                                    <th>温度</th>
                                    <th>状态</th>
                                </tr>
                            </thead>
                            <tbody id="inspectionTable">
                                <tr><td colspan="6"><div class="empty-state">暂无数据</div></td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- 右侧控制面板 -->
            <div class="right-panel">
                <!-- 运动控制 -->
                <div class="control-panel">
                    <div class="panel-header">运动控制</div>
                    <div class="panel-body">
                        <div class="control-grid">
                            <button class="ctrl-btn" onclick="sendCmd('rotate_left')">
                                <span class="icon">↰</span>
                                <span class="label">左转</span>
                            </button>
                            <button class="ctrl-btn primary" onclick="sendCmd('forward')">
                                <span class="icon">↑</span>
                                <span class="label">前进</span>
                            </button>
                            <button class="ctrl-btn" onclick="sendCmd('rotate_right')">
                                <span class="icon">↱</span>
                                <span class="label">右转</span>
                            </button>
                            <button class="ctrl-btn" onclick="sendCmd('left')">
                                <span class="icon">←</span>
                                <span class="label">左移</span>
                            </button>
                            <button class="ctrl-btn" style="opacity:0.4;cursor:default">
                                <span class="icon">⏹</span>
                                <span class="label">停止</span>
                            </button>
                            <button class="ctrl-btn" onclick="sendCmd('right')">
                                <span class="icon">→</span>
                                <span class="label">右移</span>
                            </button>
                            <button class="ctrl-btn" onclick="sendCmd('backward')">
                                <span class="icon">↓</span>
                                <span class="label">后退</span>
                            </button>
                        </div>
                        <div class="action-btns">
                            <button class="action-btn up" onclick="sendCmd('stand_up')">⬆ 起立</button>
                            <button class="action-btn down" onclick="sendCmd('stand_down')">⬇ 趴下</button>
                            <button class="action-btn emergency" onclick="sendCmd('emergency_stop')">🛑 急停</button>
                        </div>
                    </div>
                </div>

                <!-- 演示控制 -->
                <div class="control-panel">
                    <div class="panel-header">演示控制</div>
                    <div class="panel-body">
                        <div class="demo-btns">
                            <button class="demo-btn" onclick="sendDemo()">📊 发送巡检数据</button>
                            <button class="demo-btn" onclick="sendDemoStatus()">🔄 更新状态</button>
                        </div>
                    </div>
                </div>

                <!-- 实时告警 -->
                <div class="control-panel">
                    <div class="panel-header">
                        实时告警
                        <span style="color:#ef4444;font-size:12px;margin-left:auto" id="alertBadge">0</span>
                    </div>
                    <div class="panel-body">
                        <div class="alert-list" id="alertList">
                            <div class="empty-state" style="padding:20px">暂无告警</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let ws = null, inspections = [], alerts = [];
        let robot = { battery: 68, cpu_temp: 35, gpu_load: 0, memory_usage: 45, status: 'idle', waypoint: 'WP001', endurance_hours: 1.8 };
        
        function connect() {
            ws = new WebSocket('ws://' + location.host + ':8765/ws');
            ws.onopen = () => {
                document.getElementById('connDot').className = 'status-dot connected';
                document.getElementById('connStatus').textContent = '已连接';
            };
            ws.onmessage = (e) => {
                const m = JSON.parse(e.data);
                if (m.type === 'inspection') addInspection(m.data);
                else if (m.type === 'robot_status') updateRobot(m.data);
            };
            ws.onclose = () => {
                document.getElementById('connDot').className = 'status-dot';
                document.getElementById('connStatus').textContent = '未连接';
                setTimeout(connect, 3000);
            };
        }
        
        function addInspection(d) {
            inspections.unshift({ time: new Date().toLocaleTimeString(), cracks: Math.floor(Math.random()*3), temp: d.temperature?.value || 35, status: d.temperature?.status || 'NORMAL' });
            if (inspections.length > 20) inspections.pop();
            renderTable();
            document.getElementById('totalInspections').textContent = inspections.length;
            document.getElementById('crackCount').textContent = inspections.filter(i=>i.cracks>0).length;
            document.getElementById('inspectionTime').textContent = inspections[0]?.time || '--:--:--';
        }
        
        function renderTable() {
            const tb = document.getElementById('inspectionTable');
            if (!inspections.length) { tb.innerHTML = '<tr><td colspan="6"><div class="empty-state">暂无数据</div></td></tr>'; return; }
            tb.innerHTML = inspections.map(i => {
                const c = i.status === 'NORMAL' ? 'success' : i.status === 'WARN' ? 'warning' : 'danger';
                return `<tr><td>${i.time}</td><td>LITE3-001</td><td>WP00${Math.floor(Math.random()*5)+1}</td><td>${i.cracks}</td><td>${i.temp}℃</td><td><span class="badge badge-${c}">${i.status}</span></td></tr>`;
            }).join('');
        }
        
        function updateRobot(d) {
            robot = d;
            document.getElementById('batteryValue').textContent = d.battery + '%';
            document.getElementById('batteryFill').style.width = d.battery + '%';
            document.getElementById('enduranceValue').textContent = d.endurance_hours?.toFixed(1) || '1.8';
            document.getElementById('cpuTempValue').textContent = d.cpu_temp?.toFixed(1) || '35.0';
            document.getElementById('gpuLoadValue').textContent = d.gpu_load || 0;
            const sm = { 'idle': '待机', 'moving': '运动中', 'inspecting': '巡检中' };
            document.getElementById('statusValue').textContent = sm[d.status] || d.status;
            if (d.position) document.getElementById('positionValue').textContent = `(${d.position.x.toFixed(1)}, ${d.position.y.toFixed(1)})`;
        }
        
        async function sendCmd(c) {
            try { await fetch('/api/control/' + c, {method: 'POST'}); } catch(e) { console.error(e); }
        }
        
        async function sendDemo() {
            try { await fetch('/api/demo', {method: 'POST'}); document.getElementById('alertCount').textContent = Math.floor(Math.random()*5)+1; } catch(e) {}
        }
        
        async function sendDemoStatus() {
            try { await fetch('/api/demo', {method: 'POST'}); } catch(e) {}
        }
        
        function refreshData() {
            fetch('/api/robot').then(r => r.json()).then(d => updateRobot(d));
        }
        
        setInterval(() => document.getElementById('currentTime').textContent = new Date().toLocaleTimeString(), 1000);
        setInterval(() => fetch('/api/status').then(r => r.json()).then(d => {
            document.getElementById('clientCount').textContent = d.clients;
            document.getElementById('alertCount').textContent = d.alerts;
        }), 2000);
        
        connect();
    </script>
</body>
</html>"""


async def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
    server = uvicorn.Server(config)
    logger.info(f"监测平台启动: http://0.0.0.0:{HTTP_PORT}")
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
