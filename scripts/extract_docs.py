#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取绝影Lite3官方文档关键内容
"""

import fitz  # pymupdf
import os
import re

base_dir = "/opt/data/lite3-power-inspection/docs/00-参考资料"
output_dir = "/opt/data/doc_extraction"

os.makedirs(output_dir, exist_ok=True)

# 提取运动主机通讯接口文档
pdf_path = os.path.join(base_dir, "03-运动主机通讯接口V1.0.8.pdf")
doc = fitz.open(pdf_path)
print(f"运动主机通讯接口: {len(doc)}页")

text = ""
for page in doc[:50]:
    text += page.get_text()

# 保存
with open(os.path.join(output_dir, "motion_interface.txt"), 'w') as f:
    f.write(text)
print(f"已保存，字符数: {len(text)}")

# 查找关键指令
keywords = ["0x21040001", "0x21010202", "0x21020C0E", "心跳", "起立", "急停"]
for kw in keywords:
    if kw in text:
        print(f"找到: {kw}")

doc.close()

# 提取感知开发手册
pdf_path = os.path.join(base_dir, "04-感知开发手册V2.2.3.pdf")
doc = fitz.open(pdf_path)
print(f"\n感知开发手册: {len(doc)}页")

text = ""
for page in doc[:50]:
    text += page.get_text()

# 保存
with open(os.path.join(output_dir, "perception_dev.txt"), 'w') as f:
    f.write(text)
print(f"已保存，字符数: {len(text)}")

# 查找关键内容
keywords = ["UDP", "WebSocket", "RTSP", "IP", "端口", "通信"]
for kw in keywords:
    count = text.count(kw)
    if count > 0:
        print(f"{kw}: {count}次")

doc.close()

print("\n提取完成!")
