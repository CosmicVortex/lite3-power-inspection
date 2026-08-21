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

def print_fail_detail(reason, solution=""):
    """打印详细的失败原因和解决方案"""
    print(f"\n{Colors.FAIL}{Colors.BOLD}❌ 执行失败{Colors.ENDC}")
    print(f"{Colors.FAIL}原因: {reason}{Colors.ENDC}")
    if solution:
        print(f"{Colors.WARNING}建议: {solution}{Colors.ENDC}")
    print()

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
        
        required_commands = [
            ('python3', 'Python解释器'),
            ('pip3', 'Python包管理器'),
            ('rsync', '文件同步工具'),
            ('ssh', 'SSH客户端'),
            ('git', 'Git版本控制')
        ]
        
        missing = []
        for cmd, desc in required_commands:
            if shutil.which(cmd):
                print_success(f"{desc}: 已安装")
            else:
                print_warning(f"{desc}: 未安装 ({cmd})")
                print_info(f"  请安装: sudo apt-get install {cmd}")
                missing.append(cmd)
        
        if missing:
            print_warning(f"缺少 {len(missing)} 个系统依赖，可能影响部署功能")
            self.results['system_deps'] = {'status': 'WARNING', 'missing': missing}
            return False
        else:
            self.results['system_deps'] = {'status': 'PASS'}
            return True
    
    def check_gpu_environment(self):
        """检查GPU环境"""
        print_step("检查GPU环境...")
        
        nvidia_smi = shutil.which('nvidia-smi')
        if nvidia_smi:
            try:
                result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], 
                                      capture_output=True, text=True, timeout=5)
                gpu_model = result.stdout.strip().split('\n')[0] if result.returncode == 0 else ""
                if gpu_model:
                    print_success(f"GPU型号: {gpu_model}")
                    self.results['gpu'] = {'status': 'PASS', 'model': gpu_model}
                    
                    # 检查CUDA
                    nvcc_path = '/usr/local/cuda/bin/nvcc'
                    if os.path.exists(nvcc_path):
                        result = subprocess.run([nvcc_path, '--version'], 
                                              capture_output=True, text=True)
                        if result.returncode == 0:
                            cuda_version = result.stdout.split('\n')[-2].strip()
                            print_success(f"CUDA版本: {cuda_version}")
                    return True
            except Exception as e:
                print_warning(f"GPU检测失败: {e}")
        else:
            print_warning("未检测到NVIDIA GPU")
            print_info("系统将使用模拟模式运行")
            self.results['gpu'] = {'status': 'NO_GPU'}
            return False
        
        self.results['gpu'] = {'status': 'FAIL'}
        return False
    
    def check_offline_packages(self, offline_dir):
        """检查离线安装包"""
        print_step("检查离线安装包...")
        
        if not offline_dir:
            print_warning("未指定离线包目录")
            print_info("将尝试从网络安装依赖（需要网络连接）")
            return False
        
        offline_path = Path(offline_dir)
        if not offline_path.exists():
            print_warning(f"离线包目录不存在: {offline_path}")
            print_info("请使用 --offline-dir 参数指定正确的路径")
            return False
        
        # 查找wheel包
        whl_files = list(offline_path.glob("*.whl"))
        if whl_files:
            print_success(f"找到 {len(whl_files)} 个离线安装包")
            self.offline_packages = [f.name for f in whl_files]
            return True
        else:
            print_warning("离线目录中未找到wheel包")
            print_info("请重新生成离线包: python3 scripts/package_offline.py")
            return False
    
    def check_required_packages(self):
        """检查必需包是否已安装"""
        print_step("检查Python依赖包...")
        
        required_packages = [
            ('loguru', '日志处理'),
            ('numpy', '数值计算'),
            ('cv2', 'OpenCV图像处理'),
            ('websockets', 'WebSocket通信'),
            ('requests', 'HTTP请求'),
            ('yaml', 'YAML配置解析'),
            ('fastapi', 'Web框架'),
            ('uvicorn', 'ASGI服务器'),
            ('pydantic', '数据验证')
        ]
        
        optional_packages = [
            ('torch', 'PyTorch深度学习框架'),
            ('tensorrt', 'TensorRT推理引擎'),
            ('onnxruntime', 'ONNX推理运行时')
        ]
        
        missing_required = []
        missing_optional = []
        
        for pkg, desc in required_packages:
            try:
                __import__(pkg.replace('-', '_'))
                print_success(f"{pkg}: 已安装")
            except ImportError:
                print_error(f"{pkg}: 缺失 (必需)")
                missing_required.append(pkg)
        
        for pkg, desc in optional_packages:
            try:
                __import__(pkg.replace('-', '_'))
                print_info(f"{pkg}: 已安装 (可选)")
            except ImportError:
                print_info(f"{pkg}: 未安装 (将使用模拟模式)")
                missing_optional.append(pkg)
        
        self.missing_packages = missing_required
        
        if missing_required:
            print_error(f"缺少 {len(missing_required)} 个必需包: {', '.join(missing_required)}")
            print_info("将自动安装缺失的依赖...")
            return False
        else:
            print_success("所有依赖已安装")
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
        
        self.results['structure'] = {'status': 'PASS' if all_ok else 'WARNING'}
        return all_ok
    
    def check_config_file(self):
        """检查配置文件"""
        print_step("检查配置文件...")
        
        config_path = PROJECT_ROOT / 'config' / 'inspection_config.yaml'
        
        if not config_path.exists():
            print_error(f"配置文件不存在: {config_path}")
            print_info("请复制 config/inspection_config.yaml.example 并重命名为 inspection_config.yaml")
            return False
        
        print_success(f"配置文件存在: {config_path.name}")
        
        # 检查必要字段
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            required_keys = ['udp', 'websocket', 'ptz', 'temperature']
            missing_keys = [k for k in required_keys if k not in config]
            
            if missing_keys:
                print_warning(f"配置文件缺少字段: {', '.join(missing_keys)}")
                print_info("请检查配置文件完整性")
                return False
            else:
                print_success("配置文件结构完整")
                return True
        except ImportError:
            print_warning("无法解析YAML配置文件（缺少pyyaml）")
            print_info("安装依赖后可验证配置")
            return True
        except Exception as e:
            print_error(f"配置文件解析失败: {e}")
            return False

