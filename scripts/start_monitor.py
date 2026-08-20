#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor Platform Startup Script

Usage:
  python3 start_monitor.py                    # Start monitor platform
  python3 start_monitor.py --diagnostic       # Run diagnostic first
  python3 start_monitor.py --port 8080        # Specify port
  python3 start_monitor.py --host 0.0.0.0     # Specify host
"""

import sys
import asyncio
import logging
from pathlib import Path

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """Check required dependencies"""
    logger.info("Checking Python dependencies...")
    
    required = {
        "fastapi": "Web framework",
        "uvicorn": "ASGI server",
        "websockets": "WebSocket communication",
        "pydantic": "Data validation",
    }
    
    missing = []
    for module, purpose in required.items():
        try:
            __import__(module)
            logger.debug(f"  OK {module} ({purpose})")
        except ImportError:
            logger.error(f"  MISSING {module} ({purpose})")
            missing.append(module)
    
    if missing:
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        logger.info("Please run: pip install -r monitor_platform/requirements.txt")
        return False
    
    logger.info("All dependencies check passed")
    return True


async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Yueying Lite3 Monitor Platform")
    parser.add_argument("--diagnostic", action="store_true", help="Run environment diagnostic before start")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")
    parser.add_argument("--ws-port", type=int, default=8765, help="WebSocket port (default: 8765)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Listen address (default: 0.0.0.0)")
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Yueying Lite3 Monitor Platform Starting")
    logger.info("=" * 60)
    
    # Run diagnostic
    if args.diagnostic:
        logger.info("Running environment diagnostic...")
        from scripts.detect_environment import main as run_diagnostic
        run_diagnostic()
    
    # Check dependencies
    if not check_dependencies():
        logger.error("Dependency check failed, exiting")
        sys.exit(1)
    
    # Start service
    from monitor_platform.server import app, monitor
    
    logger.info(f"HTTP service: http://{args.host}:{args.port}")
    logger.info(f"WebSocket: ws://{args.host}:{args.ws_port}/ws")
    logger.info("")
    logger.info("Press Ctrl+C to stop service")
    logger.info("=" * 60)
    
    import uvicorn
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        ws_port=args.ws_port,
        log_level="info"
    )


if __name__ == "__main__":
    asyncio.run(main())
