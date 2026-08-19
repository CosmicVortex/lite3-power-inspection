#!/usr/bin/env python3
import fitz
import os

# 读取感知开发手册
pdf_path = "/tmp/perception_doc.pdf"
doc = fitz.open(pdf_path)
print(f"感知开发手册: {len(doc)}页")

text = ""
for page in doc[:100]:
    text += page.get_text()

# 保存
with open("/opt/data/doc_extraction/perception_full.txt", "w", encoding="utf-8") as f:
    f.write(text)
print(f"已保存，字符数: {len(text)}")

# 查找账户密码相关内容
keywords = ["用户名", "密码", "账户", "login", "password", "user", "admin", "root"]
for kw in keywords:
    count = text.lower().count(kw.lower())
    if count > 0:
        print(f"\n找到关键词: {kw} ({count}次)")
        # 显示上下文
        import re
        matches = list(re.finditer(kw, text, re.IGNORECASE))
        for match in matches[:5]:
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 100)
            print(f"  - {text[start:end]}")

doc.close()
