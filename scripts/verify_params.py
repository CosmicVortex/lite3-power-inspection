#!/usr/bin/env python3
"""Verify technical parameters from official documentation"""

import fitz
import re

def extract_pdf_text(filepath):
    """Extract text from PDF"""
    try:
        doc = fitz.open(filepath)
        text = ""
        for i in range(min(20, doc.page_count)):
            text += doc.load_page(i).get_text()
        doc.close()
        return text
    except Exception as e:
        return f"Error: {e}"

def check_parameter(text, patterns):
    """Check if parameters exist in text"""
    results = {}
    for name, pattern in patterns.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        results[name] = matches[:5] if matches else None
    return results

# 1. 绝影Lite3产品手册
print("="*60)
print("1. 绝影Lite3产品手册参数验证")
print("="*60)
text1 = extract_pdf_text("docs/00-参考资料/01-绝影Lite3产品手册V2.0.0.pdf")
if not text1.startswith("Error"):
    patterns = {
        "GPU型号": r"(Xavier|Orin|GPU|图形处理器)",
        "算力": r"(\d+\s*TOPS)",
        "CPU型号": r"(RK3588|ARM|CPU)",
        "内存": r"(\d+\s*GB\s*(内存|RAM))",
        "接口": r"(UDP|TCP|WebSocket|RTSP)",
    }
    for name, matches in check_parameter(text1, patterns).items():
        print(f"{name}: {matches}")
else:
    print(text1)

# 2. 运动主机通讯接口
print("\n" + "="*60)
print("2. 运动主机通讯接口参数验证")
print("="*60)
text2 = extract_pdf_text("docs/00-参考资料/03-运动主机通讯接口V1.0.8.pdf")
if not text2.startswith("Error"):
    patterns = {
        "端口号": r"(43893|端口|port)",
        "指令格式": r"(0x[0-9A-Fa-f]+|指令码)",
        "心跳周期": r"(\d+\s*ms|心跳)",
        "起立指令": r"(0x21010202|起立)",
        "趴下指令": r"(0x21010202|趴下)",
        "急停指令": r"(0x21020C0E|急停)",
    }
    for name, matches in check_parameter(text2, patterns).items():
        print(f"{name}: {matches}")
else:
    print(text2)

# 3. 感知开发手册
print("\n" + "="*60)
print("3. 感知开发手册参数验证")
print("="*60)
text3 = extract_pdf_text("docs/00-参考资料/04-感知开发手册V2.2.3.pdf")
if not text3.startswith("Error"):
    patterns = {
        "模型格式": r"(TensorRT|ONNX|TRT|engine)",
        "推理框架": r"(YOLO|U-Net|CNN)",
        "分辨率": r"(\d+x\d+)",
    }
    for name, matches in check_parameter(text3, patterns).items():
        print(f"{name}: {matches}")
else:
    print(text3)

# 4. 检查关键参数是否在文档中明确说明
print("\n" + "="*60)
print("4. 文档参数核查")
print("="*60)

tech_docs = [
    "docs/01-技术方案/01-系统架构设计.md",
    "docs/01-技术方案/02-API接口文档.md",
    "docs/01-技术方案/03-开发环境搭建指南.md",
]

key_params = {
    "UDP端口43893": r"43893",
    "IP地址192.168.1.108": r"192\.168\.1\.108",
    "IP地址192.168.1.120": r"192\.168\.1\.120",
    "IP地址192.168.1.200": r"192\.168\.1\.200",
    "RTSP端口554": r":554",
    "WebSocket端口8765": r":8765",
    "YOLOv8": r"YOLOv8",
    "U-Net": r"U-Net",
    "TensorRT": r"TensorRT",
    "Jetson Xavier NX": r"Xavier NX",
    "RK3588": r"RK3588",
}

for doc_path in tech_docs:
    print(f"\n--- {doc_path} ---")
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        for param, pattern in key_params.items():
            matches = re.findall(pattern, content)
            status = f"✅ 找到{len(matches)}处" if matches else "❌ 未找到"
            print(f"  {param}: {status}")
    except Exception as e:
        print(f"  读取错误: {e}")
