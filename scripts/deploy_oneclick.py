#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3 一键部署脚本

功能：
1. 检测运行环境（Python版本、系统依赖、GPU环境）
2. 检查缺失的Python包，自动安装（优先使用离线包）
3. 创建必要目录结构
4. 启动监测平台和演示程序
5. 提供清晰的状态提示和故障原因说明

用法：
    python3 scripts/deploy_oneclick.py              # 完整部署流程
    python3 scripts/deploy_oneclick.py --check      # 仅检查环境
    python3 scripts/deploy_oneclick.py --install    # 仅安装依赖
    python3 scripts/deploy_oneclick.py --start      # 仅启动服务
    python3 scripts/deploy_oneclick.py --offline-dir DIR  # 指定离线包目录
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKCYAN}ℹ️   {text}{Colors.ENDC}")

def print_step(text):
    print(f"\n{Colors.BOLD}[步骤] {text}{Colors.ENDC}")


# ==================== 环境检测 ====================

class EnvironmentDetector:
    """环境检测器"""
    
    def __init__(self):
        self.results = {}
        self.missing_packages = []
        self.offline_packages = []
        
    def check_python_version(self):
        """检查Python版本"""
        print_step("检查Python版本...")
        
        required_version = (3, 8)
        current_version = sys.version_info
        
        if current_version >= required_version:
            version_str = f"{current_version.major}.{current_version.minor}.{current_version.micro}"
            print_success(f"Python版本: {version_str} (满足要求 >= 3.8)")
            self.results['python_version'] = {'status': 'PASS', 'value': version_str}
            return True
        else:
            version_str = f"{current_version.major}.{current_version.minor}.{current_version.micro}"
            print_error(f"Python版本过低: {version_str} (需要 >= 3.8)")
            print_info("请升级Python版本:")
            print_info("  Ubuntu: sudo apt-get install python3.8 python3-pip")
            print_info("  macOS:  brew install python3")
            self.results['python_version'] = {'status': 'FAIL', 'value': version_str}
            return False
    
    def check_system_dependencies(self):
        """检查系统依赖"""
        print_step("检查系统依赖...")
        
        checks = [
            ('python3', 'Python解释器'),
            ('pip3', 'Python包管理器'),
            ('rsync', '文件同步工具'),
            ('ssh', 'SSH客户端'),
            ('git', 'Git版本控制'),
        ]
        
        all_pass = True
        for cmd, desc in checks:
            if shutil.which(cmd):
                print_success(f"{desc}: 已安装")
                self.results[f'system_{cmd}'] = {'status': 'PASS'}
            else:
                print_warning(f"{desc}: 未安装 ({cmd})")
                print_info(f"  请安装: sudo apt-get install {cmd}")
                self.results[f'system_{cmd}'] = {'status': 'WARN', 'value': 'missing'}
                all_pass = False
        
        return all_pass
    
    def check_gpu_environment(self):
        """检查GPU环境"""
        print_step("检查GPU环境...")
        
        has_gpu = False
        gpu_model = "未知"
        cuda_version = "未知"
        
        # 检查nvidia-smi
        if shutil.which('nvidia-smi'):
            try:
                result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], 
                                       capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    gpu_model = result.stdout.strip().split('\n')[0] if result.stdout.strip() else "NVIDIA GPU"
                    has_gpu = True
                    print_success(f"GPU型号: {gpu_model}")
            except:
                pass
        
        # 检查CUDA
        if os.path.exists('/usr/local/cuda/bin/nvcc'):
            try:
                result = subprocess.run(['nvcc', '--version'], capture_output=True, text=True)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'release' in line:
                            cuda_version = line.strip().split(',')[-1].strip()
                            break
                    print_success(f"CUDA版本: {cuda_version}")
            except:
                pass
        
        if not has_gpu:
            print_warning("未检测到NVIDIA GPU")
            print_info("系统将使用模拟模式运行")
        
        self.results['gpu'] = {'status': 'PASS' if has_gpu else 'INFO', 'model': gpu_model, 'cuda': cuda_version}
        return has_gpu
    
    def check_offline_packages(self, offline_dir):
        """检查离线安装包"""
        print_step("检查离线安装包...")
        
        offline_path = PROJECT_ROOT / offline_dir
        if not offline_path.exists():
            print_warning(f"离线包目录不存在: {offline_path}")
            print_info("将尝试从网络安装依赖")
            self.results['offline_packages'] = {'status': 'WARN', 'path': str(offline_path)}
            return []
        
        # 查找whl文件
        whl_files = list(offline_path.rglob('*.whl'))
        if whl_files:
            print_success(f"找到 {len(whl_files)} 个离线安装包")
            self.results['offline_packages'] = {'status': 'PASS', 'count': len(whl_files), 'path': str(offline_path)}
            return [str(f) for f in whl_files]
        else:
            print_warning("离线目录中未找到wheel包")
            self.results['offline_packages'] = {'status': 'WARN', 'path': str(offline_path)}
            return []
    
    def check_required_packages(self):
        """检查必需包"""
        print_step("检查Python依赖包...")
        
        required = [
            'loguru', 'numpy', 'cv2', 'websockets', 'requests',
            'yaml', 'fastapi', 'uvicorn', 'pydantic'
        ]
        
        optional = ['torch', 'tensorrt', 'onnxruntime']
        
        missing = []
        for pkg in required:
            try:
                __import__(pkg)
                print_success(f"{pkg}: 已安装")
                self.results[f'pkg_{pkg}'] = {'status': 'PASS'}
            except ImportError:
                print_error(f"{pkg}: 缺失 (必需)")
                missing.append(pkg)
                self.results[f'pkg_{pkg}'] = {'status': 'FAIL'}
        
        # 检查可选包
        optional_available = []
        for pkg in optional:
            try:
                __import__(pkg)
                optional_available.append(pkg)
                print_info(f"{pkg}: 已安装 (可选)")
            except ImportError:
                print_info(f"{pkg}: 未安装 (将使用模拟模式)")
        
        self.results['optional_packages'] = {'installed': optional_available, 'missing': [p for p in optional if p not in optional_available]}
        
        if missing:
            print_error(f"缺少 {len(missing)} 个必需包: {', '.join(missing)}")
            self.missing_packages = missing
            return False
        
        return True
    
    def check_project_structure(self):
        """检查项目结构"""
        print_step("检查项目结构...")
        
        required_dirs = ['src', 'scripts', 'docs', 'config', 'monitor_platform']
        required_files = ['requirements.txt', 'README.md']
        
        all_ok = True
        for d in required_dirs:
            if (PROJECT_ROOT / d).exists():
                print_success(f"目录: {d}/")
            else:
                print_warning(f"目录缺失: {d}/")
                all_ok = False
        
        for f in required_files:
            if (PROJECT_ROOT / f).exists():
                print_success(f"文件: {f}")
            else:
                print_error(f"文件缺失: {f}")
                all_ok = False
        
        self.results['structure'] = {'status': 'PASS' if all_ok else 'WARN'}
        return all_ok
    
    def check_config_file(self):
        """检查配置文件"""
        print_step("检查配置文件...")
        
        config_path = PROJECT_ROOT / 'config' / 'inspection_config.yaml'
        if config_path.exists():
            print_success(f"配置文件存在: {config_path.name}")
            self.results['config'] = {'status': 'PASS', 'path': str(config_path)}
            
            # 检查必要字段
            try:
                import yaml
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                required_keys = ['udp', 'websocket', 'ptz', 'temperature']
                missing_keys = [k for k in required_keys if k not in config]
                
                if missing_keys:
                    print_warning(f"配置文件缺少字段: {', '.join(missing_keys)}")
                    self.results['config']['status'] = 'WARN'
                else:
                    print_success("配置文件结构完整")
                    
            except ImportError:
                print_warning("无法解析YAML配置文件（缺少pyyaml）")
        else:
            print_error(f"配置文件缺失: {config_path}")
            self.results['config'] = {'status': 'FAIL'}
            return False
        
        return True


