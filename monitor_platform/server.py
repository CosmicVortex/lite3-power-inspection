#!/usr/bin/env python3
"""
绝影Lite3 监测平台 - 现代化UI升级版
参考Ghost CMS + xh-admin-frontend设计理念：极简、专业、高质量视觉
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

# ========== 现代化UI HTML ==========
MODERN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>绝影Lite3 · 电力巡检监控中心</title>
    <style>
        :root {
            --primary: #ff6b35;
            --primary-light: #ff8f5a;
            --success: #00c853;
            --warning: #ffb300;
            --danger: #ff3d00;
            --info: #2196f3;
            --bg: #f5f7fa;
            --surface: #ffffff;
            --text: #1a1a1a;
            --text-secondary: #666;
            --border: #e8e8e8;
            --shadow: 0 4px 20px rgba(0,0,0,0.08);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }
        
        /* 顶部导航 */
        .header {
            background: var(--surface);
            padding: 0 32px;
            height: 64px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: var(--shadow);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 20px;
            font-weight: 600;
            color: var(--primary);
        }
        
        .logo-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 20px;
        }
        
        .header-right {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        
        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 16px;
            background: #f0fdf4;
            border-radius: 20px;
            font-size: 14px;
            color: var(--success);
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        /* 主内容区 */
        .main {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }
        
        /* Hero区域 */
        .hero {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
            border-radius: 20px;
            padding: 40px;
            color: white;
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .hero-content h1 {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 8px;
        }
        
        .hero-content p {
            opacity: 0.9;
            font-size: 16px;
        }
        
        .hero-stats {
            display: flex;
            gap: 32px;
        }
        
        .hero-stat {
            text-align: center;
        }
        
        .hero-stat-value {
            font-size: 36px;
            font-weight: 700;
        }
        
        .hero-stat-label {
            font-size: 14px;
            opacity: 0.8;
        }
        
        /* 卡片网格 */
        .cards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 24px;
            margin-bottom: 24px;
        }
        
        .card {
            background: var(--surface);
            border-radius: 16px;
            padding: 24px;
            box-shadow: var(--shadow);
            transition: transform 0.2s;
        }
        
        .card:hover {
            transform: translateY(-4px);
        }
        
        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
        }
        
        .card-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--text);
        }
        
        .card-icon {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }
        
        .card-icon.orange { background: #fff3e0; }
        .card-icon.green { background: #e8f5e9; }
        .card-icon.blue { background: #e3f2fd; }
        .card-icon.red { background: #ffebee; }
        
        /* 电池环形 */
        .battery-ring {
            position: relative;
            width: 120px;
            height: 120px;
            margin: 0 auto;
        }
        
        .battery-ring svg {
            transform: rotate(-90deg);
        }
        
        .battery-ring-bg {
            fill: none;
            stroke: #f0f0f0;
            stroke-width: 8;
        }
        
        .battery-ring-fill {
            fill: none;
            stroke: var(--success);
            stroke-width: 8;
            stroke-linecap: round;
            transition: stroke-dashoffset 0.5s ease;
        }
        
        .battery-percent {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 28px;
            font-weight: 700;
            color: var(--text);
        }
        
        /* 控制面板 */
        .control-panel {
            background: var(--surface);
            border-radius: 16px;
            padding: 24px;
            box-shadow: var(--shadow);
        }
        
        .dpad {
            display: grid;
            grid-template-columns: repeat(3, 60px);
            grid-template-rows: repeat(3, 60px);
            gap: 8px;
            margin: 20px auto;
            width: fit-content;
        }
        
        .dpad-btn {
            width: 60px;
            height: 60px;
            border: none;
            border-radius: 12px;
            background: var(--bg);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            transition: all 0.2s;
        }
        
        .dpad-btn:hover {
            background: var(--primary);
            color: white;
        }
        
        .dpad-btn:active {
            transform: scale(0.95);
        }
        
        .dpad-btn.empty {
            background: transparent;
            cursor: default;
        }
        
        .action-buttons {
            display: flex;
            gap: 12px;
            justify-content: center;
            margin-top: 20px;
        }
        
        .action-btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .action-btn.primary {
            background: var(--primary);
            color: white;
        }
        
        .action-btn.danger {
            background: var(--danger);
            color: white;
        }
        
        .action-btn:hover {
            opacity: 0.9;
            transform: translateY(-2px);
        }
        
        /* 告警列表 */
        .alert-list {
            max-height: 300px;
            overflow-y: auto;
        }
        
        .alert-item {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            background: var(--bg);
        }
        
        .alert-item.warning { background: #fff8e1; }
        .alert-item.danger { background: #ffebee; }
        
        .alert-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-top: 6px;
            flex-shrink: 0;
        }
        
        .alert-dot.warning { background: var(--warning); }
        .alert-dot.danger { background: var(--danger); }
        
        .alert-content {
            flex: 1;
        }
        
        .alert-message {
            font-size: 14px;
            color: var(--text);
        }
        
        .alert-time {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 4px;
        }
        
        /* 数据表格 */
        .data-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .data-table th,
        .data-table td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        
        .data-table th {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
        }
        
        .data-table td {
            font-size: 14px;
        }
        
        .tag {
            display: inline-flex;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }
        
        .tag.success { background: #e8f5e9; color: #2e7d32; }
        .tag.warning { background: #fff8e1; color: #f57c00; }
        .tag.danger { background: #ffebee; color: #c62828; }
        
        /* 底部 */
        .footer {
            text-align: center;
            padding: 24px;
            color: var(--text-secondary);
            font-size: 14px;
        }
        
        /* 响应式 */
        @media (max-width: 768px) {
            .hero {
                flex-direction: column;
                text-align: center;
                gap: 24px;
            }
            
            .hero-stats {
                justify-content: center;
            }
            
            .cards-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <!-- 顶部导航 -->
    <header class="header">
        <div class="logo">
            <div class="logo-icon">🤖</div>
            <span>绝影Lite3 · 电力巡检监控中心</span>
        </div>
        <div class="header-right">
            <div class="status-badge">
                <span class="status-dot"></span>
                <span id="connectionStatus">已连接</span>
            </div>
            <span id="currentTime" style="color: var(--text-secondary);"></span>
        </div>
    </header>
    
    <!-- 主内容 -->
    <main class="main">
        <!-- Hero区域 -->
        <section class="hero">
            <div class="hero-content">
                <h1>实时巡检监控</h1>
                <p>绝影Lite3专业版 · 智能电力巡检系统</p>
            </div>
            <div class="hero-stats">
                <div class="hero-stat">
                    <div class="hero-stat-value" id="clientCount">0</div>
                    <div class="hero-stat-label">在线设备</div>
                </div>
                <div class="hero-stat">
                    <div class="hero-stat-value" id="alertCount">0</div>
                    <div class="hero-stat-label">告警数量</div>
                </div>
            </div>
        </section>
        
        <!-- 数据卡片 -->
        <section class="cards-grid">
            <!-- 电池状态 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">电池状态</span>
                    <div class="card-icon orange">🔋</div>
                </div>
                <div class="battery-ring">
                    <svg width="120" height="120" viewBox="0 0 120 120">
                        <circle class="battery-ring-bg" cx="60" cy="60" r="52"/>
                        <circle class="battery-ring-fill" id="batteryRing" cx="60" cy="60" r="52"
                                stroke-dasharray="326.7" stroke-dashoffset="100"/>
                    </svg>
                    <span class="battery-percent" id="batteryPercent">68%</span>
                </div>
                <div style="text-align: center; margin-top: 16px; color: var(--text-secondary);">
                    预估续航 <span id="enduranceValue" style="color: var(--text); font-weight: 600;">1.8</span> 小时
                </div>
            </div>
            
            <!-- 系统状态 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">系统状态</span>
                    <div class="card-icon green">📊</div>
                </div>
                <table class="data-table">
                    <tr>
                        <td>CPU 温度</td>
                        <td><span id="cpuTempValue" style="font-weight: 600;">35.0°C</span></td>
                    </tr>
                    <tr>
                        <td>GPU 负载</td>
                        <td><span id="gpuLoadValue" style="font-weight: 600;">0%</span></td>
                    </tr>
                    <tr>
                        <td>内存使用</td>
                        <td><span id="memoryUsageValue" style="font-weight: 600;">45%</span></td>
                    </tr>
                </table>
            </div>
            
            <!-- 位置信息 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">当前位置</span>
                    <div class="card-icon blue">📍</div>
                </div>
                <table class="data-table">
                    <tr>
                        <td>坐标</td>
                        <td><span id="positionValue" style="font-weight: 600;">(0.0, 0.0)</span></td>
                    </tr>
                    <tr>
                        <td>当前航点</td>
                        <td><span id="waypointValue" style="font-weight: 600;">WP001</span></td>
                    </tr>
                    <tr>
                        <td>完成进度</td>
                        <td>
                            <span class="tag success" id="progressTag">0/5</span>
                        </td>
                    </tr>
                </table>
            </div>
            
            <!-- 告警信息 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">实时告警</span>
                    <div class="card-icon red">⚠️</div>
                </div>
                <div class="alert-list" id="alertList">
                    <div style="text-align: center; color: var(--text-secondary); padding: 40px;">
                        暂无告警
                    </div>
                </div>
            </div>
        </section>
        
        <!-- 控制面板 -->
        <section class="control-panel">
            <div class="card-header">
                <span class="card-title">运动控制</span>
                <span style="color: var(--text-secondary); font-size: 14px;">WASD / 方向键控制</span>
            </div>
            
            <div class="dpad">
                <div class="dpad-btn empty"></div>
                <div class="dpad-btn" data-key="forward" onclick="pressKey('forward')">↑</div>
                <div class="dpad-btn empty"></div>
                
                <div class="dpad-btn" data-key="left" onclick="pressKey('left')">←</div>
                <div class="dpad-btn empty"></div>
                <div class="dpad-btn" data-key="right" onclick="pressKey('right')">→</div>
                
                <div class="dpad-btn empty"></div>
                <div class="dpad-btn" data-key="backward" onclick="pressKey('backward')">↓</div>
                <div class="dpad-btn empty"></div>
            </div>
            
            <div class="action-buttons">
                <button class="action-btn primary" onclick="sendCmd('stand_up')">⬆ 起立/趴下</button>
                <button class="action-btn danger" onclick="sendCmd('emergency_stop')">⏻ 紧急停止</button>
                <button class="action-btn" onclick="sendCmd('home')">⌂ 回零</button>
            </div>
        </section>
    </main>
    
    <!-- 底部 -->
    <footer class="footer">
        <p>绝影Lite3 电力巡检系统 V1.7 · 广西电力职业技术学院</p>
    </footer>
    
    <script>
        // WebSocket连接
        let ws = null;
        let reconnectTimer = null;
        
        function connect() {
            const wsUrl = `ws://${window.location.host}/ws`;
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                console.log('WebSocket connected');
                document.getElementById('connectionStatus').textContent = '已连接';
            };
            
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    updateDashboard(data);
                } catch (e) {
                    console.error('Parse error:', e);
                }
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
            ws.onclose = () => {
                console.log('WebSocket closed, reconnecting...');
                document.getElementById('connectionStatus').textContent = '断开';
                reconnectTimer = setTimeout(connect, 3000);
            };
        }
        
        function updateDashboard(data) {
            if (data.type === 'robot_status') {
                const status = data.data;
                
                // 电池
                const battery = status.battery || 0;
                document.getElementById('batteryPercent').textContent = battery + '%';
                const circumference = 2 * Math.PI * 52;
                const offset = circumference - (battery / 100) * circumference;
                const ring = document.getElementById('batteryRing');
                ring.style.strokeDashoffset = offset;
                ring.style.stroke = battery > 60 ? 'var(--success)' : battery > 30 ? 'var(--warning)' : 'var(--danger)';
                
                // 续航
                document.getElementById('enduranceValue').textContent = (status.endurance_hours || 1.8).toFixed(1);
                
                // 系统状态
                document.getElementById('cpuTempValue').textContent = (status.cpu_temp || 35).toFixed(1) + '°C';
                document.getElementById('gpuLoadValue').textContent = (status.gpu_load || 0) + '%';
                document.getElementById('memoryUsageValue').textContent = (status.memory_usage || 45) + '%';
                
                // 位置
                const pos = status.position || {};
                document.getElementById('positionValue').textContent = 
                    `(${pos.x.toFixed(1)}, ${pos.y.toFixed(1)})`;
                document.getElementById('waypointValue').textContent = status.waypoint || 'WP001';
                
                // 进度
                const completed = status.completed_waypoints || 0;
                const total = status.total_waypoints || 5;
                document.getElementById('progressTag').textContent = `${completed}/${total}`;
                
                // 状态标签
                const statusTag = document.getElementById('progressTag');
                if (status.status === 'moving') {
                    statusTag.className = 'tag warning';
                    statusTag.textContent = '巡检中';
                } else {
                    statusTag.className = 'tag success';
                    statusTag.textContent = `${completed}/${total}`;
                }
            } else if (data.type === 'alert') {
                addAlert(data.data);
            }
        }
        
        function addAlert(alert) {
            const list = document.getElementById('alertList');
            const item = document.createElement('div');
            item.className = `alert-item ${alert.level || ''}`;
            item.innerHTML = `
                <span class="alert-dot ${alert.level || ''}"></span>
                <div class="alert-content">
                    <div class="alert-message">${alert.message}</div>
                    <div class="alert-time">${new Date(alert.timestamp).toLocaleTimeString()}</div>
                </div>
            `;
            list.insertBefore(item, list.firstChild);
            
            // 限制显示数量
            while (list.children.length > 10) {
                list.removeChild(list.lastChild);
            }
            
            // 更新告警数量
            const count = document.querySelectorAll('.alert-item').length;
            document.getElementById('alertCount').textContent = count;
        }
        
        function pressKey(key) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'key', key: key, action: 'press' }));
            }
        }
        
        function sendCmd(cmd) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'command', command: cmd }));
            }
        }
        
        // 键盘控制
        document.addEventListener('keydown', (e) => {
            const keyMap = {
                'w': 'forward', 'ArrowUp': 'forward',
                's': 'backward', 'ArrowDown': 'backward',
                'a': 'left', 'ArrowLeft': 'left',
                'd': 'right', 'ArrowRight': 'right',
                ' ': 'stand_up',
                'Escape': 'emergency_stop'
            };
            
            const key = keyMap[e.key];
            if (key) {
                e.preventDefault();
                if (e.type === 'keydown') {
                    pressKey(key);
                }
            }
        });
        
        // 更新时间
        function updateTime() {
            document.getElementById('currentTime').textContent = 
                new Date().toLocaleTimeString('zh-CN');
        }
        
        // 定时更新
        setInterval(updateTime, 1000);
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
        if not any(key_state.values()):
            send_udp(CMD_EMERGENCY_STOP)
            robot_status["status"] = "idle"


@app.get("/")
async def root():
    return HTMLResponse(MODERN_HTML)


@app.get("/api/status")
async def status():
    return {"clients": len(connections), "inspections": len(inspections),
            "alerts": len([a for a in alerts if not a.get("ack")])}


@app.get("/api/robot")
async def get_robot():
    return robot_status


@app.get("/api/keys")
async def get_keys():
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
    def __init__(self):
        self.last_time = time.time()

    async def process(self, data: dict, websocket: WebSocket):
        global robot_status
        msg_type = data.get("type", "")

        if msg_type == "heartbeat":
            robot_status.update({
                "battery": data.get("battery", robot_status["battery"]),
                "cpu_temp": data.get("cpu_temp", robot_status["cpu_temp"]),
                "status": "inspecting",
                "last_heartbeat": datetime.now().isoformat()
            })
            for ws in connections:
                await ws.send_json({"type": "robot_status", "data": robot_status})

        elif msg_type == "inspection_result":
            payload = data.get("payload", {})
            robot_status["waypoint"] = payload.get("waypoint", robot_status["waypoint"])
            robot_status["completed_waypoints"] = payload.get("completed_waypoints", 0)
            if payload.get("defect_type"):
                alert_msg = f"发现{payload['defect_type']}: {payload.get('description', '')}"
                alerts.append({"message": alert_msg, "timestamp": data.get("ts"), "ack": False})
                for ws in connections:
                    await ws.send_json({"type": "alert", "data": {"message": alert_msg, "level": "warning", "timestamp": data.get("ts")}})

        elif msg_type == "temperature_alert":
            payload = data.get("payload", {})
            temp = payload.get("temperature", 0)
            robot_status["cpu_temp"] = temp
            level = "high" if temp >= 50 else "warning"
            alert_msg = f"温度告警: {temp}°C"
            alerts.append({"message": alert_msg, "timestamp": data.get("ts"), "ack": False, "level": level})
            for ws in connections:
                await ws.send_json({"type": "alert", "data": {"message": alert_msg, "level": level, "timestamp": data.get("ts")}})

        elif msg_type == "system_status":
            robot_status.update(data.get("payload", {}))


monitor = Monitor()


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
    http_config = uvicorn.Config(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
    http_server = uvicorn.Server(http_config)
    
    ws_task = asyncio.create_task(ws_server())
    
    logger.info(f"监测平台启动:")
    logger.info(f"  HTTP服务: http://0.0.0.0:{HTTP_PORT}")
    logger.info(f"  WebSocket: ws://0.0.0.0:{WS_PORT}")
    
    await asyncio.gather(http_server.serve(), ws_task)


if __name__ == "__main__":
    asyncio.run(main())
