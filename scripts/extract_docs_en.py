#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract key content from official docs
"""

import fitz
import os

base_dir = "/opt/data/lite3-power-inspection/docs/00-参考资料"
output_dir = "/opt/data/doc_extraction"

os.makedirs(output_dir, exist_ok=True)

# Extract motion interface doc
pdf_path = os.path.join(base_dir, "03-运动主机通讯接口V1.0.8.pdf")
doc = fitz.open(pdf_path)
print(f"Motion interface: {len(doc)} pages")

text = ""
for page in doc[:50]:
    text += page.get_text()

with open(os.path.join(output_dir, "motion.txt"), 'w', encoding='utf-8') as f:
    f.write(text)
print(f"Saved, chars: {len(text)}")

# Find key commands
keywords = ["0x21040001", "0x21010202", "0x21020C0E", "heartbeat", "stand up", "emergency stop"]
for kw in keywords:
    if kw.lower() in text.lower():
        print(f"Found: {kw}")

doc.close()

# Extract perception dev doc
pdf_path = os.path.join(base_dir, "04-感知开发手册V2.2.3.pdf")
doc = fitz.open(pdf_path)
print(f"\nPerception dev: {len(doc)} pages")

text = ""
for page in doc[:50]:
    text += page.get_text()

with open(os.path.join(output_dir, "perception.txt"), 'w', encoding='utf-8') as f:
    f.write(text)
print(f"Saved, chars: {len(text)}")

# Find key content
keywords = ["UDP", "WebSocket", "RTSP", "IP address", "port", "communication"]
for kw in keywords:
    count = text.count(kw)
    if count > 0:
        print(f"{kw}: {count} times")

doc.close()

print("\nExtraction complete!")
