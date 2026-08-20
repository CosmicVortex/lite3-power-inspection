#!/usr/bin/env python3
"""
监测平台便携部署包创建工具
"""

import zipfile
import subprocess
import os
from pathlib import Path
from datetime import datetime

def create_portable_package(output_dir: str = "deliverables"):
    """创建便携部署包"""
    
    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 定义要包含的文件
    files_to_include = [
        ("monitor_platform/server.py", "monitor_platform/server.py"),
        ("monitor_platform/__init__.py", "monitor_platform/__init__.py"),
        ("monitor_platform/requirements.txt", "monitor_platform/requirements.txt"),
        ("scripts/start_monitor.py", "scripts/start_monitor.py"),
    ]
    
    # 创建README
    readme_content = f"""监测平台便携部署包
==================

版本: V1.7
创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
依赖大小: 约2.5MB

## 启动步骤

### Linux/macOS
```bash
# 解压
unzip monitor-platform-portable.zip
cd monitor-platform

# 启动（自动创建虚拟环境）
./start_monitor.sh
```

### Windows
```cmd
:: 解压
expand-archive -Path monitor-platform-portable.zip -DestinationPath .

:: 启动
start_monitor.bat
```

## 访问地址
- Web界面: http://localhost:8000
- API文档: http://localhost:8000/docs
- WebSocket: ws://localhost:8765

## 系统要求
- Python 3.8+
- 无GPU要求
- 无CUDA要求

## 网络配置
确保机器狗与本机在同一网络，修改config/inspection_config.yaml中的server_url。

## 故障排查
- 端口被占用: 修改server.py中的WS_PORT/HTTP_PORT
- 连接失败: 检查防火墙设置，允许8000/8765端口
"""
    
    # 创建启动脚本（Linux/macOS）
    startup_script = '''#!/bin/bash
# 监测平台启动脚本（便携版）
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 监测平台启动中..."
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到Python3"
    echo "   请安装Python 3.8+: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ 检测到Python $PYTHON_VERSION"

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📦 安装依赖..."
pip install -q -r monitor_platform/requirements.txt

# 启动服务
echo ""
echo "✅ 监测平台启动成功!"
echo ""
echo "   Web界面:   http://localhost:8000"
echo "   API文档:   http://localhost:8000/docs"
echo "   WebSocket: ws://localhost:8765"
echo ""
echo "   按 Ctrl+C 停止服务"
echo ""

python3 monitor_platform/server.py
'''
    
    # 创建启动脚本（Windows）
    startup_script_win = '''@echo off
chcp 65001 >nul
echo.
echo 🚀 监测平台启动中...
echo.

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到Python
    echo    请安装Python 3.8+: https://www.python.org/downloads/
    pause
    exit /b 1
)

python --version
echo.

:: 创建虚拟环境
if not exist "venv" (
    echo 📦 创建虚拟环境...
    python -m venv venv
)

:: 激活虚拟环境
call venv\\Scripts\\activate.bat

:: 安装依赖
echo 📦 安装依赖...
pip install -q -r monitor_platform\\requirements.txt

:: 启动服务
echo.
echo ✅ 监测平台启动成功!
echo.
echo    Web界面:   http://localhost:8000
echo    API文档:   http://localhost:8000/docs
echo    WebSocket: ws://localhost:8765
echo.
echo    按 Ctrl+C 停止服务
echo.

python monitor_platform/server.py
pause
'''
    
    # 创建ZIP包
    package_name = "monitor-platform-portable.zip"
    package_path = output_path / package_name
    
    print(f"📦 创建便携包: {package_path}")
    
    with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 添加Python文件
        for src, dst in files_to_include:
            if Path(src).exists():
                zipf.write(src, dst)
                print(f"  ✅ {dst}")
        
        # 添加README
        zipf.writestr("README.txt", readme_content)
        print(f"  ✅ README.txt")
        
        # 添加启动脚本
        zipf.writestr("start_monitor.sh", startup_script)
        print(f"  ✅ start_monitor.sh")
        
        zipf.writestr("start_monitor.bat", startup_script_win)
        print(f"  ✅ start_monitor.bat")
    
    # 设置权限（仅Linux/macOS）
    if os.name != 'nt':
        try:
            os.chmod("start_monitor.sh", 0o755)
        except:
            pass
    
    # 显示文件大小
    file_size = package_path.stat().st_size
    print(f"\n✅ 便携包创建完成!")
    print(f"   文件路径: {package_path}")
    print(f"   文件大小: {file_size / 1024:.1f} KB")
    print(f"\n💡 使用方法:")
    print(f"   1. 解压到任意目录")
    print(f"   2. 运行 start_monitor.sh (Linux/macOS) 或 start_monitor.bat (Windows)")
    print(f"   3. 访问 http://localhost:8000")

if __name__ == "__main__":
    create_portable_package()