# ==================== 依赖安装 ====================

class PackageInstaller:
    """包安装器"""
    
    def __init__(self, offline_packages=None):
        self.offline_packages = offline_packages or []
        
    def install_missing_packages(self, verbose=True):
        """安装缺失的包"""
        if not self.offline_packages:
            print_warning("无离线包，尝试从网络安装")
            return self._install_from_network(verbose)
        else:
            print_info("使用离线包安装...")
            return self._install_from_offline(verbose)
    
    def _install_from_offline(self, verbose=True):
        """从离线包安装"""
        print_step("从离线包安装依赖...")
        
        # 创建虚拟环境（如果不存在）
        venv_path = PROJECT_ROOT / 'venv'
        if not (venv_path / 'bin' / 'python').exists():
            print_info("创建虚拟环境...")
            subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
        
        pip_path = venv_path / 'bin' / 'pip'
        
        # 安装离线包
        try:
            cmd = [str(pip_path), 'install', '--no-index', '--find-links', str(venv_path.parent / 'offline-packages')]
            cmd.extend(self.offline_packages)
            
            if verbose:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print_success("离线包安装成功")
                else:
                    print_error(f"安装失败: {result.stderr[:200]}")
                    return False
            else:
                subprocess.run(cmd, capture_output=True, check=True)
                print_success("离线包安装成功")
                
            return True
            
        except Exception as e:
            print_error(f"安装失败: {e}")
            print_info("请手动安装: pip install -r requirements.txt")
            return False
    
    def _install_from_network(self, verbose=True):
        """从网络安装（仅在有线上网络时可用）"""
        print_step("从网络安装依赖...")
        
        venv_path = PROJECT_ROOT / 'venv'
        if not (venv_path / 'bin' / 'python').exists():
            print_info("创建虚拟环境...")
            subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
        
        pip_path = venv_path / 'bin' / 'pip'
        
        try:
            cmd = [str(pip_path), 'install', '-r', str(PROJECT_ROOT / 'requirements.txt')]
            
            if verbose:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print_success("依赖安装成功")
                else:
                    print_error(f"安装失败: {result.stderr[:200]}")
                    return False
            else:
                subprocess.run(cmd, capture_output=True, check=True)
                print_success("依赖安装成功")
                
            return True
            
        except Exception as e:
            print_error(f"安装失败: {e}")
            print_info("请检查网络连接或手动安装")
            return False
    
    def create_virtual_environment(self):
        """创建虚拟环境"""
        print_step("创建虚拟环境...")
        
        venv_path = PROJECT_ROOT / 'venv'
        if (venv_path / 'bin' / 'python').exists():
            print_success("虚拟环境已存在")
            return True
        
        try:
            subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
            print_success("虚拟环境创建成功")
            return True
        except Exception as e:
            print_error(f"虚拟环境创建失败: {e}")
            return False