# ==================== 依赖安装 ====================

class DependencyInstaller:
    """依赖安装器"""
    
    def __init__(self, offline_packages=None, missing_packages=None):
        self.offline_packages = offline_packages
        self.missing_packages = missing_packages or []
        self.venv_path = PROJECT_ROOT / 'venv'
        
    def create_virtual_environment(self):
        """创建虚拟环境"""
        print_step("创建虚拟环境...")
        
        if self.venv_path.exists() and (self.venv_path / 'bin' / 'python').exists():
            print_success(f"虚拟环境已存在: {self.venv_path}")
            return True
        
        print_info("正在创建虚拟环境...")
        try:
            subprocess.run([sys.executable, '-m', 'venv', str(self.venv_path)], 
                          check=True, capture_output=True)
            print_success("虚拟环境创建成功")
            return True
        except subprocess.CalledProcessError as e:
            print_error(f"虚拟环境创建失败: {e}")
            return False
    
    def get_pip_path(self):
        """获取pip路径"""
        return self.venv_path / 'bin' / 'pip'
    
    def get_python_path(self):
        """获取Python路径"""
        return self.venv_path / 'bin' / 'python'
    
    def install_missing_packages(self, verbose=True):
        """安装缺失的包"""
        if not self.missing_packages:
            return True
        
        print_step(f"安装 {len(self.missing_packages)} 个缺失的包...")
        
        # 尝试离线安装
        if self.offline_packages:
            print_info("优先使用离线包安装...")
            if self._install_from_offline(verbose):
                return True
        
        # 尝试网络安装
        print_warning("离线安装失败或无离线包，尝试网络安装...")
        if self._install_from_network(verbose):
            return True
        
        print_error("所有安装方式均失败")
        return False
    
    def _install_from_offline(self, verbose=True):
        """从离线包安装"""
        if not self.offline_packages:
            return False
        
        pip_path = self.get_pip_path()
        if not pip_path.exists():
            print_error("pip路径不存在")
            return False
        
        # 查找wheel目录
        wheel_dirs = [
            Path(self.offline_packages[0]).parent,  # 假设所有包在同一目录
        ]
        
        for wheel_dir in wheel_dirs:
            if wheel_dir.exists():
                whl_count = len(list(wheel_dir.glob("*.whl")))
                if whl_count > 0:
                    print_info(f"从 {wheel_dir} 安装 {whl_count} 个wheel包")
                    try:
                        cmd = [
                            str(pip_path), 'install',
                            '--no-index',
                            '--find-links', str(wheel_dir),
                            '-r', str(PROJECT_ROOT / 'requirements.txt')
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            print_success("离线安装成功")
                            return True
                        else:
                            if verbose:
                                print_warning(f"离线安装部分失败: {result.stderr[:200]}")
                    except Exception as e:
                        if verbose:
                            print_warning(f"离线安装出错: {e}")
        
        return False
    
    def _install_from_network(self, verbose=True):
        """从网络安装"""
        pip_path = self.get_pip_path()
        if not pip_path.exists():
            print_error("pip路径不存在")
            return False
        
        print_info("正在从网络安装依赖...")
        try:
            cmd = [str(pip_path), 'install', '-r', str(PROJECT_ROOT / 'requirements.txt')]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print_success("网络安装成功")
                return True
            else:
                # 提取错误信息
                error_msg = result.stderr.split('\n')[-1] if result.stderr else "未知错误"
                print_error(f"网络安装失败: {error_msg}")
                print_info("请检查网络连接或使用离线包")
                return False
        except subprocess.TimeoutExpired:
            print_error("安装超时（超过5分钟）")
            print_info("建议使用离线包安装")
            return False
        except Exception as e:
            print_error(f"安装过程出错: {e}")
            return False

# ==================== 目录管理 ====================

class DirectoryManager:
    """目录管理器"""
    
    def __init__(self):
        self.base_dir = PROJECT_ROOT / 'data'
        
    def create_directories(self):
        """创建必要目录"""
        print_step("创建必要目录...")
        
        dirs = [
            'data/logs',      # 日志目录
            'data/cache',     # 缓存目录
            'models',         # 模型目录
            'config'          # 配置目录
        ]
        
        for d in dirs:
            path = PROJECT_ROOT / d
            path.mkdir(parents=True, exist_ok=True)
            print_success(f"目录已就绪: {d}/")
        
        return True

# ==================== 服务管理 ====================

class ServiceManager:
    """服务管理器"""
    
    @staticmethod
    def start_monitor_platform():
        """启动监测平台"""
        print_step("启动监测平台...")
        
        monitor_script = PROJECT_ROOT / 'scripts' / 'start_monitor.py'
        if not monitor_script.exists():
            print_error(f"启动脚本不存在: {monitor_script}")
            return False
        
        venv_python = PROJECT_ROOT / 'venv' / 'bin' / 'python'
        if not venv_python.exists():
            venv_python = Path(sys.executable)
        
        log_file = PROJECT_ROOT / 'data' / 'logs' / 'monitor.log'
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        print_info("监测平台应在操作员笔记本上独立运行:")
        print_info("  1. 在笔记本上执行: python3 scripts/start_monitor.py")
        print_info("  2. 访问地址: http://localhost:8000")
        print_info("")
        print_info("感知主机服务:")
        print_info("  WebSocket: ws://192.168.1.103:8765/ws")
        print_info("  UDP控制: 192.168.1.103:43893")
        
        try:
            # 后台启动
            with open(log_file, 'w') as f:
                process = subprocess.Popen(
                    [str(venv_python), str(monitor_script)],
                    stdout=f,
                    stderr=f,
                    cwd=str(PROJECT_ROOT)
                )
            
            # 等待服务启动
            time.sleep(3)
            
            # 验证服务
            import requests
            try:
                # 监测平台已在笔记本上运行，无需检查
                if resp.status_code == 200:
                    print_success(f"监测平台启动成功 (PID: {process.pid})")
                    print_info("监测平台地址: http://localhost:8000")
                    print_info(f"查看日志: tail -f {log_file}")
                    return True
                else:
                    print_warning(f"服务响应状态码: {resp.status_code}")
                    print_info(f"日志文件: {log_file}")
                    return True
            except requests.exceptions.ConnectionError:
                print_warning("服务可能正在启动，请稍后检查")
                print_info(f"日志文件: {log_file}")
                return True
        except Exception as e:
            print_error(f"启动监测平台失败: {e}")
            return False
    
    @staticmethod
    def run_demo(mode='simulation'):
        """运行演示程序"""
        print_step("运行演示程序...")
        
        demo_script = PROJECT_ROOT / 'scripts' / 'demo_12min.py'
        if not demo_script.exists():
            print_error(f"演示脚本不存在: {demo_script}")
            return False
        
        venv_python = PROJECT_ROOT / 'venv' / 'bin' / 'python'
        if not venv_python.exists():
            venv_python = Path(sys.executable)
        
        print_info(f"启动演示程序 (模式: {mode})...")
        
        try:
            result = subprocess.run(
                [str(venv_python), str(demo_script), '--mode', mode],
                cwd=str(PROJECT_ROOT)
            )
            
            if result.returncode == 0:
                print_success("演示程序执行完成")
                return True
            else:
                print_error(f"演示程序执行失败 (退出码: {result.returncode})")
                return False
        except Exception as e:
            print_error(f"运行演示程序失败: {e}")
            return False

# ==================== 部署流程 ====================

class DeploymentOrchestrator:
    """部署编排器"""
    
    def __init__(self, args):
        self.args = args
        self.detector = EnvironmentDetector()
        self.installer = None
        self.start_time = time.time()
        
        # 检查离线包
        if hasattr(args, 'offline_dir') and args.offline_dir:
            self.detector.check_offline_packages(args.offline_dir)
            if self.detector.offline_packages:
                self.installer = DependencyInstaller(self.detector.offline_packages[0])
        
    def run_full_deploy(self):
        """执行完整部署流程"""
        print_header("绝影Lite3 一键部署工具")
        print_info(f"部署时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print_info(f"项目路径: {PROJECT_ROOT}")
        print()
        
        # 步骤1: 环境检测
        print_step("=" * 50)
        print("       第一步: 环境检测")
        print("=" * 50)
        
        env_ok = True
        
        if not self.args.skip_check:
            # Python版本
            if not self.detector.check_python_version():
                env_ok = False
                if not self.args.force:
                    print_fail_detail("Python版本不满足要求", "请升级Python至3.8以上版本")
                    self._print_summary()
                    return False
            
            # 系统依赖
            self.detector.check_system_dependencies()
            
            # GPU环境
            self.detector.check_gpu_environment()
            
            # 项目结构
            self.detector.check_project_structure()
            
            # 配置文件
            self.detector.check_config_file()
        
        # 步骤2: 依赖检查与安装
        print_step("=" * 50)
        print("       第二步: 依赖检查与安装")
        print("=" * 50)
        
        if not self.args.skip_install:
            # 检查依赖
            if not self.detector.check_required_packages():
                # 创建安装器
                if not self.installer:
                    self.installer = DependencyInstaller(missing_packages=self.detector.missing_packages)
                
                # 创建虚拟环境
                if not self.installer.create_virtual_environment():
                    if self.args.force:
                        print_warning("虚拟环境创建失败，强制继续...")
                    else:
                        print_fail_detail("虚拟环境创建失败", "请检查是否有写入权限或手动创建: python3 -m venv venv")
                        self._print_summary()
                        return False
                
                # 安装依赖
                if not self.installer.install_missing_packages():
                    if self.args.force:
                        print_warning("依赖安装失败，强制继续...")
                    else:
                        print_fail_detail("依赖安装失败", 
                            "请检查网络连接或使用离线包: --offline-dir ./offline-deploy")
                        self._print_summary()
                        return False
        
        # 步骤3: 创建目录
        print_step("=" * 50)
        print("       第三步: 创建必要目录")
        print("=" * 50)
        
        dir_manager = DirectoryManager()
        dir_manager.create_directories()
        
        # 步骤4: 验证安装
        print_step("=" * 50)
        print("       第四步: 验证安装")
        print("=" * 50)
        
        if not self.args.skip_check:
            python_path = self.installer.get_python_path() if self.installer else Path(sys.executable)
            if python_path.exists():
                try:
                    result = subprocess.run(
                        [str(python_path), '-c', 
                         'import loguru, numpy, cv2, websockets, requests, yaml, fastapi, uvicorn, pydantic; print("OK")'],
                        capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        print_success("所有核心依赖验证通过")
                    else:
                        print_error("依赖验证失败")
                        print_info(f"错误信息: {result.stderr}")
                        if not self.args.force:
                            self._print_summary()
                            return False
                except Exception as e:
                    print_warning(f"验证过程出错: {e}")
        
        # 步骤5: 启动服务
        print_step("=" * 50)
        print("       第五步: 启动服务")
        print("=" * 50)
        
        if not self.args.no_start:
            # 启动监测平台
            if not ServiceManager.start_monitor_platform():
                if self.args.force:
                    print_warning("监测平台启动失败，强制继续...")
                else:
                    print_fail_detail("监测平台启动失败", "请查看日志文件 data/logs/monitor.log 了解详细错误")
                    self._print_summary()
                    return False
            
            # 运行演示（如果需要）
            if hasattr(self.args, 'demo_mode') and self.args.demo_mode:
                ServiceManager.run_demo(self.args.demo_mode)
        else:
            print_info("跳过服务启动 (--no-start)")
        
        # 完成
        elapsed = time.time() - self.start_time
        print_header("部署完成")
        print_success(f"部署耗时: {elapsed:.1f} 秒")
        print_info("")
        print_info("✅ 部署完成！")
        print_info("请切换到操作员笔记本，运行以下命令启动监测平台:")
        print_info("  python3 scripts/start_monitor.py")
        print_info("然后通过浏览器访问: http://localhost:8000")
        print_info("查看日志: tail -f data/logs/monitor.log")
        
        self._print_summary()
        return True
    
    def run_check_only(self):
        """仅执行环境检查"""
        print_header("绝影Lite3 环境检查工具")
        print()
        
        self.detector.check_python_version()
        self.detector.check_system_dependencies()
        self.detector.check_gpu_environment()
        self.detector.check_project_structure()
        self.detector.check_config_file()
        self.detector.check_required_packages()
        
        self._print_summary()
    
    def _print_summary(self):
        """打印总结报告"""
        print("\n" + "="*60)
        print("                    部署总结报告")
        print("="*60)
        
        # 环境状态
        print("\n【环境状态】")
        if self.detector.results.get('python_version', {}).get('status') == 'PASS':
            print_success("Python版本: 符合要求")
        else:
            print_error("Python版本: 不符合要求")
        
        if self.detector.results.get('gpu', {}).get('status') in ['PASS', 'NO_GPU']:
            status_text = "已检测" if self.detector.results['gpu']['status'] == 'PASS' else "未检测（使用模拟模式）"
            print_success(f"GPU环境: {status_text}")
        else:
            print_error("GPU环境: 异常")
        
        # 依赖状态
        print("\n【依赖状态】")
        if self.detector.missing_packages:
            print_error(f"缺失包: {', '.join(self.detector.missing_packages)}")
        else:
            print_success("所有依赖已就绪")
        
        # 项目结构
        print("\n【项目结构】")
        if self.detector.results.get('structure', {}).get('status') == 'PASS':
            print_success("项目结构完整")
        else:
            print_warning("项目结构可能存在缺失")
        
        print("\n" + "="*60)

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
    
    # 创建编排器
    orchestrator = DeploymentOrchestrator(args)
    
    # 执行相应操作
    if args.check:
        orchestrator.run_check_only()
    elif args.install:
        # 仅安装
        orchestrator.detector.check_required_packages()
        if orchestrator.detector.missing_packages:
            if not orchestrator.installer:
                orchestrator.installer = DependencyInstaller()
            orchestrator.installer.create_virtual_environment()
            orchestrator.installer.install_missing_packages()
    elif args.start:
        # 仅启动
        ServiceManager.start_monitor_platform()
        if args.demo_mode:
            ServiceManager.run_demo(args.demo_mode)
    else:
        # 完整部署
        orchestrator.run_full_deploy()

if __name__ == '__main__':
    main()
