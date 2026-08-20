#!/bin/bash
# 绝影Lite3 系统功能完成度全面审查脚本
# 用法: ./scripts/run_full_review.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "绝影Lite3 系统功能完成度全面审查"
echo "=========================================="
echo ""
echo "审查时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 运行Python审查脚本
$PROJECT_ROOT/venv/bin/python "$SCRIPT_DIR/full_review.py" 2>/dev/null || \
python3 "$SCRIPT_DIR/full_review.py"

echo ""
echo "=========================================="
echo "审查完成"
echo "=========================================="
echo ""
echo "详细报告: docs/02-项目管理/12-功能完成度最终审查报告.md"
echo ""
