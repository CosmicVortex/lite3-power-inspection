#!/usr/bin/env python3
"""
绝影Lite3 监测平台 - Ghost CMS风格界面
基于Ghost Admin设计系统：左侧导航栏 + 顶部Header + 卡片布局
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

# ========== Ghost CMS风格HTML ==========
GHOST_ADMIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>绝影Lite3 · 电力巡检监控中心</title>
    <style>
        /* ========== Ghost Design System ========== */
        :root {
            /* Ghost品牌色 */
            --ghost-black: #15171A;
            --ghost-dark: #222429;
            --ghost-sidebar: #1A1C23;
            --ghost-mid: #3A3E47;
            --ghost-light: #6B727A;
            --ghost-pale: #D4D7DC;
            --ghost-palest: #F1F3F5;
            --ghost-white: #FFFFFF;
            
            /* 主题色 */
            --primary: #FF6B35;
            --primary-hover: #E55A28;
            --success: #00C853;
            --warning: #FFB300;
            --danger: #FF3D00;
            
            /* 间距 */
            --space-xs: 4px;
            --space-sm: 8px;
            --space-md: 16px;
            --space-lg: 24px;
            --space-xl: 32px;
            --space-2xl: 48px;
            
            /* 圆角 */
            --radius-sm: 4px;
            --radius-md: 8px;
            --radius-lg: 12px;
            
            /* 阴影 */
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.12);
            --shadow-md: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--ghost-palest);
            color: var(--ghost-dark);
            min-height: 100vh;
            display: flex;
        }
        
        /* ========== 左侧导航栏（Ghost风格）========== */
        .sidebar {
            width: 240px;
            background: var(--ghost-sidebar);
            min-height: 100vh;
            position: fixed;
            left: 0;
            top: 0;
            z-index: 100;
            display: flex;
            flex-direction: column;
        }
        
        .sidebar-logo {
            padding: var(--space-lg) var(--space-xl);
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }
        
        .sidebar-logo a {
            display: flex;
            align-items: center;
            gap: var(--space-md);
            text-decoration: none;
            color: var(--ghost-white);
        }
        
        .sidebar-logo-icon {
            width: 36px;
            height: 36px;
            background: var(--primary);
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }
        
        .sidebar-logo-text {
            font-size: 16px;
            font-weight: 600;
            letter-spacing: -0.3px;
        }
        
        .sidebar-nav {
            flex: 1;
            padding: var(--space-md) 0;
            overflow-y: auto;
        }
        
        .nav-section {
            margin-bottom: var(--space-lg);
        }
        
        .nav-section-title {
            padding: var(--space-sm) var(--space-xl);
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--ghost-light);
        }
        
        .nav-item {
            display: flex;
            align-items: center;
            gap: var(--space-md);
            padding: var(--space-md) var(--space-xl);
            color: rgba(255,255,255,0.7);
            text-decoration: none;
            font-size: 14px;
            transition: all 0.15s ease;
            cursor: pointer;
        }
        
        .nav-item:hover {
            background: rgba(255,255,255,0.06);
            color: var(--ghost-white);
        }
        
        .nav-item.active {
            background: rgba(255,255,255,0.1);
            color: var(--ghost-white);
            border-left: 3px solid var(--primary);
            padding-left: calc(var(--space-xl) - 3px);
        }
        
        .nav-item-icon {
            width: 20px;
            text-align: center;
            font-size: 16px;
        }
        
        .nav-item-badge {
            margin-left: auto;
            background: var(--primary);
            color: white;
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 10px;
            font-weight: 600;
        }
        
        /* ========== 主内容区 ========== */
        .main-wrapper {
            flex: 1;
            margin-left: 240px;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }
        
        /* ========== 顶部Header ========== */
        .header {
            height: 60px;
            background: var(--ghost-white);
            border-bottom: 1px solid var(--ghost-pale);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 var(--space-xl);
            position: sticky;
            top: 0;
            z-index: 50;
        }
        
        .header-left {
            display: flex;
            align-items: center;
            gap: var(--space-lg);
        }
        
        .breadcrumb {
            display: flex;
            align-items: center;
            gap: var(--space-sm);
            font-size: 14px;
            color: var(--ghost-light);
        }
        
        .breadcrumb-separator {
            color: var(--ghost-pale);
        }
        
        .breadcrumb-current {
            color: var(--ghost-dark);
            font-weight: 500;
        }
        
        .header-right {
            display: flex;
            align-items: center;
            gap: var(--space-md);
        }
        
        .header-btn {
            padding: var(--space-sm) var(--space-md);
            border: 1px solid var(--ghost-pale);
            border-radius: var(--radius-md);
            background: var(--ghost-white);
            color: var(--ghost-dark);
            font-size: 14px;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        
        .header-btn:hover {
            border-color: var(--ghost-mid);
            background: var(--ghost-palest);
        }
        
        .header-btn.primary {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }
        
        .header-btn.primary:hover {
            background: var(--primary-hover);
            border-color: var(--primary-hover);
        }
        
        .connection-status {
            display: flex;
            align-items: center;
            gap: var(--space-sm);
            padding: var(--space-sm) var(--space-md);
            background: #ECFDF5;
            border-radius: var(--radius-full);
            font-size: 13px;
            color: var(--success);
        }
        
        .status-dot {
            width: 6px;
            height: 6px;
            background: var(--success);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        
        /* ========== 内容区域 ========== */
        .content {
            flex: 1;
            padding: var(--space-xl);
            overflow-y: auto;
        }
        
        .page-header {
            margin-bottom: var(--space-xl);
        }
        
        .page-title {
            font-size: 24px;
            font-weight: 700;
            color: var(--ghost-black);
            letter-spacing: -0.5px;
            margin-bottom: var(--space-sm);
        }
        
        .page-subtitle {
            font-size: 14px;
            color: var(--ghost-light);
        }
        
        /* ========== 卡片网格 ========== */
        .cards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: var(--space-lg);
            margin-bottom: var(--space-xl);
        }
        
        .card {
            background: var(--ghost-white);
            border-radius: var(--radius-lg);
            border: 1px solid var(--ghost-pale);
            overflow: hidden;
            transition: all 0.2s ease;
        }
        
        .card:hover {
            box-shadow: var(--shadow-md);
            transform: translateY(-2px);
        }
        
        .card-header {
            padding: var(--space-lg);
            border-bottom: 1px solid var(--ghost-palest);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .card-title {
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--ghost-light);
        }
        
        .card-icon {
            width: 32px;
            height: 32px;
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
        }
        
        .card-icon.orange { background: #FFF3E0; }
        .card-icon.green { background: #E8F5E9; }
        .card-icon.blue { background: #E3F2FD; }
        .card-icon.red { background: #FFEbee; }
        
        .card-body {
            padding: var(--space-lg);
        }
        
        /* ========== 电池环形 ========== */
        .battery-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: var(--space-md);
        }
        
        .battery-ring {
            position: relative;
            width: 120px;
            height: 120px;
        }
        
        .battery-ring svg {
            transform: rotate(-90deg);
        }
        
        .battery-ring-bg {
            fill: none;
            stroke: var(--ghost-palest);
            stroke-width: 8;
        }
        
        .battery-ring-fill {
            fill: none;
            stroke: var(--success);
            stroke-width: 8;
            stroke-linecap: round;
            transition: stroke-dashoffset 0.8s ease;
        }
        
        .battery-center {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
        }
        
        .battery-percent {
            font-size: 28px;
            font-weight: 700;
            color: var(--ghost-black);
            line-height: 1;
        }
        
        .battery-label {
            font-size: 11px;
            color: var(--ghost-light);
            margin-top: var(--space-xs);
        }
        
        /* ========== 数据行 ========== */
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
            font-size: 13px;
            color: var(--ghost-light);
        }
        
        .data-value {
            font-size: 18px;
            font-weight: 600;
            color: var(--ghost-black);
        }
        
        .data-value.warning { color: var(--warning); }
        .data-value.danger { color: var(--danger); }
        
        /* ========== D-Pad控制器 ========== */
        .dpad {
            display: grid;
            grid-template-columns: repeat(3, 56px);
            grid-template-rows: repeat(3, 56px);
            gap: var(--space-sm);
            margin: var(--space-lg) auto;
            width: fit-content;
        }
        
        .dpad-btn {
            width: 56px;
            height: 56px;
            border: 1px solid var(--ghost-pale);
            border-radius: var(--radius-md);
            background: var(--ghost-white);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            color: var(--ghost-mid);
            transition: all 0.15s ease;
        }
        
        .dpad-btn:hover {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }
        
        .dpad-btn:active {
            transform: scale(0.95);
        }
        
        .dpad-btn.empty {
            background: transparent;
            border: none;
            cursor: default;
        }
        
        .action-buttons {
            display: flex;
            gap: var(--space-md);
            justify-content: center;
            margin-top: var(--space-lg);
        }
        
        .action-btn {
            padding: var(--space-sm) var(--space-lg);
            border: 1px solid var(--ghost-pale);
            border-radius: var(--radius-md);
            background: var(--ghost-white);
            color: var(--ghost-dark);
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        
        .action-btn:hover {
            border-color: var(--ghost-mid);
        }
        
        .action-btn.primary {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }
        
        .action-btn.danger {
            background: var(--danger);
            border-color: var(--danger);
            color: white;
        }
        
        /* ========== 告警列表 ========== */
        .alert-list {
            max-height: 280px;
            overflow-y: auto;
        }
        
        .alert-list::-webkit-scrollbar {
            width: 4px;
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
            transition: all 0.15s ease;
        }
        
        .alert-item:hover {
            background: var(--ghost-pale);
        }
        
        .alert-item.warning { background: #FFF8E1; }
        .alert-item.danger { background: #FFEBEE; }
        
        .alert-icon {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            flex-shrink: 0;
        }
        
        .alert-icon.warning { background: var(--warning); color: white; }
        .alert-icon.danger { background: var(--danger); color: white; }
        
        .alert-content {
            flex: 1;
        }
        
        .alert-message {
            font-size: 13px;
            color: var(--ghost-dark);
            font-weight: 500;
        }
        
        .alert-time {
            font-size: 11px;
            color: var(--ghost-light);
            margin-top: 2px;
        }
        
        /* ========== 进度条 ========== */
        .progress-bar {
            height: 4px;
            background: var(--ghost-palest);
            border-radius: 2px;
            overflow: hidden;
            margin-top: var(--space-md);
        }
        
        .progress-fill {
            height: 100%;
            background: var(--primary);
            border-radius: 2px;
            transition: width 0.5s ease;
        }
        
        /* ========== 空状态 ========== */
        .empty-state {
            text-align: center;
            padding: var(--space-2xl);
            color: var(--ghost-light);
            font-size: 13px;
        }
        
        /* ========== 响应式 ========== */
        @media (max-width: 1024px) {
            .sidebar {
                width: 60px;
            }
            
            .sidebar-logo-text,
            .nav-item-text,
            .nav-section-title,
            .nav-item-badge {
                display: none;
            }
            
            .nav-item {
                justify-content: center;
                padding: var(--space-md);
            }
            
            .nav-item.active {
                padding-left: var(--space-md);
                border-left-width: 3px;
            }
            
            .main-wrapper {
                margin-left: 60px;
            }
        }
        
        @media (max-width: 768px) {
            .sidebar {
                display: none;
            }
            
            .main-wrapper {
                margin-left: 0;
            }
            
            .cards-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <!-- 左侧导航栏 -->
    <aside class="sidebar">
        <div class="sidebar-logo">
            <a href="/">
                <div class="sidebar-logo-icon">🤖</div>
                <span class="sidebar-logo-text">绝影Lite3</span>
            </a>
        </div>
        
        <nav class="sidebar-nav">
            <div class="nav-section">
                <div class="nav-section-title">监控中心</div>
                <a class="nav-item active" href="#">
                    <span class="nav-item-icon">📊</span>
                    <span class="nav-item-text">实时监控</span>
                </a>
                <a class="nav-item" href="#">
                    <span class="nav-item-icon">🌡️</span>
                    <span class="nav-item-text">温度监测</span>
                </a>
                <a class="nav-item" href="#">
                    <span class="nav-item-icon">🔍</span>
                    <span class="nav-item-text">裂缝检测</span>
                </a>
            </div>
            
            <div class="nav-section">
                <div class="nav-section-title">控制</div>
                <a class="nav-item" href="#">
                    <span class="nav-item-icon">🎮</span>
                    <span class="nav-item-text">设备控制</span>
                </a>
                <a class="nav-item" href="#">
                    <span class="nav-item-icon">📹</span>
                    <span class="nav-item-text">视频流</span>
                </a>
            </div>
            
            <div class="nav-section">
                <div class="nav-section-title">历史</div>
                <a class="nav-item" href="#">
                    <span class="nav-item-icon">📈</span>
                    <span class="nav-item-text">巡检记录</span>
                </a>
                <a class="nav-item" href="#">
                    <span class="nav-item-icon">⚠️</span>
                    <span class="nav-item-text">告警历史</span>
                    <span class="nav-item-badge" id="alertBadge">0</span>
                </a>
            </div>
        </nav>
    </aside>
    
    <!-- 主内容区 -->
    <div class="main-wrapper">
        <!-- 顶部Header -->
        <header class="header">
            <div class="header-left">
                <div class="breadcrumb">
                    <span>监控中心</span>
                    <span class="breadcrumb-separator">/</span>
                    <span class="breadcrumb-current">实时监控</span>
                </div>
            </div>
            
            <div class="header-right">
                <div class="connection-status">
                    <span class="status-dot"></span>
                    <span id="connectionStatus">已连接</span>
                </div>
                <span style="font-size: 13px; color: var(--ghost-light);" id="currentTime"></span>
                <button class="header-btn" onclick="fetchDemo()">演示模式</button>
                <button class="header-btn primary" onclick="sendCmd('stand_up')">起立/趴下</button>
            </div>
        </header>
        
        <!-- 内容区域 -->
        <main class="content">
            <div class="page-header">
                <h1 class="page-title">实时监控</h1>
                <p class="page-subtitle">绝影Lite3专业版 · 智能电力巡检系统</p>
            </div>
            
            <!-- 巡检进度 -->
            <div style="background: var(--ghost-white); border-radius: var(--radius-lg); border: 1px solid var(--ghost-pale); padding: var(--space-lg); margin-bottom: var(--space-xl);">
                <div style="display: flex; justify-content: space-between; margin-bottom: var(--space-sm);">
                    <span style="font-size: 13px; color: var(--ghost-light);">巡检进度</span>
                    <span style="font-size: 13px; color: var(--ghost-dark); font-weight: 500;" id="progressText">0 / 5</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill" style="width: 0%;"></div>
                </div>
            </div>
            
            <!-- 数据卡片 -->
            <div class="cards-grid">
                <!-- 电池状态 -->
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">电池状态</span>
                        <div class="card-icon orange">🔋</div>
                    </div>
                    <div class="card-body">
                        <div class="battery-container">
                            <div class="battery-ring">
                                <svg width="120" height="120" viewBox="0 0 120 120">
                                    <circle class="battery-ring-bg" cx="60" cy="60" r="52"/>
                                    <circle class="battery-ring-fill" id="batteryRing" cx="60" cy="60" r="52"
                                            stroke-dasharray="326.7" stroke-dashoffset="100"/>
                                </svg>
                                <div class="battery-center">
                                    <div class="battery-percent" id="batteryPercent">68%</div>
                                    <div class="battery-label">电量</div>
                                </div>
                            </div>
                            <div style="text-align: center;">
                                <span style="font-size: 13px; color: var(--ghost-light);">预估续航</span>
                                <strong style="font-size: 18px; color: var(--ghost-black); margin-left: var(--space-sm);" id="enduranceValue">1.8</strong>
                                <span style="font-size: 13px; color: var(--ghost-light);">小时</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- 系统状态 -->
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">系统状态</span>
                        <div class="card-icon green">📊</div>
                    </div>
                    <div class="card-body" style="padding: 0;">
                        <div class="data-row" style="padding: var(--space-md) var(--space-lg);">
                            <span class="data-label">CPU 温度</span>
                            <span class="data-value" id="cpuTempValue">35.0°C</span>
                        </div>
                        <div class="data-row" style="padding: var(--space-md) var(--space-lg);">
                            <span class="data-label">GPU 负载</span>
                            <span class="data-value" id="gpuLoadValue">0%</span>
                        </div>
                        <div class="data-row" style="padding: var(--space-md) var(--space-lg);">
                            <span class="data-label">内存使用</span>
                            <span class="data-value" id="memoryUsageValue">45%</span>
                        </div>
                    </div>
                </div>
                
                <!-- 位置信息 -->
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">当前位置</span>
                        <div class="card-icon blue">📍</div>
                    </div>
                    <div class="card-body" style="padding: 0;">
                        <div class="data-row" style="padding: var(--space-md) var(--space-lg);">
                            <span class="data-label">坐标</span>
                            <span class="data-value" id="positionValue">(0.0, 0.0)</span>
                        </div>
                        <div class="data-row" style="padding: var(--space-md) var(--space-lg);">
                            <span class="data-label">当前航点</span>
                            <span class="data-value" id="waypointValue">WP001</span>
                        </div>
                        <div class="data-row" style="padding: var(--space-md) var(--space-lg);">
                            <span class="data-label">运行状态</span>
                            <span class="data-value" id="statusValue">空闲</span>
                        </div>
                    </div>
                </div>
                
                <!-- 告警信息 -->
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">实时告警</span>
                        <span style="font-size: 12px; color: var(--ghost-light);" id="alertCount">0</span>
                    </div>
                    <div class="card-body" style="padding: var(--space-md);">
                        <div class="alert-list" id="alertList">
                            <div class="empty-state">暂无告警信息</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 控制面板 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">运动控制</span>
                    <span style="font-size: 12px; color: var(--ghost-light);">WASD / 方向键控制</span>
                </div>
                <div class="card-body">
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
                </div>
            </div>
        </main>
    </div>
    
    <script>
        // WebSocket连接
        let ws = null;
        let reconnectTimer = null;
        
        function connect() {
            const wsUrl = `ws://${window.location.host}/ws`;
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
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
            
            ws.onerror = () => {};
            
            ws.onclose = () => {
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
                document.getElementById('positionValue').textContent = `(${pos.x.toFixed(1)}, ${pos.y.toFixed(1)})`;
                document.getElementById('waypointValue').textContent = status.waypoint || 'WP001';
                
                const statusMap = { 'idle': '空闲', 'moving': '移动中', 'inspecting': '巡检中', 'standing': '起立中' };
                document.getElementById('statusValue').textContent = statusMap[status.status] || '未知';
                
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
            const empty = list.querySelector('.empty-state');
            if (empty) empty.remove();
            
            const item = document.createElement('div');
            item.className = `alert-item ${alert.level || ''}`;
            item.innerHTML = `
                <div class="alert-icon ${alert.level || ''}">${alert.level === 'danger' ? '🔴' : '🟡'}</div>
                <div class="alert-content">
                    <div class="alert-message">${alert.message}</div>
                    <div class="alert-time">${new Date(alert.timestamp).toLocaleTimeString('zh-CN')}</div>
                </div>
            `;
            list.insertBefore(item, list.firstChild);
            
            while (list.children.length > 10) list.removeChild(list.lastChild);
            document.getElementById('alertCount').textContent = list.children.length;
            document.getElementById('alertBadge').textContent = list.children.length;
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
        
        function fetchDemo() {
            fetch('/api/demo', { method: 'POST' });
        }
        
        // 键盘控制
        document.addEventListener('keydown', (e) => {
            const keyMap = {
                'w': 'forward', 's': 'backward', 'a': 'left', 'd': 'right',
                'ArrowUp': 'forward', 'ArrowDown': 'backward',
                'ArrowLeft': 'left', 'ArrowRight': 'right',
                ' ': 'stand_up', 'Escape': 'emergency_stop'
            };
            const key = keyMap[e.key];
            if (key) {
                e.preventDefault();
                pressKey(key);
                const btn = document.querySelector(`.dpad-btn[data-key="${key}"]`);
                if (btn) {
                    btn.style.transform = 'scale(0.9)';
                    setTimeout(() => btn.style.transform = '', 150);
                }
            }
        });
        
        // 更新时间
        setInterval(() => {
            document.getElementById('currentTime').textContent = 
                new Date().toLocaleTimeString('zh-CN');
        }, 1000);
        
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

        elif msg_type == "key":
            key = data.get("key", "")
            action = data.get("action", "")
            
            key_mapping = {
                "forward": True, "backward": True, "left": True, "right": True,
                "turn_left": True, "turn_right": True, "stand": True
            }
            
            if key in key_mapping:
                key_state[key] = action == "press"
                logger.info(f"按键: {key} = {key_state[key]}")


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


@app.get("/")
async def root():
    return HTMLResponse(GHOST_ADMIN_HTML)


@app.get("/api/status")
async def status():
    return {"clients": len(connections), "inspections": len(inspections),
            "alerts": len([a for a in alerts if not a.get("ack")])}


@app.get("/api/robot")
async def get_robot():
    return robot_status


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
    for ws_conn in connections:
        await ws_conn.send_json({"type": "inspection", "data": inspections[-1]})
        await ws_conn.send_json({"type": "robot_status", "data": robot_status})
    return {"status": "ok"}


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
