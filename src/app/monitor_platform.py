#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简易监测平台 - 电力巡检数据可视化
"""

from flask import Flask, render_template, jsonify, request
import json
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Optional
import threading
import time

app = Flask(__name__)

# 数据库路径
DB_PATH = "data/inspection.db"

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """初始化数据库"""
    if not os.path.exists(DB_PATH):
        os.makedirs("data", exist_ok=True)
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 创建表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inspection_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                timestamp REAL NOT NULL,
                waypoint_id TEXT,
                confidence REAL,
                width_mm REAL,
                length_mm REAL,
                temperature REAL,
                alert_level TEXT,
                snapshot_url TEXT,
                uploaded INTEGER DEFAULT 0,
                data_json TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                level TEXT NOT NULL,
                timestamp REAL NOT NULL,
                waypoint_id TEXT,
                details TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                battery REAL,
                status TEXT,
                cpu_temp REAL,
                memory_usage REAL,
                data JSON
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_results_type 
            ON inspection_results(type, uploaded)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_results_timestamp 
            ON inspection_results(timestamp)
        ''')
        
        conn.commit()
        conn.close()

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/status')
def get_system_status():
    """获取系统状态"""
    status = {
        "system": {
            "uptime": time.time(),
            "battery": 95.0,
            "cpu_temp": 45.2,
            "memory_usage": 65.3
        },
        "connection": {
            "udp": "connected",
            "websocket": "connected",
            "ptz": "connected"
        },
        "inspection": {
            "total_results": 0,
            "crack_detected": 0,
            "temperature_alerts": 0,
            "last_update": datetime.now().isoformat()
        }
    }
    
    # 从数据库获取统计
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM inspection_results")
        status["inspection"]["total_results"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM inspection_results WHERE type='crack'")
        status["inspection"]["crack_detected"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM alert_history")
        status["inspection"]["temperature_alerts"] = cursor.fetchone()[0]
        
        conn.close()
    except Exception as e:
        print(f"获取统计数据失败: {e}")
    
    return jsonify(status)

@app.route('/api/inspection_results', methods=['GET'])
def get_inspection_results():
    """获取检测结果"""
    limit = request.args.get('limit', 50, type=int)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM inspection_results 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row["id"],
                "type": row["type"],
                "timestamp": datetime.fromtimestamp(row["timestamp"]).isoformat(),
                "waypoint_id": row["waypoint_id"],
                "confidence": row["confidence"],
                "width_mm": row["width_mm"],
                "length_mm": row["length_mm"],
                "temperature": row["temperature"],
                "alert_level": row["alert_level"],
                "snapshot_url": row["snapshot_url"],
                "uploaded": row["uploaded"]
            })
        
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """获取告警历史"""
    limit = request.args.get('limit', 50, type=int)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM alert_history 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        alerts = []
        for row in cursor.fetchall():
            alerts.append({
                "id": row["id"],
                "alert_id": row["alert_id"],
                "type": row["type"],
                "level": row["level"],
                "timestamp": datetime.fromtimestamp(row["timestamp"]).isoformat(),
                "waypoint_id": row["waypoint_id"],
                "details": json.loads(row["details"]) if row["details"] else {}
            })
        
        conn.close()
        return jsonify(alerts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """获取统计数据"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 裂缝统计
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                AVG(width_mm) as avg_width,
                AVG(length_mm) as avg_length,
                MAX(width_mm) as max_width,
                MIN(width_mm) as min_width
            FROM inspection_results 
            WHERE type='crack'
        ''')
        crack_stats = cursor.fetchone()
        
        # 温度统计
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                AVG(max_temperature) as avg_temp,
                MAX(max_temperature) as max_temp
            FROM alert_history 
            WHERE type='temperature'
        ''')
        temp_stats = cursor.fetchone()
        
        # 按航点统计
        cursor.execute('''
            SELECT waypoint_id, COUNT(*) as count
            FROM inspection_results
            GROUP BY waypoint_id
            ORDER BY count DESC
        ''')
        waypoint_stats = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            "cracks": {
                "total": crack_stats["total"] if crack_stats else 0,
                "avg_width": crack_stats["avg_width"] if crack_stats else 0,
                "max_width": crack_stats["max_width"] if crack_stats else 0
            },
            "temperatures": {
                "total": temp_stats["total"] if temp_stats else 0,
                "avg_temp": temp_stats["avg_temp"] if temp_stats else 0,
                "max_temp": temp_stats["max_temp"] if temp_stats else 0
            },
            "waypoints": [dict(row) for row in waypoint_stats]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    """接收遥测数据"""
    try:
        data = request.json
        timestamp = time.time()
        
        # 保存检测结果
        if data.get("type") == "inspection_result":
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO inspection_results 
                (type, timestamp, waypoint_id, confidence, width_mm, length_mm,
                 temperature, alert_level, snapshot_url, data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get("type"),
                timestamp,
                data.get("data", {}).get("waypoint_id"),
                data.get("data", {}).get("confidence"),
                data.get("data", {}).get("width_mm"),
                data.get("data", {}).get("length_mm"),
                data.get("data", {}).get("temperature"),
                data.get("data", {}).get("alert_level"),
                data.get("data", {}).get("snapshot_url"),
                json.dumps(data, ensure_ascii=False)
            ))
            
            conn.commit()
            conn.close()
        
        # 保存告警
        elif data.get("type") == "temperature_alert":
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO alert_history
                (alert_id, type, level, timestamp, waypoint_id, details)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                data.get("data", {}).get("alert_id"),
                "temperature",
                data.get("data", {}).get("level"),
                timestamp,
                data.get("data", {}).get("waypoint_id"),
                json.dumps(data.get("data", {}), ensure_ascii=False)
            ))
            
            conn.commit()
            conn.close()
        
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/simulation', methods=['POST'])
def simulate_data():
    """模拟测试数据"""
    import random
    
    simulation_type = request.json.get("type", "all")
    count = request.json.get("count", 5)
    
    results = []
    
    for i in range(count):
        if simulation_type in ["crack", "all"]:
            results.append({
                "type": "inspection_result",
                "data": {
                    "waypoint_id": f"WP{random.randint(1,5):03d}",
                    "confidence": round(random.uniform(0.7, 0.95), 2),
                    "width_mm": round(random.uniform(0.1, 0.5), 2),
                    "length_mm": round(random.uniform(10, 100), 1),
                    "alert_level": "normal"
                }
            })
        
        if simulation_type in ["temperature", "all"]:
            temp = round(random.uniform(38, 55), 1)
            level = "normal"
            if temp >= 50:
                level = "critical"
            elif temp >= 45:
                level = "warn"
            
            results.append({
                "type": "temperature_alert",
                "data": {
                    "alert_id": f"ALT-{datetime.now().strftime('%Y%m%d')}-{len(results)+1:03d}",
                    "waypoint_id": f"WP{random.randint(1,5):03d}",
                    "temperature": temp,
                    "max_temperature": temp + random.uniform(1, 3),
                    "level": level
                }
            })
    
    # 批量保存
    for result in results:
        app.view_functions['receive_telemetry']()(result)
    
    return jsonify({
        "status": "ok",
        "count": len(results),
        "results": results
    })

@app.route('/api/reset', methods=['POST'])
def reset_data():
    """重置所有数据"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM inspection_results")
        cursor.execute("DELETE FROM alert_history")
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # 初始化数据库
    init_database()
    
    # 启动Flask应用
    print("="*60)
    print("绝影Lite3电力巡检监测平台")
    print("="*60)
    print(f"\n访问地址: http://localhost:5000")
    print(f"API地址: http://localhost:5000/api")
    print("\n按 Ctrl+C 停止服务\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
