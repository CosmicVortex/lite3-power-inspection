#!/usr/bin/env python3
"""绝影Lite3监测平台 - 完整版本"""

import asyncio, json, time, logging, struct, socket, base64, io, os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import websockets
import cv2
import numpy as np
import aiohttp
from PIL import Image
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置
HTTP_PORT = 8000
WS_PORT = 8765
PTZ_BASE_URL = "http://192.168.1.108"
PTZ_USER = "admin"
PTZ_PASS = "123456"

RTSP_URLS = {
    "visible_main": "rtsp://admin:123456@192.168.1.108:554/id=1&type=0",
    "visible_sub": "rtsp://admin:123456@192.168.1.108:554/id=1&type=1",
    "thermal": "rtsp://admin:123456@192.168.1.108:554/id=2&type=0",
}

# 全局状态
connections = []
inspections = []
alerts = []
robot_status = {
    "battery": 68,
    "cpu_temp": 35.0,
    "gpu_load": 45,
    "memory_usage": 52,
    "waypoint": "WP001",
    "completed_waypoints": 1,
    "endurance_hours": 2.1,
    "status": "inspecting",
    "position": {"x": 0.5, "y": 0.5, "z": 0.0},
    "temperature": {"current": 35.0, "max": 42.0, "warn": False, "critical": False},
    "ptz": {"connected": False, "yaw": 0, "pitch": -30, "zoom": 1}
}
video_captures = {}
ptz_session = None
ptz_auth = None

