#!/usr/bin/env python3
"""
绝影Lite3 监测平台 - 现代化UI升级版
参考Ghost CMS设计理念：极简、专业、高质量视觉
"""

import asyncio, json, time, logging, struct, socket, base64
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import websockets

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
WS_PORT, HTTP_PORT = 8765, 8000
MOTION_HOST, MOTION_PORT = "192.168.1.103", 43893

# ========== 官方协议指令码 ==========
CMD_FORWARD = 0x21010130
CMD_LEFT = 0x21010131
CMD_TURN = 0x21010135
CMD_STAND_UP = 0x21010202
CMD_EMERGENCY_STOP = 0x21020C0E
CMD_HOME = 0x21010C05
CMD_MOVE_MODE = 0x21010D06
CMD_STAND_MODE = 0x21010D05

# ========== 按键映射 ==========
KEY_FORWARD = ['w', 'arrowup']
KEY_BACKWARD = ['s', 'arrowdown']
KEY_LEFT = ['a', 'arrowleft']
KEY_RIGHT = ['d', 'arrowright']
KEY_TURN_LEFT = ['q', 'shift']
KEY_TURN_RIGHT = ['e', 'ctrl']
KEY_STAND_UP = [' ']
KEY_EMERGENCY = ['escape']

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
robot_status = {
    "battery": 68, "cpu_temp": 35.0, "gpu_load": 0, "memory_usage": 45,
    "status": "idle", "position": {"x": 0.0, "y": 0.0},
    "waypoint": "WP001", "total_waypoints": 5, "completed_waypoints": 0,
    "endurance_hours": 1.8
}
motion_sock = None
key_state = {"forward": False, "backward": False, "left": False, "right": False,
             "turn_left": False, "turn_right": False, "stand": False}


def send_udp(cmd: int, value: int = 0):
    global motion_sock
    try:
        if motion_sock is None:
            motion_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            motion_sock.settimeout(0.5)
        packet = struct.pack('<III', cmd, value, 0)
        motion_sock.sendto(packet, (MOTION_HOST, MOTION_PORT))
    except Exception as e:
        logger.error(f"UDP发送失败: {e}")


def calculate_velocity():
    vx, vy, vw = 0.0, 0.0, 0.0
    speed = 0.5
    if key_state["forward"]: vy -= speed
    if key_state["backward"]: vy += speed
    if key_state["left"]: vx -= speed
    if key_state["right"]: vx += speed
    if key_state["turn_left"]: vw -= speed
    if key_state["turn_right"]: vw += speed
    return vx, vy, vw


def send_velocity_command():
    vx, vy, vw = calculate_velocity()
    if vx != 0 or vy != 0 or vw != 0:
        magnitude = (vx**2 + vy**2 + vw**2)**0.5
        if magnitude > 1.0:
            vx, vy, vw = vx/magnitude, vy/magnitude, vw/magnitude
        robot_status["status"] = "moving"
        send_udp(CMD_MOVE_MODE)
        if vy != 0: send_udp(CMD_FORWARD, int(vy * 6553))
        if vx != 0: send_udp(CMD_LEFT, int(vx * 6553))
        if vw != 0: send_udp(CMD_TURN, int(vw * 9553))
    else:
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
    key = key.lower()
    if key in key_state:
        key_state[key] = state
        if state:
            robot_status["status"] = "moving"
            send_velocity_command()
        else:
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
async def get_keys(): return key_state


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
    async def process(self, data: Dict, ws=None):
        p = data.get("payload", data.get("data", {}))
        msg_type = data.get("type", "")
        try:
            if msg_type == "system_status":
                for k in ["battery","cpu_temp","gpu_load","memory_usage","status","waypoint","position","endurance_hours"]:
                    if k in p: robot_status[k] = p[k]
                for conn in connections:
                    try:
                        if hasattr(conn, 'send_json'):
                            await conn.send_json({"type": "robot_status", "data": robot_status})
                    except: pass
            elif msg_type == "inspection_result":
                inspections.append({
                    "ts": int(time.time() * 1000),
                    "waypoint": p.get("waypoint_id", "WP001"),
                    "defect_type": p.get("defect_type", "crack"),
                    "confidence": p.get("confidence", 0.0),
                    "measurements": p.get("measurements", {})
                })
                for conn in connections:
                    try:
                        if hasattr(conn, 'send_json'):
                            await conn.send_json({"type": "inspection", "data": inspections[-1]})
                    except: pass
            elif msg_type in ["crack_alert", "temperature_alert"]:
                alerts.append({
                    "ts": int(time.time() * 1000),
                    "type": msg_type,
                    "level": p.get("level", "warning"),
                    "value": p.get("value", 0),
                    "waypoint": p.get("waypoint_id", "WP001")
                })
                for conn in connections:
                    try:
                        if hasattr(conn, 'send_json'):
                            await conn.send_json({"type": "alert", "data": alerts[-1]})
                    except: pass
        except Exception as e:
            logger.error(f"处理消息失败: {e}")


