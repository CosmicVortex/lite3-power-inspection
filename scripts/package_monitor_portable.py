#!/usr/bin/env python3
"""Create portable monitor platform package"""

import zipfile
import os
from pathlib import Path
from datetime import datetime

def create_portable_package(output_dir: str = "deliverables"):
    """Create portable deployment package"""
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Files to include
    files_to_include = [
        ("monitor_platform/server.py", "monitor_platform/server.py"),
        ("monitor_platform/__init__.py", "monitor_platform/__init__.py"),
        ("monitor_platform/requirements.txt", "monitor_platform/requirements.txt"),
        ("scripts/start_monitor.py", "scripts/start_monitor.py"),
        ("scripts/start_monitor.sh", "start_monitor.sh"),
        ("scripts/start_monitor.bat", "start_monitor.bat"),
    ]
    
    # README content inline
    readme_content = """Monitor Platform Portable Package
==================================

Version: V1.7
Created: {date}

Quick Start:
  Linux/macOS: ./start_monitor.sh
  Windows:     start_monitor.bat

Access:
  Web: http://localhost:8000
  API: http://localhost:8000/docs
  WS:  ws://localhost:8765

Requirements:
  - Python 3.8+
  - No GPU required
""".format(date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    # Create ZIP package
    package_name = "monitor-platform-portable.zip"
    package_path = output_path / package_name
    
    print(f"Creating portable package: {package_path}")
    
    with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add Python files
        for src, dst in files_to_include:
            src_path = Path(src)
            if src_path.exists():
                zipf.write(src, dst)
                print(f"  OK {dst}")
            else:
                print(f"  SKIP {src} (not found)")
        
        # Add README
        zipf.writestr("README.txt", readme_content)
        print(f"  OK README.txt")
    
    # Set executable permission for shell script
    if os.name != 'nt' and Path("scripts/start_monitor.sh").exists():
        try:
            os.chmod("scripts/start_monitor.sh", 0o755)
        except:
            pass
    
    # Show file size
    file_size = package_path.stat().st_size
    print(f"\nPackage created: {package_path}")
    print(f"Size: {file_size / 1024:.1f} KB")
    print(f"\nUsage:")
    print(f"  1. Unzip to any directory")
    print(f"  2. Run start_monitor.sh (Linux/macOS) or start_monitor.bat (Windows)")
    print(f"  3. Access http://localhost:8000")

if __name__ == "__main__":
    create_portable_package()
