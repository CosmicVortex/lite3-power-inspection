#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监测平台服务（Flask版本）- 【已废弃】

警告：此模块已被废弃，请勿使用！

请使用以下替代方案：
- 监测平台服务端：monitor_platform/server.py (FastAPI + WebSocket)
- 启动命令：python3 scripts/start_monitor.py

废弃原因：
1. 功能不完整，缺少WebSocket实时推送
2. 端口冲突（5000 vs 8000）
3. 数据结构与前端不匹配
4. 未被项目实际使用

保留此文件仅为历史参考，将在下个大版本中删除。
"""

import sys
import warnings

# 显示废弃警告
warnings.warn(
    "WARNING: src.app.monitor_platform is DEPRECATED!\n"
    "Please use monitor_platform/server.py instead.\n"
    "Start command: python3 scripts/start_monitor.py",
    DeprecationWarning,
    stacklevel=2
)

# 阻止直接导入使用
if __name__ == "__main__":
    print("=" * 60)
    print("⚠️  警告：此模块已废弃！")
    print("=" * 60)
    print()
    print("请勿使用此脚本启动监测平台。")
    print()
    print("正确做法：")
    print("  python3 scripts/start_monitor.py")
    print()
    print("详情参见：")
    print("  docs/01-技术方案/06-部署运维指南.md")
    print("=" * 60)
    sys.exit(1)
