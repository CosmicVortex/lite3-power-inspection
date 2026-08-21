#!/bin/bash
# Monitor Platform Startup Script (Portable)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "Monitor Platform Starting..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found"
    echo "Please install Python 3.8+: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "Detected Python $PYTHON_VERSION"
echo ""

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r monitor_platform/requirements.txt

# Start service
echo ""
echo "============================================"
echo "Monitor Platform Started Successfully!"
echo "============================================"
echo ""
echo "  Web Interface:   http://localhost:8000"
echo "  API Docs:        http://localhost:8000/docs"
echo "  WebSocket:       ws://localhost:8765/ws"
echo ""
echo "  Press Ctrl+C to stop"
echo ""

python3 monitor_platform/server.py
