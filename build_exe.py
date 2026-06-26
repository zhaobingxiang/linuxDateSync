#!/usr/bin/env python
"""
DateSync 打包脚本

使用方法：
1. 安装 Python 3.12+
2. 创建虚拟环境并安装依赖：
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
3. 运行此脚本：
   python build_exe.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def build_exe():
    # 定义路径
    project_dir = Path(__file__).parent
    dist_dir = project_dir / 'dist_new'
    build_dir = project_dir / 'build_new'
    
    # 确保输出目录存在
    dist_dir.mkdir(exist_ok=True)
    build_dir.mkdir(exist_ok=True)
    
    # 准备 PyInstaller 参数
    args = [
        sys.executable,
        '-m', 'PyInstaller',
        'main.py',
        '--name=DateSync',
        '--onefile',
        '--windowed',
        '--icon=logo.ico',
        '--distpath=' + str(dist_dir),
        '--workpath=' + str(build_dir),
        '--specpath=' + str(project_dir),
        '--add-data=logo.ico;.',
        '--add-data=logo.jpeg;.',
        '--clean',
        '--noconfirm',
    ]
    
    print(f"Building executable with command: {' '.join(args)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(args, cwd=project_dir, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Build completed successfully!")
            print("-" * 60)
            print(f"Executable location: {dist_dir / 'DateSync.exe'}")
            print("\n打包成功！请在 dist_new 目录中找到 DateSync.exe")
            return True
        else:
            print(f"Build failed with error code: {result.returncode}")
            print("STDERR:", result.stderr)
            print("STDOUT:", result.stdout)
            return False
    except Exception as e:
        print(f"Build failed with exception: {str(e)}")
        return False

if __name__ == '__main__':
    # 检查是否有足够的参数
    if len(sys.argv) == 1:
        # 直接运行打包
        success = build_exe()
        sys.exit(0 if success else 1)
    elif len(sys.argv) == 2 and sys.argv[1] == '--help':
        print(__doc__)
        sys.exit(0)
    else:
        print("Usage: python build_exe.py [--help]")
        sys.exit(1)