monitor = Monitor()


# ============== 现代化UI设计 ==============
# 参考Ghost CMS设计理念：极简、专业、高质量视觉
# 配色方案：温暖中性色 + 强调色（琥珀/绯红/翠绿）
# 字体：系统字体栈，高质量排版层次

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>绝影Lite3 · 电力巡检监控中心</title>
<style>
/* ============================================
   设计系统 - 参考Ghost CMS现代设计语言
   ============================================ */

/* 字体栈 - 专业级排版 */
:root {
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
    --font-mono: 'SF Mono', SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    
    /* 配色方案 - 温暖中性 + 强调色 */
    --color-bg: #fafafa;
    --color-surface: #ffffff;
    --color-surface-elevated: #ffffff;
    --color-border: #e8e8e8;
    --color-border-subtle: #f0f0f0;
    
    /* 文字色彩 */
    --color-text-primary: #15171a;
    --color-text-secondary: #65676b;
    --color-text-tertiary: #909297;
    
    /* 强调色 - 灵感来自专业仪表板 */
    --color-accent: #ff6b35;  /* 活力橙 - 品牌色 */
    --color-accent-hover: #e85a2b;
    --color-success: #00c853;   /* 翠绿 - 正常状态 */
    --color-warning: #ffb300;   /* 琥珀 - 预警 */
    --color-danger: #ff3d00;    /* 绯红 - 告警 */
    --color-info: #2196f3;      /* 蓝色 - 信息 */
    
    /* 阴影层级 */
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06);
    --shadow-md: 0 4px 6px rgba(0,0,0,0.04), 0 2px 4px rgba(0,0,0,0.06);
    --shadow-lg: 0 10px 25px rgba(0,0,0,0.06), 0 4px 10px rgba(0,0,0,0.08);
    
    /* 圆角 */
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 16px;
    
    /* 过渡动画 */
    --transition-fast: 150ms ease;
    --transition-normal: 250ms ease;
    --transition-slow: 400ms ease;
}

/* 基础重置 */
*, *::before, *::after {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html {
    font-size: 16px;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

body {
    font-family: var(--font-sans);
    background: var(--color-bg);
    color: var(--color-text-primary);
    line-height: 1.6;
    min-height: 100vh;
}

/* ============================================
   顶部导航栏 - 极简风格
   ============================================ */
.navbar {
    background: var(--color-surface);
    border-bottom: 1px solid var(--color-border);
    padding: 0 32px;
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: var(--shadow-sm);
}

.navbar-brand {
    display: flex;
    align-items: center;
    gap: 12px;
}

.brand-icon {
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, var(--color-accent) 0%, #ff8f5a 100%);
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 18px;
    font-weight: 700;
}

.brand-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--color-text-primary);
    letter-spacing: -0.3px;
}

.brand-subtitle {
    font-size: 12px;
    color: var(--color-text-tertiary);
    font-weight: 400;
}

.navbar-meta {
    display: flex;
    align-items: center;
    gap: 24px;
    font-size: 13px;
    color: var(--color-text-secondary);
}

.connection-status {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: var(--color-bg);
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--color-text-tertiary);
    transition: background var(--transition-fast);
}

.status-dot.online {
    background: var(--color-success);
    box-shadow: 0 0 0 3px rgba(0, 200, 83, 0.2);
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { box-shadow: 0 0 0 3px rgba(0, 200, 83, 0.2); }
    50% { box-shadow: 0 0 0 6px rgba(0, 200, 83, 0.1); }
}

/* ============================================
   主内容区 - 网格布局
   ============================================ */
.main-container {
    max-width: 1440px;
    margin: 0 auto;
    padding: 32px;
}

/* ============================================
   英雄区域 - 机器人信息卡片
   参考Ghost的Hero设计：大图+关键数据
   ============================================ */
.hero-section {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 32px;
    margin-bottom: 32px;
}

.robot-card {
    background: var(--color-surface);
    border-radius: var(--radius-lg);
    overflow: hidden;
    box-shadow: var(--shadow-md);
    transition: transform var(--transition-normal), box-shadow var(--transition-normal);
}

.robot-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
}

