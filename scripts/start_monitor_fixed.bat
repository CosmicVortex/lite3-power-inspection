@echo off
chcp 437 >nul
setlocal enabledelayedexpansion

:: Get the project root directory (parent of scripts)
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

echo.
echo ============================================
echo  Lite3 Monitor Platform - Start Script
echo ============================================
echo.

:: Change to project root
cd /d "%PROJECT_DIR%"
echo Working directory: %CD%
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    pause
    exit /b 1
)

echo Python version:
python --version
echo.

:: Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo Virtual environment activated
)

:: Install dependencies
echo Installing dependencies...
pip install -q -r monitor_platform\requirements.txt 2>nul

echo.
echo ============================================
echo  Platform Started Successfully
echo ============================================
echo.
echo   Web Interface:   http://localhost:8000
echo   API Docs:        http://localhost:8000/docs
echo   WebSocket:       ws://localhost:8765/ws
echo.
echo   Press Ctrl+C to stop
echo.

python monitor_platform\server.py
pause
