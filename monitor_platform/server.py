#!/usr/bin/env python3
"""
监测平台WebSocket服务端 - 独立运行版本
用于接收机器人上报的巡检数据
"""

import asyncio
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import websockets
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
WS_HOST = "0.0.0.0"
WS_PORT = 8765
HTTP_PORT = 8000

# 全局数据存储
connections: List[websockets.WebSocketServerProtocol] = []
inspections: List[Dict] = []
alerts: List[Dict] = []


class MonitorServer:
    """监测平台服务端"""
    
    def __init__(self):
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        
    async def handle_client(self, websocket):
        """处理客户端连接"""
        connections.append(websocket)
        logger.info(f"客户端已连接，当前在线: {len(connections)}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.process_message(data, websocket)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format"
                    }))
        except websockets.exceptions.ConnectionClosed:
            logger.info("客户端断开连接")
        finally:
            if websocket in connections:
                connections.remove(websocket)
    
    async def process_message(self, data: Dict, websocket):
        """处理接收到的消息"""
        msg_type = data.get("type")
        timestamp = time.time()
        
        if msg_type == "inspection_result":
            # 存储巡检结果
            result = {
                "id": f"INS_{int(timestamp * 1000)}",
                "timestamp": timestamp,
                "datetime": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                "device_id": data.get("device_id", "LITE3-001"),
                "data": data.get("data", {})
            }
            inspections.append(result)
            
            # 检查告警
            self.check_alerts(result)
            
            # 广播给所有客户端
            await self.broadcast({
                "type": "inspection_result",
                "data": result
            })
            
            logger.info(f"收到巡检数据: {result['id']}")
        
        elif msg_type == "heartbeat":
            await websocket.send(json.dumps({
                "type": "heartbeat_ack",
                "timestamp": timestamp
            }))
        
        else:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Unknown message type: {msg_type}"
            }))
    
    def check_alerts(self, result: Dict):
        """检查并生成告警"""
        data = result.get("data", {})
        
        # 温度告警
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
            logger.warning(f"温度告警: {alert['value']}℃")
        
        # 裂缝告警（数量>0且置信度>0.8）
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
                    logger.warning(f"裂缝告警: {detail.get('id')}")
    
    async def broadcast(self, message: Dict):
        """广播消息给所有连接的客户端"""
        if not connections:
            return
        
        disconnected = []
        for conn in connections:
            try:
                await conn.send(json.dumps(message, ensure_ascii=False))
            except Exception as e:
                logger.error(f"广播失败: {e}")
                disconnected.append(conn)
        
        # 清理断开的连接
        for conn in disconnected:
            if conn in connections:
                connections.remove(conn)
    
    def get_stats(self) -> Dict:
        """获取统计数据"""
        return {
            "connected_clients": len(connections),
            "total_inspections": len(inspections),
            "pending_alerts": len([a for a in alerts if not a.get("acknowledged")]),
            "total_alerts": len(alerts),
            "inspections_last_minute": len([i for i in inspections 
                                           if time.time() - i["timestamp"] < 60])
        }


# FastAPI应用
app = FastAPI(title="绝影Lite3监测平台")
monitor = MonitorServer()