.robot-image-wrap {
    height: 180px;
    background: linear-gradient(135deg, #f5f5f7 0%, #e8e8ed 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
}

.robot-image-wrap::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle, rgba(255,107,53,0.05) 0%, transparent 70%);
    animation: rotate 20s linear infinite;
}

@keyframes rotate {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

.robot-image {
    width: 140px;
    height: 140px;
    object-fit: contain;
    position: relative;
    z-index: 1;
    filter: drop-shadow(0 8px 16px rgba(0,0,0,0.12));
    transition: transform var(--transition-normal);
}

.robot-image:hover {
    transform: scale(1.05);
}

.robot-info {
    padding: 20px;
}

.robot-name {
    font-size: 16px;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 4px;
}

.robot-model {
    font-size: 12px;
    color: var(--color-text-tertiary);
    margin-bottom: 16px;
}

.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
    color: #16a34a;
}

.status-badge.moving {
    background: #fff7ed;
    border-color: #fed7aa;
    color: #c2410c;
}

.status-badge.inspecting {
    background: #eff6ff;
    border-color: #bfdbfe;
    color: #1d4ed8;
}

/* 统计指标卡片 */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
}

.stat-card {
    background: var(--color-surface);
    border-radius: var(--radius-md);
    padding: 20px;
    box-shadow: var(--shadow-sm);
    transition: box-shadow var(--transition-fast);
}

.stat-card:hover {
    box-shadow: var(--shadow-md);
}

.stat-label {
    font-size: 11px;
    font-weight: 500;
    color: var(--color-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}

.stat-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--color-text-primary);
    letter-spacing: -1px;
    line-height: 1;
}

.stat-unit {
    font-size: 14px;
    font-weight: 400;
    color: var(--color-text-secondary);
    margin-left: 2px;
}

/* 电量环 - 参考Apple Watch设计 */
.battery-ring {
    width: 64px;
    height: 64px;
    margin: 0 auto 12px;
    position: relative;
}

.battery-ring svg {
    transform: rotate(-90deg);
}

.battery-ring-bg {
    fill: none;
    stroke: #f0f0f0;
    stroke-width: 6;
}

.battery-ring-fill {
    fill: none;
    stroke: var(--color-success);
    stroke-width: 6;
    stroke-linecap: round;
    transition: stroke-dashoffset 0.5s ease, stroke var(--transition-fast);
}

.battery-percent {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-primary);
}

/* ============================================
   主内容区域 - 两栏布局
   ============================================ */
.content-grid {
    display: grid;
    grid-template-columns: 1fr 380px;
    gap: 24px;
}

/* 面板基础样式 */
.panel {
    background: var(--color-surface);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
}

.panel-header {
    padding: 16px 20px;
    border-bottom: 1px solid var(--color-border-subtle);
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.panel-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-primary);
    display: flex;
    align-items: center;
    gap: 8px;
}

.panel-title::before {
    content: '';
    width: 3px;
    height: 16px;
    background: var(--color-accent);
    border-radius: 2px;
}

.panel-body {
    padding: 20px;
}

/* ============================================
   控制区域 - 现代化手柄设计
   ============================================ */
.control-section {
    margin-bottom: 24px;
}

.control-panel {
    background: var(--color-surface);
    border-radius: var(--radius-lg);
    padding: 24px;
    box-shadow: var(--shadow-sm);
}

.control-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
}

.control-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-primary);
}

.control-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--color-text-tertiary);
}

/* D-Pad控制器 - 参考游戏手柄设计 */
.dpad-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
}

.dpad-grid {
    display: grid;
    grid-template-columns: repeat(3, 64px);
    grid-template-rows: repeat(3, 64px);
    gap: 8px;
}

.dpad-btn {
    width: 64px;
    height: 64px;
    border: 2px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    transition: all var(--transition-fast);
    user-select: none;
}

.dpad-btn:hover {
    border-color: var(--color-accent);
    background: #fff7f5;
}

.dpad-btn.active {
    border-color: var(--color-accent);
    background: var(--color-accent);
    color: white;
    transform: scale(0.95);
}

.dpad-btn .icon {
    font-size: 20px;
    line-height: 1;
}

