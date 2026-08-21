@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================
echo  Lite3 Monitor Platform - Deploy Script
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python 3.8+: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] Python check passed
python --version
echo.

:: Build Frontend (optional)
where pnpm >nul 2>&1
if not errorlevel 1 (
    echo [2/4] Building frontend...
    if exist "frontend" (
        cd frontend
        pnpm install --no-frozen-lockfile 2>nul || pnpm install
        pnpm build
        cd ..
        echo Frontend build completed
    )
) else (
    echo [2/4] Skipping frontend build (pnpm not found)
)
echo.

:: Install Python dependencies
echo [3/4] Installing Python dependencies...
if exist "requirements.txt" (
    pip install -q -r requirements.txt
)
if exist "monitor_platform\requirements.txt" (
    pip install -q -r monitor_platform\requirements.txt
)
echo Dependencies installed
echo.

:: Start Server
echo [4/4] Starting server...
echo.
echo ============================================
echo  Platform started successfully
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
