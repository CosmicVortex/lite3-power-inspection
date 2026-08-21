#!/usr/bin/env python3
"""
绝影Lite3监测平台 - 一键部署脚本
支持前后端一体化部署
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def check_prerequisites():
    """检查前置条件"""
    print("\n检查系统环境...")
    
    # 检查Python
    try:
        result = subprocess.run([sys.executable, '--version'], capture_output=True, text=True)
        print(f"✓ Python: {result.stdout.strip()}")
    except:
        print("✗ Python未找到")
        return False
    
    # 检查Node.js和pnpm
    node_ok = False
    pnpm_ok = False
    
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Node.js: {result.stdout.strip()}")
            node_ok = True
        else:
            print("⚠ Node.js未找到")
    except:
        print("⚠ Node.js未找到")
    
    try:
        result = subprocess.run(['pnpm', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ pnpm: {result.stdout.strip()}")
            pnpm_ok = True
        else:
            print("⚠ pnpm未找到")
    except:
        print("⚠ pnpm未找到")
    
    return node_ok and pnpm_ok

def build_frontend():
    """构建前端"""
    frontend_dir = Path(__file__).parent.parent / 'frontend'
    if not frontend_dir.exists():
        print("✗ 前端目录不存在")
        return False
    
    print("\n构建Vue3前端...")
    
    # 安装依赖
    subprocess.run(['pnpm', 'install'], cwd=frontend_dir, capture_output=True)
    
    # 构建
    result = subprocess.run(['pnpm', 'build'], cwd=frontend_dir, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"✗ 前端构建失败: {result.stderr}")
        return False
    
    print("✓ 前端构建完成")
    return True

def install_python_deps():
    """安装Python依赖"""
    print("\n安装Python依赖...")
    
    requirements = Path(__file__).parent.parent / 'requirements.txt'
    if requirements.exists():
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(requirements), '-q'], 
                      capture_output=True)
        print("✓ Python依赖安装完成")
    
    # monitor_platform依赖
    monitor_reqs = Path(__file__).parent / 'requirements.txt'
    if monitor_reqs.exists():
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(monitor_reqs), '-q'], 
                      capture_output=True)
        print("✓ Monitor依赖安装完成")
    
    return True

def start_server():
    """启动服务器"""
    server_script = Path(__file__).parent / 'server.py'
    print("\n启动监测平台服务器...")
    print(f"Web界面: http://localhost:8000")
    print(f"API文档: http://localhost:8000/docs")
    print(f"WebSocket: ws://localhost:8765/ws")
    print("\n按 Ctrl+C 停止服务\n")
    
    subprocess.run([sys.executable, str(server_script)])

def main():
    print("=" * 50)
    print("绝影Lite3监测平台 - 一键部署")
    print("=" * 50)
    
    # 检查前置条件
    if not check_prerequisites():
        print("\n⚠ 警告: Node.js/pnpm未找到，将跳过前端构建")
        build_frontend_flag = input("\n是否继续？(y/n): ").lower()
        if build_frontend_flag != 'y':
            sys.exit(0)
    else:
        # 构建前端
        if not build_frontend():
            print("\n✗ 前端构建失败，请检查错误信息")
            sys.exit(1)
    
    # 安装Python依赖
    install_python_deps()
    
    # 启动服务器
    start_server()

if __name__ == '__main__':
    main()
