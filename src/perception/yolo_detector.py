#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLO裂缝检测器（支持真实模型和模拟模式）

当模型文件不存在时，自动进入模拟模式，生成符合规范的测试数据。
"""

import os
import random
import time
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from loguru import logger


@dataclass
class DetectionResult:
    """检测结果数据类"""
    class_id: int
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    width_mm: float = 0.0
    length_mm: float = 0.0


class YOLODetector:
    """YOLO裂缝检测器
    
    支持两种模式：
    1. 真实模式：加载TensorRT/ONNX模型进行推理
    2. 模拟模式：生成符合规范的测试数据（用于开发测试）
    """
    
    def __init__(self, 
                 model_path: Optional[str] = None,
                 confidence_threshold: float = 0.5,
                 enable_simulation: bool = True):
        """
        Args:
            model_path: 模型文件路径 (.trt 或 .onnx)
            confidence_threshold: 置信度阈值
            enable_simulation: 是否启用模拟模式
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.enable_simulation = enable_simulation and (not os.path.exists(model_path))
        
        self.model = None
        self._mode = "simulation" if self.enable_simulation else "real"
        
        logger.info(f"初始化YOLO检测器: mode={self._mode}, model={model_path}")
        
        if not self.enable_simulation:
            self._load_model()
    
    def _load_model(self):
        """加载TensorRT模型"""
        try:
            from .tensorrt_engine import TensorRTModel
            self.model = TensorRTModel(self.model_path)
            self._mode = "real"
            logger.info("TensorRT模型加载成功")
        except Exception as e:
            logger.warning(f"模型加载失败，回退到模拟模式: {e}")
            self.enable_simulation = True
            self._mode = "simulation"
    
    def detect(self, image) -> List[DetectionResult]:
        """执行裂缝检测
        
        Args:
            image: 输入图像 (numpy array)
            
        Returns:
            检测结果列表
        """
        if self._mode == "simulation":
            return self._simulate_detect(image)
        else:
            return self._real_detect(image)
    
    def _simulate_detect(self, image) -> List[DetectionResult]:
        """模拟检测 - 生成符合规范的测试数据"""
        h, w = image.shape[:2]
        results = []
        
        # 模拟检测到裂缝的概率
        num_cracks = random.choice([0, 0, 0, 1, 1, 2])  # 60%概率有裂缝
        
        for _ in range(num_cracks):
            # 生成随机边界框
            x1 = random.randint(50, w - 150)
            y1 = random.randint(50, h - 150)
            x2 = x1 + random.randint(50, 150)
            y2 = y1 + random.randint(30, 100)
            
            # 生成符合规范的检测结果
            confidence = random.uniform(0.7, 0.95)
            width_mm = round(random.uniform(0.1, 0.5), 2)
            length_mm = round(random.uniform(10, 100), 1)
            
            results.append(DetectionResult(
                class_id=0,
                confidence=confidence,
                bbox=(x1, y1, x2, y2),
                width_mm=width_mm,
                length_mm=length_mm
            ))
        
        logger.debug(f"模拟检测: 发现 {len(results)} 条裂缝")
        return results
    
    def _real_detect(self, image) -> List[DetectionResult]:
        """真实检测 - 使用TensorRT模型推理"""
        # TODO: 实现TensorRT推理（需加载TensorRT引擎后使用）
        # 当前模拟模式生成合理数据，等待真实模型部署后可切换
        logger.warning("TensorRT推理未实现，回退到模拟模式")
        return self._simulate_detect(image)
    
    @property
    def is_simulation(self) -> bool:
        """是否处于模拟模式"""
        return self._mode == "simulation"


if __name__ == "__main__":
    # 测试代码
    import numpy as np
    detector = YOLODetector("models/yolov8s-crack.trt", enable_simulation=True)
    
    test_image = np.zeros((640, 640, 3), dtype=np.uint8)
    results = detector.detect(test_image)
    
    print(f"检测模式: {detector._mode}")
    print(f"发现 {len(results)} 条裂缝:")
    for r in results:
        print(f"  - 置信度: {r.confidence:.2f}, 宽度: {r.width_mm:.2f}mm, 长度: {r.length_mm:.1f}mm")
        print(f"    边界框: {r.bbox}")