GHOST_ADMIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>绝影Lite3 - 电力巡检监测平台</title>
    <style>
        :root {
            --ghost-black: #15171a;
            --ghost-runner: #0065ff;
            --ghost-ink: #222426;
            --ghost-mute: #65676a;
            --ghost-muted: #a2a3a7;
            --ghost-border: #e6e6e6;
            --ghost-bg: #f8f8f8;
            --ghost-green: #00875a;
            --ghost-red: #dc1a29;
            --ghost-yellow: #f5c517;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
            background: var(--ghost-bg);
            color: var(--ghost-ink);
            height: 100vh;
            overflow: hidden;
        }
        .login-page {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .login-card {
            background: white;
            border-radius: 12px;
            padding: 40px;
            width: 100%;
            max-width: 400px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .login-card h1 {
            font-size: 28px;
            margin-bottom: 8px;
            color: var(--ghost-ink);
        }
        .login-card p {
            color: var(--ghost-muted);
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 6px;
            color: var(--ghost-ink);
        }
        .form-group input {
            width: 100%;
            padding: 12px 16px;
            border: 1px solid var(--ghost-border);
            border-radius: 6px;
            font-size: 15px;
            transition: border-color 0.2s;
        }
        .form-group input:focus {
            outline: none;
            border-color: var(--ghost-runner);
        }
        .btn {
            width: 100%;
            padding: 14px;
            background: var(--ghost-runner);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        .btn:hover { background: #0052cc; }
        .dashboard {
            display: none;
            height: 100vh;
        }
        .sidebar {
            position: fixed;
            left: 0;
            top: 0;
            width: 240px;
            height: 100vh;
            background: var(--ghost-black);
            padding: 20px 0;
            overflow-y: auto;
        }
        .sidebar-logo {
            padding: 0 20px 20px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 20px;
        }
        .sidebar-logo h2 {
            color: white;
            font-size: 18px;
        }
        .sidebar-logo span {
            color: var(--ghost-muted);
            font-size: 12px;
        }
        .nav-section {
            margin-bottom: 20px;
        }
        .nav-section-title {
            padding: 8px 20px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--ghost-muted);
        }
        .nav-item {
            display: flex;
            align-items: center;
            padding: 10px 20px;
            color: rgba(255,255,255,0.7);
            text-decoration: none;
            transition: all 0.2s;
        }
        .nav-item:hover, .nav-item.active {
            background: rgba(255,255,255,0.1);
            color: white;
        }
        .nav-item.active {
            border-left: 3px solid var(--ghost-runner);
        }
        .nav-item-icon {
            width: 20px;
            margin-right: 12px;
            text-align: center;
        }
        .nav-item-badge {
            margin-left: auto;
            background: var(--ghost-red);
            color: white;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 10px;
        }
        .main {
            margin-left: 240px;
            height: 100vh;
            overflow-y: auto;
        }
        .header {
            position: sticky;
            top: 0;
            background: white;
            padding: 16px 30px;
            border-bottom: 1px solid var(--ghost-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 100;
        }
        .breadcrumb {
            font-size: 14px;
            color: var(--ghost-muted);
        }
        .breadcrumb span { color: var(--ghost-ink); }
        .header-actions {
            display: flex;
            gap: 10px;
        }
        .btn-secondary {
            padding: 8px 16px;
            background: var(--ghost-bg);
            border: 1px solid var(--ghost-border);
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
        }
        .btn-primary {
            padding: 8px 16px;
            background: var(--ghost-runner);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
        }
        .content {
            padding: 30px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .stat-card label {
            font-size: 12px;
            color: var(--ghost-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stat-card .value {
            font-size: 32px;
            font-weight: 600;
            margin: 8px 0;
        }
        .stat-card .trend {
            font-size: 13px;
        }
        .trend.up { color: var(--ghost-green); }
        .trend.down { color: var(--ghost-red); }
        .video-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        .video-card {
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .video-header {
            padding: 15px 20px;
            border-bottom: 1px solid var(--ghost-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .video-title {
            font-weight: 600;
            font-size: 14px;
        }
        .video-status {
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .video-status .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--ghost-green);
        }
        .video-status.offline .dot { background: var(--ghost-red); }
        .video-body {
            position: relative;
            padding: 0;
            background: #000;
            min-height: 200px;
        }
        .video-body img {
            width: 100%;
            height: 240px;
            object-fit: cover;
        }
        .video-footer {
            padding: 10px 20px;
            border-top: 1px solid var(--ghost-border);
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: var(--ghost-muted);
        }
        .control-panel {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .control-panel h3 {
            font-size: 16px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--ghost-border);
        }
        .dpad {
            display: grid;
            grid-template-columns: repeat(3, 50px);
            grid-template-rows: repeat(3, 50px);
            gap: 5px;
            justify-content: center;
            margin: 20px 0;
        }
        .dpad-btn {
            background: var(--ghost-bg);
            border: 1px solid var(--ghost-border);
            border-radius: 8px;
            cursor: pointer;
            font-size: 18px;
            transition: all 0.2s;
        }
        .dpad-btn:hover { background: var(--ghost-runner); color: white; }
        .dpad-btn:active { transform: scale(0.95); }
        .dpad-center { background: var(--ghost-runner); color: white; }
        .function-buttons {
            display: flex;
            gap: 10px;
            justify-content: center;
            margin-top: 20px;
        }
        .func-btn {
            padding: 10px 20px;
            background: var(--ghost-runner);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
        }
        .func-btn:hover { background: #0052cc; }
        .alerts-list {
            background: white;
            border-radius: 8px;
            padding: 20px;
            max-height: 300px;
            overflow-y: auto;
        }
        .alert-item {
            display: flex;
            align-items: center;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 10px;
            background: var(--ghost-bg);
        }
        .alert-item.danger { background: #fee; border-left: 3px solid var(--ghost-red); }
        .alert-item.warning { background: #ffc; border-left: 3px solid var(--ghost-yellow); }
        .alert-item.info { background: #eef; border-left: 3px solid var(--ghost-runner); }
        .alert-time { font-size: 12px; color: var(--ghost-muted); margin-right: 15px; }
        @media (max-width: 1024px) {
            .sidebar { width: 60px; }
            .sidebar-logo-text, .nav-item-text, .nav-section-title, .nav-item-badge { display: none; }
            .nav-item { justify-content: center; padding: 15px; }
            .nav-item-icon { margin-right: 0; }
            .main { margin-left: 60px; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .video-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 768px) {
            .sidebar { display: none; }
            .main { margin-left: 0; }
            .stats-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <!-- 登录页面 -->
    <div id="loginPage" class="login-page">
        <div class="login-card">
            <h1>绝影Lite3</h1>
            <p>电力巡检监测平台</p>
            <form id="loginForm">
                <div class="form-group">
                    <label>用户名</label>
                    <input type="text" id="username" value="admin" required>
                </div>
                <div class="form-group">
                    <label>密码</label>
                    <input type="password" id="password" value="admin" required>
                </div>
                <button type="submit" class="btn">登录</button>
            </form>
        </div>
    </div>
    
    <!-- 主界面 -->
    <div id="dashboard" class="dashboard">
        <aside class="sidebar">
            <div class="sidebar-logo">
                <h2>绝影Lite3</h2>
                <span>电力巡检系统</span>
            </div>
            <nav>
                <div class="nav-section">
                    <div class="nav-section-title">监控中心</div>
                    <a href="#" class="nav-item active">
                        <span class="nav-item-icon">📊</span>
                        <span class="nav-item-text">实时监控</span>
                    </a>
                    <a href="#" class="nav-item">
                        <span class="nav-item-icon">📈</span>
                        <span class="nav-item-text">温度趋势</span>
                    </a>
                    <a href="#" class="nav-item">
                        <span class="nav-item-icon">🔍</span>
                        <span class="nav-item-text">裂缝检测</span>
                        <span class="nav-item-badge">3</span>
                    </a>
                </div>
                <div class="nav-section">
                    <div class="nav-section-title">控制面板</div>
                    <a href="#" class="nav-item">
                        <span class="nav-item-icon">🎮</span>
                        <span class="nav-item-text">设备控制</span>
                    </a>
                    <a href="#" class="nav-item">
                        <span class="nav-item-icon">📹</span>
                        <span class="nav-item-text">视频管理</span>
                    </a>
                    <a href="#" class="nav-item">
                        <span class="nav-item-icon">🎯</span>
                        <span class="nav-item-text">云台控制</span>
                    </a>
                </div>
                <div class="nav-section">
                    <div class="nav-section-title">历史记录</div>
                    <a href="#" class="nav-item">
                        <span class="nav-item-icon">📈</span>
                        <span class="nav-item-text">巡检记录</span>
                    </a>
                    <a href="#" class="nav-item">
                        <span class="nav-item-icon">⚠️</span>
                        <span class="nav-item-text">告警记录</span>
                        <span class="nav-item-badge" id="alertBadge">0</span>
                    </a>
                </div>
                <div class="nav-section">
                    <div class="nav-section-title">系统</div>
                    <a href="#" class="nav-item">
                        <span class="nav-item-icon">⚙️</span>
                        <span class="nav-item-text">Admin</span>
                    </a>
                    <a href="#" class="nav-item" onclick="logout()">
                        <span class="nav-item-icon">🚪</span>
                        <span class="nav-item-text">退出</span>
                    </a>
                </div>
            </nav>
        </aside>
        
        <main class="main">
            <header class="header">
                <div class="breadcrumb">
                    监控中心 / <span>实时监控</span>
                </div>
                <div class="header-actions">
                    <button class="btn-secondary" onclick="startDemo()">演示模式</button>
                    <button class="btn-primary" onclick="robotStand()">起立</button>
                </div>
            </header>
            
            <div class="content">
                <div class="stats-grid">
                    <div class="stat-card">
                        <label>电池电量</label>
                        <div class="value" id="batteryValue">68%</div>
                        <div class="trend up">续航 2.1小时</div>
                    </div>
                    <div class="stat-card">
                        <label>当前温度</label>
                        <div class="value" id="tempValue">35°C</div>
                        <div class="trend">目标: 45°C</div>
                    </div>
                    <div class="stat-card">
                        <label>巡检进度</label>
                        <div class="value">3/5</div>
                        <div class="trend up">60%完成</div>
                    </div>
                    <div class="stat-card">
                        <label>告警数量</label>
                        <div class="value" id="alertCount">0</div>
                        <div class="trend">正常</div>
                    </div>
                </div>
                
                <div class="video-grid">
                    <div class="video-card">
                        <div class="video-header">
                            <span class="video-title">可见光（主）</span>
                            <span class="video-status" id="visibleMainConn">
                                <span class="dot"></span> 在线
                            </span>
                        </div>
                        <div class="video-body">
                            <img id="visibleMain" src="/api/video/visible_main?t=0" alt="可见光主画面">
                        </div>
                        <div class="video-footer">
                            <span>CAM-01</span>
                            <span>30 FPS</span>
                        </div>
                    </div>
                    
                    <div class="video-card">
                        <div class="video-header">
                            <span class="video-title">热成像</span>
                            <span class="video-status" id="thermalConn">
                                <span class="dot"></span> 在线
                            </span>
                        </div>
                        <div class="video-body">
                            <img id="thermal" src="/api/video/thermal?t=0" alt="热成像画面">
                        </div>
                        <div class="video-footer">
                            <span>THERMAL-01</span>
                            <span id="thermalTemp">35°C</span>
                        </div>
                    </div>
                </div>
                
                <div class="control-panel">
                    <h3>运动控制</h3>
                    <div class="dpad">
                        <div></div>
                        <button class="dpad-btn" onclick="moveRobot('forward')" title="前进">↑</button>
                        <div></div>
                        <button class="dpad-btn" onclick="moveRobot('left')" title="左转">←</button>
                        <button class="dpad-btn dpad-center" onclick="emergencyStop()" title="急停">⏻</button>
                        <button class="dpad-btn" onclick="moveRobot('right')" title="右转">→</button>
                        <div></div>
                        <button class="dpad-btn" onclick="moveRobot('backward')" title="后退">↓</button>
                        <div></div>
                    </div>
                    <div class="function-buttons">
                        <button class="func-btn" onclick="robotStand()">起立</button>
                        <button class="func-btn" onclick="robotSit()">趴下</button>
                        <button class="func-btn" onclick="robotHome()">回零</button>
                        <button class="func-btn" onclick="emergencyStop()" style="background:#dc1a29">急停</button>
                    </div>
                </div>
                
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
                    <div class="control-panel">
                        <h3>云台控制</h3>
                        <div style="margin-bottom:15px">
                            <label>偏航角: <span id="yawValue">0</span>°</label>
                            <input type="range" min="-280" max="280" value="0" 
                                   oninput="updatePTZ('yaw', this.value)" style="width:100%">
                        </div>
                        <div style="margin-bottom:15px">
                            <label>俯仰角: <span id="pitchValue">-30</span>°</label>
                            <input type="range" min="-115" max="40" value="-30" 
                                   oninput="updatePTZ('pitch', this.value)" style="width:100%">
                        </div>
                        <div style="margin-bottom:15px">
                            <label>变倍: <span id="zoomValue">1</span>x</label>
                            <input type="range" min="1" max="20" value="1" 
                                   oninput="updatePTZ('zoom', this.value)" style="width:100%">
                        </div>
                        <div style="display:flex;gap:10px">
                            <button class="btn-secondary" onclick="ptzHome()" style="flex:1">回零</button>
                            <button class="btn-secondary" onclick="ptzConnect()" style="flex:1">重连</button>
                        </div>
                    </div>
                    
                    <div class="control-panel">
                        <h3>温度阈值设置</h3>
                        <div style="margin-bottom:15px">
                            <label>预警阈值 (°C)</label>
                            <input type="number" id="warnThreshold" value="45" min="30" max="60" 
                                   style="width:100%;padding:10px;border:1px solid #e6e6e6;border-radius:6px">
                        </div>
                        <div style="margin-bottom:15px">
                            <label>告警阈值 (°C)</label>
                            <input type="number" id="criticalThreshold" value="50" min="40" max="70" 
                                   style="width:100%;padding:10px;border:1px solid #e6e6e6;border-radius:6px">
                        </div>
                        <button class="btn" onclick="saveThresholds()">保存设置</button>
                    </div>
                </div>
                
                <div class="alerts-list">
                    <h3 style="margin-bottom:15px">实时告警</h3>
                    <div id="alertList">
                        <div class="empty-state" style="text-align:center;padding:40px;color:#a2a3a7">
                            暂无告警
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
    
    <script>
        let ws = null;
        let videoRefreshInterval = null;
        let alertCounter = 0;
        
        // 登录处理
        document.getElementById('loginForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            if (username === 'admin' && password === 'admin') {
                document.getElementById('loginPage').style.display = 'none';
                document.getElementById('dashboard').style.display = 'block';
                initPlatform();
            } else {
                alert('账号或密码错误');
            }
        });
        
        function logout() {
            document.getElementById('loginPage').style.display = 'flex';
            document.getElementById('dashboard').style.display = 'none';
            if (ws) ws.close();
        }
        
        function initPlatform() {
            connectWebSocket();
            startVideoRefresh();
            loadStatus();
        }
        
        function connectWebSocket() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(protocol + '//' + location.host + ':8765/ws');
            
            ws.onopen = () => console.log('WebSocket连接成功');
            ws.onclose = () => setTimeout(connectWebSocket, 3000);
            ws.onerror = () => ws.close();
            ws.onmessage = (e) => {
                const data = JSON.parse(e.data);
                if (data.type === 'robot_status') updateRobotStatus(data.data);
                if (data.type === 'alert') addAlert(data.data);
            };
        }
        
        function startVideoRefresh() {
            videoRefreshInterval = setInterval(() => {
                const timestamp = Date.now();
                document.getElementById('visibleMain').src = '/api/video/visible_main?t=' + timestamp;
                document.getElementById('thermal').src = '/api/video/thermal?t=' + timestamp;
                checkVideoStatus();
            }, 1000);
        }
        
        function checkVideoStatus() {
            // 模拟视频状态检查
            const visibleMain = document.getElementById('visibleMainConn');
            const thermal = document.getElementById('thermalConn');
            
            // 实际项目中应该通过API检测视频流连接状态
            visibleMain.innerHTML = '<span class="dot" style="background:#00875a"></span> 连接正常';
            thermal.innerHTML = '<span class="dot" style="background:#00875a"></span> 连接正常';
        }
        
        function updateRobotStatus(status) {
            document.getElementById('batteryValue').textContent = status.battery + '%';
            document.getElementById('tempValue').textContent = status.temperature.current + '°C';
            
            // 更新温度显示
            const thermalTemp = document.getElementById('thermalTemp');
            if (thermalTemp) thermalTemp.textContent = Math.round(status.temperature.current) + '°C';
        }
        
        function addAlert(alert) {
            const list = document.getElementById('alertList');
            const empty = list.querySelector('.empty-state');
            if (empty) empty.remove();
            
            alertCounter++;
            document.getElementById('alertCount').textContent = alertCounter;
            document.getElementById('alertBadge').textContent = alertCounter;
            
            const item = document.createElement('div');
            item.className = 'alert-item ' + (alert.level || 'info');
            item.innerHTML = '<span class="alert-time">' + new Date().toLocaleTimeString() + '</span>' + alert.message;
            list.insertBefore(item, list.firstChild);
            
            // 限制告警数量
            while (list.children.length > 10) {
                list.removeChild(list.lastChild);
            }
        }
        
        function moveRobot(direction) {
            if (!ws || ws.readyState !== WebSocket.OPEN) return;
            ws.send(JSON.stringify({type: 'motion', direction: direction}));
        }
        
        function emergencyStop() {
            if (!ws || ws.readyState !== WebSocket.OPEN) return;
            ws.send(JSON.stringify({type: 'emergency_stop'}));
        }
        
        function robotStand() {
            if (!ws || ws.readyState !== WebSocket.OPEN) return;
            ws.send(JSON.stringify({type: 'motion', command: 'stand'}));
        }
        
        function robotSit() {
            if (!ws || ws.readyState !== WebSocket.OPEN) return;
            ws.send(JSON.stringify({type: 'motion', command: 'sit'}));
        }
        
        function robotHome() {
            if (!ws || ws.readyState !== WebSocket.OPEN) return;
            ws.send(JSON.stringify({type: 'motion', command: 'home'}));
        }
        
        function startDemo() {
            fetch('/api/demo', {method: 'POST'})
                .then(r => r.json())
                .then(data => console.log('演示模式启动', data));
        }
        
        function updatePTZ(parameter, value) {
            document.getElementById(parameter + 'Value').textContent = value;
            if (!ws || ws.readyState !== WebSocket.OPEN) return;
            ws.send(JSON.stringify({type: 'ptz_control', parameter: parameter, value: parseFloat(value)}));
        }
        
        function ptzHome() {
            updatePTZ('yaw', 0);
            updatePTZ('pitch', -30);
            updatePTZ('zoom', 1);
        }
        
        function ptzConnect() {
            fetch('/api/ptz/login', {method: 'POST'})
                .then(r => r.json())
                .then(data => console.log('云台连接', data));
        }
        
        function saveThresholds() {
            const warn = parseFloat(document.getElementById('warnThreshold').value);
            const critical = parseFloat(document.getElementById('criticalThreshold').value);
            
            if (warn >= critical) {
                alert('预警阈值必须小于告警阈值');
                return;
            }
            
            if (!ws || ws.readyState !== WebSocket.OPEN) return;
            ws.send(JSON.stringify({type: 'temperature_threshold', warn: warn, critical: critical}));
            
            alert('阈值设置已保存');
        }
        
        // 键盘控制
        document.addEventListener('keydown', (e) => {
            if (document.getElementById('dashboard').style.display === 'none') return;
            
            switch(e.key) {
                case 'w': case 'ArrowUp': moveRobot('forward'); break;
                case 's': case 'ArrowDown': moveRobot('backward'); break;
                case 'a': case 'ArrowLeft': moveRobot('left'); break;
                case 'd': case 'ArrowRight': moveRobot('right'); break;
                case ' ': emergencyStop(); break;
            }
        });
    </script>
</body>
</html>"""

# API端点
@app.get("/", response_class=HTMLResponse)
async def root():
    return GHOST_ADMIN_HTML

@app.get("/api/status")
async def get_status():
    return {
        "clients": len(connections),
        "inspections": len(inspections),
        "alerts": len([a for a in alerts if not a.get("ack")])
    }

@app.get("/api/robot")
async def get_robot():
    return robot_status

@app.get("/api/video/{stream_name}")
async def get_video_frame(stream_name: str):
    """获取单帧视频截图"""
    if stream_name not in RTSP_URLS:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    try:
        cap = video_captures.get(stream_name)
        if cap and cap.isOpened():
            ret, frame = cap.read()
            if ret:
                # 转换颜色空间 (BGR -> RGB)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # 压缩为JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                return StreamingResponse(
                    io.BytesIO(buffer.tobytes()),
                    media_type="image/jpeg"
                )
    except Exception as e:
        logger.error(f"获取视频帧失败: {e}")
    
    # 返回默认图片
    return HTMLResponse("<img src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22640%22 height=%22480%22><rect fill=%22%23333%22 width=%22640%22 height=%22480%22/><text fill=%22%23666%22 x=%2250%%22 y=%2250%%22 text-anchor=%22middle%22 dy=%22.3em%22 font-size=%2220%22>暂无视频信号</text></svg>'>")

@app.post("/api/ptz/login")
async def ptz_login():
    """云台登录"""
    global ptz_session, ptz_auth
    try:
        url = f"{PTZ_BASE_URL}/merlin/Login.cgi"
        params = {"Type": "WEB", "Expires": "30"}
        resp = requests.get(url, params=params, auth=(PTZ_USER, PTZ_PASS), timeout=5)
        if resp.status_code == 200:
            ptz_session = resp.text.strip()
            ptz_auth = (PTZ_USER, PTZ_PASS)
            robot_status["ptz"]["connected"] = True
            logger.info("云台登录成功")
            return {"status": "ok", "session": ptz_session}
    except Exception as e:
        logger.warning(f"云台登录失败: {e}")
    return {"status": "error", "message": str(e)}

@app.post("/api/ptz/logout")
async def ptz_logout():
    """云台登出"""
    global ptz_session, ptz_auth
    try:
        url = f"{PTZ_BASE_URL}/merlin/Logout.cgi"
        params = {"Expires": "0"}
        resp = requests.get(url, params=params, auth=ptz_auth, timeout=5)
        ptz_session = None
        ptz_auth = None
        robot_status["ptz"]["connected"] = False
    except Exception as e:
        logger.error(f"云台登出失败: {e}")
    return {"status": "ok"}

@app.post("/api/ptz/set_angle")
async def ptz_set_angle(yaw: float = 0, pitch: float = -30, zoom: float = 1):
    """设置云台角度"""
    try:
        if not ptz_session:
            return {"status": "error", "message": "请先登录云台"}
        
        url = f"{PTZ_BASE_URL}/merlin/PTZCtrl.cgi"
        params = {
            "Session": ptz_session,
            "Action": "SetPanTiltZoom",
            "PanTilt": f"{yaw},{pitch}",
            "Zoom": str(zoom)
        }
        resp = requests.get(url, params=params, auth=ptz_auth, timeout=5)
        if resp.status_code == 200:
            robot_status["ptz"]["yaw"] = yaw
            robot_status["ptz"]["pitch"] = pitch
            robot_status["ptz"]["zoom"] = zoom
            return {"status": "ok"}
    except Exception as e:
        logger.error(f"云台控制失败: {e}")
    return {"status": "error", "message": str(e)}

@app.get("/api/ptz/state")
async def ptz_state():
    """获取云台状态"""
    return robot_status.get("ptz", {})

@app.get("/api/temperature")
async def get_temperature():
    """获取温度数据"""
    return {
        "current": robot_status["temperature"]["current"],
        "max": robot_status["temperature"]["max"],
        "warn_threshold": 45.0,
        "critical_threshold": 50.0,
        "history": []
    }

@app.post("/api/demo")
async def demo_mode():
    """演示模式"""
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
    return {"status": "ok"}

async def ws_server():
    """WebSocket服务器"""
    async def handler(websocket):
        connections.append(websocket)
        logger.info(f"感知主机连接: {websocket.remote_address}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    logger.info(f"收到消息: {data.get('type')}")
                except json.JSONDecodeError:
                    logger.warning("收到非JSON消息")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"感知主机断开: {websocket.remote_address}")
        finally:
            if websocket in connections:
                connections.remove(websocket)
            logger.info(f"感知主机已断开连接")
    
    async with websockets.serve(handler, "0.0.0.0", WS_PORT):
        logger.info(f"WebSocket服务器启动: ws://0.0.0.0:{WS_PORT}")
        await asyncio.Future()

async def main():
    """主函数"""
    # 启动HTTP服务器
    http_config = uvicorn.Config(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
    http_server = uvicorn.Server(http_config)
    
    # 启动WebSocket服务器
    ws_task = asyncio.create_task(ws_server())
    
    # 启动视频流
    for name, url in RTSP_URLS.items():
        try:
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                video_captures[name] = cap
                logger.info(f"视频流启动成功: {name}")
            else:
                logger.warning(f"无法打开视频流: {name}")
        except Exception as e:
            logger.error(f"启动视频流失败 {name}: {e}")
    
    # 云台登录
    try:
        url = f"{PTZ_BASE_URL}/merlin/Login.cgi"
        params = {"Type": "WEB", "Expires": "30"}
        resp = requests.get(url, params=params, auth=(PTZ_USER, PTZ_PASS), timeout=5)
        if resp.status_code == 200:
            global ptz_session, ptz_auth
            ptz_session = resp.text.strip()
            ptz_auth = (PTZ_USER, PTZ_PASS)
            robot_status["ptz"]["connected"] = True
            logger.info("云台登录成功")
    except Exception as e:
        logger.warning(f"云台登录失败（将继续运行）: {e}")
    
    logger.info(f"监测平台启动:")
    logger.info(f"  HTTP服务: http://0.0.0.0:{HTTP_PORT}")
    logger.info(f"  WebSocket: ws://0.0.0.0:{WS_PORT}")
    logger.info(f"  视频流: http://localhost:{HTTP_PORT}/api/video/visible_main")
    
    await asyncio.gather(http_server.serve(), ws_task)

if __name__ == "__main__":
    asyncio.run(main())
