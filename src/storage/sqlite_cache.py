#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite本地缓存
"""

import sqlite3
import json
import time
from typing import List, Dict, Optional
from pathlib import Path
from loguru import logger


class SQLiteCache:
    """SQLite本地缓存
    
    提供本地数据缓存功能，支持断网时的数据暂存和网络恢复后的补传。
    """
    
    def __init__(self, db_path: str = "data/inspection.db"):
        """
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._conn = None
        self._init_db()
        
        logger.info(f"SQLite缓存初始化: {db_path}")
    
    def _init_db(self):
        """初始化数据库表"""
        self._conn = sqlite3.connect(self.db_path)
        cursor = self._conn.cursor()
        
        # 检测结果表
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
        
        # 告警历史表
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
        
        # 航点配置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS waypoints (
                id TEXT PRIMARY KEY,
                x REAL NOT NULL,
                y REAL NOT NULL,
                theta REAL NOT NULL,
                type TEXT NOT NULL,
                ptz_yaw REAL,
                ptz_pitch REAL,
                zoom_level INTEGER DEFAULT 1,
                wait_time REAL DEFAULT 0.0
            )
        ''')
        
        # 索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_results_type 
            ON inspection_results(type, uploaded)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_results_timestamp 
            ON inspection_results(timestamp)
        ''')
        
        self._conn.commit()
        logger.info("数据库表初始化完成")
    
    def save_inspection_result(self, result: Dict) -> int:
        """保存检测结果
        
        Args:
            result: 检测结果字典
            
        Returns:
            插入的行ID
        """
        cursor = self._conn.cursor()
        
        cursor.execute('''
            INSERT INTO inspection_results 
            (type, timestamp, waypoint_id, confidence, width_mm, length_mm,
             temperature, alert_level, snapshot_url, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result.get('type'),
            result.get('timestamp', time.time()),
            result.get('waypoint_id'),
            result.get('confidence'),
            result.get('width_mm'),
            result.get('length_mm'),
            result.get('temperature'),
            result.get('alert_level'),
            result.get('snapshot_url'),
            json.dumps(result, ensure_ascii=False)
        ))
        
        self._conn.commit()
        return cursor.lastrowid
    
    def save_alert(self, alert: Dict) -> int:
        """保存告警记录
        
        Args:
            alert: 告警字典
            
        Returns:
            插入的行ID
        """
        cursor = self._conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO alert_history
            (alert_id, type, level, timestamp, waypoint_id, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            alert.get('alert_id'),
            alert.get('type'),
            alert.get('level'),
            alert.get('timestamp', time.time()),
            alert.get('waypoint_id'),
            json.dumps(alert.get('details', {}), ensure_ascii=False)
        ))
        
        self._conn.commit()
        return cursor.lastrowid
    
    def save_waypoint(self, waypoint: Dict):
        """保存航点配置
        
        Args:
            waypoint: 航点字典
        """
        cursor = self._conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO waypoints
            (id, x, y, theta, type, ptz_yaw, ptz_pitch, zoom_level, wait_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            waypoint.get('id'),
            waypoint.get('x'),
            waypoint.get('y'),
            waypoint.get('theta'),
            waypoint.get('type'),
            waypoint.get('ptz_yaw'),
            waypoint.get('ptz_pitch'),
            waypoint.get('zoom_level', 1),
            waypoint.get('wait_time', 0.0)
        ))
        
        self._conn.commit()
    
    def get_unuploaded_results(self, limit: int = 100) -> List[Dict]:
        """获取未上传的检测结果
        
        Args:
            limit: 最大返回数量
            
        Returns:
            检测结果列表
        """
        cursor = self._conn.cursor()
        cursor.execute('''
            SELECT * FROM inspection_results 
            WHERE uploaded = 0 
            ORDER BY timestamp ASC 
            LIMIT ?
        ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            result = dict(zip(columns, row))
            if result.get('data_json'):
                result.update(json.loads(result['data_json']))
            results.append(result)
        
        return results
    
    def mark_uploaded(self, result_id: int):
        """标记结果为已上传
        
        Args:
            result_id: 结果ID
        """
        cursor = self._conn.cursor()
        cursor.execute('''
            UPDATE inspection_results 
            SET uploaded = 1 
            WHERE id = ?
        ''', (result_id,))
        self._conn.commit()
    
    def get_alert_history(self, limit: int = 100) -> List[Dict]:
        """获取告警历史
        
        Args:
            limit: 最大返回数量
            
        Returns:
            告警列表
        """
        cursor = self._conn.cursor()
        cursor.execute('''
            SELECT * FROM alert_history 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            result = dict(zip(columns, row))
            if result.get('details'):
                result['details'] = json.loads(result['details'])
            results.append(result)
        
        return results
    
    def get_waypoints(self) -> List[Dict]:
        """获取所有航点配置
        
        Returns:
            航点列表
        """
        cursor = self._conn.cursor()
        cursor.execute('SELECT * FROM waypoints ORDER BY id')
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            logger.info("数据库连接已关闭")
    
    def __del__(self):
        """析构函数"""
        self.close()


if __name__ == "__main__":
    # 测试代码
    cache = SQLiteCache("data/test.db")
    
    # 测试保存结果
    result_id = cache.save_inspection_result({
        "type": "crack",
        "confidence": 0.92,
        "width_mm": 0.15,
        "length_mm": 45.2
    })
    print(f"保存结果ID: {result_id}")
    
    # 测试保存告警
    alert_id = cache.save_alert({
        "alert_id": "ALT-20260819-001",
        "type": "temperature",
        "level": "warn",
        "temperature": 46.5
    })
    print(f"保存告警ID: {alert_id}")
    
    # 测试查询
    unuploaded = cache.get_unuploaded_results()
    print(f"未上传结果数: {len(unuploaded)}")
    
    alerts = cache.get_alert_history()
    print(f"告警历史数: {len(alerts)}")
    
    cache.close()
    print("测试完成")
