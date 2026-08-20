#!/bin/bash
# 绝影Lite3 部署准备脚本
# 用途：打包部署包并生成部署说明

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_ROOT="/tmp/lite3_deploy"
PACKAGE_NAME="lite3-power-inspection"

echo "=========================================="
echo "绝影Lite3 部署包准备"
echo "=========================================="
echo ""

# 创建部署目录
echo "[1/4] 创建部署目录..."
rm -rf "$DEPLOY_ROOT"
mkdir -p "$DEPLOY_ROOT"
echo "  ✓ 部署目录: $DEPLOY_ROOT"
echo ""

# 复制项目文件
echo "[2/4] 复制项目文件..."
cp -r "$PROJECT_ROOT" "$DEPLOY_ROOT/$PACKAGE_NAME"

# 清理不需要的文件
cd "$DEPLOY_ROOT/$PACKAGE_NAME"
rm -rf .git
rm -rf __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
rm -rf data/logs/*
rm -rf data/cache/*
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true

echo "  ✓ 项目文件已复制"
echo ""

# 生成部署包清单
echo "[3/4] 生成部署说明..."
cat > "$DEPLOY_ROOT/$PACKAGE_NAME/DEPLOY.md" << 'EOF'
# 绝影Lite3 部署包说明

## 部署包信息

- **名称**: lite3-power-inspection
- **版本**: V1.6
- **编制日期**: 2026-08-19
- **传输方式**: MobaXterm SCP/SFTP

## 快速部署

```bash
# 1. 传输到机器狗
scp -r lite3-power-inspection ysc@192.168.1.103:/home/ysc/

# 2. SSH登录机器狗
ssh ysc@192.168.1.103
# 密码: '（英文单引号）

# 3. 进入项目目录
cd /home/ysc/lite3-power-inspection

# 4. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 5. 安装依赖
pip install -r requirements.txt

# 6. 运行诊断
./scripts/run_diagnostic.sh

# 7. 启动演示
python3 scripts/demo_12min.py --mode simulation
```

## 详细部署步骤

请查看完整文档：docs/01-技术方案/09-部署指南.md
EOF

echo "  ✓ 部署说明已生成"
echo ""

# 生成校验和
echo "[4/4] 生成校验和..."
cd "$DEPLOY_ROOT"
tar czf "${PACKAGE_NAME}.tar.gz" "$PACKAGE_NAME"
md5sum "${PACKAGE_NAME}.tar.gz" > "${PACKAGE_NAME}.tar.gz.md5"
echo "  ✓ 打包完成: ${PACKAGE_NAME}.tar.gz"
echo "  ✓ 校验和: $(cat ${PACKAGE_NAME}.tar.gz.md5)"
echo ""

# 输出总结
echo "=========================================="
echo "部署包准备完成"
echo "=========================================="
echo ""
echo "部署包位置: $DEPLOY_ROOT/${PACKAGE_NAME}.tar.gz"
echo "文件大小: $(du -sh $DEPLOY_ROOT/${PACKAGE_NAME}.tar.gz | cut -f1)"
echo ""
echo "校验和:"
cat "$DEPLOY_ROOT/${PACKAGE_NAME}.tar.gz.md5"
echo ""
echo "传输命令:"
echo "  scp $DEPLOY_ROOT/${PACKAGE_NAME}.tar.gz ysc@192.168.1.103:/home/ysc/"
echo ""
echo "解压命令（在机器狗上执行）:"
echo "  cd /home/ysc"
echo "  tar xzf ${PACKAGE_NAME}.tar.gz"
echo "  cd ${PACKAGE_NAME}"
echo ""
echo "=========================================="
