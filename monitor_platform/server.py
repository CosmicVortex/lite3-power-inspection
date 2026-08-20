#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3 监测平台 - 键盘手柄控制版
支持方向键/WASD手柄操作
"""

import asyncio, json, time, logging, struct, socket, base64
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
WS_PORT, HTTP_PORT = 8765, 8000
MOTION_HOST, MOTION_PORT = "192.168.1.103", 43893

# ========== 官方协议指令码（来自03-运动主机通讯接口V1.0.8.md）==========
CMD_FORWARD = 0x21010130      # 前后平移：正值向前
CMD_LEFT = 0x21010131        # 左右平移：正值向右  
CMD_TURN = 0x21010135        # 左右转弯：正值向右转
CMD_STAND_UP = 0x21010202    # 起立/趴下切换
CMD_EMERGENCY_STOP = 0x21020C0E  # 软急停
CMD_HOME = 0x21010C05        # 回零
CMD_MOVE_MODE = 0x21010D06   # 移动模式
CMD_STAND_MODE = 0x21010D05  # 原地模式

# ========== 手柄映射键位 ==========
KEY_FORWARD = ['w', 'arrowup']
KEY_BACKWARD = ['s', 'arrowdown']
KEY_LEFT = ['a', 'arrowleft']
KEY_RIGHT = ['d', 'arrowright']
KEY_TURN_LEFT = ['q', 'shift']
KEY_TURN_RIGHT = ['e', 'ctrl']
KEY_STAND_UP = [' ']  # 空格键起立/趴下
KEY_EMERGENCY = ['escape']  # ESC急停

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

# 按键状态
key_state = {"forward": False, "backward": False, "left": False, "right": False,
             "turn_left": False, "turn_right": False, "stand": False}

def send_udp(cmd: int, value: int = 0):
    """发送UDP指令（官方协议格式）"""
    global motion_sock
    try:
        if motion_sock is None:
            motion_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            motion_sock.settimeout(0.5)
        # 官方格式: [cmd:4bytes][value:4bytes][reserved:4bytes]
        packet = struct.pack('<III', cmd, value, 0)
        motion_sock.sendto(packet, (MOTION_HOST, MOTION_PORT))
        logger.debug(f"发送指令: 0x{cmd:08X}, value={value}")
    except Exception as e:
        logger.error(f"UDP发送失败: {e}")

def calculate_velocity():
    """根据按键状态计算速度向量"""
    vx, vy, vw = 0.0, 0.0, 0.0
    speed = 0.5  # 基础速度
    
    if key_state["forward"]:
        vy -= speed    # 向前
    if key_state["backward"]:
        vy += speed    # 向后
    if key_state["left"]:
        vx -= speed    # 向左
    if key_state["right"]:
        vx += speed    # 向右
    if key_state["turn_left"]:
        vw -= speed    # 左转
    if key_state["turn_right"]:
        vw += speed    # 右转
    
    return vx, vy, vw

def send_velocity_command():
    """发送速度控制指令"""
    vx, vy, vw = calculate_velocity()
    
    # 同时有多个方向时，按比例合成
    if vx != 0 or vy != 0 or vw != 0:
        # 对角线移动时降速（约0.707）
        magnitude = (vx**2 + vy**2 + vw**2)**0.5
        if magnitude > 1.0:
            vx, vy, vw = vx/magnitude, vy/magnitude, vw/magnitude
        
        robot_status["status"] = "moving"
        send_udp(CMD_MOVE_MODE)  # 切换到移动模式
        # 官方协议使用独立的轴指令
        if vy != 0: send_udp(CMD_FORWARD, int(vy * 6553))
        if vx != 0: send_udp(CMD_LEFT, int(vx * 6553))
        if vw != 0: send_udp(CMD_TURN, int(vw * 9553))
    else:
        # 停止移动
        if robot_status["status"] == "moving":
            send_udp(CMD_EMERGENCY_STOP)
            robot_status["status"] = "idle"

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
    """处理来自Web界面的控制请求"""
    if action == "stand_up":
        send_udp(CMD_STAND_UP)
        robot_status["status"] = "idle"
    elif action == "emergency_stop":
        send_udp(CMD_EMERGENCY_STOP)
        robot_status["status"] = "idle"
    elif action == "home":
        send_udp(CMD_HOME)
    elif action == "move_mode":
        send_udp(CMD_MOVE_MODE)
    elif action == "stand_mode":
        send_udp(CMD_STAND_MODE)
    return {"status": "ok"}

@app.post("/api/key/{key}")
async def key_press(key: str, state: bool = True):
    """处理键盘按下/释放事件"""
    key = key.lower()
    if key in key_state:
        key_state[key] = state
        if state:  # 按下
            robot_status["status"] = "moving"
            send_velocity_command()
        else:  # 释放
            # 检查是否还有其他键按下
            if not any(key_state.values()):
                send_udp(CMD_EMERGENCY_STOP)
                robot_status["status"] = "idle"
    return {"status": "ok", "key": key, "state": state}

@app.get("/")
async def root(): return HTMLResponse(DASHBOARD_HTML)

@app.get("/api/status")
async def status():
    return {"clients": len(connections), "inspections": len(inspections),
            "alerts": len([a for a in alerts if not a.get("ack")])}

@app.get("/api/robot")
async def get_robot(): return robot_status

@app.get("/api/keys")
async def get_keys():
    """获取当前按键状态"""
    return key_state

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
<title>绝影Lite3 监测平台 - 手柄控制版</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f0f2f5;
    color: #1a1a1a;
    min-height: 100vh;
}

/* 顶部导航 */
.topbar {
    background: #fff;
    border-bottom: 1px solid #e8e8e8;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
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
    font-size: 18px;
    font-weight: 600;
    color: #000;
}

.topbar-right {
    display: flex;
    align-items: center;
    gap: 20px;
}

/* 手柄控制面板 */
.joystick-panel {
    background: #fff;
    border-radius: 12px;
    border: 2px solid #1890ff;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 12px rgba(24, 144, 255, 0.15);
}

.joystick-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #e8e8e8;
}

.joystick-title {
    font-size: 16px;
    font-weight: 600;
    color: #1890ff;
    display: flex;
    align-items: center;
    gap: 8px;
}

.joystick-status {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
}

.status-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #d9d9d9;
    transition: all 0.3s;
}

.status-indicator.active {
    background: #52c41a;
    box-shadow: 0 0 8px #52c41a;
    animation: pulse 1.5s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* 手柄布局 */
.joystick-container {
    display: grid;
    grid-template-columns: repeat(3, 80px);
    grid-template-rows: repeat(3, 80px);
    gap: 8px;
    justify-content: center;
    margin-bottom: 20px;
}

.key-btn {
    width: 80px;
    height: 80px;
    border: 2px solid #d9d9d9;
    border-radius: 12px;
    background: #fafafa;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    transition: all 0.15s;
    user-select: none;
}

.key-btn:hover {
    border-color: #1890ff;
    background: #e6f7ff;
}

.key-btn.active {
    border-color: #1890ff;
    background: #1890ff;
    color: #fff;
    transform: scale(0.95);
    box-shadow: 0 4px 12px rgba(24, 144, 255, 0.4);
}

.key-btn .key-icon {
    font-size: 24px;
}

.key-btn .key-label {
    font-size: 11px;
    color: #666;
}

.key-btn.active .key-label {
    color: #fff;
}

.key-btn .key-hint {
    font-size: 10px;
    color: #999;
    margin-top: 2px;
}

.key-btn.emergency {
    border-color: #ff4d4f;
    background: #fff2f0;
}

.key-btn.emergency:hover, .key-btn.emergency.active {
    background: #ff4d4f;
    border-color: #ff4d4f;
}

/* 辅助按键区 */
.action-buttons {
    display: flex;
    gap: 12px;
    justify-content: center;
    flex-wrap: wrap;
}

.action-btn {
    padding: 12px 24px;
    border: 2px solid #d9d9d9;
    border-radius: 8px;
    background: #fafafa;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 8px;
}

.action-btn:hover {
    border-color: #1890ff;
    color: #1890ff;
}

.action-btn.primary {
    border-color: #52c41a;
    background: #f6ffed;
    color: #52c41a;
}

.action-btn.primary:hover {
    background: #52c41a;
    color: #fff;
}

.action-btn.danger {
    border-color: #ff4d4f;
    background: #fff2f0;
    color: #ff4d4f;
}

.action-btn.danger:hover {
    background: #ff4d4f;
    color: #fff;
}

/* 键盘提示 */
.key-hints {
    margin-top: 20px;
    padding: 16px;
    background: #f9f9f9;
    border-radius: 8px;
    font-size: 12px;
    color: #666;
}

.key-hints h4 {
    margin-bottom: 8px;
    color: #333;
}

.hint-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
}

.hint-item {
    display: flex;
    align-items: center;
    gap: 8px;
}

.key-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 24px;
    height: 24px;
    padding: 0 6px;
    background: #fff;
    border: 1px solid #d9d9d9;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    color: #333;
    box-shadow: 0 2px 0 #d9d9d9;
}

/* 页面主体 */
.page-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px;
}

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
}

.section-title::before {
    content: '';
    width: 4px;
    height: 18px;
    background: linear-gradient(180deg, #1890ff, #096dd9);
    border-radius: 2px;
}

.refresh-btn {
    padding: 6px 12px;
    background: #fafafa;
    border: 1px solid #d9d9d9;
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
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
}

.detail-value {
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
    transition: width 0.5s;
}

.detail-number {
    font-size: 22px;
    font-weight: 600;
    color: #1a1a1a;
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
}

.panel-body {
    padding: 16px;
}

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

.tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 2px;
    font-size: 11px;
    font-weight: 500;
}

.tag-success { background: #f6ffed; color: #52c41a; }
.tag-warning { background: #fffbe6; color: #faad14; }
.tag-error { background: #fff2f0; color: #ff4d4f; }

.video-placeholder {
    background: #fafafa;
    border: 1px dashed #d9d9d9;
    border-radius: 4px;
    padding: 32px;
    text-align: center;
    color: #8c8c8c;
}

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

.empty-state {
    text-align: center;
    padding: 40px;
    color: #bfbfbf;
}

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
            <span class="topbar-title">巡检监控中心</span>
        </div>
        <div class="topbar-right">
            <div class="status-indicator">
                <div class="status-dot" id="connDot"></div>
                <span id="connStatus">未连接</span>
            </div>
            <div>📡 <span id="clientCount">0</span> 在线</div>
            <div>🕐 <span id="currentTime">--:--:--</span></div>
        </div>
    </div>

    <!-- 页面主体 -->
    <div class="page-container">
        <!-- 手柄控制面板 -->
        <div class="joystick-panel">
            <div class="joystick-header">
                <div class="joystick-title">
                    🎮 手柄控制面板
                    <span style="font-size:12px;color:#999;font-weight:400">（按住按键持续移动，松开停止）</span>
                </div>
                <div class="joystick-status">
                    <div class="status-indicator" id="joystickStatus"></div>
                    <span id="joystickText">就绪</span>
                </div>
            </div>
            
            <!-- 方向控制区 -->
            <div class="joystick-container">
                <div></div>
                <div class="key-btn" id="key-forward" data-key="forward">
                    <span class="key-icon">↑</span>
                    <span class="key-label">前进</span>
                    <span class="key-hint">W / ↑</span>
                </div>
                <div></div>
                
                <div class="key-btn" id="key-left" data-key="left">
                    <span class="key-icon">←</span>
                    <span class="key-label">左移</span>
                    <span class="key-hint">A / ←</span>
                </div>
                <div class="key-btn" id="key-stop" style="opacity:0.3;cursor:default">
                    <span class="key-icon">⏹</span>
                    <span class="key-label">停止</span>
                </div>
                <div class="key-btn" id="key-right" data-key="right">
                    <span class="key-icon">→</span>
                    <span class="key-label">右移</span>
                    <span class="key-hint">D / →</span>
                </div>
                
                <div></div>
                <div class="key-btn" id="key-backward" data-key="backward">
                    <span class="key-icon">↓</span>
                    <span class="key-label">后退</span>
                    <span class="key-hint">S / ↓</span>
                </div>
                <div></div>
            </div>
            
            <!-- 旋转控制 -->
            <div style="text-align:center;margin-bottom:16px">
                <span style="font-size:12px;color:#999">旋转控制: </span>
                <span class="key-badge">Q</span> 左转 
                <span class="key-badge">E</span> 右转 
                <span class="key-badge">Shift</span> 左转 
                <span class="key-badge">Ctrl</span> 右转
            </div>
            
            <!-- 功能按键 -->
            <div class="action-buttons">
                <button class="action-btn primary" onclick="sendCmd('stand_up')">⬆ 起立/趴下</button>
                <button class="action-btn danger" onclick="sendCmd('emergency_stop')">🛑 急停</button>
                <button class="action-btn" onclick="sendCmd('home')">🏠 回零</button>
            </div>
            
            <!-- 键盘提示 -->
            <div class="key-hints">
                <h4>📋 键盘操作说明</h4>
                <div class="hint-grid">
                    <div class="hint-item"><span class="key-badge">W</span> / <span class="key-badge">↑</span> 前进</div>
                    <div class="hint-item"><span class="key-badge">S</span> / <span class="key-badge">↓</span> 后退</div>
                    <div class="hint-item"><span class="key-badge">A</span> / <span class="key-badge">←</span> 左移</div>
                    <div class="hint-item"><span class="key-badge">D</span> / <span class="key-badge">→</span> 右移</div>
                    <div class="hint-item"><span class="key-badge">Q</span> / <span class="key-badge">Shift</span> 左转</div>
                    <div class="hint-item"><span class="key-badge">E</span> / <span class="key-badge">Ctrl</span> 右转</div>
                    <div class="hint-item"><span class="key-badge">Space</span> 起立/趴下</div>
                    <div class="hint-item"><span class="key-badge">Esc</span> 急停</div>
                </div>
            </div>
        </div>

        <!-- 章节标题 -->
        <div class="section-header">
            <div class="section-title">实时数据</div>
            <button class="refresh-btn" onclick="refreshData()">↻ 刷新</button>
        </div>

        <!-- 机器人信息卡片 -->
        <div class="robot-info-card">
            <div class="robot-info-header">
                <div class="robot-name">机器狗 #02</div>
                <div class="status-tag"><span>●</span> 在线</div>
            </div>
            <div class="robot-info-body">
                <div class="robot-image">
                    <img src="__ROBOT_IMAGE__" alt="机器狗" onerror="this.style.display='none';this.parentElement.innerHTML='🐕'">
                </div>
                <div class="robot-details">
                    <div class="detail-item">
                        <div class="detail-label">电量</div>
                        <div class="detail-value">
                            <div class="battery-icon"><div class="battery-level" id="batteryLevel" style="width:68%"></div></div>
                            <span class="detail-number" id="batteryValue">68%</span>
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

        <!-- 主内容 -->
        <div class="main-layout">
            <div class="left-column">
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">最近巡检记录</div>
                        <span style="font-size:12px;color:#8c8c8c" id="inspectionTime">--:--:--</span>
                    </div>
                    <div class="panel-body" style="padding:0">
                        <table class="data-table">
                            <thead>
                                <tr><th>时间</th><th>设备</th><th>航点</th><th>裂缝数</th><th>温度</th><th>状态</th></tr>
                            </thead>
                            <tbody id="inspectionTable">
                                <tr><td colspan="6"><div class="empty-state">暂无数据</div></td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
                <div class="panel" style="margin-top:16px">
                    <div class="panel-header"><div class="panel-title">实时视频流</div></div>
                    <div class="panel-body">
                        <div class="video-placeholder">
                            <div style="font-size:36px;margin-bottom:8px;opacity:0.5">📹</div>
                            <div>视频流暂未连接</div>
                            <div style="font-size:12px;color:#bfbfbf;margin-top:8px">RTSP: rtsp://192.168.1.108:554/id=1&type=0</div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="right-column">
                <div class="panel">
                    <div class="panel-header"><div class="panel-title">演示控制</div></div>
                    <div class="panel-body">
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                            <button class="action-btn" onclick="sendDemo()" style="justify-content:center">📊 发送巡检数据</button>
                            <button class="action-btn" onclick="sendDemoStatus()" style="justify-content:center">🔄 更新状态</button>
                        </div>
                    </div>
                </div>
                <div class="panel" style="margin-top:16px">
                    <div class="panel-header"><div class="panel-title">实时告警</div></div>
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
        let activeKeys = new Set();
        
        // 按键映射
        const keyMap = {
            'w': 'forward', 'arrowup': 'forward',
            's': 'backward', 'arrowdown': 'backward',
            'a': 'left', 'arrowleft': 'left',
            'd': 'right', 'arrowright': 'right',
            'q': 'turn_left', 'shift': 'turn_left',
            'e': 'turn_right', 'ctrl': 'turn_right'
        };
        
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
            ws.onclose = () => setTimeout(connect, 3000);
        }
        
        // 键盘事件处理
        document.addEventListener('keydown', (e) => {
            const key = e.key.toLowerCase();
            const mappedKey = keyMap[key];
            
            if (mappedKey) {
                e.preventDefault();
                if (!activeKeys.has(mappedKey)) {
                    activeKeys.add(mappedKey);
                    updateKeyVisual(mappedKey, true);
                    sendKeyCommand(mappedKey, true);
                }
            } else if (key === ' ') {
                e.preventDefault();
                sendCmd('stand_up');
            } else if (key === 'escape') {
                e.preventDefault();
                sendCmd('emergency_stop');
            }
        });
        
        document.addEventListener('keyup', (e) => {
            const key = e.key.toLowerCase();
            const mappedKey = keyMap[key];
            
            if (mappedKey) {
                activeKeys.delete(mappedKey);
                updateKeyVisual(mappedKey, false);
                sendKeyCommand(mappedKey, false);
            }
        });
        
        function updateKeyVisual(key, active) {
            const btn = document.getElementById('key-' + key);
            if (btn) {
                btn.classList.toggle('active', active);
            }
        }
        
        async function sendKeyCommand(key, isPressed) {
            try {
                await fetch('/api/key/' + key + '?state=' + isPressed, {method: 'POST'});
            } catch(e) { console.error(e); }
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
            
            // 更新手柄状态指示
            const isActive = d.status === 'moving';
            document.getElementById('joystickStatus').className = 'status-indicator' + (isActive ? ' active' : '');
            document.getElementById('joystickText').textContent = isActive ? '移动中' : '就绪';
        }
        
        async function sendCmd(c) {
            try { await fetch('/api/control/' + c, {method: 'POST'}); } catch(e) {}
        }
        
        async function sendDemo() {
            try { await fetch('/api/demo', {method: 'POST'}); } catch(e) {}
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
        }), 2000);
        
        connect();
    </script>
</body>
</html>"""


async def main():
    global DASHBOARD_HTML
    if ROBOT_IMAGE_URI:
        DASHBOARD_HTML = DASHBOARD_HTML.replace("__ROBOT_IMAGE__", ROBOT_IMAGE_URI)
    else:
        DASHBOARD_HTML = DASHBOARD_HTML.replace('__ROBOT_IMAGE__', 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48Y2lyY2xlIGN4PSI1MCIgY3k9IjUwIiByPSI0MCIgZmlsbD0iI2RkZCIvPjx0ZXh0IHg9IjUwIiB5PSI2MCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZm9udC1zaXplPSI0MCI+8J+OwDwvdGV4dD48L3N2Zz4=')
    
    config = uvicorn.Config(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
    server = uvicorn.Server(config)
    logger.info(f"监测平台启动(手柄版): http://0.0.0.0:{HTTP_PORT}")
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