@app.get("/", response_class=HTMLResponse)
async def root():
    """主页"""
    return DASHBOARD_HTML


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点"""
    await websocket.accept()
    connections.append(websocket)
    logger.info(f"WebSocket客户端连接，在线: {len(connections)}")
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await monitor.process_message(message, websocket)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
    except WebSocketDisconnect:
        logger.info("WebSocket客户端断开")
    finally:
        if websocket in connections:
            connections.remove(websocket)


@app.get("/api/status")
async def get_status():
    """系统状态"""
    return monitor.get_stats()


@app.get("/api/inspections")
async def get_inspections(limit: int = 100):
    """获取巡检记录"""
    return JSONResponse(inspections[-limit:])


@app.get("/api/alerts")
async def get_alerts(unacknowledged: bool = True):
    """获取告警"""
    if unacknowledged:
        return JSONResponse([a for a in alerts if not a.get("acknowledged")])
    return JSONResponse(alerts)


@app.post("/api/alert/ack")
async def acknowledge_alert(alert_id: str):
    """确认告警"""
    for alert in alerts:
        if alert.get("id") == alert_id:
            alert["acknowledged"] = True
            return {"status": "ok", "alert_id": alert_id}
    raise HTTPException(status_code=404, detail="Alert not found")


@app.post("/api/demo/send")
async def send_demo():
    """发送演示数据"""
    demo_data = {
        "type": "inspection_result",
        "device_id": "LITE3-001",
        "timestamp": time.time(),
        "data": {
            "crack": {
                "detected": True,
                "count": 2,
                "details": [
                    {"id": "CRACK_001", "width_mm": 0.5, "length_mm": 12.3, 
                     "confidence": 0.92, "location": {"x": 120, "y": 340}},
                    {"id": "CRACK_002", "width_mm": 0.3, "length_mm": 8.5,
                     "confidence": 0.87, "location": {"x": 450, "y": 200}}
                ]
            },
            "temperature": {
                "status": "WARN",
                "value": 46.5,
                "max_value": 48.2,
                "roi": {"x": 200, "y": 150, "w": 50, "h": 50}
            }
        }
    }
    # 模拟处理
    import asyncio
    dummy_ws = None  # 临时对象
    await monitor.process_message(demo_data, dummy_ws)
    return {"status": "ok", "message": "演示数据已发送"}


# 管理界面HTML
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>绝影Lite3 监测平台</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; }
        .header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 20px 40px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 24px; }
        .status-bar { display: flex; gap: 20px; align-items: center; }
        .status-item { display: flex; align-items: center; gap: 8px; }
        .dot { width: 10px; height: 10px; border-radius: 50%; background: #ccc; }
        .dot.connected { background: #22c55e; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .container { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; padding: 20px 40px; max-width: 1600px; margin: 0 auto; }
        .panel { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .panel h2 { font-size: 18px; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #e5e7eb; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 12px; text-align: center; }
        .stat-value { font-size: 32px; font-weight: bold; }
        .stat-label { font-size: 14px; opacity: 0.9; margin-top: 5px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        th { background: #f9fafb; }
        tr:hover { background: #f9fafb; }
        .badge { padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 500; }
        .badge-success { background: #dcfce7; color: #166534; }
        .badge-warning { background: #fef3c7; color: #92400e; }
        .badge-danger { background: #fee2e2; color: #991b1b; }
        .alert-item { padding: 15px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .alert-item.warn { background: #fef3c7; border-left: 4px solid #f59e0b; }
        .alert-item.critical { background: #fee2e2; border-left: 4px solid #ef4444; }
        .btn { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-danger { background: #ef4444; color: white; }
        .empty { color: #999; text-align: center; padding: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>绝影Lite3 监测平台</h1>
        <div class="status-bar">
            <div class="status-item"><div class="dot" id="connDot"></div><span id="connStatus">未连接</span></div>
            <div class="status-item">📡 <span id="clientCount">0</span> 设备在线</div>
        </div>
    </div>
    
    <div class="container">
        <div class="left">
            <div class="stats">
                <div class="stat-card"><div class="stat-value" id="totalInspections">0</div><div class="stat-label">总巡检次数</div></div>
                <div class="stat-card" style="background:linear-gradient(135deg,#4facfe,#00f2fe)"><div class="stat-value" id="normalCount">0</div><div class="stat-label">正常检测</div></div>
                <div class="stat-card" style="background:linear-gradient(135deg,#f093fb,#f5576c)"><div class="stat-value" id="crackCount">0</div><div class="stat-label">裂缝检测</div></div>
                <div class="stat-card" style="background:linear-gradient(135deg,#fa709a,#fee140)"><div class="stat-value" id="alertCount">0</div><div class="stat-label">待处理告警</div></div>
            </div>
            <div class="panel">
                <h2>最近巡检记录</h2>
                <table>
                    <thead><tr><th>时间</th><th>设备</th><th>裂缝数</th><th>温度状态</th><th>温度值</th></tr></thead>
                    <tbody id="inspectionTable"><tr><td colspan="5" class="empty">暂无数据</td></tr></tbody>
                </table>
            </div>
        </div>
        <div class="right">
            <div class="panel">
                <h2>实时告警</h2>
                <div id="alertList"><p class="empty">暂无告警</p></div>
            </div>
            <div class="panel" style="margin-top:20px">
                <h2>演示控制</h2>
                <button class="btn btn-primary" onclick="sendDemo()" style="width:100%;margin-top:10px;padding:12px">发送演示数据</button>
                <p style="color:#666;font-size:12px;margin-top:10px;text-align:center">点击按钮模拟巡检数据上报</p>
            </div>
        </div>
    </div>
    
    <script>
        let ws = null;
        let inspections = [];
        let alerts = [];
        
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
            
            inspections.unshift({ time: now, crackCount, tempStatus, tempValue });
            if (inspections.length > 20) inspections.pop();
            updateTable();
            updateStats();
        }
        
        function updateTable() {
            const tbody = document.getElementById('inspectionTable');
            if (!inspections.length) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty">暂无数据</td></tr>';
                return;
            }
            tbody.innerHTML = inspections.map(i => {
                const cls = i.tempStatus === 'NORMAL' ? 'badge-success' : i.tempStatus === 'WARN' ? 'badge-warning' : 'badge-danger';
                return `<tr><td>${i.time}</td><td>LITE3-001</td><td>${i.crackCount}</td><td><span class="badge ${cls}">${i.tempStatus}</span></td><td>${i.tempValue}℃</td></tr>`;
            }).join('');
        }
        
        function updateStats() {
            document.getElementById('totalInspections').textContent = inspections.length;
            document.getElementById('crackCount').textContent = inspections.filter(i => i.crackCount > 0).length;
        }
        
        async function sendDemo() {
            try {
                const resp = await fetch('/api/demo/send', {method: 'POST'});
                const data = await resp.json();
                console.log('演示数据发送成功', data);
            } catch (e) {
                console.error('发送失败', e);
            }
        }
        
        // 启动
        connect();
        setInterval(() => fetch('/api/status').then(r => r.json()).then(d => {
            document.getElementById('alertCount').textContent = d.pending_alerts;
        }), 2000);
    </script>
</body>
</html>
"""


async def main():
    """主函数"""
    # 启动HTTP服务器
    config = uvicorn.Config(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
    server = uvicorn.Server(config)
    
    # 启动WebSocket服务器
    ws_server = await websockets.serve(monitor.handle_client, WS_HOST, WS_PORT)
    
    logger.info(f"监测平台启动:")
    logger.info(f"  HTTP界面: http://0.0.0.0:{HTTP_PORT}")
    logger.info(f"  WebSocket: ws://0.0.0.0:{WS_PORT}/ws")
    
    # 运行HTTP服务器（异步）
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
