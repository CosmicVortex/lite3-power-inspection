#!/usr/bin/env python3
"""
绝影Lite3 监测平台 - Ghost CMS风格UI升级版
参考Ghost CMS设计理念：极简、专业、高质量视觉、大量留白
适应电力巡检主题内容
"""

import asyncio, json, time, logging, struct, socket, base64
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
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

# ========== Ghost CMS风格UI ==========
GHOST_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>绝影Lite3 · 电力巡检监控中心</title>
    <style>
        /* ========== Ghost CMS设计系统 ========== */
        :root {
            /* Ghost品牌色 */
            --ghost-black: #15171A;
            --ghost-dark: #222429;
            --ghost-gray: #3A3E47;
            --ghost-mid: #515761;
            --ghost-light: #6B727A;
            --ghost-pale: #Brodie: #D4D7DC;
            --ghost-palest: #F1F3F5;
            --ghost-white: #FFFFFF;
            
            /* 主题色（电力巡检） */
            --primary: #FF6B35;
            --primary-light: #FF8F5A;
            --success: #00C853;
            --warning: #FFB300;
            --danger: #FF3D00;
            --info: #2196F3;
            
            /* 间距系统 */
            --space-xs: 4px;
            --space-sm: 8px;
            --space-md: 16px;
            --space-lg: 24px;
            --space-xl: 32px;
            --space-2xl: 48px;
            --space-3xl: 64px;
            
            /* 圆角 */
            --radius-sm: 4px;
            --radius-md: 8px;
            --radius-lg: 12px;
            --radius-xl: 16px;
            --radius-full: 9999px;
            
            /* 阴影 */
            --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.1);
            --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.1);
            --shadow-xl: 0 20px 25px -5px rgba(0,0,0,0.1);
        }
        
        /* ========== 基础重置 ========== */
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
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--ghost-palest);
            color: var(--ghost-gray);
            line-height: 1.6;
            min-height: 100vh;
        }
        
        /* ========== 顶部导航（Ghost风格：简洁、白色、sticky） ========== */
        .header {
            background: var(--ghost-white);
            border-bottom: 1px solid var(--ghost-pale);
            padding: 0 var(--space-xl);
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: var(--space-md);
            text-decoration: none;
            color: var(--ghost-black);
        }
        
        .logo-icon {
            width: 32px;
            height: 32px;
            background: var(--primary);
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 18px;
        }
        
        .logo-text {
            font-size: 18px;
            font-weight: 600;
            letter-spacing: -0.3px;
        }
        
        .logo-subtitle {
            font-size: 12px;
            color: var(--ghost-light);
            font-weight: 400;
            margin-left: var(--space-sm);
            padding-left: var(--space-sm);
            border-left: 1px solid var(--ghost-pale);
        }
        
        .header-right {
            display: flex;
            align-items: center;
            gap: var(--space-lg);
        }
        
        .status-badge {
            display: flex;
            align-items: center;
            gap: var(--space-sm);
            padding: var(--space-sm) var(--space-md);
            background: #ECFDF5;
            border-radius: var(--radius-full);
            font-size: 13px;
            color: var(--success);
            font-weight: 500;
        }
        
        .status-dot {
            width: 6px;
            height: 6px;
            background: var(--success);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.2); }
        }
        
        .time-display {
            font-size: 13px;
            color: var(--ghost-light);
            font-variant-numeric: tabular-nums;
        }
        
        /* ========== 主内容区（大量留白） ========== */
        .main {
            max-width: 1200px;
            margin: 0 auto;
            padding: var(--space-2xl) var(--space-xl);
        }
        
        /* ========== Ghost风格Hero区域 ========== */
        .hero {
            background: var(--ghost-white);
            border-radius: var(--radius-xl);
            padding: var(--space-3xl);
            margin-bottom: var(--space-2xl);
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--ghost-pale);
        }
        
        .hero-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: var(--space-2xl);
        }
        
        .hero-title {
            font-size: 42px;
            font-weight: 700;
            color: var(--ghost-black);
            letter-spacing: -1.5px;
            line-height: 1.1;
            margin-bottom: var(--space-sm);
        }
        
        .hero-subtitle {
            font-size: 18px;
            color: var(--ghost-light);
            font-weight: 400;
        }
        
        .hero-meta {
            text-align: right;
        }
        
        .hero-meta-value {
            font-size: 48px;
            font-weight: 700;
            color: var(--primary);
            letter-spacing: -2px;
            line-height: 1;
        }
        
        .hero-meta-label {
            font-size: 13px;
            color: var(--ghost-light);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: var(--space-sm);
        }
        
        /* ========== 卡片网格（Ghost风格：大间距、简洁） ========== */
        .cards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: var(--space-xl);
            margin-bottom: var(--space-2xl);
        }
        
        .card {
            background: var(--ghost-white);
            border-radius: var(--radius-xl);
            padding: var(--space-xl);
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--ghost-pale);
            transition: all 0.2s ease;
        }
        
        .card:hover {
            box-shadow: var(--shadow-md);
            transform: translateY(-2px);
        }
        
        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: var(--space-lg);
            padding-bottom: var(--space-md);
            border-bottom: 1px solid var(--ghost-palest);
        }
        
        .card-title {
            font-size: 14px;
            font-weight: 600;
            color: var(--ghost-black);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .card-badge {
            font-size: 11px;
            padding: 2px 8px;
            background: var(--ghost-palest);
            color: var(--ghost-light);
            border-radius: var(--radius-full);
            font-weight: 500;
        }
        
        .card-icon {
            width: 36px;
            height: 36px;
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
        }
        
        .card-icon.orange { background: #FFF3E0; }
        .card-icon.green { background: #E8F5E9; }
        .card-icon.blue { background: #E3F2FD; }
        .card-icon.red { background: #FFEbee; }
        
        /* ========== 电池环形（优化版） ========== */
        .battery-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: var(--space-md);
        }
        
        .battery-ring {
            position: relative;
            width: 140px;
            height: 140px;
        }
        
        .battery-ring svg {
            transform: rotate(-90deg);
            filter: drop-shadow(0 2px 8px rgba(0,0,0,0.1));
        }
        
        .battery-ring-bg {
            fill: none;
            stroke: var(--ghost-palest);
            stroke-width: 10;
        }
        
        .battery-ring-fill {
            fill: none;
            stroke: var(--success);
            stroke-width: 10;
            stroke-linecap: round;
            transition: stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .battery-center {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
        }
        
        .battery-percent {
            font-size: 36px;
            font-weight: 700;
            color: var(--ghost-black);
            letter-spacing: -1px;
            line-height: 1;
        }
        
        .battery-label {
            font-size: 12px;
            color: var(--ghost-light);
            margin-top: var(--space-xs);
        }
        
        .battery-info {
            text-align: center;
        }
        
        .battery-endurance {
            font-size: 14px;
            color: var(--ghost-gray);
        }
        
        .battery-endurance strong {
            color: var(--ghost-black);
            font-weight: 600;
        }
        
        /* ========== 数据展示（Ghost风格：简洁大字体） ========== */
        .data-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: var(--space-md) 0;
            border-bottom: 1px solid var(--ghost-palest);
        }
        
        .data-row:last-child {
            border-bottom: none;
        }
        
        .data-label {
            font-size: 14px;
            color: var(--ghost-light);
        }
        
        .data-value {
            font-size: 20px;
            font-weight: 600;
            color: var(--ghost-black);
            font-variant-numeric: tabular-nums;
        }
        
        .data-value.warning {
            color: var(--warning);
        }
        
        .data-value.danger {
            color: var(--danger);
        }
        
        /* ========== 控制面板（Ghost风格：简洁清晰） ========== */
        .control-section {
            background: var(--ghost-white);
            border-radius: var(--radius-xl);
            padding: var(--space-xl);
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--ghost-pale);
            margin-bottom: var(--space-xl);
        }
        
        .control-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--space-lg);
        }
        
        .control-title {
            font-size: 14px;
            font-weight: 600;
            color: var(--ghost-black);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .control-hint {
            font-size: 13px;
            color: var(--ghost-light);
        }
        
        .dpad {
            display: grid;
            grid-template-columns: repeat(3, 64px);
            grid-template-rows: repeat(3, 64px);
            gap: var(--space-sm);
            margin: var(--space-xl) auto;
            width: fit-content;
        }
        
        .dpad-btn {
            width: 64px;
            height: 64px;
            border: 1px solid var(--ghost-pale);
            border-radius: var(--radius-lg);
            background: var(--ghost-white);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            color: var(--ghost-gray);
            transition: all 0.15s ease;
        }
        
        .dpad-btn:hover {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
            transform: scale(1.05);
        }
        
        .dpad-btn:active {
            transform: scale(0.95);
        }
        
        .dpad-btn.empty {
            background: transparent;
            border: none;
            cursor: default;
            pointer-events: none;
        }
        
        .action-buttons {
            display: flex;
            gap: var(--space-md);
            justify-content: center;
            margin-top: var(--space-xl);
            padding-top: var(--space-lg);
            border-top: 1px solid var(--ghost-palest);
        }
        
        .action-btn {
            padding: var(--space-md) var(--space-xl);
            border: 1px solid var(--ghost-pale);
            border-radius: var(--radius-md);
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
            background: var(--ghost-white);
            color: var(--ghost-gray);
        }
        
        .action-btn:hover {
            border-color: var(--ghost-mid);
            color: var(--ghost-black);
        }
        
        .action-btn.primary {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }
        
        .action-btn.primary:hover {
            background: var(--primary-light);
            border-color: var(--primary-light);
        }
        
        .action-btn.danger {
            background: var(--danger);
            border-color: var(--danger);
            color: white;
        }
        
        .action-btn.danger:hover {
            background: #E53935;
            border-color: #E53935;
        }
        
        /* ========== 告警列表（Ghost风格：时间线设计） ========== */
        .alert-list {
            max-height: 320px;
            overflow-y: auto;
            padding-right: var(--space-sm);
        }
        
        .alert-list::-webkit-scrollbar {
            width: 4px;
        }
        
        .alert-list::-webkit-scrollbar-track {
            background: var(--ghost-palest);
            border-radius: 2px;
        }
        
        .alert-list::-webkit-scrollbar-thumb {
            background: var(--ghost-pale);
            border-radius: 2px;
        }
        
        .alert-item {
            display: flex;
            gap: var(--space-md);
            padding: var(--space-md);
            border-radius: var(--radius-md);
            margin-bottom: var(--space-sm);
            background: var(--ghost-palest);
            transition: all 0.2s ease;
        }
        
        .alert-item:hover {
            background: var(--ghost-pale);
        }
        
        .alert-item.warning {
            background: #FFF8E1;
        }
        
        .alert-item.danger {
            background: #FFEBEE;
        }
        
        .alert-indicator {
            width: 32px;
            height: 32px;
            border-radius: var(--radius-full);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            flex-shrink: 0;
        }
        
        .alert-indicator.warning {
            background: var(--warning);
            color: white;
        }
        
        .alert-indicator.danger {
            background: var(--danger);
            color: white;
        }
        
        .alert-content {
            flex: 1;
        }
        
        .alert-message {
            font-size: 14px;
            color: var(--ghost-black);
            font-weight: 500;
        }
        
        .alert-time {
            font-size: 12px;
            color: var(--ghost-light);
            margin-top: var(--space-xs);
        }
        
        .alert-empty {
            text-align: center;
            padding: var(--space-2xl);
            color: var(--ghost-light);
            font-size: 14px;
        }
        
        /* ========== 进度条（Ghost风格） ========== */
        .progress-bar {
            height: 4px;
            background: var(--ghost-palest);
            border-radius: var(--radius-full);
            overflow: hidden;
            margin-top: var(--space-md);
        }
        
        .progress-fill {
            height: 100%;
            background: var(--primary);
            border-radius: var(--radius-full);
            transition: width 0.5s ease;
        }
        
        /* ========== Footer ========== */
        .footer {
            text-align: center;
            padding: var(--space-2xl);
            color: var(--ghost-light);
            font-size: 13px;
            border-top: 1px solid var(--ghost-pale);
            margin-top: var(--space-2xl);
        }
        
        /* ========== 响应式 ========== */
        @media (max-width: 768px) {
            .header {
                padding: 0 var(--space-md);
            }
            
            .main {
                padding: var(--space-lg) var(--space-md);
            }
            
            .hero {
                padding: var(--space-xl);
            }
            
            .hero-header {
                flex-direction: column;
                gap: var(--space-lg);
            }
            
            .hero-meta {
                text-align: left;
            }
            
            .hero-title {
                font-size: 28px;
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
        <a href="/" class="logo">
            <div class="logo-icon">🤖</div>
            <span class="logo-text">绝影Lite3</span>
            <span class="logo-subtitle">电力巡检监控中心</span>
        </a>
        <div class="header-right">
            <div class="status-badge">
                <span class="status-dot"></span>
                <span id="connectionStatus">已连接</span>
            </div>
            <span class="time-display" id="currentTime"></span>
        </div>
    </header>
    
    <!-- 主内容 -->
    <main class="main">
        <!-- Hero区域（Ghost风格：大标题+关键数据） -->
        <section class="hero">
            <div class="hero-header">
                <div>
                    <h1 class="hero-title">实时巡检监控</h1>
                    <p class="hero-subtitle">绝影Lite3专业版 · 智能电力巡检系统</p>
                </div>
                <div class="hero-meta">
                    <div class="hero-meta-value" id="clientCount">0</div>
                    <div class="hero-meta-label">在线设备</div>
                </div>
            </div>
            
            <!-- 进度条：巡检进度 -->
            <div style="margin-top: var(--space-xl);">
                <div style="display: flex; justify-content: space-between; margin-bottom: var(--space-sm);">
                    <span style="font-size: 13px; color: var(--ghost-light);">巡检进度</span>
                    <span style="font-size: 13px; color: var(--ghost-gray); font-weight: 500;" id="progressText">0 / 5</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill" style="width: 0%;"></div>
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
                <div class="battery-container">
                    <div class="battery-ring">
                        <svg width="140" height="140" viewBox="0 0 140 140">
                            <circle class="battery-ring-bg" cx="70" cy="70" r="60"/>
                            <circle class="battery-ring-fill" id="batteryRing" cx="70" cy="70" r="60"
                                    stroke-dasharray="377" stroke-dashoffset="113"/>
                        </svg>
                        <div class="battery-center">
                            <div class="battery-percent" id="batteryPercent">68%</div>
                            <div class="battery-label">电量</div>
                        </div>
                    </div>
                    <div class="battery-info">
                        <div class="battery-endurance">预估续航 <strong id="enduranceValue">1.8</strong> 小时</div>
                    </div>
                </div>
            </div>
            
            <!-- 系统状态 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">系统状态</span>
                    <div class="card-icon green">📊</div>
                </div>
                <div class="data-row">
                    <span class="data-label">CPU 温度</span>
                    <span class="data-value" id="cpuTempValue">35.0°C</span>
                </div>
                <div class="data-row">
                    <span class="data-label">GPU 负载</span>
                    <span class="data-value" id="gpuLoadValue">0%</span>
                </div>
                <div class="data-row">
                    <span class="data-label">内存使用</span>
                    <span class="data-value" id="memoryUsageValue">45%</span>
                </div>
            </div>
            
            <!-- 位置信息 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">当前位置</span>
                    <div class="card-icon blue">📍</div>
                </div>
                <div class="data-row">
                    <span class="data-label">坐标</span>
                    <span class="data-value" id="positionValue">(0.0, 0.0)</span>
                </div>
                <div class="data-row">
                    <span class="data-label">当前航点</span>
                    <span class="data-value" id="waypointValue">WP001</span>
                </div>
                <div class="data-row">
                    <span class="data-label">运行状态</span>
                    <span class="data-value" id="statusValue">空闲</span>
                </div>
            </div>
            
            <!-- 告警信息 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">实时告警</span>
                    <span class="card-badge" id="alertCount">0</span>
                </div>
                <div class="alert-list" id="alertList">
                    <div class="alert-empty">暂无告警信息</div>
                </div>
            </div>
        </section>
        
        <!-- 控制面板 -->
        <section class="control-section">
            <div class="control-header">
                <span class="control-title">运动控制</span>
                <span class="control-hint">WASD / 方向键控制</span>
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
                <button class="action-btn" onclick="sendCmd('home')">⌂ 回零</button>
                <button class="action-btn danger" onclick="sendCmd('emergency_stop')">⏻ 紧急停止</button>
            </div>
        </section>
    </main>
    
    <!-- Footer -->
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
                const circumference = 2 * Math.PI * 60;
                const offset = circumference - (battery / 100) * circumference;
                const ring = document.getElementById('batteryRing');
                ring.style.strokeDashoffset = offset;
                ring.style.stroke = battery > 60 ? 'var(--success)' : battery > 30 ? 'var(--warning)' : 'var(--danger)';
                
                // 续航
                document.getElementById('enduranceValue').textContent = (status.endurance_hours || 1.8).toFixed(1);
                
                // 系统状态
                const cpuTemp = status.cpu_temp || 35;
                const cpuTempEl = document.getElementById('cpuTempValue');
                cpuTempEl.textContent = cpuTemp.toFixed(1) + '°C';
                cpuTempEl.className = 'data-value' + (cpuTemp >= 50 ? ' danger' : cpuTemp >= 45 ? ' warning' : '');
                
                document.getElementById('gpuLoadValue').textContent = (status.gpu_load || 0) + '%';
                document.getElementById('memoryUsageValue').textContent = (status.memory_usage || 45) + '%';
                
                // 位置
                const pos = status.position || {};
                document.getElementById('positionValue').textContent = 
                    `(${pos.x.toFixed(1)}, ${pos.y.toFixed(1)})`;
                document.getElementById('waypointValue').textContent = status.waypoint || 'WP001';
                
                // 状态
                const statusEl = document.getElementById('statusValue');
                const statusMap = {
                    'idle': '空闲',
                    'moving': '移动中',
                    'inspecting': '巡检中',
                    'standing': '起立中'
                };
                statusEl.textContent = statusMap[status.status] || '未知';
                
                // 进度
                const completed = status.completed_waypoints || 0;
                const total = status.total_waypoints || 5;
                document.getElementById('progressText').textContent = `${completed} / ${total}`;
                document.getElementById('progressFill').style.width = `${(completed/total)*100}%`;
            } else if (data.type === 'alert') {
                addAlert(data.data);
            }
        }
        
        function addAlert(alert) {
            const list = document.getElementById('alertList');
            
            // 清空空状态提示
            const empty = list.querySelector('.alert-empty');
            if (empty) empty.remove();
            
            const item = document.createElement('div');
            item.className = `alert-item ${alert.level || ''}`;
            item.innerHTML = `
                <div class="alert-indicator ${alert.level || ''}">
                    ${alert.level === 'danger' ? '🔴' : '🟡'}
                </div>
                <div class="alert-content">
                    <div class="alert-message">${alert.message}</div>
                    <div class="alert-time">${new Date(alert.timestamp).toLocaleTimeString('zh-CN')}</div>
                </div>
            `;
            list.insertBefore(item, list.firstChild);
            
            // 限制显示数量
            while (list.children.length > 10) {
                list.removeChild(list.lastChild);
            }
            
            // 更新告警数量
            document.getElementById('alertCount').textContent = list.children.length;
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
        
        // 键盘控制（完整实现）
        document.addEventListener('keydown', (e) => {
            const keyMap = {
                'w': 'forward', 'W': 'forward',
                's': 'backward', 'S': 'backward',
                'a': 'left', 'A': 'left',
                'd': 'right', 'D': 'right',
                'ArrowUp': 'forward',
                'ArrowDown': 'backward',
                'ArrowLeft': 'left',
                'ArrowRight': 'right',
                ' ': 'stand_up',
                'Escape': 'emergency_stop'
            };
            
            const key = keyMap[e.key];
            if (key) {
                e.preventDefault();
                pressKey(key);
                
                // 视觉反馈
                const btn = document.querySelector(`.dpad-btn[data-key="${key}"]`);
                if (btn) {
                    btn.style.transform = 'scale(0.9)';
                    setTimeout(() => btn.style.transform = '', 150);
                }
            }
        });
        
        // 更新时间
        function updateTime() {
            document.getElementById('currentTime').textContent = 
                new Date().toLocaleTimeString('zh-CN');
        }
        
        // 定时更新状态
        setInterval(updateTime, 1000);
        setInterval(() => {
            fetch('/api/status').then(r => r.json()).then(d => {
                document.getElementById('clientCount').textContent = d.clients;
            }).catch(() => {});
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
    return HTMLResponse(GHOST_HTML)


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

        # ========== 新增：键盘控制处理 ==========
        elif msg_type == "key":
            key = data.get("key", "")
            action = data.get("action", "")
            
            key_mapping = {
                "forward": ("forward", True),
                "backward": ("backward", True),
                "left": ("left", True),
                "right": ("right", True),
                "turn_left": ("turn_left", True),
                "turn_right": ("turn_right", True),
                "stand_up": ("stand", True),
            }
            
            if key in key_mapping:
                key_name, _ = key_mapping[key]
                if action == "press":
                    key_state[key_name] = True
                    logger.info(f"按键按下: {key}")
                elif action == "release":
                    key_state[key_name] = False
                    logger.info(f"按键释放: {key}")
                
                # 发送UDP控制指令
                send_velocity_command()

        # ========== 新增：命令处理 ==========
        elif msg_type == "command":
            cmd = data.get("command", "")
            logger.info(f"收到命令: {cmd}")
            
            if cmd == "stand_up":
                send_udp(CMD_STAND_UP)
                robot_status["status"] = "standing"
            elif cmd == "emergency_stop":
                send_udp(CMD_EMERGENCY_STOP)
                robot_status["status"] = "idle"
                # 重置所有按键状态
                for k in key_state:
                    key_state[k] = False
            elif cmd == "home":
                send_udp(CMD_HOME)
                robot_status["position"] = {"x": 0.0, "y": 0.0}


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
