@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo Monitor Platform Starting...
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python 3.8+: https://www.python.org/downloads/
    pause
    exit /b 1
)

python --version
echo.

:: Create virtual environment if not exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Install dependencies
echo Installing dependencies...
pip install -q -r monitor_platform\requirements.txt

echo.
echo ============================================
echo Monitor Platform Started Successfully!
echo ============================================
echo.
echo   Web Interface:   http://localhost:8000
echo   API Docs:        http://localhost:8000/docs
echo   WebSocket:       ws://localhost:8765
echo.
echo   Press Ctrl+C to stop
echo.

python monitor_platform/server.py
pause
