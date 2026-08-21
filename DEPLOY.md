# Lite3 Monitor Platform - Deployment Guide

## Quick Start (Windows)

### Method 1: One-Click Deploy
Double-click: `scripts\deploy_oneclick.bat`

### Method 2: Manual Start
Double-click: `scripts\start_monitor_fixed.bat`

---

## Deployment Steps

### 1. Extract Package
```cmd
# Extract to your desired location
# Example: D:\lite3-monitor\
```

### 2. Install Python Dependencies (First Time Only)
```cmd
cd D:\lite3-monitor
pip install -r monitor_platform\requirements.txt
```

### 3. Start Platform
```cmd
# Method 1: One-click deploy
scripts\deploy_oneclick.bat

# Method 2: Manual start
scripts\start_monitor_fixed.bat
```

---

## Access URLs

| Service | URL |
|---------|-----|
| Web Interface | http://localhost:8000 |
| API Documentation | http://localhost:8000/docs |
| WebSocket | ws://localhost:8765/ws |

---

## Prerequisites

### Required
- Python 3.8+
- pip

### Optional (for frontend build)
- Node.js 18+
- pnpm 8+

> If Node.js/pnpm is not installed, the script will skip frontend build automatically.

---

## Troubleshooting

### Port Already in Use
If port 8000 or 8765 is occupied, modify in `monitor_platform/server.py`:
```python
WS_PORT = 8765  # WebSocket port
HTTP_PORT = 8000  # HTTP port
```

### Python Not Found
Install Python from: https://www.python.org/downloads/
Make sure to check "Add Python to PATH" during installation.

### Dependency Installation Failed
```cmd
pip install --upgrade pip
pip install -r monitor_platform\requirements.txt --no-cache-dir
```

---

## Version Info

- System Version: V1.7
- Frontend: Vue 3.5 + Element Plus 2.13
- Backend: FastAPI + WebSocket
- Update Date: 2025-09-16
