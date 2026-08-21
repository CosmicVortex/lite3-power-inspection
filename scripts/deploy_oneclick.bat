@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================
echo  绝影Lite3监测平台 - 一键部署脚本
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python 3.8+
    pause
    exit /b 1
)

echo [1/4] Python检查通过
python --version
echo.

:: Build Frontend (optional)
where pnpm >nul 2>&1
if not errorlevel 1 (
    echo [2/4] 构建前端...
    cd frontend
    pnpm install >nul 2>&1
    pnpm build
    cd ..
    echo ✓ 前端构建完成
) else (
    echo [2/4] 跳过前端构建 (pnpm未安装)
)
echo.

:: Install Python dependencies
echo [3/4] 安装Python依赖...
if exist requirements.txt (
    pip install -q -r requirements.txt
)
if exist monitor_platform\requirements.txt (
    pip install -q -r monitor_platform\requirements.txt
)
echo ✓ 依赖安装完成
echo.

:: Start Server
echo [4/4] 启动服务...
echo.
echo ============================================
echo  监测平台启动成功
echo ============================================
echo.
echo   Web界面:   http://localhost:8000
echo   API文档:   http://localhost:8000/docs
echo   WebSocket: ws://localhost:8765/ws
echo.
echo   按 Ctrl+C 停止服务
echo.

python monitor_platform\server.py

pause
