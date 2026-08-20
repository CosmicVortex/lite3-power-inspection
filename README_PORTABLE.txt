# Monitor Platform Portable Package
# Version: V1.7
# Date: 2025-09-16

## Quick Start

### Linux/macOS
```bash
unzip monitor-platform-portable.zip
cd monitor-platform
chmod +x start_monitor.sh
./start_monitor.sh
```

### Windows
```cmd
expand-archive -Path monitor-platform-portable.zip -DestinationPath .
cd monitor-platform
start_monitor.bat
```

## Access
- Web Interface: http://localhost:8000
- API Docs: http://localhost:8000/docs
- WebSocket: ws://localhost:8765

## Requirements
- Python 3.8+
- No GPU required
- No CUDA required

## Files
- monitor_platform/server.py - Main application
- monitor_platform/requirements.txt - Dependencies
- scripts/start_monitor.py - Startup script
- start_monitor.sh - Linux/macOS launcher
- start_monitor.bat - Windows launcher

## Troubleshooting
- Port in use: Modify WS_PORT/HTTP_PORT in server.py
- Connection failed: Check firewall settings for ports 8000/8765
- Module not found: Run pip install -r monitor_platform/requirements.txt
