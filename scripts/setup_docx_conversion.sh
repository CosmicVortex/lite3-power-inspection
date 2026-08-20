#!/bin/bash
# 绝影Lite3项目 - DOCX转换环境准备脚本
# 安装必要的转换工具

set -e

echo "================================================"
echo "绝影Lite3项目 - DOCX转换环境准备"
echo "================================================"
echo ""

# 检查并安装pandoc
echo "🔧 检查pandoc..."
if ! command -v pandoc &> /dev/null; then
    echo "  ⚠️  pandoc未安装，正在安装..."
    sudo apt-get update -qq
    sudo apt-get install -y pandoc
    echo "  ✅ pandoc已安装"
else
    echo "  ✅ pandoc已安装: $(pandoc --version | head -1)"
fi

# 检查并安装python-docx
echo ""
echo "🔧 检查python-docx..."
if ! python3 -c "import docx" 2>/dev/null; then
    echo "  ⚠️  python-docx未安装，正在安装..."
    if command -v uv &> /dev/null; then
        uv pip install python-docx --quiet
    else
        python3 -m pip install python-docx --quiet
    fi
    echo "  ✅ python-docx已安装"
else
    echo "  ✅ python-docx已安装"
fi

# 创建模板目录
echo ""
echo "🔧 创建模板目录..."
mkdir -p templates
mkdir -p deliverables/docx
echo "  ✅ 目录创建完成"

# 创建模板
echo ""
echo "🔧 创建商业级模板..."
python3 scripts/create_docx_template.py

echo ""
echo "================================================"
echo "✅ 环境准备完成！"
echo "================================================"
echo ""
echo "下一步："
echo "  1. 运行转换脚本: python3 scripts/convert_docs_to_docx.py"
echo "  2. 检查生成的DOCX文件: ls deliverables/docx/"
echo "  3. 创建交付包: python3 scripts/create_delivery_package.py"
echo ""
