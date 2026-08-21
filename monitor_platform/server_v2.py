#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3 监测平台 - 完整WebSocket服务器版本

功能：
1. HTTP服务器（端口8000）- Web界面和控制API
2. WebSocket服务器（端口8765）- 实时数据推送
3. UDP控制器 - 运动控制指令发送
"""

import asyncio, json, time, logging, struct, socket, base64, threading
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

# ========== 官方协议指令码 ==========
CMD_FORWARD = 0x21010130
CMD_LEFT = 0x21010131
CMD_TURN = 0x21010135
CMD_STAND_UP = 0x21010202
CMD_EMERGENCY_STOP = 0x21020C0E
CMD_HOME = 0x21010C05
CMD_MOVE_MODE = 0x21010D06
CMD_STAND_MODE = 0x21010D05

# ========== 全局状态 ==========
connections: List[WebSocket] = []
inspections: List[Dict] = []
alerts: List[Dict] = []
robot_status = {
    "battery": 68, "cpu_temp": 35, "gpu_load": 0, 
    "memory_usage": 45, "status": "idle", 
    "waypoint": "WP001", "endurance_hours": 1.8
}
key_state = {
    'forward': False, 'backward': False,
    'left': False, 'right': False,
    'turn_left': False, 'turn_right': False
}

# ========== UDP控制器 ==========
_udp_socket = None

def send_udp(cmd: int, value: int = 0):
    """发送UDP控制指令"""
    global _udp_socket
    if _udp_socket is None:
        _udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        data = struct.pack('<III', cmd, value, 0)
        _udp_socket.sendto(data, (MOTION_HOST, MOTION_PORT))
        logger.debug(f"发送UDP指令: 0x{cmd:08X}")
    except Exception as e:
        logger.error(f"UDP发送失败: {e}")

def send_velocity_command():
    """发送速度控制指令"""
    vx, vy, vw = 0.0, 0.0, 0.0
    if key_state['forward']: vx += 0.5
    if key_state['backward']: vx -= 0.5
    if key_state['left']: vy -= 0.5
    if key_state['right']: vy += 0.5
    if key_state['turn_left']: vw += 0.5
    if key_state['turn_right']: vw -= 0.5
    
    if any(key_state.values()):
        send_udp(0x21010201, 0)  # 移动模式
        # 发送速度指令（复杂格式）
        try:
            if _udp_socket:
                data = struct.pack('<IIIfff', 0x21010201, 0, 0, vx, vy, vw)
                _udp_socket.sendto(data, (MOTION_HOST, MOTION_PORT))
        except:
            pass

def send_heartbeat():
    """发送心跳包"""
    send_udp(0x21040001, 0)

# ========== 按键状态监控线程 ==========
def key_monitor_thread():
    """后台线程监控按键状态"""
    last_state = {}
    while True:
        time.sleep(0.05)  # 20ms轮询
        current_state = dict(key_state)
        
        # 检测状态变化
        if current_state != last_state:
            send_velocity_command()
            last_state = current_state.copy()
        
        # 定期发送心跳
        if int(time.time()) % 5 == 0:
            send_heartbeat()

# 启动按键监控线程
key_thread = threading.Thread(target=key_monitor_thread, daemon=True)
key_thread.start()

# ========== WebSocket消息处理器 ==========
class Monitor:
    async def process(self, data: Dict, ws: WebSocket):
        """处理来自感知主机的WebSocket消息"""
        p = data.get("payload", data.get("data", {}))
        msg_type = data.get("type", "")
        
        try:
            if msg_type == "system_status":
                for k in ["battery", "cpu_temp", "gpu_load", "memory_usage", "status", "waypoint", "position", "endurance_hours"]:
                    if k in p:
                        robot_status[k] = p[k]
                await ws.send_json({"type": "robot_status", "data": robot_status})
                
            elif msg_type == "inspection_result":
                inspections.append({
                    "ts": int(time.time() * 1000),
                    "waypoint": p.get("waypoint_id", "WP001"),
                    "defect_type": p.get("defect_type", "crack"),
                    "confidence": p.get("confidence", 0.0),
                    "measurements": p.get("measurements", {})
                })
                # 广播给所有连接的客户端
                for conn in connections:
                    try:
                        await conn.send_json({"type": "inspection", "data": inspections[-1]})
                    except:
                        pass
                        
            elif msg_type in ["crack_alert", "temperature_alert"]:
                alerts.append({
                    "ts": int(time.time() * 1000),
                    "type": msg_type,
                    "level": p.get("level", "warning"),
                    "value": p.get("value", 0),
                    "waypoint": p.get("waypoint_id", "WP001")
                })
                # 广播告警
                for conn in connections:
                    try:
                        await conn.send_json({"type": "alert", "data": alerts[-1]})
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"处理WebSocket消息失败: {e}")

monitor = Monitor()

# ========== FastAPI路由 ==========
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """WebSocket端点 - 接收感知主机数据"""
    await ws.accept()
    connections.append(ws)
    # 发送当前状态
    await ws.send_json({"type": "robot_status", "data": robot_status})
    logger.info(f"感知主机连接: {ws.client.host}")
    
    try:
        async for msg in ws:
            try:
                data = json.loads(msg)
                await monitor.process(data, ws)
            except json.JSONDecodeError:
                logger.warning("收到非JSON消息")
            except Exception as e:
                logger.error(f"处理消息失败: {e}")
    except Exception as e:
        logger.error(f"WebSocket连接异常: {e}")
    finally:
        if ws in connections:
            connections.remove(ws)
        logger.info(f"感知主机断开: {ws.client.host}")

@app.post("/api/control/{action}")
async def control(action: str):
    """处理Web界面的控制请求"""
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

@app.post("/api/demo")
async def demo():
    """演示模式 - 模拟生成数据"""
    import random
    # 模拟巡检结果
    inspections.append({
        "ts": int(time.time() * 1000),
        "waypoint": f"WP{random.randint(1,5):03d}",
        "defect_type": random.choice(["crack", "temperature"]),
        "confidence": round(random.uniform(0.7, 0.95), 2),
        "measurements": {
            "width_mm": round(random.uniform(0.1, 0.5), 2),
            "length_mm": round(random.uniform(10, 100), 1)
        }
    })
    # 广播
    for ws in connections:
        try:
            await ws.send_json({"type": "inspection", "data": inspections[-1]})
        except:
            pass
    return {"status": "ok"}

@app.get("/")
async def root():
    """返回Web界面"""
    return HTMLResponse(DASHBOARD_HTML)

@app.get("/api/status")
async def status():
    """获取系统状态"""
    return {
        "clients": len(connections),
        "inspections": len(inspections),
        "alerts": len([a for a in alerts if not a.get("ack")]),
        "timestamp": int(time.time() * 1000)
    }

@app.get("/api/robot")
async def get_robot():
    """获取机器人状态"""
    return robot_status

@app.get("/api/keys")
async def get_keys():
    """获取按键状态"""
    return key_state

@app.get("/api/inspections")
async def get_inspections():
    """获取巡检记录"""
    return inspections[-100:] if inspections else []

@app.get("/api/alerts")
async def get_alerts():
    """获取告警记录"""
    return alerts[-50:] if alerts else []

# ========== Web界面HTML ==========
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>绝影Lite3 监测平台</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f0f2f5; }
.topbar { background: #fff; height: 56px; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; border-bottom: 1px solid #e8e8e8; }
.topbar-title { font-size: 18px; font-weight: 600; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #ccc; display: inline-block; margin-right: 8px; }
.status-dot.online { background: #52c41a; }
.panel { background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.panel-title { font-size: 14px; font-weight: 600; margin-bottom: 12px; color: #333; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
.stat-card { background: #fafafa; padding: 16px; border-radius: 8px; text-align: center; }
.stat-value { font-size: 24px; font-weight: 600; color: #1890ff; }
.stat-label { font-size: 12px; color: #999; margin-top: 4px; }
.alert-item { padding: 12px; border-left: 4px solid #faad14; background: #fffbe6; margin-bottom: 8px; border-radius: 4px; }
.alert-item.critical { border-left-color: #f5222d; background: #fff1f0; }
.inspection-item { padding: 12px; border-left: 4px solid #52c41a; background: #f6ffed; margin-bottom: 8px; border-radius: 4px; }
.btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; margin: 4px; }
.btn-primary { background: #1890ff; color: #fff; }
.btn-danger { background: #ff4d4f; color: #fff; }
.btn:hover { opacity: 0.8; }
</style>
</head>
<body>
<div class="topbar">
    <div class="topbar-title">绝影Lite3 监测平台</div>
    <div>
        <span class="status-dot" id="connDot"></span>
        <span id="connStatus">未连接</span>
    </div>
</div>

<div style="padding: 24px;">
    <div class="grid">
        <div class="stat-card">
            <div class="stat-value" id="batteryValue">--</div>
            <div class="stat-label">电池电量</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="cpuTempValue">--</div>
            <div class="stat-label">CPU温度</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="statusValue">--</div>
            <div class="stat-label">运行状态</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="clientCount">0</div>
            <div class="stat-label">连接设备</div>
        </div>
    </div>
    
    <div class="panel" style="margin-top: 16px;">
        <div class="panel-title">控制指令</div>
        <button class="btn btn-primary" onclick="sendCmd('stand_up')">起立</button>
        <button class="btn btn-danger" onclick="sendCmd('emergency_stop')">急停</button>
        <button class="btn btn-primary" onclick="sendCmd('home')">回零</button>
        <button class="btn btn-primary" onclick="sendDemo()">模拟巡检</button>
    </div>
    
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
        <div class="panel">
            <div class="panel-title">巡检记录</div>
            <div id="inspectionList"><div style="color:#999;padding:20px;text-align:center">暂无记录</div></div>
        </div>
        <div class="panel">
            <div class="panel-title">实时告警</div>
            <div id="alertList"><div style="color:#999;padding:20px;text-align:center">暂无告警</div></div>
        </div>
    </div>
</div>

<script>
let ws = null, inspections = [], alerts = [];
let robot = { battery: 0, cpu_temp: 0, status: 'idle' };

function connect() {
    ws = new WebSocket('ws://' + location.host + ':8765/ws');
    ws.onopen = () => {
        document.getElementById('connDot').className = 'status-dot online';
        document.getElementById('connStatus').textContent = '已连接';
    };
    ws.onmessage = (e) => {
        const m = JSON.parse(e.data);
        if (m.type === 'inspection') {
            inspections.push(m.data);
            updateInspections();
        } else if (m.type === 'robot_status') {
            robot = m.data;
            updateRobot();
        } else if (m.type === 'alert') {
            alerts.push(m.data);
            updateAlerts();
        }
    };
    ws.onclose = () => setTimeout(connect, 3000);
}

function updateRobot() {
    document.getElementById('batteryValue').textContent = robot.battery + '%';
    document.getElementById('cpuTempValue').textContent = robot.cpu_temp + '°C';
    document.getElementById('statusValue').textContent = robot.status;
}

function updateInspections() {
    const list = document.getElementById('inspectionList');
    if (inspections.length === 0) {
        list.innerHTML = '<div style="color:#999;padding:20px;text-align:center">暂无记录</div>';
        return;
    }
    list.innerHTML = inspections.slice(-10).reverse().map(i => `
        <div class="inspection-item">
            <div><strong>${i.waypoint}</strong> - ${i.defect_type}</div>
            <div style="font-size:12px;color:#666">置信度: ${(i.confidence*100).toFixed(1)}%</div>
        </div>
    `).join('');
}

function updateAlerts() {
    const list = document.getElementById('alertList');
    if (alerts.length === 0) {
        list.innerHTML = '<div style="color:#999;padding:20px;text-align:center">暂无告警</div>';
        return;
    }
    list.innerHTML = alerts.slice(-10).reverse().map(a => `
        <div class="alert-item ${a.level === 'critical' ? 'critical' : ''}">
            <div><strong>${a.type}</strong> - ${a.waypoint}</div>
            <div style="font-size:12px;color:#666">${new Date(a.ts).toLocaleTimeString()}</div>
        </div>
    `).join('');
}

async function sendCmd(c) {
    try { await fetch('/api/control/' + c, {method: 'POST'}); } catch(e) {}
}

async function sendDemo() {
    try { await fetch('/api/demo', {method: 'POST'}); } catch(e) {}
}

setInterval(() => fetch('/api/status').then(r => r.json()).then(d => {
    document.getElementById('clientCount').textContent = d.clients;
}), 2000);

connect();
</script>
</body>
</html>"""