# ==================== 目录创建 ====================

class DirectoryCreator:
    """目录创建器"""
    
    def __init__(self):
        self.directories = [
            'data/logs',
            'data/cache',
            'models',
            'config',
        ]
    
    def create_directories(self):
        """创建必要目录"""
        print_step("创建必要目录...")
        
        for d in self.directories:
            path = PROJECT_ROOT / d
            path.mkdir(parents=True, exist_ok=True)
            print_success(f"目录: {path.name}/")
        
        return True


# ==================== 服务启动 ====================

class ServiceLauncher:
    """服务启动器"""
    
    @staticmethod
    def start_monitor_platform():
        """启动监测平台"""
        print_step("启动监测平台...")
        
        monitor_script = PROJECT_ROOT / 'scripts' / 'start_monitor.py'
        if not monitor_script.exists():
            print_error(f"启动脚本不存在: {monitor_script}")
            return False
        
        try:
            # 激活虚拟环境
            venv_python = PROJECT_ROOT / 'venv' / 'bin' / 'python'
            if venv_python.exists():
                cmd = [str(venv_python), str(monitor_script)]
            else:
                cmd = [sys.executable, str(monitor_script)]
            
            print_info("启动监测平台服务 (http://192.168.1.103:8000)...")
            
            # 后台启动
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            time.sleep(2)  # 等待服务启动
            
            # 验证服务是否启动
            try:
                import requests
                response = requests.get('http://192.168.1.103:8000/api/status', timeout=3)
                if response.status_code == 200:
                    print_success("监测平台启动成功")
                    return True
                else:
                    print_warning(f"服务响应异常: HTTP {response.status_code}")
                    return False
            except requests.exceptions.ConnectionError:
                print_warning("无法连接到服务，可能需要等待几秒")
                return True
                
        except Exception as e:
            print_error(f"启动失败: {e}")
            return False
    
    @staticmethod
    def run_demo(mode='simulation'):
        """运行演示程序"""
        print_step(f"运行演示程序 (模式: {mode})...")
        
        demo_script = PROJECT_ROOT / 'scripts' / 'demo_12min.py'
        if not demo_script.exists():
            print_error(f"演示脚本不存在: {demo_script}")
            return False
        
        try:
            venv_python = PROJECT_ROOT / 'venv' / 'bin' / 'python'
            if venv_python.exists():
                cmd = [str(venv_python), str(demo_script), '--mode', mode]
            else:
                cmd = [sys.executable, str(demo_script), '--mode', mode]
            
            print_info("启动演示程序...")
            subprocess.run(cmd, check=True)
            
            print_success("演示程序执行完成")
            return True
            
        except subprocess.CalledProcessError as e:
            print_error(f"演示程序执行失败 (错误码: {e.returncode})")
            print_info("请检查日志获取详细信息")
            return False
        except Exception as e:
            print_error(f"启动失败: {e}")
            return False


