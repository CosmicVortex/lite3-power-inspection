#!/usr/bin/env python3
"""创建商业级DOCX模板"""

from docx import Document
from docx.shared import Inches, Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.enum.style import WD_STYLE_TYPE

def create_commercial_template(output_path: str = "templates/commercial.docx"):
    """创建商业级DOCX模板"""
    
    doc = Document()
    
    # 设置页面边距
    sections = doc.sections
    for section in sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(3)
        section.right_margin = Cm(3)
    
    # 设置默认字体（中文）
    style = doc.styles['Normal']
    font = style.font
    font.name = 'SimSun'
    font.size = Pt(12)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), 'SimSun')
    
    # 设置段落格式
    pf = style.paragraph_format
    pf.line_spacing = 1.5
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    
    # 配置标题样式
    for i in range(1, 4):
        heading_style = doc.styles[f'Heading {i}']
        heading_font = heading_style.font
        heading_font.name = 'SimHei'
        heading_font.size = Pt(14 - (i - 1) * 2)
        heading_font.bold = True
        heading_style.element.rPr.rFonts.set(qn('w:eastAsia'), 'SimHei')
        
        # 设置段落格式
        heading_pf = heading_style.paragraph_format
        heading_pf.space_before = Pt(12)
        heading_pf.space_after = Pt(6)
    
    # 保存模板
    doc.save(output_path)
    print(f"✅ 商业级模板已创建: {output_path}")
    print("   - 页面边距: 上2.5cm, 下2.5cm, 左3cm, 右3cm")
    print("   - 正文字体: 宋体 12pt")
    print("   - 标题字体: 黑体 12-14pt")
    print("   - 行间距: 1.5倍")

if __name__ == "__main__":
    create_commercial_template()
