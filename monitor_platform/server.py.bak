#!/usr/bin/env python3
"""
绝影Lite3 监测平台 - Ghost CMS Admin风格界面 V3
功能：登录 + 左侧导航 + 视频流(可见光/热成像) + 云台控制 + 温度监测 + WebSocket通信
"""

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

WS_PORT, HTTP_PORT = 8765, 8000
MOTION_HOST, MOTION_PORT = "192.168.1.103", 43893
PTZ_BASE_URL = "http://192.168.1.108"
PTZ_USER, PTZ_PASS = "admin", "123456"

# RTSP流地址
RTSP_URLS = {
    "visible_main": "rtsp://admin:123456@192.168.1.108:554/id=1&type=0",
    "visible_sub": "rtsp://admin:123456@192.168.1.108:554/id=1&type=1",
    "thermal": "rtsp://admin:123456@192.168.1.108:554/id=2&type=0"
}

# 全局状态
connections: List[WebSocket] = []
inspections: List[Dict] = []
alerts: List[Dict] = []
robot_status = {
    "battery": 68, "cpu_temp": 35.0, "gpu_load": 0, "memory_usage": 45,
    "status": "idle", "position": {"x": 0.0, "y": 0.0},
    "waypoint": "WP001", "total_waypoints": 5, "completed_waypoints": 0,
    "endurance_hours": 1.8, 
    "ptz": {"yaw": 0.0, "pitch": -30.0, "zoom": 1, "connected": False},
    "temperature": {"current": 35.0, "max": 35.0, "warn": False, "critical": False}
}
motion_sock = None
key_state = {"forward": False, "backward": False, "left": False, "right": False,
             "turn_left": False, "turn_right": False, "stand": False}

# 视频流
video_captures = {}
video_cache = {"visible_main": None, "visible_sub": None, "thermal": None}
video_frame_times = {"visible_main": 0, "visible_sub": 0, "thermal": 0}

# 云台会话
ptz_session = None
ptz_auth = None

# 温度监测
temperature_data = {"current": 35.0, "max": 35.0, "history": []}

# ========== 官方协议指令码 ==========
CMD_FORWARD = 0x21010130
CMD_LEFT = 0x21010131
CMD_TURN = 0x21010135
CMD_STAND_UP = 0x21010202
CMD_EMERGENCY_STOP = 0x21020C0E
CMD_HOME = 0x21010C05
CMD_MOVE_MODE = 0x21010D06
CMD_STAND_MODE = 0x21010D05

