#!/bin/bash
# 绝影Lite3 文档优化检查脚本
# 用法: ./scripts/check_docs.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=========================================="
echo "绝影Lite3 文档完整性检查"
echo "=========================================="
echo ""

# 检查核心文档
echo "[检查] 核心文档..."
core_docs=(
    "README.md"
    "CHANGELOG.md"
    "docs/01-技术方案/01-系统架构设计.md"
    "docs/01-技术方案/02-API接口文档.md"
    "docs/01-技术方案/06-部署运维指南.md"
    "docs/01-技术方案/09-部署指南.md"
    "docs/01-技术方案/12-硬件配置评估报告.md"
    "docs/02-项目管理/10-部署就绪审查报告.md"
    "docs/02-项目管理/11-部署包使用说明.md"
    "docs/02-项目管理/13-第四次全面审查报告.md"
)

missing=0
for doc in "${core_docs[@]}"; do
    if [ -f "$PROJECT_ROOT/$doc" ]; then
        lines=$(wc -l < "$PROJECT_ROOT/$doc")
        size=$(ls -lh "$PROJECT_ROOT/$doc" | awk '{print $5}')
        echo "  ✓ $doc ($lines lines, $size)"
    else
        echo "  ✗ $doc (缺失)"
        missing=$((missing + 1))
    fi
done

echo ""
echo "=========================================="
echo "检查结果: $missing 个文档缺失"
echo "=========================================="

if [ $missing -eq 0 ]; then
    echo "✓ 所有核心文档完整"
    exit 0
else
    echo "⚠ 存在缺失文档，请检查"
    exit 1
fi
