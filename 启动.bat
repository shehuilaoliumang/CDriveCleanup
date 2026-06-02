@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo ========================================
echo   C盘扫描和安全清理工具 - 快速启动
echo ========================================
echo.

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if exist "%PYTHON_EXE%" (
    echo [信息] 使用项目虚拟环境启动。
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [错误] 未检测到 Python，也未找到项目虚拟环境。
        echo 请先安装 Python 3.7+，或重新创建 .venv 虚拟环境。
        pause
        exit /b 1
    )
    set "PYTHON_EXE=python"
    echo [信息] 使用系统 Python 启动。
)

net session >nul 2>&1
if errorlevel 1 (
    echo [警告] 当前不是管理员权限，部分系统清理功能可能受限。
) else (
    echo [信息] 当前为管理员权限。
)

echo.
echo [信息] 正在启动程序...
"%PYTHON_EXE%" "%~dp0main.py"

if errorlevel 1 (
    echo.
    echo [错误] 程序运行出错。
    pause
)

endlocal
