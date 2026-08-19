#!/usr/bin/env python3
import fitz

# Extract motion interface doc
doc = fitz.open("/tmp/motion_doc.pdf")
print(f"Pages: {len(doc)}")

text = ""
for page in doc[:30]:
    text += page.get_text()

with open("/opt/data/doc_extraction/motion.txt", "w") as f:
    f.write(text)
print(f"Saved {len(text)} chars")

for kw in ["0x21040001", "0x21010202", "0x21020C0E", "heartbeat", "stand"]:
    if kw.lower() in text.lower():
        print(f"Found: {kw}")

doc.close()

# Extract perception dev doc
doc = fitz.open("/tmp/perception_doc.pdf")
print(f"\nPerception pages: {len(doc)}")

text = ""
for page in doc[:30]:
    text += page.get_text()

with open("/opt/data/doc_extraction/perception.txt", "w") as f:
    f.write(text)
print(f"Saved {len(text)} chars")

for kw in ["UDP", "WebSocket", "RTSP", "IP", "port"]:
    count = text.count(kw)
    if count > 0:
        print(f"{kw}: {count}")

doc.close()
print("\nDone!")