.dpad-btn .label {
    font-size: 9px;
    font-weight: 500;
    color: var(--color-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.dpad-btn.active .label {
    color: rgba(255,255,255,0.8);
}

.dpad-btn.empty {
    border: none;
    background: transparent;
    cursor: default;
}

/* 功能按钮 */
.action-buttons {
    display: flex;
    gap: 12px;
    margin-top: 20px;
    justify-content: center;
}

.action-btn {
    padding: 10px 20px;
    border: 1.5px solid var(--color-border);
    border-radius: var(--radius-sm);
    background: var(--color-surface);
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    color: var(--color-text-secondary);
    transition: all var(--transition-fast);
    display: flex;
    align-items: center;
    gap: 6px;
}

.action-btn:hover {
    border-color: var(--color-accent);
    color: var(--color-accent);
}

.action-btn.primary {
    border-color: var(--color-success);
    color: var(--color-success);
    background: #f0fdf4;
}

.action-btn.primary:hover {
    background: var(--color-success);
    color: white;
}

.action-btn.danger {
    border-color: var(--color-danger);
    color: var(--color-danger);
    background: #fff5f5;
}

.action-btn.danger:hover {
    background: var(--color-danger);
    color: white;
}

/* 快捷键提示 */
.keyboard-hints {
    margin-top: 20px;
    padding: 16px;
    background: var(--color-bg);
    border-radius: var(--radius-md);
}

.keyboard-hints h4 {
    font-size: 11px;
    font-weight: 500;
    color: var(--color-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 12px;
}

.hint-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
}

.hint-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--color-text-secondary);
}

.key-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 24px;
    height: 22px;
    padding: 0 6px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    box-shadow: 0 2px 0 var(--color-border);
}

/* ============================================
   数据表格 - 现代化设计
   ============================================ */
.data-table {
    width: 100%;
    border-collapse: collapse;
}

.data-table th {
    background: var(--color-bg);
    padding: 12px 16px;
    text-align: left;
    font-size: 11px;
    font-weight: 600;
    color: var(--color-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid var(--color-border);
}

.data-table td {
    padding: 14px 16px;
    font-size: 13px;
    color: var(--color-text-secondary);
    border-bottom: 1px solid var(--color-border-subtle);
}

.data-table tr:last-child td {
    border-bottom: none;
}

.data-table tr:hover td {
    background: var(--color-bg);
}

/* 状态标签 */
.tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
}

