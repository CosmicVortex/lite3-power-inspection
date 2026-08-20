#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3 监测平台 - 设计稿还原版
"""

import asyncio, json, time, logging, struct, socket, base64
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

# 读取机器狗图片
ROBOT_IMAGE_URI = ""
try:
    with open(Path(__file__).parent.parent / "docs/assets/03-绝影Lite3机器狗.jpg", "rb") as f:
        ROBOT_IMAGE_URI = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
except:
    ROBOT_IMAGE_URI = ""

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
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: #f0f2f5;
    color: #1a1a1a;
    min-height: 100vh;
}

/* 顶部导航 */
.topbar {
    background: #fff;
    border-bottom: 1px solid #e8e8e8;
    padding: 0 24px;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    position: sticky;
    top: 0;
    z-index: 100;
}

.topbar-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.topbar-logo {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, #1890ff, #096dd9);
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 16px;
}

.topbar-title {
    font-size: 16px;
    font-weight: 500;
    color: #1a1a1a;
}

.topbar-right {
    display: flex;
    align-items: center;
    gap: 20px;
    font-size: 13px;
    color: #666;
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 6px;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #d9d9d9;
    transition: all 0.3s;
}

.status-dot.online {
    background: #52c41a;
    box-shadow: 0 0 0 3px rgba(82, 196, 26, 0.15);
}

/* 页面主体 */
.page-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px;
}

/* 章节标题 */
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
    color: #1a1a1a;
}

.section-title::before {
    content: '';
    width: 4px;
    height: 18px;
    background: linear-gradient(180deg, #1890ff, #096dd9);
    border-radius: 2px;
}

.refresh-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px;
    background: #fafafa;
    border: 1px solid #d9d9d9;
    border-radius: 4px;
    font-size: 13px;
    color: #666;
    cursor: pointer;
    transition: all 0.2s;
}

.refresh-btn:hover {
    border-color: #1890ff;
    color: #1890ff;
}

/* 机器人信息卡片 */
.robot-info-card {
    background: #fff;
    border-radius: 8px;
    border: 1px solid #e8e8e8;
    overflow: hidden;
    margin-bottom: 24px;
}

.robot-info-header {
    padding: 16px 20px;
    border-bottom: 1px solid #f0f0f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.robot-name {
    font-size: 15px;
    font-weight: 600;
    color: #1a1a1a;
}

.status-tag {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    background: #f6ffed;
    border: 1px solid #b7eb8f;
    border-radius: 20px;
    font-size: 12px;
    color: #52c41a;
}

.status-tag.offline {
    background: #fff2f0;
    border-color: #ffa39e;
    color: #ff4d4f;
}

.robot-info-body {
    display: grid;
    grid-template-columns: 140px 1fr;
}

.robot-image {
    width: 140px;
    height: 140px;
    background: linear-gradient(135deg, #f5f5f5, #ebebeb);
    display: flex;
    align-items: center;
    justify-content: center;
    border-right: 1px solid #f0f0f0;
}

.robot-image img {
    max-width: 90%;
    max-height: 90%;
    object-fit: contain;
}

.robot-details {
    padding: 20px;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
}

.detail-item {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.detail-label {
    font-size: 12px;
    color: #8c8c8c;
    font-weight: 500;
}

.detail-value {
    display: flex;
    align-items: center;
    gap: 8px;
}

.battery-widget {
    display: flex;
    align-items: center;
    gap: 8px;
}

.battery-icon {
    position: relative;
    width: 24px;
    height: 12px;
    border: 2px solid #52c41a;
    border-radius: 2px;
    display: flex;
    align-items: center;
    padding: 1px;
}

.battery-icon::after {
    content: '';
    position: absolute;
    right: -5px;
    width: 4px;
    height: 6px;
    background: #52c41a;
    border-radius: 0 1px 1px 0;
}

.battery-level {
    height: 100%;
    background: #52c41a;
    border-radius: 1px;
    transition: width 0.5s;
}

.detail-number {
    font-size: 22px;
    font-weight: 600;
    color: #1a1a1a;
    line-height: 1;
}

.detail-unit {
    font-size: 13px;
    color: #8c8c8c;
}

/* 统计卡片 */
.stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}

.stat-card {
    background: #fff;
    border-radius: 8px;
    border: 1px solid #e8e8e8;
    padding: 20px;
    transition: all 0.2s;
}

.stat-card:hover {
    border-color: #1890ff;
    box-shadow: 0 2px 8px rgba(24, 144, 255, 0.1);
}

.stat-icon {
    font-size: 24px;
    margin-bottom: 12px;
}

.stat-number {
    font-size: 32px;
    font-weight: 700;
    color: #1a1a1a;
    line-height: 1;
}

.stat-label {
    font-size: 13px;
    color: #8c8c8c;
    margin-top: 8px;
}

/* 主内容布局 */
.main-layout {
    display: grid;
    grid-template-columns: 1fr 380px;
    gap: 24px;
}

/* 面板 */
.panel {
    background: #fff;
    border-radius: 8px;
    border: 1px solid #e8e8e8;
    overflow: hidden;
}

.panel-header {
    padding: 14px 16px;
    border-bottom: 1px solid #f0f0f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.panel-title {
    font-size: 14px;
    font-weight: 600;
    color: #1a1a1a;
}

.panel-body {
    padding: 16px;
}

/* 表格 */
.data-table {
    width: 100%;
    border-collapse: collapse;
}

.data-table th {
    background: #fafafa;
    padding: 12px 16px;
    text-align: left;
    font-size: 12px;
    font-weight: 600;
    color: #8c8c8c;
    border-bottom: 1px solid #f0f0f0;
}

.data-table td {
    padding: 12px 16px;
    font-size: 13px;
    color: #595959;
    border-bottom: 1px solid #f0f0f0;
}

.data-table tr:hover td {
    background: #fafafa;
}

.tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 2px;
    font-size: 11px;
    font-weight: 500;
}

.tag-success { background: #f6ffed; color: #52c41a; border: 1px solid #b7eb8f; }
.tag-warning { background: #fffbe6; color: #faad14; border: 1px solid #ffe58f; }
.tag-error { background: #fff2f0; color: #ff4d4f; border: 1px solid #ffa39e; }

/* 视频区域 */
.video-placeholder {
    background: #fafafa;
    border: 1px dashed #d9d9d9;
    border-radius: 4px;
    padding: 32px;
    text-align: center;
    color: #8c8c8c;
}

.video-placeholder .icon {
    font-size: 36px;
    margin-bottom: 8px;
    opacity: 0.5;
}

.video-placeholder .info {
    font-size: 12px;
    color: #bfbfbf;
}

/* 控制按钮 */
.control-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 12px;
}

.ctrl-btn {
    padding: 14px 8px;
    background: #fafafa;
    border: 1px solid #d9d9d9;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
    text-align: center;
}

.ctrl-btn:hover {
    border-color: #1890ff;
    color: #1890ff;
    background: #e6f7ff;
}

.ctrl-btn .icon {
    font-size: 20px;
    display: block;
    margin-bottom: 4px;
}

.ctrl-btn .label {
    font-size: 10px;
    color: #8c8c8c;
}

.ctrl-btn.primary {
    background: #1890ff;
    border-color: #1890ff;
    color: #fff;
}

.ctrl-btn.primary:hover {
    background: #40a9ff;
    border-color: #40a9ff;
}

.ctrl-btn.danger {
    background: #ff4d4f;
    border-color: #ff4d4f;
    color: #fff;
}

.ctrl-btn.danger:hover {
    background: #ff7875;
    border-color: #ff7875;
}

.action-buttons {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.action-btn {
    padding: 10px 12px;
    background: #fafafa;
    border: 1px solid #d9d9d9;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    color: #595959;
    text-align: left;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 8px;
}

.action-btn:hover {
    border-color: #1890ff;
    color: #1890ff;
}

.action-btn.up { border-left: 3px solid #52c41a; }
.action-btn.down { border-left: 3px solid #faad14; }
.action-btn.emergency { border-left: 3px solid #ff4d4f; color: #ff4d4f; }

/* 演示按钮 */
.demo-buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}

.demo-btn {
    padding: 10px;
    background: #fafafa;
    border: 1px solid #d9d9d9;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    color: #595959;
    transition: all 0.2s;
}

.demo-btn:hover {
    border-color: #722ed1;
    color: #722ed1;
    background: #f9f0ff;
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
    background: #fafafa;
    font-size: 12px;
}

.alert-item.warn { border-color: #faad14; }
.alert-item.critical { border-color: #ff4d4f; }
.alert-item.crack { border-color: #722ed1; }

.alert-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.alert-text { color: #595959; }
.alert-time { color: #bfbfbf; font-size: 11px; }

/* 空状态 */
.empty-state {
    text-align: center;
    padding: 40px;
    color: #bfbfbf;
}

/* 响应式 */
@media (max-width: 1200px) {
    .main-layout { grid-template-columns: 1fr; }
    .robot-info-body { grid-template-columns: 1fr; }
    .robot-image { width: 100%; height: 160px; border-right: none; border-bottom: 1px solid #f0f0f0; }
    .robot-details { grid-template-columns: repeat(2, 1fr); }
}
</style>
</head>
<body>
    <!-- 顶部导航 -->
    <div class="topbar">
        <div class="topbar-left">
            <div class="topbar-logo">🤖</div>
            <span class="topbar-title">绝影Lite3 监测平台</span>
        </div>
        <div class="topbar-right">
            <div class="status-indicator">
                <div class="status-dot" id="connDot"></div>
                <span id="connStatus">未连接</span>
            </div>
            <div class="status-indicator">📡 <span id="clientCount">0</span> 在线</div>
            <div class="status-indicator">🕐 <span id="currentTime">--:--:--</span></div>
        </div>
    </div>

    <!-- 页面主体 -->
    <div class="page-container">
        <!-- 章节标题 -->
        <div class="section-header">
            <div class="section-title">实时数据</div>
            <button class="refresh-btn" onclick="refreshData()">
                <span>↻</span> 刷新
            </button>
        </div>

        <!-- 机器人信息卡片 -->
        <div class="robot-info-card">
            <div class="robot-info-header">
                <div class="robot-name">机器狗 #02</div>
                <div class="status-tag" id="onlineTag">
                    <span>●</span> 在线
                </div>
            </div>
            <div class="robot-info-body">
                <div class="robot-image">
                    <img src="__ROBOT_IMAGE__" alt="绝影Lite3机器狗" onerror="this.style.display='none';this.parentElement.innerHTML='🐕'">
                </div>
                <div class="robot-details">
                    <div class="detail-item">
                        <div class="detail-label">电量</div>
                        <div class="detail-value">
                            <div class="battery-widget">
                                <div class="battery-icon">
                                    <div class="battery-level" id="batteryLevel" style="width:68%"></div>
                                </div>
                                <span class="detail-number" id="batteryValue">68%</span>
                            </div>
                        </div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">预估续航</div>
                        <div class="detail-value">
                            <span class="detail-number" id="enduranceValue">1.8</span>
                            <span class="detail-unit">h</span>
                        </div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">CPU温度</div>
                        <div class="detail-value">
                            <span class="detail-number" id="cpuTempValue">35.0</span>
                            <span class="detail-unit">℃</span>
                        </div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">GPU负载</div>
                        <div class="detail-value">
                            <span class="detail-number" id="gpuLoadValue">0</span>
                            <span class="detail-unit">%</span>
                        </div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">运行状态</div>
                        <div class="detail-value">
                            <span class="detail-number" id="statusValue" style="font-size:16px">待机</span>
                        </div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">当前位置</div>
                        <div class="detail-value">
                            <span class="detail-number" id="positionValue" style="font-size:14px">(0.0, 0.0)</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 统计卡片 -->
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-icon">📊</div>
                <div class="stat-number" id="totalInspections">0</div>
                <div class="stat-label">总巡检次数</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">✅</div>
                <div class="stat-number" id="normalCount">0</div>
                <div class="stat-label">正常检测</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🔍</div>
                <div class="stat-number" id="crackCount">0</div>
                <div class="stat-label">裂缝检测</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">⚠️</div>
                <div class="stat-number" id="alertCount">0</div>
                <div class="stat-label">待处理告警</div>
            </div>
        </div>

        <!-- 主内容布局 -->
        <div class="main-layout">
            <!-- 左侧 -->
            <div class="left-column">
                <!-- 巡检记录表格 -->
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">最近巡检记录</div>
                        <span style="font-size:12px;color:#8c8c8c" id="inspectionTime">--:--:--</span>
                    </div>
                    <div class="panel-body" style="padding:0">
                        <table class="data-table">
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

                <!-- 视频流 -->
                <div class="panel" style="margin-top:16px">
                    <div class="panel-header">
                        <div class="panel-title">实时视频流</div>
                    </div>
                    <div class="panel-body">
                        <div class="video-placeholder">
                            <div class="icon">📹</div>
                            <div>视频流暂未连接</div>
                            <div class="info" style="margin-top:8px">RTSP: rtsp://192.168.1.108:554/id=1&type=0</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 右侧控制面板 -->
            <div class="right-column">
                <!-- 运动控制 -->
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">运动控制</div>
                    </div>
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
                        <div class="action-buttons">
                            <button class="action-btn up" onclick="sendCmd('stand_up')">⬆ 起立</button>
                            <button class="action-btn down" onclick="sendCmd('stand_down')">⬇ 趴下</button>
                            <button class="action-btn emergency" onclick="sendCmd('emergency_stop')">🛑 急停</button>
                        </div>
                    </div>
                </div>

                <!-- 演示控制 -->
                <div class="panel" style="margin-top:16px">
                    <div class="panel-header">
                        <div class="panel-title">演示控制</div>
                    </div>
                    <div class="panel-body">
                        <div class="demo-buttons">
                            <button class="demo-btn" onclick="sendDemo()">📊 发送巡检数据</button>
                            <button class="demo-btn" onclick="sendDemoStatus()">🔄 更新状态</button>
                        </div>
                    </div>
                </div>

                <!-- 实时告警 -->
                <div class="panel" style="margin-top:16px">
                    <div class="panel-header">
                        <div class="panel-title">实时告警 <span style="color:#ff4d4f;font-size:12px;margin-left:auto" id="alertBadge">0</span></div>
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
                document.getElementById('connDot').className = 'status-dot online';
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
                const c = i.status === 'NORMAL' ? 'success' : i.status === 'WARN' ? 'warning' : 'error';
                return `<tr><td>${i.time}</td><td>LITE3-001</td><td>WP00${Math.floor(Math.random()*5)+1}</td><td>${i.cracks}</td><td>${i.temp}℃</td><td><span class="tag tag-${c}">${i.status}</span></td></tr>`;
            }).join('');
        }
        
        function updateRobot(d) {
            robot = d;
            document.getElementById('batteryValue').textContent = d.battery + '%';
            document.getElementById('batteryLevel').style.width = d.battery + '%';
            document.getElementById('enduranceValue').textContent = (d.endurance_hours || 1.8).toFixed(1);
            document.getElementById('cpuTempValue').textContent = (d.cpu_temp || 35).toFixed(1);
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
    # 替换图片占位符
    global DASHBOARD_HTML
    if ROBOT_IMAGE_URI:
        DASHBOARD_HTML = DASHBOARD_HTML.replace("__ROBOT_IMAGE__", ROBOT_IMAGE_URI)
    else:
        DASHBOARD_HTML = DASHBOARD_HTML.replace('__ROBOT_IMAGE__', 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48Y2lyY2xlIGN4PSI1MCIgY3k9IjUwIiByPSI0MCIgZmlsbD0iI2RkZCIvPjx0ZXh0IHg9IjUwIiB5PSI2MCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZm9udC1zaXplPSI0MCI+8J+OwDwvdGV4dD48L3N2Zz4=')
    
    config = uvicorn.Config(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
    server = uvicorn.Server(config)
    logger.info(f"监测平台启动: http://0.0.0.0:{HTTP_PORT}")
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