# ==================== 主部署流程 ====================

class OneClickDeployer:
    """一键部署器"""
    
    def __init__(self, args):
        self.args = args
        self.detector = EnvironmentDetector()
        self.installer = PackageInstaller()
        self.creator = DirectoryCreator()
        self.launcher = ServiceLauncher()
        self.start_time = time.time()
        
    def run_full_deploy(self):
        """执行完整部署流程"""
        print_header("绝影Lite3 一键部署工具")
        print_info(f"部署时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print_info(f"项目路径: {PROJECT_ROOT}")
        
        # 检查离线包目录
        offline_dir = self.args.offline_dir if hasattr(self.args, 'offline_dir') else None
        if offline_dir:
            self.installer.offline_packages = self.detector.check_offline_packages(offline_dir)
        
        # 步骤1: 环境检测
        if not self.args.skip_check:
            print_header("步骤1/5: 环境检测")
            checks = [
                ('Python版本', self.detector.check_python_version),
                ('系统依赖', self.detector.check_system_dependencies),
                ('GPU环境', self.detector.check_gpu_environment),
                ('项目结构', self.detector.check_project_structure),
                ('配置文件', self.detector.check_config_file),
                ('Python包', self.detector.check_required_packages),
            ]
            
            all_passed = True
            for name, check_func in checks:
                if not check_func():
                    all_passed = False
            
            if not all_passed and not self.args.force:
                print_error("\n环境检测未通过，请先解决上述问题")
                print_info("使用 --force 参数可强制继续部署")
                return False
        
        # 步骤2: 创建目录
        if not self.args.skip_install:
            print_header("步骤2/5: 创建目录结构")
            if not self.creator.create_directories():
                print_error("目录创建失败")
                return False
        
        # 步骤3: 安装依赖
        if not self.args.skip_install:
            print_header("步骤3/5: 安装依赖")
            if not self.installer.create_virtual_environment():
                print_error("虚拟环境创建失败")
                return False
            
            if self.detector.missing_packages:
                if not self.installer.install_missing_packages():
                    print_error("依赖安装失败")
                    return False
            else:
                print_success("所有依赖已安装")
        
        # 步骤4: 验证安装
        if not self.args.skip_check:
            print_header("步骤4/5: 验证安装")
            try:
                import loguru
                import numpy
                import cv2
                import websockets
                import requests
                import yaml
                import fastapi
                import uvicorn
                import pydantic
                print_success("所有核心依赖验证通过")
            except ImportError as e:
                print_error(f"验证失败: 缺少 {e.name}")
                return False
        
        # 步骤5: 启动服务
        if not self.args.no_start:
            print_header("步骤5/5: 启动服务")
            
            # 启动监测平台
            if not self.launcher.start_monitor_platform():
                print_warning("监测平台启动失败，请手动检查")
            
            # 运行演示（如指定）
            if hasattr(self.args, 'demo_mode') and self.args.demo_mode:
                self.launcher.run_demo(self.args.demo_mode)
        
        # 完成
        elapsed = time.time() - self.start_time
        print_header("部署完成")
        print_success(f"部署耗时: {elapsed:.1f} 秒")
        print_info("\n访问地址: http://192.168.1.103:8000")
        print_info("查看日志: tail -f data/logs/monitor.log")
        print_info("停止服务: pkill -f start_monitor.py")
        
        return True


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(
        description='绝影Lite3 一键部署工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 scripts/deploy_oneclick.py                    # 完整部署
  python3 scripts/deploy_oneclick.py --check            # 仅检查环境
  python3 scripts/deploy_oneclick.py --install          # 仅安装依赖
  python3 scripts/deploy_oneclick.py --start            # 仅启动服务
  python3 scripts/deploy_oneclick.py --offline-dir ../offline-packages  # 使用离线包
  python3 scripts/deploy_oneclick.py --demo-mode simulation  # 运行演示
        """
    )
    
    # 操作选项
    parser.add_argument('--check', action='store_true', help='仅检查环境，不执行部署')
    parser.add_argument('--install', action='store_true', help='仅安装依赖，不启动服务')
    parser.add_argument('--start', action='store_true', help='仅启动服务，不安装依赖')
    parser.add_argument('--force', action='store_true', help='强制部署，忽略环境警告')
    parser.add_argument('--no-start', action='store_true', help='部署完成后不自动启动服务')
    parser.add_argument('--skip-check', action='store_true', help='跳过环境检查')
    parser.add_argument('--skip-install', action='store_true', help='跳过依赖安装')
    parser.add_argument('--offline-dir', type=str, help='指定离线包目录路径')
    parser.add_argument('--demo-mode', type=str, choices=['simulation', 'real', 'hybrid'],
                       help='运行演示程序的模式')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出模式')
    
    args = parser.parse_args()
    
    # 创建部署器
    deployer = OneClickDeployer(args)
    
    # 执行部署
    if args.check:
        # 仅检查
        deployer.detector.check_python_version()
        deployer.detector.check_system_dependencies()
        deployer.detector.check_gpu_environment()
        deployer.detector.check_project_structure()
        deployer.detector.check_config_file()
        deployer.detector.check_required_packages()
    elif args.install:
        # 仅安装
        deployer.creator.create_directories()
        deployer.installer.create_virtual_environment()
        if deployer.detector.missing_packages:
            deployer.installer.install_missing_packages()
    elif args.start:
        # 仅启动
        deployer.launcher.start_monitor_platform()
        if args.demo_mode:
            deployer.launcher.run_demo(args.demo_mode)
    else:
        # 完整部署
        success = deployer.run_full_deploy()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
