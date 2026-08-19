#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLOv8裂缝检测器
"""

import os
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from .tensorrt_engine import TensorRTModel


class DetectClass(Enum):
    """检测类别"""
    CRACK = "crack"              # 裂缝
    HONEYCOMB = "honeycomb"      # 蜂窝麻面
    OTHER = "other"              # 其他缺陷


@dataclass
class DetectionResult:
    """检测结果数据类"""
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    center: Tuple[float, float]      # (x, y)
    width_mm: Optional[float] = None
    length_mm: Optional[float] = None


class YOLODetector:
    """YOLOv8裂缝检测器
    
    封装YOLOv8模型的广角检测功能。
    支持TensorRT加速和CPU降级。
    """
    
    def __init__(self, model_path: str, 
                 confidence_threshold: float = 0.5,
                 iou_threshold: float = 0.45,
                 input_size: Tuple[int, int] = (640, 640)):
        """
        Args:
            model_path: YOLOv8 TensorRT引擎路径
            confidence_threshold: 置信度阈值
            iou_threshold: NMS IoU阈值
            input_size: 输入图像尺寸 (width, height)
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.input_size = input_size
        
        self.model = None
        self.class_names = [c.value for c in DetectClass]
        
        logger.info(f"初始化YOLO检测器: {model_path}")
        self._load_model()
    
    def _load_model(self):
        """加载模型"""
        try:
            self.model = TensorRTModel(self.model_path, precision="int8")
            logger.info("YOLO模型加载成功")
        except Exception as e:
            logger.error(f"YOLO模型加载失败: {e}")
            raise
    
    def detect(self, image: np.ndarray) -> List[DetectionResult]:
        """执行裂缝检测
        
        Args:
            image: BGR格式图像
            
        Returns:
            检测结果列表
        """
        if self.model is None:
            logger.error("模型未加载")
            return []
        
        # 预处理
        input_tensor = self._preprocess(image)
        
        # 推理
        outputs = self.model.infer(input_tensor)
        
        # 后处理
        results = self._postprocess(outputs, image.shape)
        
        logger.debug(f"检测到 {len(results)} 个目标")
        return results
    
    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """图像预处理
        
        Args:
            image: BGR图像
            
        Returns:
            归一化后的张量 (1, 3, 640, 640)
        """
        # 缩放
        src_h, src_w = image.shape[:2]
        ratio = min(self.input_size[0] / src_w, self.input_size[1] / src_h)
        new_w, new_h = int(src_w * ratio), int(src_h * ratio)
        
        resized = cv2.resize(image, (new_w, new_h))
        
        # 填充
        canvas = np.zeros((self.input_size[1], self.input_size[0], 3), dtype=np.uint8)
        canvas[:new_h, :new_w] = resized
        
        # 归一化
        tensor = canvas.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))  # HWC -> CHW
        tensor = np.expand_dims(tensor, 0)  # (1, C, H, W)
        
        return tensor
    
    def _postprocess(self, outputs: Dict[str, np.ndarray], 
                     img_shape: Tuple[int, int]) -> List[DetectionResult]:
        """后处理：NMS + 坐标还原
        
        Args:
            outputs: 模型输出
            img_shape: 原始图像尺寸 (h, w)
            
        Returns:
            检测结果列表
        """
        results = []
        
        # TODO: 实现完整的后处理逻辑
        # 1. 解析模型输出
        # 2. 应用置信度过滤
        # 3. 应用NMS
        # 4. 坐标还原到原始图像
        
        logger.warning("后处理逻辑待实现")
        return results
    
    def _nms(self, boxes: np.ndarray, scores: np.ndarray, 
             iou_threshold: float) -> List[int]:
        """非极大值抑制
        
        Args:
            boxes: (N, 4) 边界框 [x1, y1, x2, y2]
            scores: (N,) 置信度分数
            iou_threshold: IoU阈值
            
        Returns:
            保留的索引列表
        """
        # TODO: 实现NMS算法
        return []
    
    def detect_with_heatmap(self, image: np.ndarray) -> Tuple[List[DetectionResult], np.ndarray]:
        """检测并生成热力图
        
        Args:
            image: BGR图像
            
        Returns:
            (检测结果, 热力图)
        """
        results = self.detect(image)
        heatmap = self._generate_heatmap(image, results)
        return results, heatmap
    
    def _generate_heatmap(self, image: np.ndarray, 
                          results: List[DetectionResult]) -> np.ndarray:
        """生成检测结果热力图
        
        Args:
            image: 原始图像
            results: 检测结果列表
            
        Returns:
            带标注的热力图
        """
        vis_image = image.copy()
        
        for result in results:
            x1, y1, x2, y2 = result.bbox
            # 绘制边界框
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            # 绘制标签
            label = f"{result.class_name}: {result.confidence:.2f}"
            cv2.putText(vis_image, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return vis_image


if __name__ == "__main__":
    # 测试代码
    detector = YOLODetector("models/yolov8s-crack.trt")
    test_image = np.zeros((640, 640, 3), dtype=np.uint8)
    results = detector.detect(test_image)
    print(f"检测结果: {results}")
