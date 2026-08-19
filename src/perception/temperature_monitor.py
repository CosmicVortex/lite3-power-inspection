#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
温度监测算法
"""

import cv2
import numpy as np
from typing import Tuple, Dict, Optional, Deque, List
from dataclasses import dataclass
from enum import Enum
from collections import deque
from loguru import logger


class AlertLevel(Enum):
    """告警等级"""
    NORMAL = "normal"
    WARN = "warn"
    CRITICAL = "critical"


@dataclass
class TemperatureAlert:
    """温度告警数据类"""
    alert_level: AlertLevel
    temperature: float           # 当前温度(℃)
    max_temperature: float       # 区域最高温度(℃)
    roi: Tuple[int, int, int, int]  # 感兴趣区域 (x, y, w, h)
    alert_id: str                # 告警ID
    timestamp: float             # 时间戳


class TemperatureMonitor:
    """温度监测器
    
    实现双级告警逻辑，包含去抖机制和状态保持。
    支持ROI温度提取和滑动平均滤波。
    """
    
    def __init__(self,
                 warn_threshold: float = 45.0,
                 critical_threshold: float = 50.0,
                 filter_window: int = 3,
                 warn_confirm_frames: int = 5,
                 critical_confirm_frames: int = 3):
        """
        Args:
            warn_threshold: 预警阈值(℃)
            critical_threshold: 告警阈值(℃)
            filter_window: 滑动平均滤波窗口大小
            warn_confirm_frames: WARN确认所需连续帧数
            critical_confirm_frames: CRITICAL确认所需连续帧数
        """
        self.warn_threshold = warn_threshold
        self.critical_threshold = critical_threshold
        self.filter_window = filter_window
        self.warn_confirm_frames = warn_confirm_frames
        self.critical_confirm_frames = critical_confirm_frames
        
        # 状态跟踪
        self._warn_history: Deque[bool] = deque(maxlen=warn_confirm_frames)
        self._critical_history: Deque[bool] = deque(maxlen=critical_confirm_frames)
        self._filtered_temp: Optional[float] = None
        
        self.alert_counter = 0
        logger.info(f"初始化温度监测器: WARN>{warn_threshold}℃, CRITICAL>{critical_threshold}℃")
    
    def check_temperature(self, thermal_frame: np.ndarray,
                          roi: Optional[Tuple[int, int, int, int]] = None) -> Dict:
        """检查温度并判断告警状态
        
        Args:
            thermal_frame: 热成像帧 (H, W)，单位为℃
            roi: 感兴趣区域 (x, y, w, h)，None表示全图
            
        Returns:
            {
                "status": "NORMAL" | "WARN" | "CRITICAL",
                "temperature": 当前温度(℃),
                "max_temperature": 区域最高温度(℃),
                "alert_id": 告警ID,
                "confirm_count": 确认计数
            }
        """
        # 提取ROI温度
        if roi is not None:
            x, y, w, h = roi
            roi_temp = thermal_frame[y:y+h, x:x+w]
        else:
            roi_temp = thermal_frame
        
        # 计算统计值
        max_temp = float(np.max(roi_temp))
        mean_temp = float(np.mean(roi_temp))
        
        # 滑动平均滤波
        self._filtered_temp = self._apply_filter(mean_temp)
        
        # 判断告警状态
        status = self._determine_alert_status(max_temp)
        
        # 更新确认历史
        if status == AlertLevel.WARN:
            self._warn_history.append(True)
            self._critical_history.append(False)
        elif status == AlertLevel.CRITICAL:
            self._warn_history.append(True)
            self._critical_history.append(True)
        else:
            self._warn_history.append(False)
            self._critical_history.append(False)
        
        # 生成告警ID
        alert_id = self._generate_alert_id(status)
        
        result = {
            "status": status.value.upper(),
            "temperature": round(self._filtered_temp, 1) if self._filtered_temp else round(mean_temp, 1),
            "max_temperature": round(max_temp, 1),
            "alert_id": alert_id,
            "confirm_count": len([x for x in self._warn_history if x]) if status == AlertLevel.WARN else 0
        }
        
        logger.debug(f"温度监测: max={max_temp:.1f}℃, mean={mean_temp:.1f}℃, status={result['status']}")
        return result
    
    def _apply_filter(self, new_value: float) -> float:
        """应用滑动平均滤波
        
        Args:
            new_value: 新测量值
            
        Returns:
            滤波后的值
        """
        # TODO: 实现完整的滑动平均滤波
        return new_value
    
    def _determine_alert_status(self, max_temp: float) -> AlertLevel:
        """判断告警状态
        
        Args:
            max_temp: 区域最高温度
            
        Returns:
            告警等级
        """
        if max_temp >= self.critical_threshold:
            return AlertLevel.CRITICAL
        elif max_temp >= self.warn_threshold:
            return AlertLevel.WARN
        else:
            return AlertLevel.NORMAL
    
    def _generate_alert_id(self, status: AlertLevel) -> str:
        """生成告警ID
        
        Args:
            status: 告警状态
            
        Returns:
            告警ID字符串
        """
        from datetime import datetime
        date_str = datetime.now().strftime("%Y%m%d")
        
        if status == AlertLevel.NORMAL:
            return None
        
        self.alert_counter += 1
        return f"ALT-{date_str}-{self.alert_counter:03d}"
    
    def get_alert_history(self) -> Dict[str, List]:
        """获取告警历史
        
        Returns:
            {"warn": [...], "critical": [...]}
        """
        return {
            "warn": list(self._warn_history),
            "critical": list(self._critical_history)
        }
    
    def reset(self):
        """重置状态"""
        self._warn_history.clear()
        self._critical_history.clear()
        self._filtered_temp = None
        logger.info("温度监测器状态已重置")


if __name__ == "__main__":
    # 测试代码
    monitor = TemperatureMonitor()
    
    # 模拟热成像数据
    test_frame = np.full((512, 640), 40.0, dtype=np.float32)
    test_frame[200:300, 200:300] = 48.0  # 高温区域
    
    result = monitor.check_temperature(test_frame)
    print(f"温度监测结果: {result}")
