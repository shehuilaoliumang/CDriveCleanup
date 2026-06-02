#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C盘扫描和安全清理工具 - 一键打包脚本
使用PyInstaller打包为独立的exe文件
"""

import os
import sys
import subprocess
import shutil


def check_dependencies():
    """检查依赖是否已安装"""
    print("检查依赖...")
    
    required_packages = ['pyinstaller']
    
    for package in required_packages:
        try:
            __import__('PyInstaller' if package == 'pyinstaller' else package)
            print(f"[OK] {package} 已安装")
        except ImportError:
            print(f"[MISSING] {package} 未安装，正在安装...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"[OK] {package} 安装成功")
    
    # 检查可选依赖
    optional_packages = {
        'pillow': 'PIL',
        'pystray': 'pystray',
        'matplotlib': 'matplotlib',
        'psutil': 'psutil',
    }
    for package, import_name in optional_packages.items():
        try:
            __import__(import_name)
            print(f"[OK] {package} 已安装（可选）")
        except ImportError:
            print(f"[OPTIONAL] {package} 未安装（可选，不影响核心功能）")
    
    print("所有依赖检查完成！\n")


def clean_build():
    """清理之前的构建文件"""
    print("清理之前的构建文件...")
    dirs_to_remove = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"[OK] 已删除 {dir_name}")
            except Exception as e:
                print(f"[WARN] 无法删除 {dir_name}: {e}")
    
    files_to_remove = [f for f in os.listdir('.') if f.endswith('.spec')]
    for file_name in files_to_remove:
        try:
            os.remove(file_name)
            print(f"[OK] 已删除 {file_name}")
        except Exception as e:
            print(f"[WARN] 无法删除 {file_name}: {e}")
    
    print("清理完成！\n")


def build_executable():
    """使用PyInstaller构建exe文件"""
    print("开始构建...")
    
    # 构建参数
    pyinstaller_args = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name=CDriveCleanup',
        '--clean',
        '--noconfirm',
    ]
    
    # 添加数据文件
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pyinstaller_args.extend([
        f'--add-data={os.path.join(script_dir, "scanner.py")};.',
        f'--add-data={os.path.join(script_dir, "cleaner.py")};.',
    ])
    
    # 隐藏导入
    pyinstaller_args.extend([
        '--hidden-import=PIL._tkinter_finder',
        '--hidden-import=pystray',
        '--hidden-import=matplotlib',
        '--hidden-import=matplotlib.backends.backend_tkagg',
        '--hidden-import=psutil',
    ])
    
    # 主文件
    pyinstaller_args.append(os.path.join(script_dir, 'main.py'))
    
    try:
        print("执行 PyInstaller 命令...")
        print(f"命令：{' '.join(pyinstaller_args[:10])} ...")
        subprocess.check_call(pyinstaller_args)
        print("\n[OK] 构建成功！")
        
        exe_path = os.path.join(script_dir, 'dist', 'CDriveCleanup.exe')
        if os.path.exists(exe_path):
            size = os.path.getsize(exe_path)
            size_mb = size / (1024 * 1024)
            print(f"[OK] 可执行文件位置：{exe_path}")
            print(f"[OK] 文件大小：{size_mb:.2f} MB")
            
            return True, exe_path
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] 构建失败 (返回码：{e.returncode})")
        return False, None
    except Exception as e:
        print(f"\n[ERROR] 构建失败：{e}")
        return False, None


def main():
    print("="*60)
    print("C盘扫描和安全清理工具 - 一键打包脚本")
    print("="*60)
    print()
    
    # 切换到脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"工作目录: {script_dir}")
    print()
    
    # 检查依赖
    check_dependencies()
    
    # 清理构建文件
    clean_build()
    
    # 构建
    success, exe_path = build_executable()
    
    if success:
        print("\n" + "="*60)
        print("打包完成！")
        print("="*60)
        print("\n提示:")
        print("1. 生成的exe文件位于 dist 文件夹中")
        print(f"2. 完整路径: {exe_path}")
        print("3. 可以直接运行该exe文件，无需安装Python")
        print("4. 建议以管理员身份运行以获得完整功能")
    else:
        print("\n打包失败，请检查错误信息！")
        print("\n常见问题:")
        print("- 确保以管理员身份运行")
        print("- 检查是否有足够的磁盘空间")
        print("- 尝试手动安装PyInstaller: pip install pyinstaller")
        sys.exit(1)


if __name__ == "__main__":
    main()