.tag-success { background: #f0fdf4; color: #16a34a; }
.tag-warning { background: #fffbeb; color: #d97706; }
.tag-error { background: #fff5f5; color: #dc2626; }
.tag-info { background: #eff6ff; color: #2563eb; }

/* ============================================
   告警列表 - 时间线样式
   ============================================ */
.alert-timeline {
    max-height: 320px;
    overflow-y: auto;
}

.alert-timeline::-webkit-scrollbar {
    width: 4px;
}

.alert-timeline::-webkit-scrollbar-track {
    background: transparent;
}

.alert-timeline::-webkit-scrollbar-thumb {
    background: var(--color-border);
    border-radius: 2px;
}

.alert-item {
    display: flex;
    gap: 12px;
    padding: 14px 0;
    border-bottom: 1px solid var(--color-border-subtle);
    animation: slideIn 0.3s ease;
}

@keyframes slideIn {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}

.alert-item:last-child {
    border-bottom: none;
}

.alert-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-top: 6px;
    flex-shrink: 0;
}

.alert-indicator.warn { background: var(--color-warning); }
.alert-indicator.critical { background: var(--color-danger); }
.alert-indicator.normal { background: var(--color-success); }

.alert-content {
    flex: 1;
}

.alert-type {
    font-size: 12px;
    font-weight: 500;
    color: var(--color-text-primary);
}

.alert-detail {
    font-size: 12px;
    color: var(--color-text-secondary);
    margin-top: 2px;
}

.alert-time {
    font-size: 11px;
    color: var(--color-text-tertiary);
    white-space: nowrap;
}

/* ============================================
   视频占位符 - 高质量设计
   ============================================ */
.video-placeholder {
    background: linear-gradient(135deg, #f5f5f7 0%, #e8e8ed 100%);
    border-radius: var(--radius-md);
    padding: 48px;
    text-align: center;
    color: var(--color-text-tertiary);
}

.video-placeholder .icon {
    font-size: 40px;
    margin-bottom: 12px;
    opacity: 0.5;
}

.video-placeholder .text {
    font-size: 14px;
    font-weight: 500;
}

.video-placeholder .subtext {
    font-size: 12px;
    margin-top: 4px;
    font-family: var(--font-mono);
}

/* ============================================
   空状态
   ============================================ */
.empty-state {
    text-align: center;
    padding: 48px 24px;
    color: var(--color-text-tertiary);
}

.empty-state .icon {
    font-size: 32px;
    margin-bottom: 12px;
    opacity: 0.4;
}

.empty-state .text {
    font-size: 14px;
}

/* ============================================
   响应式设计
   ============================================ */
@media (max-width: 1200px) {
    .hero-section {
        grid-template-columns: 1fr;
    }
    .robot-card {
        max-width: 400px;
    }
    .content-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 768px) {
    .navbar {
        padding: 0 16px;
    }
    .main-container {
        padding: 16px;
    }
    .stats-grid {
        grid-template-columns: 1fr;
    }
    .hint-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    .dpad-grid {
        grid-template-columns: repeat(3, 56px);
        grid-template-rows: repeat(3, 56px);
    }
    .dpad-btn {
        width: 56px;
        height: 56px;
    }
}
</style>
</head>
<body>
    <!-- 顶部导航栏 -->
    <nav class="navbar">
        <div class="navbar-brand">
            <div class="brand-icon">L3</div>
            <div>
                <div class="brand-title">绝影Lite3 · 电力巡检监控中心</div>
                <div class="brand-subtitle">Guangxi Electric Power Vocational College</div>
            </div>
        </div>
        <div class="navbar-meta">
            <div class="connection-status">
                <div class="status-dot" id="connDot"></div>
                <span id="connStatus">未连接</span>
            </div>
            <div>
                <span style="color:var(--color-text-tertiary)">在线:</span>
                <strong id="clientCount">0</strong>
            </div>
            <div>
                <span style="color:var(--color-text-tertiary)">时间:</span>
                <strong id="currentTime">--:--:--</strong>
            </div>
        </div>
    </nav>

    <!-- 主内容区 -->
    <main class="main-container">
        <!-- 英雄区域：机器人状态 -->
        <section class="hero-section">
            <!-- 机器人卡片 -->
            <div class="robot-card">
                <div class="robot-image-wrap">
                    <img src="__ROBOT_IMAGE__" alt="绝影Lite3" class="robot-image" 
                         onerror="this.style.display='none';this.parentElement.innerHTML='<div style=\\'font-size:64px;opacity:0.3\\'>🐕</div>'">
                </div>
                <div class="robot-info">
                    <div class="robot-name">绝影Lite3 #001</div>
                    <div class="robot-model">云深处 · 专业版 · Jetson NX</div>
                    <div class="status-badge" id="statusBadge">
                        <span>●</span>
                        <span id="statusText">待机中</span>
                    </div>
                </div>
            </div>
            
            <!-- 统计指标 -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">电池电量</div>
                    <div class="battery-ring">
                        <svg width="64" height="64" viewBox="0 0 64 64">
                            <circle class="battery-ring-bg" cx="32" cy="32" r="28"/>
                            <circle class="battery-ring-fill" id="batteryRing" cx="32" cy="32" r="28"
                                    stroke-dasharray="175.9" stroke-dashoffset="53"/>
                        </svg>
                        <span class="battery-percent" id="batteryPercent">70%</span>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">预估续航</div>
                    <div class="stat-value"><span id="enduranceValue">1.8</span><span class="stat-unit">h</span></div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">CPU 温度</div>
                    <div class="stat-value"><span id="cpuTempValue">35.0</span><span class="stat-unit">°C</span></div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">GPU 负载</div>
                    <div class="stat-value"><span id="gpuLoadValue">0</span><span class="stat-unit">%</span></div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">当前位置</div>
                    <div class="stat-value" style="font-size:18px"><span id="positionValue">(0.0, 0.0)</span></div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">当前航点</div>
                    <div class="stat-value" style="font-size:20px"><span id="waypointValue">WP001</span></div>
                </div>
            </div>
        </section>

        <!-- 主内容区域 -->
        <section class="content-grid">
            <!-- 左栏：数据与控制 -->
            <div class="left-column">
                <!-- 控制区域 -->
                <div class="control-section">
                    <div class="control-panel">
                        <div class="control-header">
                            <div class="control-title">运动控制</div>
                            <div class="control-status">
                                <div class="status-dot" id="joystickStatus"></div>
                                <span id="joystickText">就绪</span>
                            </div>
                        </div>
                        
                        <div class="dpad-container">
                            <div class="dpad-grid">
                                <div class="dpad-btn empty"></div>
                                <div class="dpad-btn" id="key-forward" data-key="forward">
                                    <span class="icon">↑</span>
                                    <span class="label">前进</span>
                                </div>
                                <div class="dpad-btn empty"></div>
                                
                                <div class="dpad-btn" id="key-left" data-key="left">
                                    <span class="icon">←</span>
                                    <span class="label">左移</span>
                                </div>
                                <div class="dpad-btn empty" style="opacity:0.2;cursor:default">
                                    <span class="icon">⏹</span>
                                </div>
                                <div class="dpad-btn" id="key-right" data-key="right">
                                    <span class="icon">→</span>
                                    <span class="label">右移</span>
                                </div>
                                
                                <div class="dpad-btn empty"></div>
                                <div class="dpad-btn" id="key-backward" data-key="backward">
                                    <span class="icon">↓</span>
                                    <span class="label">后退</span>
                                </div>
                                <div class="dpad-btn empty"></div>
                            </div>
                            
                            <div class="action-buttons">
                                <button class="action-btn primary" onclick="sendCmd('stand_up')">
                                    <span>⬆</span> 起立/趴下
                                </button>
                                <button class="action-btn danger" onclick="sendCmd('emergency_stop')">
                                    <span>⏻</span> 急停
                                </button>
                                <button class="action-btn" onclick="sendCmd('home')">
                                    <span>⌂</span> 回零
                                </button>
                            </div>
                        </div>
                        
                        <div class="keyboard-hints">
                            <h4>快捷键操作</h4>
                            <div class="hint-grid">
                                <div class="hint-item"><span class="key-badge">W</span> 前进</div>
                                <div class="hint-item"><span class="key-badge">S</span> 后退</div>
                                <div class="hint-item"><span class="key-badge">A</span> 左移</div>
                                <div class="hint-item"><span class="key-badge">D</span> 右移</div>
                                <div class="hint-item"><span class="key-badge">Q</span> 左转</div>
                                <div class="hint-item"><span class="key-badge">E</span> 右转</div>
                                <div class="hint-item"><span class="key-badge">Space</span> 起立</div>
                                <div class="hint-item"><span class="key-badge">Esc</span> 急停</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 巡检记录 -->
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">实时巡检记录</div>
                        <span style="font-size:12px;color:var(--color-text-tertiary)" id="inspectionTime">--:--:--</span>
                    </div>
                    <div class="panel-body" style="padding:0">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>时间</th>
                                    <th>设备</th>
                                    <th>航点</th>
                                    <th>缺陷类型</th>
                                    <th>置信度</th>
                                    <th>状态</th>
                                </tr>
                            </thead>
                            <tbody id="inspectionTable">
                                <tr><td colspan="6"><div class="empty-state"><div class="icon">📊</div><div class="text">暂无巡检数据</div></div></td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- 视频流 -->
                <div class="panel" style="margin-top:24px">
                    <div class="panel-header">
                        <div class="panel-title">实时视频流</div>
                        <span style="font-size:12px;color:var(--color-text-tertiary)">RTSP: 192.168.1.108:554</span>
                    </div>
                    <div class="panel-body">
                        <div class="video-placeholder">
                            <div class="icon">📹</div>
                            <div class="text">视频流暂未连接</div>
                            <div class="subtext">等待感知主机连接后自动加载</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 右栏：告警与控制 -->
            <div class="right-column">
                <!-- 演示控制 -->
                <div class="panel" style="margin-bottom:24px">
                    <div class="panel-header">
                        <div class="panel-title">演示控制</div>
                    </div>
                    <div class="panel-body">
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                            <button class="action-btn primary" onclick="sendDemo()" style="justify-content:center">
                                <span>📊</span> 发送数据
                            </button>
                            <button class="action-btn" onclick="sendDemoStatus()" style="justify-content:center">
                                <span>🔄</span> 更新状态
                            </button>
                        </div>
                    </div>
                </div>

                <!-- 实时告警 -->
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">实时告警</div>
                        <span style="font-size:12px;color:var(--color-text-tertiary)" id="alertCount">0 条</span>
                    </div>
                    <div class="panel-body" style="padding:0">
                        <div class="alert-timeline" id="alertList">
                            <div class="empty-state" style="padding:32px">
                                <div class="icon">✓</div>
                                <div class="text">暂无告警</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 系统统计 -->
                <div class="panel" style="margin-top:24px">
                    <div class="panel-header">
                        <div class="panel-title">系统统计</div>
                    </div>
                    <div class="panel-body">
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                            <div style="text-align:center">
                                <div style="font-size:24px;font-weight:700;color:var(--color-text-primary)" id="totalInspections">0</div>
                                <div style="font-size:11px;color:var(--color-text-tertiary);margin-top:4px">总巡检次数</div>
                            </div>
                            <div style="text-align:center">
                                <div style="font-size:24px;font-weight:700;color:var(--color-success)" id="normalCount">0</div>
                                <div style="font-size:11px;color:var(--color-text-tertiary);margin-top:4px">正常检测</div>
                            </div>
                            <div style="text-align:center">
                                <div style="font-size:24px;font-weight:700;color:var(--color-warning)" id="crackCount">0</div>
                                <div style="font-size:11px;color:var(--color-text-tertiary);margin-top:4px">裂缝检测</div>
                            </div>
                            <div style="text-align:center">
                                <div style="font-size:24px;font-weight:700;color:var(--color-danger)" id="alertTotal">0</div>
                                <div style="font-size:11px;color:var(--color-text-tertiary);margin-top:4px">待处理告警</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    </main>

    <script>
        let ws = null;
        let inspections = [];
        let alerts = [];
        let robot = { battery: 68, cpu_temp: 35, gpu_load: 0, memory_usage: 45, 
                      status: 'idle', waypoint: 'WP001', endurance_hours: 1.8, 
                      position: {x: 0, y: 0} };
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
        
        // WebSocket连接
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
                else if (m.type === 'alert') addAlert(m.data);
            };
            ws.onclose = () => setTimeout(connect, 3000);
        }
        
        // 键盘事件
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
            if (btn) btn.classList.toggle('active', active);
        }
        
        async function sendKeyCommand(key, isPressed) {
            try {
                await fetch('/api/key/' + key + '?state=' + isPressed, {method: 'POST'});
            } catch(e) { console.error(e); }
        }
        
        // 数据处理
        function addInspection(d) {
            inspections.unshift({
                time: new Date().toLocaleTimeString(),
                waypoint: d.waypoint_id || 'WP001',
                defect_type: d.defect_type || 'crack',
                confidence: d.confidence || 0.9,
                measurements: d.measurements || {}
            });
            if (inspections.length > 20) inspections.pop();
            renderTable();
            updateStats();
            document.getElementById('inspectionTime').textContent = inspections[0]?.time || '--:--:--';
        }
        
        function renderTable() {
            const tb = document.getElementById('inspectionTable');
            if (!inspections.length) {
                tb.innerHTML = '<tr><td colspan="6"><div class="empty-state"><div class="icon">📊</div><div class="text">暂无巡检数据</div></div></td></tr>';
                return;
            }
            tb.innerHTML = inspections.map(i => {
                const c = i.defect_type === 'crack' ? 'info' : 'warning';
                const conf = Math.round((i.confidence || 0.9) * 100);
                return `<tr>
                    <td>${i.time}</td>
                    <td>LITE3-001</td>
                    <td>${i.waypoint}</td>
                    <td><span class="tag tag-${c}">${i.defect_type === 'crack' ? '裂缝' : '蜂窝'}</span></td>
                    <td>${conf}%</td>
                    <td><span class="tag tag-success">正常</span></td>
                </tr>`;
            }).join('');
        }
        
        function updateRobot(d) {
            robot = {...robot, ...d};
            
            // 更新电量环
            const battery = d.battery || 68;
            const circumference = 175.9;
            const offset = circumference - (battery / 100) * circumference;
            const ring = document.getElementById('batteryRing');
            ring.style.strokeDashoffset = offset;
            ring.style.stroke = battery > 50 ? 'var(--color-success)' : battery > 20 ? 'var(--color-warning)' : 'var(--color-danger)';
            document.getElementById('batteryPercent').textContent = battery + '%';
            
            // 更新数值
            document.getElementById('enduranceValue').textContent = (d.endurance_hours || 1.8).toFixed(1);
            document.getElementById('cpuTempValue').textContent = (d.cpu_temp || 35).toFixed(1);
            document.getElementById('gpuLoadValue').textContent = d.gpu_load || 0;
            
            // 更新状态
            const sm = { 'idle': '待机中', 'moving': '运动中', 'inspecting': '巡检中' };
            const st = sm[d.status] || d.status;
            document.getElementById('statusText').textContent = st;
            
            // 更新状态徽章样式
            const badge = document.getElementById('statusBadge');
            badge.className = 'status-badge' + (d.status === 'moving' ? ' moving' : d.status === 'inspecting' ? ' inspecting' : '');
            
            // 更新位置
            if (d.position) {
                document.getElementById('positionValue').textContent = 
                    `(${d.position.x.toFixed(1)}, ${d.position.y.toFixed(1)})`;
            }
            
            // 更新航点
            if (d.waypoint) {
                document.getElementById('waypointValue').textContent = d.waypoint;
            }
            
            // 更新手柄状态
            const isActive = d.status === 'moving';
            document.getElementById('joystickStatus').className = 'status-dot' + (isActive ? ' online' : '');
            document.getElementById('joystickText').textContent = isActive ? '移动中' : '就绪';
        }
        
        function addAlert(d) {
            alerts.unshift({
                time: new Date().toLocaleTimeString(),
                type: d.type || 'temperature_alert',
                level: d.level || 'warn',
                waypoint: d.waypoint || 'WP001'
            });
            if (alerts.length > 10) alerts.pop();
            renderAlerts();
            updateStats();
        }
        
        function renderAlerts() {
            const container = document.getElementById('alertList');
            if (!alerts.length) {
                container.innerHTML = '<div class="empty-state" style="padding:32px"><div class="icon">✓</div><div class="text">暂无告警</div></div>';
                return;
            }
            container.innerHTML = alerts.map(a => {
                const icons = { warn: '⚠️', critical: '🔴', normal: '✅' };
                const labels = { warn: '温度预警', critical: '高温告警', normal: '恢复正常' };
                return `<div class="alert-item">
                    <div class="alert-indicator ${a.level}"></div>
                    <div class="alert-content">
                        <div class="alert-type">${icons[a.level] || '⚠️'} ${labels[a.level] || a.type}</div>
                        <div class="alert-detail">航点: ${a.waypoint}</div>
                    </div>
                    <div class="alert-time">${a.time}</div>
                </div>`;
            }).join('');
            document.getElementById('alertCount').textContent = alerts.length + ' 条';
        }
        
        function updateStats() {
            document.getElementById('totalInspections').textContent = inspections.length;
            document.getElementById('normalCount').textContent = inspections.filter(i => i.defect_type !== 'crack').length;
            document.getElementById('crackCount').textContent = inspections.filter(i => i.defect_type === 'crack').length;
            document.getElementById('alertTotal').textContent = alerts.length;
        }
        
        // API调用
        async function sendCmd(c) {
            try { await fetch('/api/control/' + c, {method: 'POST'}); } catch(e) {}
        }
        
        async function sendDemo() {
            try { await fetch('/api/demo', {method: 'POST'}); } catch(e) {}
        }
        
        async function sendDemoStatus() {
            try { await fetch('/api/demo', {method: 'POST'}); } catch(e) {}
        }
        
        // 定时更新
        setInterval(() => {
            document.getElementById('currentTime').textContent = new Date().toLocaleTimeString();
        }, 1000);
        
        setInterval(() => {
            fetch('/api/status').then(r => r.json()).then(d => {
                document.getElementById('clientCount').textContent = d.clients;
            });
        }, 2000);
        
        // 初始化
        connect();
    </script>
</body>
</html>"""


async def ws_server():
    """独立的WebSocket服务器（端口8765）"""
    async def handler(websocket, path=None):
        connections.append(websocket)
        logger.info(f"感知主机连接: {websocket.remote_address}")
        
        import websockets
        await websocket.send(json.dumps({"type": "robot_status", "data": robot_status}))
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await monitor.process(data, websocket)
                except json.JSONDecodeError:
                    logger.warning("收到非JSON消息")
                except Exception as e:
                    logger.error(f"处理消息失败: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"感知主机断开: {websocket.remote_address}")
        except Exception as e:
            logger.error(f"WebSocket处理异常: {e}")
        finally:
            if websocket in connections:
                connections.remove(websocket)
            logger.info(f"感知主机已断开连接")
    
    async with websockets.serve(handler, "0.0.0.0", WS_PORT):
        logger.info(f"WebSocket服务器启动: ws://0.0.0.0:{WS_PORT}")
        await asyncio.Future()


async def main():
    global DASHBOARD_HTML
    if ROBOT_IMAGE_URI:
        DASHBOARD_HTML = DASHBOARD_HTML.replace("__ROBOT_IMAGE__", ROBOT_IMAGE_URI)
    else:
        DASHBOARD_HTML = DASHBOARD_HTML.replace('__ROBOT_IMAGE__', 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48Y2lyY2xlIGN4PSI1MCIgY3k9IjUwIiByPSI0MCIgZmlsbD0iI2RkZCIvPjx0ZXh0IHg9IjUwIiB5PSI2MCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZm9udC1zaXplPSI0MCI+8J+OwDwvdGV4dD48L3N2Zz4=')
    
    http_config = uvicorn.Config(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
    http_server = uvicorn.Server(http_config)
    
    ws_task = asyncio.create_task(ws_server())
    
    logger.info(f"监测平台启动:")
    logger.info(f"  HTTP服务: http://0.0.0.0:{HTTP_PORT}")
    logger.info(f"  WebSocket: ws://0.0.0.0:{WS_PORT}")
    
    await asyncio.gather(http_server.serve(), ws_task)


if __name__ == "__main__":
    asyncio.run(main())
