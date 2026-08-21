@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================
echo  绝影Lite3 离线安装脚本 (Windows版)
echo ============================================
echo.

:: 检查参数
if "%~1"=="" (
    echo 用法: offline_install.bat [sensors|monitor|all]
    echo.
    echo 参数:
    echo   sensors - 安装感知主机依赖
    echo   monitor - 安装监测平台依赖
    echo   all     - 安装全部依赖
    echo.
    pause
    exit /b 1
)

set WHEEL_DIR=%~dp0..\offline-deploy\%~1

if not exist "%WHEEL_DIR%" (
    echo [错误] 离线包目录不存在: %WHEEL_DIR%
    pause
    exit /b 1
)

echo [信息] 找到wheel包目录: %WHEEL_DIR%
echo.

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

python --version
echo.

:: 创建虚拟环境
if not exist "%~dp0..\venv" (
    echo [信息] 创建虚拟环境...
    python -m venv "%~dp0..\venv"
)

:: 激活虚拟环境
call "%~dp0..\venv\Scripts\activate.bat"

:: 安装依赖
echo [信息] 开始安装...
python -m pip install --no-index --find-links="%WHEEL_DIR%" "%WHEEL_DIR%\*.whl" -q

echo.
echo ============================================
echo  ✅ %~1 依赖安装完成
echo ============================================
echo.
echo 项目根目录: %~dp0..
echo 虚拟环境:   %~dp0..\venv
echo.
pause
