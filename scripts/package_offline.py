#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绝影Lite3 离线包准备脚本

功能：
1. 下载所有Python依赖为wheel包
2. 打包项目文件（排除venv、数据目录）
3. 生成离线部署包

用法：
    python3 scripts/package_offline.py [--output DIR]
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

def download_packages(output_dir):
    """下载Python依赖为wheel包"""
    print("\n=== 下载Python依赖包 ===")
    
    output_path = PROJECT_ROOT / output_dir
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 创建虚拟环境
    venv_path = PROJECT_ROOT / 'offline_venv'
    if venv_path.exists():
        shutil.rmtree(venv_path)
    
    print("创建虚拟环境...")
    subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
    
    pip_path = venv_path / 'bin' / 'pip'
    
    # 下载requirements.txt中的包
    print("下载核心依赖...")
    result = subprocess.run(
        [str(pip_path), 'download', '-r', str(PROJECT_ROOT / 'requirements.txt'), 
         '-d', str(output_path), '--only-binary=:all:'],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        print(f"警告: 部分包下载失败: {result.stderr[:200]}")
    else:
        whl_count = len(list(output_path.glob('*.whl')))
        print(f"✅ 已下载 {whl_count} 个wheel包")
    
    # 清理虚拟环境
    shutil.rmtree(venv_path)
    
    return output_path

def package_project(output_dir):
    """打包项目文件"""
    print("\n=== 打包项目文件 ===")
    
    package_path = PROJECT_ROOT / output_dir / 'project'
    
    # 排除的目录和文件
    exclude_patterns = {
        'venv', '__pycache__', '.git', '.github',
        '*.pyc', '*.pyo', '*.db', 'data/*', 'logs/*'
    }
    
    # 复制项目文件
    print("复制项目文件...")
    for item in PROJECT_ROOT.iterdir():
        if item.name in ['venv', '__pycache__', '.git', '.github']:
            continue
        if item.suffix in ['.pyc', '.pyo']:
            continue
        if item.name == 'data' or item.name == 'logs':
            continue
            
        dest = package_path / item.name
        if item.is_dir():
            shutil.copytree(item, dest, ignore=lambda x, y: exclude_patterns)
        else:
            shutil.copy2(item, dest)
    
    print(f"✅ 项目文件已打包到: {package_path}")
    return package_path

def create_deployment_package():
    """创建完整部署包"""
    print("\n=== 创建离线部署包 ===")
    
    output_dir = 'offline-deploy'
    
    # 下载依赖包
    pkg_dir = download_packages(output_dir)
    
    # 打包项目
    project_dir = package_project(output_dir)
    
    # 创建README
    readme_content = """# 绝影Lite3 离线部署包

## 目录结构

```
offline-deploy/
├── packages/          # Python依赖wheel包
├── project/           # 项目源代码
└── README.md          # 本说明文件
```

## 部署步骤

### 1. 传输到目标机器

将 `offline-deploy` 目录复制到机器狗主机：

```bash
scp -r offline-deploy/ ysc@192.168.1.103:/home/ysc/
```

### 2. 执行一键部署

```bash
# SSH登录到机器狗
ssh ysc@192.168.1.103

# 进入项目目录
cd ~/lite3-power-inspection

# 执行离线部署
./scripts/deploy_oneclick.sh --offline-dir ../offline-deploy/packages
```

## 系统要求

- Python >= 3.8
- 操作系统: Ubuntu 20.04/22.04 (推荐)
- 内存: >= 4GB
- 磁盘: >= 2GB可用空间
- GPU (可选): NVIDIA Jetson系列

## 故障排查

如遇问题，请运行诊断脚本：
```bash
./scripts/run_diagnostic.sh
```

查看日志：
```bash
tail -f data/logs/monitor.log
```
"""
    
    (PROJECT_ROOT / output_dir / 'README.md').write_text(readme_content)
    
    # 统计包大小
    total_size = sum(f.stat().st_size for f in pkg_dir.rglob('*') if f.is_file())
    total_size_mb = total_size / (1024 * 1024)
    
    print(f"\n✅ 离线部署包创建完成")
    print(f"   位置: {PROJECT_ROOT / output_dir}")
    print(f"   大小: {total_size_mb:.1f} MB")
    
    return PROJECT_ROOT / output_dir

def main():
    parser = argparse.ArgumentParser(description='准备绝影Lite3离线部署包')
    parser.add_argument('--output', '-o', type=str, default='offline-deploy',
                       help='输出目录 (默认: offline-deploy)')
    parser.add_argument('--skip-download', action='store_true',
                       help='跳过下载依赖包（仅打包项目文件）')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("绝影Lite3 离线包准备工具")
    print("=" * 60)
    
    output_path = PROJECT_ROOT / args.output
    output_path.mkdir(parents=True, exist_ok=True)
    
    if not args.skip_download:
        # 下载依赖包
        pkg_path = download_packages(args.output)
    else:
        pkg_path = output_path / 'packages'
        pkg_path.mkdir(exist_ok=True)
        print("跳过依赖包下载")
    
    # 打包项目
    project_path = package_project(args.output)
    
    # 创建说明文件
    readme = output_path / 'README.md'
    if not readme.exists():
        readme.write_text(f"# 离线部署包\n\n生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n包含:\n- packages/: Python依赖wheel包\n- project/: 项目源代码\n\n使用方法:\n```bash\n./scripts/deploy_oneclick.sh --offline-dir ../{args.output}/packages\n```\n")
    
    print("\n" + "=" * 60)
    print("✅ 离线部署包准备完成")
    print(f"   路径: {output_path}")
    print("=" * 60)

if __name__ == '__main__':
    main()
