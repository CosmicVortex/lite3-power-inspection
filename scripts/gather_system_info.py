#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3 机器狗环境信息采集脚本

用途：采集机器狗主机环境信息，用于后续部署配置调整
用法：python3 scripts/gather_system_info.py [--output report.md]
"""

import sys
import platform
import subprocess
import os
from pathlib import Path
from datetime import datetime
from loguru import logger

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_command(cmd, timeout=10):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


def gather_system_info():
    """收集系统信息"""
    info = {}
    
    # 操作系统信息
    info['os'] = {
        'name': platform.system(),
        'version': platform.version(),
        'release': platform.release(),
        'machine': platform.machine(),
        'processor': platform.processor(),
    }
    
    # Python信息
    info['python'] = {
        'version': platform.python_version(),
        'executable': sys.executable,
        'prefix': sys.prefix,
        'implementation': platform.python_implementation(),
    }
    
    # 系统路径
    info['paths'] = {
        'project_root': str(PROJECT_ROOT),
        'current_dir': os.getcwd(),
        'home': os.path.expanduser('~'),
    }
    
    return info


def gather_hardware_info():
    """收集硬件信息"""
    info = {}
    
    # CPU信息
    rc, out, err = run_command("nproc")
    info['cpu_cores'] = int(out) if rc == 0 else "N/A"
    
    rc, out, err = run_command("cat /proc/cpuinfo | grep 'model name' | head -1")
    info['cpu_model'] = out if rc == 0 else "N/A"
    
    rc, out, err = run_command("cat /proc/loadavg")
    info['cpu_load'] = out if rc == 0 else "N/A"
    
    # 内存信息
    rc, out, err = run_command("free -h | grep Mem")
    info['memory'] = out if rc == 0 else "N/A"
    
    # GPU信息（NVIDIA）
    rc, out, err = run_command("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader")
    if rc == 0 and out:
        info['gpu'] = {
            'available': True,
            'model': out.split('\n')[0].strip() if out else "N/A",
            'memory': out.split('\n')[0].split(',')[1].strip() if out else "N/A",
            'driver': out.split('\n')[0].split(',')[2].strip() if out else "N/A",
        }
    else:
        info['gpu'] = {
            'available': False,
            'model': "N/A",
            'memory': "N/A",
            'driver': "N/A",
        }
    
    # CUDA信息
    rc, out, err = run_command("nvcc --version | grep release")
    info['cuda'] = {
        'available': rc == 0,
        'version': out if rc == 0 else "N/A",
    }
    
    return info


def gather_network_info():
    """收集网络信息"""
    info = {}
    
    # 网络接口
    rc, out, err = run_command("ip addr show | grep 'inet ' | awk '{print $2}'")
    info['ip_addresses'] = out.split('\n') if rc == 0 and out else []
    
    # 网络接口列表
    rc, out, err = run_command("ip link show | grep '<' | awk -F: '{print $2}' | tr -d ' <>'")
    info['network_interfaces'] = [i.strip() for i in out.split('\n') if i.strip()] if rc == 0 else []
    
    # WiFi信息
    rc, out, err = run_command("nmcli device wifi list | head -5")
    info['wifi'] = {
        'available': rc == 0,
        'status': out if rc == 0 else "N/A",
    }
    
    # 测试连接到目标设备
    targets = {
        '运动主机(192.168.1.103)': '192.168.1.103',
        '云台相机(192.168.1.108)': '192.168.1.108',
        '监测平台(192.168.1.103)': '192.168.1.103',
    }
    
    connectivity = {}
    for name, ip in targets.items():
        rc, out, err = run_command(f"ping -c 2 -W 1 {ip}")
        connectivity[name] = {
            'reachable': rc == 0,
            'loss': '0%' if rc == 0 else '100%',
        }
    
    info['connectivity'] = connectivity
    
    return info


def gather_python_env():
    """收集Python环境信息"""
    info = {}
    
    # pip版本
    rc, out, err = run_command("pip --version")
    info['pip'] = out if rc == 0 else "N/A"
    
    # 虚拟环境
    info['venv'] = {
        'active': sys.prefix != sys.base_prefix,
        'path': sys.prefix,
    }
    
    # 已安装的包
    rc, out, err = run_command("pip list --format=columns")
    info['packages'] = out if rc == 0 else "N/A"
    
    # 检查关键依赖
    required_packages = [
        'loguru', 'numpy', 'opencv-python', 'websockets', 
        'requests', 'PyYAML', 'fastapi', 'uvicorn', 'pydantic'
    ]
    
    installed = {}
    for pkg in required_packages:
        try:
            module = __import__(pkg.replace('-', '_'))
            version = getattr(module, '__version__', 'unknown')
            installed[pkg] = {'installed': True, 'version': version}
        except ImportError:
            installed[pkg] = {'installed': False, 'version': 'N/A'}
    
    info['required_packages'] = installed
    
    # GPU相关包
    gpu_packages = ['torch', 'tensorrt', 'onnx', 'onnxruntime']
    gpu_installed = {}
    for pkg in gpu_packages:
        try:
            module = __import__(pkg)
            version = getattr(module, '__version__', 'unknown')
            gpu_installed[pkg] = {'installed': True, 'version': version}
        except ImportError:
            gpu_installed[pkg] = {'installed': False, 'version': 'N/A'}
    
    info['gpu_packages'] = gpu_installed
    
    return info


def gather_disk_info():
    """收集磁盘信息"""
    info = {}
    
    # 磁盘使用情况
    rc, out, err = run_command("df -h | grep -E '/$|/home'")
    info['disk'] = out if rc == 0 else "N/A"
    
    # 项目目录大小
    project_size = sum(f.stat().st_size for f in PROJECT_ROOT.rglob('*') if f.is_file())
    info['project_size'] = f"{project_size / 1024 / 1024:.1f} MB"
    
    return info


def gather_system_service():
    """收集系统服务信息"""
    info = {}
    
    # SSH服务
    rc, out, err = run_command("systemctl is-active ssh")
    info['ssh'] = {
        'active': out == 'active',
        'status': out,
    }
    
    # 防火墙
    rc, out, err = run_command("sudo ufw status 2>/dev/null || echo 'firewall not found'")
    info['firewall'] = {
        'status': out,
    }
    
    return info


def generate_report(info):
    """生成报告"""
    report = []
    
    report.append("=" * 70)
    report.append("绝影Lite3 机器狗环境信息采集报告")
    report.append(f"采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 70)
    report.append("")
    
    # 系统信息
    report.append("## 一、系统信息")
    report.append("-" * 70)
    report.append(f"操作系统: {info['os']['name']} {info['os']['version']}")
    report.append(f"内核版本: {info['os']['release']}")
    report.append(f"架构: {info['os']['machine']}")
    report.append(f"处理器: {info['os']['processor']}")
    report.append("")
    
    # Python信息
    report.append("## 二、Python环境")
    report.append("-" * 70)
    report.append(f"Python版本: {info['python']['version']}")
    report.append(f"Python路径: {info['python']['executable']}")
    report.append(f"虚拟环境: {'已激活' if info['python_env']['venv']['active'] else '未激活'}")
    report.append(f"虚拟环境路径: {info['python_env']['venv']['path']}")
    report.append("")
    
    # 硬件信息
    report.append("## 三、硬件信息")
    report.append("-" * 70)
    report.append(f"CPU核心数: {info['hardware']['cpu_cores']}")
    report.append(f"CPU型号: {info['hardware']['cpu_model']}")
    report.append(f"CPU负载: {info['hardware']['cpu_load']}")
    report.append(f"内存: {info['hardware']['memory']}")
    report.append("")
    
    # GPU信息
    report.append("### GPU信息")
    if info['hardware']['gpu']['available']:
        report.append(f"GPU型号: {info['hardware']['gpu']['model']}")
        report.append(f"显存: {info['hardware']['gpu']['memory']}")
        report.append(f"驱动版本: {info['hardware']['gpu']['driver']}")
        report.append(f"CUDA版本: {info['hardware']['cuda']['version']}")
    else:
        report.append("GPU: 未检测到NVIDIA GPU")
        report.append("说明: 将使用模拟模式，无法进行真实模型推理")
    report.append("")
    
    # 网络信息
    report.append("## 四、网络信息")
    report.append("-" * 70)
    report.append("IP地址:")
    for ip in info['network']['ip_addresses']:
        report.append(f"  - {ip}")
    report.append("")
    report.append("网络接口:")
    for iface in info['network']['network_interfaces']:
        report.append(f"  - {iface}")
    report.append("")
    
    report.append("设备连通性:")
    for name, status in info['network']['connectivity'].items():
        icon = "✓" if status['reachable'] else "✗"
        report.append(f"  {icon} {name}: {'可达' if status['reachable'] else '不可达'}")
    report.append("")
    
    # 依赖包信息
    report.append("## 五、Python依赖包")
    report.append("-" * 70)
    report.append("核心依赖:")
    for pkg, status in info['python_env']['required_packages'].items():
        icon = "✓" if status['installed'] else "✗"
        report.append(f"  {icon} {pkg}: {status['version'] if status['installed'] else '未安装'}")
    report.append("")
    
    report.append("GPU依赖（可选）:")
    for pkg, status in info['python_env']['gpu_packages'].items():
        icon = "✓" if status['installed'] else "✗"
        report.append(f"  {icon} {pkg}: {status['version'] if status['installed'] else '未安装'}")
    report.append("")
    
    # 磁盘信息
    report.append("## 六、磁盘信息")
    report.append("-" * 70)
    report.append(info['disk']['disk'])
    report.append(f"项目大小: {info['disk']['project_size']}")
    report.append("")
    
    # 系统服务
    report.append("## 七、系统服务")
    report.append("-" * 70)
    ssh_status = "✓ 运行中" if info['services']['ssh']['active'] else "✗ 未运行"
    report.append(f"SSH服务: {ssh_status}")
    report.append(f"防火墙: {info['services']['firewall']['status']}")
    report.append("")
    
    # 部署建议
    report.append("## 八、部署建议")
    report.append("-" * 70)
    
    suggestions = []
    
    # Python版本检查
    py_version = tuple(map(int, info['python']['version'].split('.')[:2]))
    if py_version >= (3, 8):
        suggestions.append("✓ Python版本满足要求 (>= 3.8)")
    else:
        suggestions.append(f"✗ Python版本过低 ({info['python']['version']} < 3.8)，需要升级")
    
    # GPU检查
    if info['hardware']['gpu']['available']:
        suggestions.append("✓ 检测到NVIDIA GPU，支持真实模式")
        if info['python_env']['gpu_packages']['torch']['installed']:
            suggestions.append("✓ PyTorch已安装，GPU加速可用")
        else:
            suggestions.append("⚠ PyTorch未安装，将使用CPU推理（速度较慢）")
    else:
        suggestions.append("ℹ 未检测到GPU，系统将使用模拟模式")
    
    # 依赖检查
    missing_deps = [pkg for pkg, status in info['python_env']['required_packages'].items() if not status['installed']]
    if missing_deps:
        suggestions.append(f"✗ 缺少依赖包: {', '.join(missing_deps)}")
        suggestions.append(f"  安装命令: pip install {' '.join(missing_deps)}")
    else:
        suggestions.append("✓ 所有核心依赖已安装")
    
    # 网络检查
    unreachable = [name for name, status in info['network']['connectivity'].items() if not status['reachable']]
    if unreachable:
        suggestions.append(f"⚠ 部分设备不可达: {', '.join(unreachable)}")
        suggestions.append("  请检查网络配置和防火墙设置")
    else:
        suggestions.append("✓ 所有目标设备可达")
    
    for suggestion in suggestions:
        report.append(suggestion)
    
    report.append("")
    
    # 总结
    report.append("## 九、总结")
    report.append("-" * 70)
    
    can_deploy = len(missing_deps) == 0 and py_version >= (3, 8)
    
    if can_deploy and info['hardware']['gpu']['available']:
        report.append("✅ 系统具备完整部署条件（支持真实模式）")
    elif can_deploy:
        report.append("✅ 系统具备部署条件（模拟模式）")
    else:
        report.append("⚠️  系统需要修复后才能部署")
    
    report.append("")
    report.append("=" * 70)
    
    return "\n".join(report)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="绝影Lite3 机器狗环境信息采集")
    parser.add_argument("--output", type=str, help="报告输出路径（默认：data/system_info_report.md）")
    parser.add_argument("--json", action="store_true", help="同时输出JSON格式报告")
    
    args = parser.parse_args()
    
    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )
    
    logger.info("开始采集系统信息...")
    
    # 收集信息
    info = {
        'system': gather_system_info(),
        'hardware': gather_hardware_info(),
        'network': gather_network_info(),
        'python_env': gather_python_env(),
        'disk': gather_disk_info(),
        'services': gather_system_service(),
    }
    
    # 生成报告
    report = generate_report(info)
    
    # 保存报告
    output_path = args.output or str(PROJECT_ROOT / "data" / "system_info_report.md")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(report, encoding='utf-8')
    logger.info(f"报告已保存: {output_path}")
    
    # 输出到控制台
    print()
    print(report)
    
    # 保存JSON格式
    if args.json:
        json_path = str(PROJECT_ROOT / "data" / "system_info_report.json")
        import json
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"JSON报告已保存: {json_path}")
    
    return info


if __name__ == "__main__":
    main()