# ========== 独立WebSocket服务器 ==========
async def ws_server():
    """独立的WebSocket服务器（端口8765）"""
    import websockets
    
    async def handler(websocket, path=None):
        # 复用现有的connections列表
        connections.append(websocket)
        logger.info(f"感知主机连接: {websocket.remote_address}")
        
        # 发送初始状态
        await websocket.send_json({"type": "robot_status", "data": robot_status})
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await monitor.process(data, websocket)
                except json.JSONDecodeError:
                    logger.warning("收到非JSON消息")
                except Exception as e:
                    logger.error(f"处理消息失败: {e}")
        except Exception as e:
            logger.error(f"WebSocket处理异常: {e}")
        finally:
            if websocket in connections:
                connections.remove(websocket)
            logger.info(f"感知主机断开: {websocket.remote_address}")
    
    async with websockets.serve(handler, "0.0.0.0", WS_PORT):
        logger.info(f"WebSocket服务器启动: ws://0.0.0.0:{WS_PORT}")
        await asyncio.Future()  # 永久运行

# ========== 主函数 ==========
async def main():
    global DASHBOARD_HTML
    if ROBOT_IMAGE_URI:
        DASHBOARD_HTML = DASHBOARD_HTML.replace("__ROBOT_IMAGE__", ROBOT_IMAGE_URI)
    else:
        DASHBOARD_HTML = DASHBOARD_HTML.replace('__ROBOT_IMAGE__', '<svg>...</svg>')
    
    # 启动HTTP服务器
    http_config = uvicorn.Config(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
    http_server = uvicorn.Server(http_config)
    
    # 启动WebSocket服务器（并发运行）
    ws_task = asyncio.create_task(ws_server())
    
    logger.info(f"监测平台启动:")
    logger.info(f"  HTTP服务: http://0.0.0.0:{HTTP_PORT}")
    logger.info(f"  WebSocket: ws://0.0.0.0:{WS_PORT}")
    
    # 并发运行
    await asyncio.gather(http_server.serve(), ws_task)

if __name__ == "__main__":
    asyncio.run(main())
