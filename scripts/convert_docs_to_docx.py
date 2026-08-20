#!/usr/bin/env python3
"""
批量将Markdown文档转换为DOCX格式
"""

import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime

# 配置
DOCS_DIR = Path("docs/01-技术方案")
OUTPUT_DIR = Path("deliverables/docx")
TEMPLATE_DIR = Path("templates")
TEMPLATE_FILE = TEMPLATE_DIR / "commercial.docx"

# Emoji转文字映射
EMOJI_MAP = {
    '📊': '[图表]',
    '🦴': '[机器狗]',
    '📷': '[相机]',
    '🎯': '[目标]',
    '🔍': '[检测]',
    '📡': '[通信]',
    '🌐': '[网络]',
    '📹': '[视频]',
    '🔬': '[分析]',
    '🌡️': '[温度]',
    '✅': '[通过]',
    '⚠️': '[警告]',
    '❌': '[失败]',
    '📄': '[文档]',
    '🔧': '[工具]',
    '📦': '[包]',
    '🚀': '[启动]',
}

def check_prerequisites():
    """检查前置条件"""
    print("🔍 检查转换工具...")
    
    # 检查pandoc
    try:
        result = subprocess.run(["pandoc", "--version"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("  ✅ pandoc已安装")
        else:
            print("  ❌ pandoc未安装，请运行: sudo apt-get install pandoc")
            return False
    except FileNotFoundError:
        print("  ❌ pandoc未安装，请运行: sudo apt-get install pandoc")
        return False
    
    # 检查模板
    if TEMPLATE_FILE.exists():
        print(f"  ✅ 找到模板: {TEMPLATE_FILE}")
    else:
        print(f"  ⚠️ 未找到模板: {TEMPLATE_FILE}")
        print("     将使用默认模板")
    
    return True

def preprocess_md(content: str) -> str:
    """预处理Markdown内容"""
    
    # 移除HTML标签
    content = re.sub(r'<br\s*/?>', '\n', content)
    content = re.sub(r'<[^>]+>', '', content)
    
    # 替换emoji
    for emoji, text in EMOJI_MAP.items():
        content = content.replace(emoji, text)
    
    return content

def convert_md_to_docx(md_file: Path) -> bool:
    """转换单个Markdown文件为DOCX"""
    
    # 预处理
    content = md_file.read_text(encoding='utf-8')
    content = preprocess_md(content)
    
    # 临时保存预处理后的文件
    temp_file = md_file.parent / f"_temp_{md_file.name}"
    temp_file.write_text(content, encoding='utf-8')
    
    try:
        # 构建输出路径
        output_file = OUTPUT_DIR / f"{md_file.stem}.docx"
        
        # 构建pandoc命令
        cmd = [
            "pandoc",
            str(temp_file),
            "-o", str(output_file),
            "--from", "markdown+gfm+task_lists",
            "--to", "docx",
            "--metadata", f"title={md_file.stem}",
            "--metadata", "author=陈伟",
            "--metadata", "date=2025-09-16",
            "--metadata", "subject=绝影Lite3电力巡检系统技术文档",
            "--metadata", "keywords=电力巡检,机器狗,裂缝检测,温度监测",
        ]
        
        # 如果有模板，使用模板
        if TEMPLATE_FILE.exists():
            cmd.extend(["--reference-doc", str(TEMPLATE_FILE)])
        
        # 执行转换
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"  ✅ {md_file.name} -> {output_file.name}")
            return True
        else:
            print(f"  ❌ {md_file.name} 转换失败:")
            print(f"     {result.stderr}")
            return False
            
    finally:
        # 清理临时文件
        if temp_file.exists():
            temp_file.unlink()

def create_delivery_package():
    """创建交付包"""
    import zipfile
    
    docx_files = sorted(OUTPUT_DIR.glob("*.docx"))
    if not docx_files:
        print("❌ 未找到DOCX文件")
        return False
    
    package_name = f"绝影Lite3_技术文档包_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    
    with zipfile.ZipFile(package_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 添加DOCX文件
        for docx_file in docx_files:
            zipf.write(docx_file, docx_file.name)
        
        # 添加README
        readme_content = f"""绝影Lite3电力巡检系统 - 技术文档包
========================================

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
文档数量: {len(docx_files)}

文档列表:
"""
        for docx_file in docx_files:
            readme_content += f"  - {docx_file.name}\n"
        
        readme_content += f"""
使用说明:
1. 请阅读各文档了解系统架构和部署流程
2. 文档采用标准商业格式，可直接打印或编辑
3. 如有疑问，请联系项目负责人

联系信息:
- 项目负责人: 陈伟
- GitHub: https://github.com/CosmicVortex/lite3-power-inspection
- 版本: V1.7
"""
        zipf.writestr('README.txt', readme_content)
    
    print(f"\n✅ 交付包已创建: {package_name}")
    return True

def main():
    """主函数"""
    print("=" * 60)
    print("绝影Lite3项目文档转换工具")
    print("=" * 60)
    
    # 检查前置条件
    if not check_prerequisites():
        sys.exit(1)
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 获取所有Markdown文件
    md_files = sorted(DOCS_DIR.glob("*.md"))
    if not md_files:
        print("❌ 未找到Markdown文档")
        sys.exit(1)
    
    print(f"\n📄 开始转换 {len(md_files)} 个文档...")
    print("-" * 60)
    
    # 转换文档
    success_count = 0
    for md_file in md_files:
        if convert_md_to_docx(md_file):
            success_count += 1
    
    print("-" * 60)
    print(f"\n✅ 转换完成: {success_count}/{len(md_files)}")
    
    if success_count == len(md_files):
        # 创建交付包
        print("\n📦 创建交付包...")
        create_delivery_package()
    else:
        print(f"\n⚠️ 有 {len(md_files) - success_count} 个文档转换失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
