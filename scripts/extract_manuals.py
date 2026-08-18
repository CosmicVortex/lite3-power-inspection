#!/usr/bin/env python3
import sys
sys.path.insert(0, '/tmp/pdf_venv/lib/python3.13/site-packages')
import pymupdf

print('========== 运动主机通讯接口 V1.0.8 ==========\n')
doc = pymupdf.open('/tmp/comm.pdf')
for i, page in enumerate(doc):
    if i < 8:
        text = page.get_text('text')
        if text.strip():
            print(f'--- Page {i+1} ---')
            print(text[:2500])
doc.close()

print('\n========== 感知开发手册 V2.2.3 (关键章节) ==========\n')
doc = pymupdf.open('/tmp/perception.pdf')
for i, page in enumerate(doc):
    if 5 <= i < 12:
        text = page.get_text('text')
        if text.strip():
            print(f'--- Page {i+1} ---')
            print(text[:2000])
doc.close()

print('\n========== 运动开发手册 V2.2.0 ==========\n')
doc = pymupdf.open('/tmp/motion.pdf')
for i, page in enumerate(doc):
    if i < 12:
        text = page.get_text('text')
        if text.strip():
            print(f'--- Page {i+1} ---')
            print(text[:2000])
doc.close()
