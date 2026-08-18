#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract text from Shuer official documents"""

import fitz
import sys
import os

def extract_pdf(filepath):
    """Extract text from PDF file"""
    try:
        doc = fitz.open(filepath)
        output_lines = []
        output_lines.append(f"\n{'='*60}")
        output_lines.append(f"文件: {filepath}")
        output_lines.append(f"页数: {doc.page_count}")
        output_lines.append(f"{'='*60}")
        
        for i in range(min(20, doc.page_count)):
            page = doc.load_page(i)
            text = page.get_text()
            if text.strip():
                output_lines.append(f"\n--- 第{i+1}页 ---")
                output_lines.append(text[:2500])
        doc.close()
        return '\n'.join(output_lines)
    except Exception as e:
        return f"错误读取 {filepath}: {e}"

if __name__ == "__main__":
    pdf_files = [
        "docs/00-参考资料/数尔安防官方资料/数尔安防吊舱_快速操作手册V2.pdf",
        "docs/00-参考资料/数尔安防官方资料/软件开发协议V1.0-精简版.pdf"
    ]
    
    all_output = []
    for pdf_path in pdf_files:
        if os.path.exists(pdf_path):
            result = extract_pdf(pdf_path)
            all_output.append(result)
        else:
            all_output.append(f"文件不存在: {pdf_path}")
    
    print('\n'.join(all_output))
