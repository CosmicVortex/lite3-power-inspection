#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3 环境诊断工具

功能：
1. 检查系统环境（Python版本、操作系统、内存、磁盘）
2. 检查Python依赖包
3. 检测GPU/CUDA环境
4. 测试网络连接
5. 检查配置文件和模型文件
6. 生成诊断报告（HTML/JSON/Markdown）

用法：
    python3 scripts/detect_environment.py [--check-deps] [--check-network] [--full] [--output FILE]
"""

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class DiagnosticResult:
    """诊断结果类"""
    
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.items = []
    
    def add(self, category, name, status, detail="", suggestion=""):
        """添加诊断项
        
        Args:
            category: 类别（系统/依赖/GPU/网络/配置）
            name: 项目名称
            status: 状态（PASS/WARN/FAIL/INFO）
            detail: 详细信息
            suggestion: 建议
        """
        self.items.append({
            "category": category,
            "name": name,
            "status": status,
            "detail": detail,
            "suggestion": suggestion,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_summary(self):
        """获取摘要统计"""
        summary = {"PASS": 0, "WARN": 0, "FAIL": 0, "INFO": 0}
        for item in self.items:
            summary[item["status"]] = summary.get(item["status"], 0) + 1
        return summary
    
    def is_warning(self):
        """是否有警告"""
        return any(item["status"] == "WARN" for item in self.items)
    
    def has_failure(self):
        """是否有失败"""
        return any(item["status"] == "FAIL" for item in self.items)


def check_system_environment(result):
    """检查系统环境"""
    print("\n[1/6] 检查系统环境...")
    
    # Python版本
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 8):
        result.add("系统", "Python版本", "PASS", f"Python {python_version}")
    else:
        result.add("系统", "Python版本", "FAIL", f"Python {python_version}", "需要Python 3.8+")
    
    # 操作系统
    os_name = platform.system()
    os_release = platform.release()
    result.add("系统", "操作系统", "INFO", f"{os_name} {os_release}")
    
    # 内存
    try:
        import psutil
        memory = psutil.virtual_memory()
        available_gb = memory.available / (1024 ** 3)
        total_gb = memory.total / (1024 ** 3)
        if available_gb >= 4:
            result.add("系统", "可用内存", "PASS", f"{available_gb:.1f}GB / {total_gb:.1f}GB")
        else:
            result.add("系统", "可用内存", "WARN", f"{available_gb:.1f}GB / {total_gb:.1f}GB", "建议至少4GB可用内存")
    except ImportError:
        result.add("系统", "内存检测", "INFO", "psutil未安装，跳过内存检测")
    
    # 磁盘空间
    try:
        disk = os.statvfs(str(PROJECT_ROOT))
        free_gb = (disk.f_bavail * disk.f_frsize) / (1024 ** 3)
        if free_gb >= 2:
            result.add("系统", "磁盘空间", "PASS", f"可用 {free_gb:.1f}GB")
        else:
            result.add("系统", "磁盘空间", "WARN", f"可用 {free_gb:.1f}GB", "建议至少2GB可用空间")
    except Exception as e:
        result.add("系统", "磁盘空间", "INFO", f"无法检测磁盘空间: {e}")


def check_dependencies(result):
    """检查Python依赖"""
    print("[2/6] 检查Python依赖...")
    
    # 核心依赖（必需）
    core_deps = {
        "loguru": {"min_version": "0.6.0", "purpose": "日志管理"},
        "numpy": {"min_version": "1.21.0", "purpose": "数值计算"},
        "cv2": {"min_version": "4.5.0", "package": "opencv-python", "purpose": "图像处理"},
        "websockets": {"min_version": "12.0", "purpose": "WebSocket通信"},
        "requests": {"min_version": "2.28.0", "purpose": "HTTP请求"},
        "yaml": {"min_version": "6.0", "package": "pyyaml", "purpose": "配置解析"},
        "fastapi": {"min_version": "0.104.0", "purpose": "Web框架"},
        "uvicorn": {"min_version": "0.24.0", "purpose": "ASGI服务器"},
        "pydantic": {"min_version": "2.0.0", "purpose": "数据验证"},
    }
    
    # GPU依赖（可选）
    gpu_deps = {
        "torch": {"min_version": "2.0.0", "purpose": "深度学习框架"},
        "tensorrt": {"min_version": "8.0.0", "purpose": "GPU推理加速"},
        "onnx": {"min_version": "1.12.0", "purpose": "模型格式"},
    }
    
    installed_core = 0
    missing_core = []
    
    for module_name, info in core_deps.items():
        try:
            module = __import__(module_name)
            version = getattr(module, "__version__", "unknown")
            result.add("依赖", f"{info.get('package', module_name)}", "PASS", f"版本 {version}")
            installed_core += 1
        except ImportError:
            pkg_name = info.get("package", module_name)
            result.add("依赖", pkg_name, "FAIL", "", f"请运行: pip install {pkg_name}>={info['min_version']}")
            missing_core.append(pkg_name)
    
    # 检查GPU依赖
    gpu_available = True
    for module_name in gpu_deps:
        try:
            module = __import__(module_name)
            version = getattr(module, "__version__", "unknown")
            result.add("依赖", module_name, "PASS", f"版本 {version} (GPU模式)")
        except ImportError:
            result.add("依赖", module_name, "INFO", "", "未安装，将使用模拟模式")
            gpu_available = False
    
    if missing_core:
        result.add("依赖", "核心依赖", "FAIL", f"缺少 {len(missing_core)} 个包", f"请运行: pip install -r requirements.txt")
    else:
        result.add("依赖", "核心依赖", "PASS", f"已安装 {installed_core}/{len(core_deps)} 个包")
    
    if not gpu_available:
        result.add("依赖", "GPU依赖", "INFO", "未安装GPU依赖，系统将使用模拟模式")


def check_gpu_environment(result):
    """检查GPU环境"""
    print("[3/6] 检查GPU环境...")
    
    # CUDA
    try:
        result.add("GPU", "CUDA", "INFO", "正在检查CUDA...")
        cuda_version = subprocess.run(
            ["nvcc", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if cuda_version.returncode == 0:
            for line in cuda_version.stdout.split('\n'):
                if 'release' in line:
                    result.add("GPU", "CUDA", "PASS", line.strip())
                    break
        else:
            result.add("GPU", "CUDA", "WARN", "CUDA未安装或不在PATH中", "模拟模式不需要CUDA")
    except FileNotFoundError:
        result.add("GPU", "CUDA", "WARN", "nvcc未找到", "模拟模式不需要CUDA")
    except Exception as e:
        result.add("GPU", "CUDA", "INFO", f"检查CUDA时出错: {e}")
    
    # NVIDIA GPU
    try:
        nvidia_smi = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if nvidia_smi.returncode == 0:
            result.add("GPU", "NVIDIA GPU", "PASS", "检测到NVIDIA GPU")
        else:
            result.add("GPU", "NVIDIA GPU", "WARN", "nvidia-smi失败", "可能没有NVIDIA GPU")
    except FileNotFoundError:
        result.add("GPU", "NVIDIA GPU", "WARN", "nvidia-smi未找到", "可能没有NVIDIA GPU或驱动未安装")
    except Exception as e:
        result.add("GPU", "NVIDIA GPU", "INFO", f"检查GPU时出错: {e}")
    
    # PyTorch GPU支持
    try:
        import torch
        if torch.cuda.is_available():
            result.add("GPU", "PyTorch CUDA", "PASS", f"GPU: {torch.cuda.get_device_name(0)}")
        else:
            result.add("GPU", "PyTorch CUDA", "WARN", "PyTorch未检测到CUDA", "将使用CPU推理（速度较慢）")
    except ImportError:
        result.add("GPU", "PyTorch", "INFO", "PyTorch未安装", "模拟模式不需要PyTorch")
    except Exception as e:
        result.add("GPU", "PyTorch", "INFO", f"检查PyTorch时出错: {e}")


def check_network(result):
    """检查网络连接"""
    print("[4/6] 检查网络连接...")
    
    # 目标设备
    targets = [
        {"ip": "192.168.1.103", "port": 43893, "protocol": "UDP", "name": "运动主机"},
        {"ip": "192.168.1.108", "port": 80, "protocol": "HTTP", "name": "云台相机"},
        {"ip": "192.168.1.108", "port": 554, "protocol": "RTSP", "name": "RTSP流"},
        # 注意：监测平台独立部署在笔记本上，监听本地8765端口
        # 感知主机通过WebSocket连接到笔记本的192.168.1.103:8765
    ]
    
    unreachable = []
    
    for target in targets:
        try:
            if target["protocol"] == "UDP":
                # UDP是无连接协议，只能测试连通性
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(2.0)
                try:
                    sock.connect((target["ip"], target["port"]))
                    sock.send(b'\x00' * 8)
                    result.add("网络", f"{target['name']}", "PASS", f"{target['ip']}:{target['port']} ({target['protocol']})")
                except socket.timeout:
                    result.add("网络", f"{target['name']}", "WARN", f"{target['ip']}:{target['port']} 超时", "请检查网络连接和防火墙设置")
                    unreachable.append(target["name"])
                except Exception as e:
                    result.add("网络", f"{target['name']}", "INFO", f"{target['ip']}:{target['port']} 无法测试: {e}")
                finally:
                    sock.close()
            else:
                # TCP连接测试
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                try:
                    sock.connect((target["ip"], target["port"]))
                    result.add("网络", f"{target['name']}", "PASS", f"{target['ip']}:{target['port']} ({target['protocol']})")
                except (socket.timeout, ConnectionRefusedError, OSError):
                    result.add("网络", f"{target['name']}", "WARN", f"{target['ip']}:{target['port']} 不可达", "请检查网络连接和防火墙设置")
                    unreachable.append(target["name"])
                finally:
                    sock.close()
        except Exception as e:
            result.add("网络", f"{target['name']}", "INFO", f"测试时出错: {e}")
    
    if unreachable:
        result.add("网络", "总结", "WARN", f"{len(unreachable)}个目标不可达: {', '.join(unreachable)}", "当前可能在云端环境，无法访问内网设备")
    else:
        result.add("网络", "总结", "PASS", "所有目标可达")


def check_configuration(result):
    """检查配置文件"""
    print("[5/6] 检查配置文件...")
    
    # 主配置文件
    config_path = PROJECT_ROOT / "config" / "inspection_config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            result.add("配置", "inspection_config.yaml", "PASS", "配置文件有效")
            
            # 检查关键配置项
            required_keys = ["network", "camera", "ptz", "perception"]
            missing_keys = [k for k in required_keys if k not in config]
            if missing_keys:
                result.add("配置", "必要配置项", "WARN", f"缺少: {', '.join(missing_keys)}")
            else:
                result.add("配置", "必要配置项", "PASS", "所有必要配置项存在")
        except Exception as e:
            result.add("配置", "inspection_config.yaml", "FAIL", f"解析失败: {e}")
    else:
        result.add("配置", "inspection_config.yaml", "FAIL", "配置文件不存在", "请检查config/inspection_config.yaml")
    
    # 模型文件
    models_dir = PROJECT_ROOT / "models"
    if models_dir.exists():
        model_files = list(models_dir.glob("*.trt")) + list(models_dir.glob("*.onnx"))
        if model_files:
            result.add("配置", "模型文件", "PASS", f"发现 {len(model_files)} 个模型文件")
            for mf in model_files:
                result.add("配置", mf.name, "INFO", f"大小: {(mf.stat().st_size / 1024 / 1024):.1f}MB")
        else:
            result.add("配置", "模型文件", "WARN", "未找到模型文件", "系统将使用模拟模式")
    else:
        result.add("配置", "models目录", "INFO", "models目录不存在", "模拟模式不需要模型文件")


def check_project_structure(result):
    """检查项目结构"""
    print("[6/6] 检查项目结构...")
    
    required_dirs = [
        "src",
        "scripts",
        "config",
        "docs",
        "data",
        "tests"
    ]
    
    missing_dirs = []
    for dir_name in required_dirs:
        dir_path = PROJECT_ROOT / dir_name
        if dir_path.exists():
            result.add("结构", dir_name, "PASS", "目录存在")
        else:
            result.add("结构", dir_name, "FAIL", "目录不存在")
            missing_dirs.append(dir_name)
    
    # 检查关键脚本
    critical_scripts = [
        "scripts/run_demo.py",
        "scripts/start_monitor.py",
        "scripts/deploy.sh",
        "monitor_platform/server.py"
    ]
    
    missing_scripts = []
    for script in critical_scripts:
        script_path = PROJECT_ROOT / script
        if script_path.exists():
            result.add("结构", script, "PASS", "脚本存在")
        else:
            result.add("结构", script, "FAIL", "脚本不存在")
            missing_scripts.append(script)
    
    if missing_dirs or missing_scripts:
        result.add("结构", "总结", "WARN", f"缺少 {len(missing_dirs)} 个目录和 {len(missing_scripts)} 个脚本", "请检查项目完整性")
    else:
        result.add("结构", "总结", "PASS", "项目结构完整")


def generate_html_report(result, output_path):
    """生成HTML报告"""
    html_path = Path(output_path) if output_path.endswith('.html') else Path(output_path) / "diagnostic_report.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    
    summary = result.get_summary()
    
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>绝影Lite3 环境诊断报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        .header .timestamp {{ opacity: 0.8; font-size: 14px; }}
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }}
        .summary-card {{ background: white; padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .summary-card.pass {{ border-left: 4px solid #22c55e; }}
        .summary-card.warn {{ border-left: 4px solid #f59e0b; }}
        .summary-card.fail {{ border-left: 4px solid #ef4444; }}
        .summary-card.info {{ border-left: 4px solid #3b82f6; }}
        .summary-card .count {{ font-size: 36px; font-weight: bold; }}
        .summary-card.pass .count {{ color: #22c55e; }}
        .summary-card.warn .count {{ color: #f59e0b; }}
        .summary-card.fail .count {{ color: #ef4444; }}
        .summary-card.info .count {{ color: #3b82f6; }}
        .summary-card .label {{ font-size: 14px; color: #666; margin-top: 5px; }}
        .section {{ background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .section h2 {{ font-size: 18px; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #e5e7eb; }}
        .item {{ padding: 12px; border-bottom: 1px solid #f3f4f6; display: flex; justify-content: space-between; align-items: flex-start; }}
        .item:last-child {{ border-bottom: none; }}
        .item-header {{ display: flex; align-items: center; gap: 10px; }}
        .item-category {{ font-size: 12px; color: #666; background: #f3f4f6; padding: 2px 8px; border-radius: 4px; }}
        .item-name {{ font-weight: 500; }}
        .item-status {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 500; }}
        .item-status.pass {{ background: #dcfce7; color: #166534; }}
        .item-status.warn {{ background: #fef3c7; color: #92400e; }}
        .item-status.fail {{ background: #fee2e2; color: #991b1b; }}
        .item-status.info {{ background: #dbeafe; color: #1e40af; }}
        .item-detail {{ font-size: 13px; color: #666; margin-top: 5px; }}
        .item-suggestion {{ font-size: 12px; color: #f59e0b; margin-top: 5px; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 绝影Lite3 环境诊断报告</h1>
            <div class="timestamp">生成时间: {result.timestamp}</div>
        </div>
        
        <div class="summary">
            <div class="summary-card pass">
                <div class="count">{summary['PASS']}</div>
                <div class="label">通过</div>
            </div>
            <div class="summary-card warn">
                <div class="count">{summary['WARN']}</div>
                <div class="label">警告</div>
            </div>
            <div class="summary-card fail">
                <div class="count">{summary['FAIL']}</div>
                <div class="label">失败</div>
            </div>
            <div class="summary-card info">
                <div class="count">{summary['INFO']}</div>
                <div class="label">信息</div>
            </div>
        </div>
"""
    
    # 按类别分组
    categories = {}
    for item in result.items:
        cat = item["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)
    
    for cat, items in categories.items():
        html_content += f"""
        <div class="section">
            <h2>{cat}</h2>
"""
        for item in items:
            status_class = item["status"].lower()
            html_content += f"""
            <div class="item">
                <div>
                    <div class="item-header">
                        <span class="item-category">{item['category']}</span>
                        <span class="item-name">{item['name']}</span>
                    </div>
                    <div class="item-detail">{item['detail']}</div>
                    {f'<div class="item-suggestion">💡 {item["suggestion"]}</div>' if item['suggestion'] else ''}
                </div>
                <span class="item-status {status_class}">{item['status']}</span>
            </div>
"""
        html_content += """
        </div>
"""
    
    html_content += f"""
        <div class="footer">
            <p>绝影Lite3电力巡检系统 | 环境诊断工具 V1.0</p>
            <p>生成时间: {result.timestamp}</p>
        </div>
    </div>
</body>
</html>
"""
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return html_path


def generate_json_report(result, output_path):
    """生成JSON报告"""
    json_path = Path(output_path) if output_path.endswith('.json') else Path(output_path) / "diagnostic_report.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    
    report_data = {
        "timestamp": result.timestamp,
        "summary": result.get_summary(),
        "items": result.items,
        "can_run_simulation": not result.has_failure(),
        "needs_gpu": any(item["name"] == "PyTorch CUDA" and item["status"] == "WARN" for item in result.items)
    }
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    return json_path


def generate_markdown_report(result, output_path):
    """生成Markdown报告"""
    md_path = Path(output_path) if output_path.endswith('.md') else Path(output_path) / "diagnostic_report.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    
    summary = result.get_summary()
    
    md_content = f"""# 绝影Lite3 环境诊断报告

> 生成时间: {result.timestamp}

## 摘要

| 状态 | 数量 |
|------|------|
| ✅ 通过 | {summary['PASS']} |
| ⚠️ 警告 | {summary['WARN']} |
| ❌ 失败 | {summary['FAIL']} |
| ℹ️ 信息 | {summary['INFO']} |

"""
    
    # 按类别分组
    categories = {}
    for item in result.items:
        cat = item["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)
    
    for cat, items in categories.items():
        md_content += f"## {cat}\n\n"
        md_content += "| 项目 | 状态 | 详情 | 建议 |\n"
        md_content += "|------|------|------|------|\n"
        
        for item in items:
            status_icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "INFO": "ℹ️"}.get(item["status"], "❓")
            md_content += f"| {item['name']} | {status_icon} {item['status']} | {item['detail']} | {item['suggestion'] or '-'} |\n"
        
        md_content += "\n"
    
    md_content += """---

*生成时间: """ + result.timestamp + """*
"""
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    return md_path


def print_summary(result):
    """打印摘要到控制台"""
    summary = result.get_summary()
    
    print("\n" + "=" * 60)
    print("诊断摘要")
    print("=" * 60)
    print(f"  ✅ 通过: {summary['PASS']}")
    print(f"  ⚠️  警告: {summary['WARN']}")
    print(f"  ❌ 失败: {summary['FAIL']}")
    print(f"  ℹ️  信息: {summary['INFO']}")
    print("=" * 60)
    
    if result.has_failure():
        print("\n❌ 存在失败项，请修复后重新运行诊断")
        for item in result.items:
            if item["status"] == "FAIL":
                print(f"  - {item['category']}: {item['name']} - {item['detail']}")
                if item["suggestion"]:
                    print(f"    建议: {item['suggestion']}")
    elif result.is_warning():
        print("\n⚠️  存在警告项，但可以尝试运行模拟模式")
    else:
        print("\n✅ 所有检查通过，可以正常运行")


def main():
    parser = argparse.ArgumentParser(
        description="绝影Lite3 环境诊断工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 scripts/detect_environment.py                    # 完整诊断
  python3 scripts/detect_environment.py --check-deps       # 仅检查依赖
  python3 scripts/detect_environment.py --check-network    # 仅检查网络
  python3 scripts/detect_environment.py --full --output ./report
        """
    )
    
    parser.add_argument("--check-deps", action="store_true", help="仅检查Python依赖")
    parser.add_argument("--check-network", action="store_true", help="仅检查网络连接")
    parser.add_argument("--full", action="store_true", help="完整诊断（默认）")
    parser.add_argument("--output", type=str, help="报告输出路径（不含扩展名）")
    parser.add_argument("--format", choices=["html", "json", "md", "all"], default="all", help="报告格式")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("绝影Lite3 环境诊断工具 V1.0")
    print("=" * 60)
    print(f"项目路径: {PROJECT_ROOT}")
    print(f"Python版本: {sys.version}")
    print(f"诊断时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    result = DiagnosticResult()
    
    # 执行诊断
    if args.check_deps or args.full:
        check_dependencies(result)
    
    if args.check_network or args.full:
        check_network(result)
    
    if args.full:
        check_system_environment(result)
        check_gpu_environment(result)
        check_configuration(result)
        check_project_structure(result)
    
    # 打印摘要
    print_summary(result)
    
    # 生成报告
    output_base = args.output or str(PROJECT_ROOT / "data" / "diagnostic_report")
    
    if args.format in ["html", "all"]:
        html_path = generate_html_report(result, output_base)
        print(f"\n📄 HTML报告已生成: {html_path}")
    
    if args.format in ["json", "all"]:
        json_path = generate_json_report(result, output_base)
        print(f"📄 JSON报告已生成: {json_path}")
    
    if args.format in ["md", "all"]:
        md_path = generate_markdown_report(result, output_base)
        print(f"📄 Markdown报告已生成: {md_path}")
    
    # 返回退出码
    sys.exit(1 if result.has_failure() else 0)


if __name__ == "__main__":
    main()