# ========== Ghost CMS Admin HTML ==========
GHOST_ADMIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>绝影Lite3 · 电力巡检监控中心</title>
    <style>
        :root {
            --ghost-black: #15171A;
            --ghost-dark: #222429;
            --ghost-sidebar: #1A1C23;
            --ghost-mid: #3A3E47;
            --ghost-light: #6B727A;
            --ghost-pale: #D4D7DC;
            --ghost-palest: #F1F3F5;
            --ghost-white: #FFFFFF;
            --primary: #FF6B35;
            --primary-hover: #E55A28;
            --success: #00C853;
            --warning: #FFB300;
            --danger: #FF3D00;
            --space-xs: 4px;
            --space-sm: 8px;
            --space-md: 16px;
            --space-lg: 24px;
            --space-xl: 32px;
            --space-2xl: 48px;
            --radius-sm: 4px;
            --radius-md: 8px;
            --radius-lg: 12px;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.12);
            --shadow-md: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--ghost-palest);
            color: var(--ghost-dark);
            min-height: 100vh;
        }
        
        /* 登录界面 */
        .login-page {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, var(--ghost-black) 0%, var(--ghost-dark) 100%);
        }
        
        .login-container {
            width: 100%;
            max-width: 400px;
            padding: var(--space-xl);
        }
        
        .login-logo {
            text-align: center;
            margin-bottom: var(--space-2xl);
        }
        
        .login-logo-icon {
            width: 64px;
            height: 64px;
            background: var(--primary);
            border-radius: var(--radius-lg);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 32px;
            margin-bottom: var(--space-lg);
        }
        
        .login-logo h1 {
            font-size: 24px;
            font-weight: 700;
            color: var(--ghost-white);
            margin-bottom: var(--space-sm);
        }
        
        .login-logo p {
            font-size: 14px;
            color: var(--ghost-light);
        }
        
        .login-card {
            background: var(--ghost-white);
            border-radius: var(--radius-lg);
            padding: var(--space-2xl);
            box-shadow: var(--shadow-md);
        }
        
        .login-title {
            font-size: 20px;
            font-weight: 600;
            color: var(--ghost-black);
            margin-bottom: var(--space-lg);
        }
        
        .form-group { margin-bottom: var(--space-lg); }
        
        .form-label {
            display: block;
            font-size: 13px;
            font-weight: 500;
            color: var(--ghost-mid);
            margin-bottom: var(--space-sm);
        }
        
        .form-input {
            width: 100%;
            padding: var(--space-md);
            border: 1px solid var(--ghost-pale);
            border-radius: var(--radius-md);
            font-size: 15px;
            transition: all 0.15s ease;
            outline: none;
        }
        
        .form-input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(255, 107, 53, 0.1);
        }
        
        .btn-login {
            width: 100%;
            padding: var(--space-md);
            background: var(--primary);
            border: none;
            border-radius: var(--radius-md);
            color: white;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        
        .btn-login:hover { background: var(--primary-hover); }
        
        .login-footer {
            text-align: center;
            margin-top: var(--space-xl);
            font-size: 13px;
            color: var(--ghost-light);
        }
        
        /* 主界面 */
        .app-container { display: none; min-height: 100vh; }
        .app-container.visible { display: flex; }
        
        /* 左侧导航栏 */
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
        }
        
        .sidebar-nav { flex: 1; padding: var(--space-md) 0; overflow-y: auto; }
        
        .nav-section { margin-bottom: var(--space-lg); }
        
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
        
        .nav-item-icon { width: 20px; text-align: center; }
        
        .nav-item-badge {
            margin-left: auto;
            background: var(--primary);
            color: white;
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 10px;
            font-weight: 600;
        }
        
        .sidebar-footer {
            padding: var(--space-md) var(--space-xl);
            border-top: 1px solid rgba(255,255,255,0.08);
        }
        
        .user-info {
            display: flex;
            align-items: center;
            gap: var(--space-md);
        }
        
        .user-avatar {
            width: 32px;
            height: 32px;
            background: var(--primary);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 14px;
            font-weight: 600;
        }
        
        .user-name { flex: 1; font-size: 13px; color: var(--ghost-white); }
        
        .btn-logout {
            background: none;
            border: none;
            color: var(--ghost-light);
            cursor: pointer;
            font-size: 13px;
            padding: var(--space-sm);
        }
        
        .btn-logout:hover { color: var(--ghost-white); }
        
        /* 主内容区 */
        .main-wrapper {
            flex: 1;
            margin-left: 240px;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }
        
        /* 顶部Header */
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
        
        .breadcrumb-separator { color: var(--ghost-pale); }
        .breadcrumb-current { color: var(--ghost-dark); font-weight: 500; }
        
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
        
        /* 内容区域 */
        .content {
            flex: 1;
            padding: var(--space-xl);
            overflow-y: auto;
        }
        
        .page-header { margin-bottom: var(--space-xl); }
        
        .page-title {
            font-size: 24px;
            font-weight: 700;
            color: var(--ghost-black);
            margin-bottom: var(--space-sm);
        }
        
        .page-subtitle {
            font-size: 14px;
            color: var(--ghost-light);
        }
        
        /* 视频流区域 */
        .video-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: var(--space-lg);
            margin-bottom: var(--space-xl);
        }
        
        .video-card {
            background: var(--ghost-white);
            border-radius: var(--radius-lg);
            border: 1px solid var(--ghost-pale);
            overflow: hidden;
        }
        
        .video-header {
            padding: var(--space-md) var(--space-lg);
            border-bottom: 1px solid var(--ghost-palest);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .video-title {
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--ghost-light);
        }
        
        .video-status {
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 10px;
            background: #ECFDF5;
            color: var(--success);
        }
        
        .video-status.offline { background: #FEF2F2; color: var(--danger); }
        
        .video-feed {
            width: 100%;
            height: 240px;
            background: var(--ghost-dark);
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }
        
        .video-feed img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .video-overlay {
            position: absolute;
            bottom: var(--space-md);
            left: var(--space-md);
            display: flex;
            gap: var(--space-sm);
        }
        
        .video-tag {
            padding: 2px 8px;
            background: rgba(0,0,0,0.6);
            color: white;
            font-size: 11px;
            border-radius: 4px;
        }
        
        /* 数据卡片 */
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
        
        .card-body { padding: var(--space-lg); }
        
        .data-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: var(--space-md) 0;
            border-bottom: 1px solid var(--ghost-palest);
        }
        
        .data-row:last-child { border-bottom: none; }
        
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
        
        /* 温度仪表 */
        .temp-gauge {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: var(--space-md);
        }
        
        .temp-display {
            font-size: 48px;
            font-weight: 700;
            color: var(--ghost-black);
            line-height: 1;
        }
        
        .temp-display.warning { color: var(--warning); }
        .temp-display.danger { color: var(--danger); }
        
        .temp-status {
            font-size: 13px;
            color: var(--ghost-light);
        }
        
        .temp-status.warn { color: var(--warning); }
        .temp-status.critical { color: var(--danger); }
        
        /* D-Pad控制器 */
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
        
        .dpad-btn:active { transform: scale(0.95); }
        .dpad-btn.empty { background: transparent; border: none; cursor: default; }
        
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
        
        .action-btn:hover { border-color: var(--ghost-mid); }
        
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
        
        /* 告警列表 */
        .alert-list {
            max-height: 280px;
            overflow-y: auto;
        }
        
        .alert-list::-webkit-scrollbar { width: 4px; }
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
        
        .alert-item:hover { background: var(--ghost-pale); }
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
        
        .alert-content { flex: 1; }
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
        
        /* 进度条 */
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
        
        /* 空状态 */
        .empty-state {
            text-align: center;
            padding: var(--space-2xl);
            color: var(--ghost-light);
            font-size: 13px;
        }
        
        /* 响应式 */
        @media (max-width: 1024px) {
            .sidebar { width: 60px; }
            .sidebar-logo-text, .nav-item-text, .nav-section-title, .nav-item-badge { display: none; }
            .nav-item { justify-content: center; padding: var(--space-md); }
            .main-wrapper { margin-left: 60px; }
            .video-grid { grid-template-columns: 1fr; }
        }
        
        @media (max-width: 768px) {
            .sidebar { display: none; }
            .main-wrapper { margin-left: 0; }
            .cards-grid { grid-template-columns: 1fr; }
            .video-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <!-- 登录界面 -->
    <div class="login-page" id="loginPage">
        <div class="login-container">
            <div class="login-logo">
                <div class="login-logo-icon">🤖</div>
                <h1>绝影Lite3</h1>
                <p>电力巡检监控中心</p>
            </div>
            
            <div class="login-card">
                <h2 class="login-title">登录系统</h2>
                <form onsubmit="handleLogin(event)">
                    <div class="form-group">
                        <label class="form-label">用户名</label>
                        <input type="text" class="form-input" id="username" placeholder="请输入用户名" value="admin">
                    </div>
                    <div class="form-group">
                        <label class="form-label">密码</label>
                        <input type="password" class="form-input" id="password" placeholder="请输入密码" value="admin">
                    </div>
                    <button type="submit" class="btn-login">登录</button>
                </form>
            </div>
            
            <div class="login-footer">
                <p>绝影Lite3 电力巡检系统 V1.9 · 广西电力职业技术学院</p>
            </div>
        </div>
    </div>
    
    <!-- 主应用界面 -->
    <div class="app-container" id="appContainer">
        <!-- 左侧导航栏 -->
        <aside class="sidebar">
            <div class="sidebar-logo">
                <a href="#">
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
                    <a class="nav-item" href="#">
                        <span class="nav-item-icon">🎯</span>
                        <span class="nav-item-text">云台控制</span>
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
            
            <div class="sidebar-footer">
                <div class="user-info">
                    <div class="user-avatar">A</div>
                    <span class="user-name">Admin</span>
                    <button class="btn-logout" onclick="handleLogout()">退出</button>
                </div>
            </div>
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
                
                <!-- 视频流区域 -->
                <div class="video-grid">
                    <div class="video-card">
                        <div class="video-header">
                            <span class="video-title">可见光（主）</span>
                            <span class="video-status" id="visibleMainStatus">● 在线</span>
                        </div>
                        <div class="video-feed">
                            <img id="visibleMainImg" src="/api/video/visible_main" alt="可见光主画面">
                            <div class="video-overlay">
                                <span class="video-tag">CAM-01</span>
                                <span class="video-tag" id="visibleMainFps">30 FPS</span>
                                <span class="video-tag" id="visibleMainConn" style="background: var(--success);">连接正常</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="video-card">
                        <div class="video-header">
                            <span class="video-title">热成像</span>
                            <span class="video-status" id="thermalStatus">● 在线</span>
                        </div>
                        <div class="video-feed">
                            <img id="thermalImg" src="/api/video/thermal" alt="热成像画面">
                            <div class="video-overlay">
                                <span class="video-tag">THERMAL</span>
                                <span class="video-tag" id="thermalTemp">35.0°C</span>
                                <span class="video-tag" id="thermalConn" style="background: var(--success);">连接正常</span>
                            </div>
                        </div>
                    </div>
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
                    
                    <!-- 温度监测 -->
                    <div class="card">
                        <div class="card-header">
                            <span class="card-title">温度监测</span>
                            <div class="card-icon green">🌡️</div>
                        </div>
                        <div class="card-body">
                            <div class="temp-gauge">
                                <div class="temp-display" id="tempDisplay">35.0°C</div>
                                <div class="temp-status" id="tempStatus">正常</div>
                                <div style="margin-top: var(--space-md);">
                                    <div class="data-row">
                                        <span class="data-label">最高温度</span>
                                        <span class="data-value" id="maxTempValue">35.0°C</span>
                                    </div>
                                    <div class="data-row">
                                        <span class="data-label">预警阈值</span>
                                        <span class="data-value">45.0°C</span>
                                    </div>
                                    <div class="data-row">
                                        <span class="data-label">告警阈值</span>
                                        <span class="data-value">50.0°C</span>
                                    </div>
                                </div>
                            </div>
                            <!-- 阈值设置 -->
                            <div style="margin-top: var(--space-lg); padding-top: var(--space-lg); border-top: 1px solid var(--ghost-palest);">
                                <div style="font-size: 12px; color: var(--ghost-light); margin-bottom: var(--space-md);">阈值设置（可编辑）</div>
                                <div style="display: flex; gap: var(--space-md);">
                                    <div style="flex: 1;">
                                        <label style="font-size: 11px; color: var(--ghost-light);">预警阈值</label>
                                        <input type="number" id="warnThreshold" value="45" min="30" max="60"
                                               style="width: 100%; padding: var(--space-sm); border: 1px solid var(--ghost-pale); border-radius: var(--radius-sm); font-size: 13px; margin-top: 2px;">
                                    </div>
                                    <div style="flex: 1;">
                                        <label style="font-size: 11px; color: var(--ghost-light);">告警阈值</label>
                                        <input type="number" id="criticalThreshold" value="50" min="40" max="70"
                                               style="width: 100%; padding: var(--space-sm); border: 1px solid var(--ghost-pale); border-radius: var(--radius-sm); font-size: 13px; margin-top: 2px;">
                                    </div>
                                    <div style="display: flex; align-items: flex-end;">
                                        <button class="action-btn" onclick="saveThresholds()" style="padding: var(--space-sm) var(--space-md);">保存</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 系统状态 -->
                    <div class="card">
                        <div class="card-header">
                            <span class="card-title">系统状态</span>
                            <div class="card-icon blue">📊</div>
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
                    
                    <!-- 云台状态 -->
                    <div class="card">
                        <div class="card-header">
                            <span class="card-title">云台状态</span>
                            <div class="card-icon green">🎯</div>
                        </div>
                        <div class="card-body" style="padding: 0;">
                            <div class="data-row" style="padding: var(--space-md) var(--space-lg);">
                                <span class="data-label">偏航角</span>
                                <span class="data-value" id="ptzYawValue">0.0°</span>
                            </div>
                            <div class="data-row" style="padding: var(--space-md) var(--space-lg);">
                                <span class="data-label">俯仰角</span>
                                <span class="data-value" id="ptzPitchValue">-30.0°</span>
                            </div>
                            <div class="data-row" style="padding: var(--space-md) var(--space-lg);">
                                <span class="data-label">变倍</span>
                                <span class="data-value" id="ptzZoomValue">1x</span>
                            </div>
                            <div class="data-row" style="padding: var(--space-md) var(--space-lg);">
                                <span class="data-label">连接状态</span>
                                <span class="data-value" id="ptzStatusValue" style="color: var(--success);">已连接</span>
                            </div>
                        </div>
                        <!-- 云台控制面板 -->
                        <div style="padding: var(--space-lg); border-top: 1px solid var(--ghost-palest);">
                            <div style="font-size: 12px; color: var(--ghost-light); margin-bottom: var(--space-md);">云台控制</div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-sm);">
                                    <span style="font-size: 11px; color: var(--ghost-light);">偏航角</span>
                                    <input type="range" id="ptzYawSlider" min="-280" max="280" value="0"
                                           style="width: 120px;" oninput="updatePTZ('yaw', this.value)">
                                    <span id="ptzYawSliderVal" style="font-size: 11px; color: var(--ghost-mid);">0°</span>
                                </div>
                                <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-sm);">
                                    <span style="font-size: 11px; color: var(--ghost-light);">俯仰角</span>
                                    <input type="range" id="ptzPitchSlider" min="-115" max="40" value="-30"
                                           style="width: 120px;" oninput="updatePTZ('pitch', this.value)">
                                    <span id="ptzPitchSliderVal" style="font-size: 11px; color: var(--ghost-mid);">-30°</span>
                                </div>
                                <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-sm);">
                                    <span style="font-size: 11px; color: var(--ghost-light);">变倍</span>
                                    <input type="range" id="ptzZoomSlider" min="1" max="20" value="1"
                                           style="width: 120px;" oninput="updatePTZ('zoom', this.value)">
                                    <span id="ptzZoomSliderVal" style="font-size: 11px; color: var(--ghost-mid);">1x</span>
                                </div>
                            </div>
                            <div style="display: flex; gap: var(--space-sm); margin-top: var(--space-md); justify-content: center;">
                                <button class="action-btn" onclick="ptzHome()">⌂ 回零</button>
                                <button class="action-btn" onclick="ptzConnect()">🔗 重连</button>
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
    </div>
    
    <script>
        // WebSocket连接
        let ws = null;
        let reconnectTimer = null;
        
        // 登录处理
        function handleLogin(e) {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            if (username && password) {
                document.getElementById('loginPage').style.display = 'none';
                document.getElementById('appContainer').classList.add('visible');
                connect();
                startVideoRefresh();
            }
        }
        
        function handleLogout() {
            if (ws) ws.close();
            document.getElementById('loginPage').style.display = 'flex';
            document.getElementById('appContainer').classList.remove('visible');
        }
        
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
                
                // 云台状态
                if (status.ptz) {
                    document.getElementById('ptzYawValue').textContent = (status.ptz.yaw || 0).toFixed(1) + '°';
                    document.getElementById('ptzPitchValue').textContent = (status.ptz.pitch || -30).toFixed(1) + '°';
                    document.getElementById('ptzZoomValue').textContent = (status.ptz.zoom || 1) + 'x';
                    const ptzConnected = status.ptz.connected;
                    const ptzStatusEl = document.getElementById('ptzStatusValue');
                    ptzStatusEl.textContent = ptzConnected ? '已连接' : '未连接';
                    ptzStatusEl.style.color = ptzConnected ? 'var(--success)' : 'var(--danger)';
                }
                
                // 温度状态
                if (status.temperature) {
                    const temp = status.temperature.current || 35;
                    const tempEl = document.getElementById('tempDisplay');
                    tempEl.textContent = temp.toFixed(1) + '°C';
                    tempEl.className = 'temp-display' + (temp >= 50 ? ' danger' : temp >= 45 ? ' warning' : '');
                    
                    const tempStatusEl = document.getElementById('tempStatus');
                    if (temp >= 50) {
                        tempStatusEl.textContent = '严重告警';
                        tempStatusEl.className = 'temp-status critical';
                    } else if (temp >= 45) {
                        tempStatusEl.textContent = '预警';
                        tempStatusEl.className = 'temp-status warn';
                    } else {
                        tempStatusEl.textContent = '正常';
                        tempStatusEl.className = 'temp-status';
                    }
                    
                    document.getElementById('maxTempValue').textContent = (status.temperature.max || 35).toFixed(1) + '°C';
                    document.getElementById('thermalTemp').textContent = temp.toFixed(1) + '°C';
                }
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
                <button onclick="clearAlert(this)" style="background:none;border:none;cursor:pointer;font-size:16px;color:var(--ghost-light);padding:2px 6px;">✕</button>
            `;
            list.insertBefore(item, list.firstChild);
            
            while (list.children.length > 10) list.removeChild(list.lastChild);
            document.getElementById('alertCount').textContent = list.children.length;
            document.getElementById('alertBadge').textContent = list.children.length;
        }
        
        function clearAlert(btn) {
            const item = btn.parentElement;
            item.remove();
            const list = document.getElementById('alertList');
            if (list.children.length === 0) {
                list.innerHTML = '<div class="empty-state">暂无告警信息</div>';
            }
            document.getElementById('alertCount').textContent = list.children.length;
            document.getElementById('alertBadge').textContent = list.children.length;
        }
        
        // 云台控制函数
        function updatePTZ(param, value) {
            // 更新显示值
            const val = parseFloat(value);
            if (param === 'yaw') {
                document.getElementById('ptzYawSliderVal').textContent = val.toFixed(0) + '°';
            } else if (param === 'pitch') {
                document.getElementById('ptzPitchSliderVal').textContent = val.toFixed(0) + '°';
            } else if (param === 'zoom') {
                document.getElementById('ptzZoomSliderVal').textContent = val.toFixed(0) + 'x';
            }
            
            // 发送控制指令
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'ptz_control',
                    parameter: param,
                    value: val
                }));
            }
        }
        
        function ptzHome() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'command', command: 'home' }));
            }
        }
        
        function ptzConnect() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ptz_connect' }));
            }
        }
        
        // 温度阈值设置
        function saveThresholds() {
            const warnThreshold = parseFloat(document.getElementById('warnThreshold').value);
            const criticalThreshold = parseFloat(document.getElementById('criticalThreshold').value);
            
            // 验证阈值
            if (warnThreshold >= criticalThreshold) {
                alert('预警阈值必须小于告警阈值');
                return;
            }
            
            // 发送阈值设置
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'temperature_threshold',
                    warn: warnThreshold,
                    critical: criticalThreshold
                }));
            }
            
            // 更新显示
            document.querySelectorAll('#tempDisplay + .data-row .data-value').forEach((el, i) => {
                if (i === 1) el.textContent = warnThreshold + '.0°C';
                if (i === 2) el.textContent = criticalThreshold + '.0°C';
            });
            
            alert('阈值已保存');
        }
        
        // 视频连接状态检测
        function updateVideoStatus(streamName, connected) {
            const statusEl = document.getElementById(streamName + 'Status');
            const connEl = document.getElementById(streamName + 'Conn');
            
            if (connected) {
                statusEl.textContent = '● 在线';
                statusEl.className = 'video-status';
                if (connEl) {
                    connEl.textContent = '连接正常';
                    connEl.style.background = 'var(--success)';
                }
            } else {
                statusEl.textContent = '● 离线';
                statusEl.className = 'video-status offline';
                if (connEl) {
                    connEl.textContent = '连接失败';
                    connEl.style.background = 'var(--danger)';
                }
            }
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
        
        // 视频刷新
        let videoRefreshInterval = null;
        
        function startVideoRefresh() {
            // 每秒刷新一次视频截图
            videoRefreshInterval = setInterval(() => {
                const timestamp = Date.now();
                document.getElementById('visibleMainImg').src = `/api/video/visible_main?t=${timestamp}`;
                document.getElementById('thermalImg').src = `/api/video/thermal?t=${timestamp}`;
            }, 1000);
            
            // 检测视频连接状态（每5秒）
            setInterval(async () => {
                try {
                    const resp1 = await fetch('/api/video/visible_main?t=' + Date.now());
                    updateVideoStatus('visibleMain', resp1.ok);
                } catch (e) {
                    updateVideoStatus('visibleMain', false);
                }
                
                try {
                    const resp2 = await fetch('/api/video/thermal?t=' + Date.now());
                    updateVideoStatus('thermal', resp2.ok);
                } catch (e) {
                    updateVideoStatus('thermal', false);
                }
            }, 5000);
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


@app.get("/api/video/{stream_name}")
async def get_video_frame_endpoint(stream_name: str):
    """获取单帧视频"""
    if stream_name not in RTSP_URLS:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    # 从缓存获取或启动流
    if stream_name not in video_captures:
        try:
            cap = cv2.VideoCapture(RTSP_URLS[stream_name])
            if cap.isOpened():
                video_captures[stream_name] = cap
                logger.info(f"视频流启动: {stream_name}")
            else:
                raise HTTPException(status_code=503, detail="无法打开视频流")
        except Exception as e:
            logger.error(f"视频流启动失败 {stream_name}: {e}")
            raise HTTPException(status_code=503, detail=str(e))
    
    cap = video_captures[stream_name]
    ret, frame = cap.read()
    
    if not ret or frame is None:
        raise HTTPException(status_code=503, detail="无法读取视频帧")
    
    success, encoded_img = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        raise HTTPException(status_code=500, detail="编码失败")
    
    return StreamingResponse(io.BytesIO(encoded_img.tobytes()), media_type="image/jpeg")


@app.post("/api/ptz/login")
async def ptz_login_endpoint():
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
            return {"success": True, "connected": True}
        else:
            return {"success": False, "connected": False}
    except Exception as e:
        logger.error(f"云台登录失败: {e}")
        return {"success": False, "connected": False}


@app.post("/api/ptz/logout")
async def ptz_logout_endpoint():
    """云台登出"""
    global ptz_session, ptz_auth
    
    try:
        url = f"{PTZ_BASE_URL}/merlin/Logout.cgi"
        resp = requests.get(url, auth=ptz_auth, timeout=5)
        ptz_session = None
        ptz_auth = None
        robot_status["ptz"]["connected"] = False
        return {"success": True}
    except Exception as e:
        logger.error(f"云台登出失败: {e}")
        return {"success": False}


@app.post("/api/ptz/set_angle")
async def ptz_set_angle_endpoint(yaw: float = None, pitch: float = None, zoom: int = None):
    """设置云台角度"""
    global ptz_session, ptz_auth
    
    if not ptz_session:
        login_resp = await ptz_login_endpoint()
        if not login_resp["success"]:
            return {"success": False}
    
    try:
        url = f"{PTZ_BASE_URL}/merlin/SetPtzangle.cgi"
        data = {"Angle": {}}
        if yaw is not None:
            data["Angle"]["yaw"] = max(-280, min(280, yaw))
        if pitch is not None:
            data["Angle"]["pitch"] = max(-115, min(40, pitch))
        if zoom is not None:
            data["Angle"]["zoom"] = max(1, min(20, zoom))
        
        resp = requests.post(url, json=data, auth=ptz_auth, timeout=5)
        
        if resp.status_code == 200:
            if yaw is not None:
                robot_status["ptz"]["yaw"] = yaw
            if pitch is not None:
                robot_status["ptz"]["pitch"] = pitch
            if zoom is not None:
                robot_status["ptz"]["zoom"] = zoom
            return {"success": True, "ptz": robot_status["ptz"]}
        else:
            return {"success": False}
    except Exception as e:
        logger.error(f"云台角度设置失败: {e}")
        return {"success": False}


@app.get("/api/ptz/state")
async def ptz_get_state_endpoint():
    """获取云台状态"""
    global ptz_session, ptz_auth
    
    if not ptz_session:
        login_resp = await ptz_login_endpoint()
        if not login_resp["success"]:
            return {"success": False}
    
    try:
        url = f"{PTZ_BASE_URL}/merlin/GetFlyStateInfo.cgi"
        resp = requests.get(url, auth=ptz_auth, timeout=5)
        
        if resp.status_code == 200:
            state = resp.json()
            robot_status["ptz"]["yaw"] = state.get("Angle", {}).get("yaw", 0)
            robot_status["ptz"]["pitch"] = state.get("Angle", {}).get("pitch", 0)
            robot_status["ptz"]["zoom"] = state.get("Zoom", {}).get("zoom", 1)
            return {"state": state, "ptz": robot_status["ptz"]}
        else:
            return {"success": False}
    except Exception as e:
        logger.error(f"获取云台状态失败: {e}")
        return {"success": False}


@app.get("/api/temperature")
async def get_temperature_endpoint():
    """获取温度数据"""
    global temperature_data
    
    # 模拟温度数据
    import random
    base_temp = 35.0
    variation = random.uniform(-3, 3)
    current_temp = base_temp + variation
    
    temperature_data["current"] = round(current_temp, 1)
    temperature_data["max"] = max(temperature_data["max"], current_temp)
    temperature_data["history"].append({
        "time": datetime.now().isoformat(),
        "temp": current_temp
    })
    
    if len(temperature_data["history"]) > 100:
        temperature_data["history"] = temperature_data["history"][-100:]
    
    # 更新告警状态
    warn_threshold = 45.0
    critical_threshold = 50.0
    
    robot_status["temperature"]["current"] = current_temp
    robot_status["temperature"]["max"] = temperature_data["max"]
    robot_status["temperature"]["warn"] = current_temp >= warn_threshold
    robot_status["temperature"]["critical"] = current_temp >= critical_threshold
    
    # 发送告警
    if current_temp >= critical_threshold and not robot_status["temperature"].get("last_critical"):
        alert_msg = f"温度告警（严重）: {current_temp}°C 超过阈值 {critical_threshold}°C"
        alerts.append({"message": alert_msg, "timestamp": datetime.now().isoformat(),
                      "ack": False, "level": "danger"})
        robot_status["temperature"]["last_critical"] = True
    elif current_temp >= warn_threshold and not robot_status["temperature"].get("last_warn"):
        alert_msg = f"温度告警（预警）: {current_temp}°C 超过阈值 {warn_threshold}°C"
        alerts.append({"message": alert_msg, "timestamp": datetime.now().isoformat(),
                      "ack": False, "level": "warning"})
        robot_status["temperature"]["last_warn"] = True
    else:
        robot_status["temperature"].pop("last_critical", None)
        robot_status["temperature"].pop("last_warn", None)
    
    return {
        "current": current_temp,
        "max": temperature_data["max"],
        "warn_threshold": warn_threshold,
        "critical_threshold": critical_threshold,
        "warn": current_temp >= warn_threshold,
        "critical": current_temp >= critical_threshold,
        "history": temperature_data["history"][-10:]
    }


@app.post("/api/demo")
async def demo():
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
    for ws_conn in connections:
        await ws_conn.send_json({"type": "inspection", "data": inspections[-1]})
        await ws_conn.send_json({"type": "robot_status", "data": robot_status})
    return {"status": "ok"}


async def main():
    http_config = uvicorn.Config(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
    http_server = uvicorn.Server(http_config)
    
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
