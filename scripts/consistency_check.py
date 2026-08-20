#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3 系统功能完成度审查工具

检查项目代码、文档和配置的一致性，生成审查报告。
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class ConsistencyChecker:
    """一致性检查器"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.info = []
    
    def check_document_consistency(self):
        """检查文档一致性"""
        print("\n【文档一致性检查】")
        print("-" * 70)
        
        # 读取关键文档
        docs = {
            "README": PROJECT_ROOT / "README.md",
            "CHANGELOG": PROJECT_ROOT / "CHANGELOG.md",
            "deploy_guide": PROJECT_ROOT / "docs/01-技术方案/06-部署运维指南.md",
            "api_doc": PROJECT_ROOT / "docs/01-技术方案/02-API接口文档.md",
        }
        
        contents = {}
        for name, path in docs.items():
            if path.exists():
                contents[name] = path.read_text(encoding="utf-8")
            else:
                self.warnings.append(f"文档不存在: {path.name}")
        
        # 检查版本号
        readme_version = self._extract_version(contents.get("README", ""))
        changelog_version = self._extract_version(contents.get("CHANGELOG", ""))
        
        if readme_version and changelog_version:
            if readme_version != changelog_version:
                self.issues.append(f"版本不一致: README={readme_version}, CHANGELOG={changelog_version}")
            else:
                self.info.append(f"版本号一致: {readme_version}")
        
        # 检查IP地址一致性
        ip_patterns = {
            "运动主机": r"192\.168\.1\.103",
            "云台相机": r"192\.168\.1\.108",
            "监测平台": r"192\.168\.1\.200",
        }
        
        for doc_name, content in contents.items():
            for name, pattern in ip_patterns.items():
                matches = re.findall(pattern, content)
                if matches:
                    self.info.append(f"{doc_name}中{name}IP正确: {matches[0]}")
        
        # 检查路径引用
        old_paths = [
            ("src/app/main.py", "scripts/run_demo.py"),
            ("src/app/monitor_platform.py", "monitor_platform/server.py"),
        ]
        
        for doc_name, content in contents.items():
            for old_path, new_path in old_paths:
                if old_path in content:
                    self.issues.append(f"{doc_name}引用了旧路径 {old_path}，应改为 {new_path}")
        
        # 检查端口号一致性
        port_patterns = {
            "UDP": r"43893",
            "WebSocket": r"8765",
            "RTSP": r"554",
            "HTTP": r"8000",
        }
        
        for doc_name, content in contents.items():
            for name, pattern in port_patterns.items():
                matches = re.findall(pattern, content)
                if matches:
                    self.info.append(f"{doc_name}中{name}端口正确: {pattern}")
    
    def check_code_document_consistency(self):
        """检查代码与文档一致性"""
        print("\n【代码-文档一致性检查】")
        print("-" * 70)
        
        # 检查API文档中的接口定义
        api_doc = PROJECT_ROOT / "docs/01-技术方案/02-API接口文档.md"
        if api_doc.exists():
            content = api_doc.read_text(encoding="utf-8")
            
            # 检查WebSocket端点
            if "ws://192.168.1.200:8765/ws" in content:
                self.info.append("API文档中WebSocket端点正确")
            else:
                self.warnings.append("API文档中WebSocket端点可能不正确")
            
            # 检查消息格式
            if '"payload"' in content or "'payload'" in content:
                self.info.append("API文档中消息格式包含payload字段")
            else:
                self.issues.append("API文档中消息格式缺少payload字段说明")
        
        # 检查配置文件
        config_file = PROJECT_ROOT / "config/inspection_config.yaml"
        if config_file.exists():
            import yaml
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                
                # 检查必要配置项
                required = ["network", "camera", "ptz", "perception"]
                missing = [k for k in required if k not in config]
                if missing:
                    self.issues.append(f"配置文件缺少必要节: {', '.join(missing)}")
                else:
                    self.info.append("配置文件结构完整")
                
                # 检查IP地址
                if config.get("network", {}).get("robot_motion", {}).get("ip") == "192.168.1.103":
                    self.info.append("配置文件中运动主机IP正确")
                else:
                    self.issues.append("配置文件中运动主机IP不正确")
                
                # 检查端口
                if config.get("network", {}).get("robot_motion", {}).get("port") == 43893:
                    self.info.append("配置文件中UDP端口正确")
                else:
                    self.issues.append("配置文件中UDP端口不正确")
                    
            except Exception as e:
                self.issues.append(f"配置文件解析失败: {e}")
    
    def check_code_completeness(self):
        """检查代码完成度"""
        print("\n【代码完成度检查】")
        print("-" * 70)
        
        # 检查核心模块
        modules = [
            ("src/services/simulation_generator.py", "模拟数据生成器"),
            ("src/perception/temperature_monitor.py", "温度监测算法"),
            ("src/storage/sqlite_cache.py", "SQLite缓存"),
            ("src/gateway/udp_controller.py", "UDP控制器"),
            ("src/gateway/ptz_controller.py", "云台控制器"),
            ("src/gateway/websocket_client.py", "WebSocket网关"),
            ("monitor_platform/server.py", "监测平台服务"),
        ]
        
        for module_path, name in modules:
            full_path = PROJECT_ROOT / module_path
            if full_path.exists():
                content = full_path.read_text(encoding="utf-8")
                
                # 检查是否有TODO
                todos = re.findall(r"TODO|FIXME|XXX", content, re.IGNORECASE)
                if todos:
                    self.warnings.append(f"{name}: 存在{len(todos)}个TODO/FIXME标记")
                else:
                    self.info.append(f"{name}: 代码完整")
            else:
                self.issues.append(f"模块缺失: {name} ({module_path})")
        
        # 检查演示脚本
        demo_script = PROJECT_ROOT / "scripts/demo_12min.py"
        if demo_script.exists():
            self.info.append("12分钟演示脚本已创建")
        else:
            self.issues.append("12分钟演示脚本缺失")
    
    def check_requirements_consistency(self):
        """检查依赖文件一致性"""
        print("\n【依赖管理检查】")
        print("-" * 70)
        
        req_file = PROJECT_ROOT / "requirements.txt"
        gpu_req_file = PROJECT_ROOT / "requirements-gpu.txt"
        
        if req_file.exists():
            content = req_file.read_text(encoding="utf-8")
            deps = [line.strip() for line in content if line.strip() and not line.startswith('#')]
            self.info.append(f"核心依赖文件: {len(deps)}个依赖")
        else:
            self.issues.append("requirements.txt文件缺失")
        
        if gpu_req_file.exists():
            content = gpu_req_file.read_text(encoding="utf-8")
            deps = [line.strip() for line in content if line.strip() and not line.startswith('#')]
            self.info.append(f"GPU依赖文件: {len(deps)}个依赖")
        else:
            self.warnings.append("requirements-gpu.txt文件缺失（可选）")
    
    def _extract_version(self, content):
        """从文档中提取版本号"""
        if not content:
            return None
        match = re.search(r'版本.*?V?(\d+\.\d+)', content)
        if match:
            return f"V{match.group(1)}"
        match = re.search(r'Version.*?(\d+\.\d+)', content)
        if match:
            return f"V{match.group(1)}"
        return None
    
    def generate_report(self):
        """生成审查报告"""
        report = []
        report.append("=" * 70)
        report.append("绝影Lite3 系统功能完成度审查报告")
        report.append(f"审查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 70)
        
        report.append("\n【审查结果摘要】")
        report.append(f"  问题: {len(self.issues)}")
        report.append(f"  警告: {len(self.warnings)}")
        report.append(f"  信息: {len(self.info)}")
        
        if self.issues:
            report.append("\n【发现的问题】")
            for issue in self.issues:
                report.append(f"  ❌ {issue}")
        
        if self.warnings:
            report.append("\n【警告】")
            for warning in self.warnings:
                report.append(f"  ⚠️  {warning}")
        
        if self.info:
            report.append("\n【通过项】")
            for info in self.info:
                report.append(f"  ✅ {info}")
        
        report.append("\n" + "=" * 70)
        
        # 判断是否具备部署条件
        if len(self.issues) == 0 and len(self.warnings) <= 3:
            report.append("✅ 系统具备部署条件")
        elif len(self.issues) <= 2:
            report.append("⚠️  系统基本可用，建议修复问题后部署")
        else:
            report.append("❌ 系统不具备部署条件，需要修复问题")
        
        report.append("=" * 70)
        
        return "\n".join(report)


def main():
    checker = ConsistencyChecker()
    
    print("=" * 70)
    print("绝影Lite3 系统功能完成度审查")
    print("=" * 70)
    
    checker.check_document_consistency()
    checker.check_code_document_consistency()
    checker.check_code_completeness()
    checker.check_requirements_consistency()
    
    print("\n" + checker.generate_report())
    
    # 保存报告
    report_path = PROJECT_ROOT / "data" / f"consistency_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(checker.generate_report(), encoding="utf-8")
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    main()
