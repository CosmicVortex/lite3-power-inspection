#!/usr/bin/env python3
import fitz
import sys

# Extract motion interface doc
doc = fitz.open("/tmp/motion.pdf")
print(f"Motion doc: {len(doc)} pages")

text = ""
for page in doc[:30]:
    text += page.get_text()

with open("/opt/data/doc_extraction/motion.txt", "w", encoding="utf-8") as f:
    f.write(text)
print(f"Saved motion.txt, {len(text)} chars")

# Find key commands
for kw in ["0x21040001", "0x21010202", "0x21020C0E", "heartbeat", "stand"]:
    if kw.lower() in text.lower():
        print(f"Found: {kw}")

doc.close()

# Extract perception dev doc
doc = fitz.open("/tmp/perception.pdf")
print(f"\nPerception doc: {len(doc)} pages")

text = ""
for page in doc[:30]:
    text += page.get_text()

with open("/opt/data/doc_extraction/perception.txt", "w", encoding="utf-8") as f:
    f.write(text)
print(f"Saved perception.txt, {len(text)} chars")

# Find key content
for kw in ["UDP", "WebSocket", "RTSP", "IP", "port"]:
    count = text.count(kw)
    if count > 0:
        print(f"{kw}: {count} times")

doc.close()
print("\nDone!")
