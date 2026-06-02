# C盘扫描和安全清理工具 v2.5

这是一个基于 Python/Tkinter 的 Windows 桌面工具，用于扫描磁盘空间、查看大文件、查找重复文件，并安全清理临时文件、浏览器缓存、系统缓存等内容。

## 当前状态

本版本已修复主界面在加入右侧滚动条和宽度自适应后空白、未响应的问题。根因是滚动容器的 `<Configure>` 事件互相触发，造成 Tk 主线程布局循环。现在主界面使用标准的 Canvas + Frame 滚动布局：

- Frame 尺寸变化只更新滚动区域。
- Canvas 尺寸变化才同步内部窗口宽度。
- 启动时不会自动扫描清理建议，避免界面加载阶段卡顿。
- 耗时操作改为后台线程执行，并通过主线程安全更新界面。

## 启动方式

推荐双击：

```bat
启动.bat
```

脚本会优先使用项目内 `.venv\Scripts\python.exe`，找不到虚拟环境时才使用系统 Python。

也可以手动运行：

```powershell
.\.venv\Scripts\python.exe main.py
```

建议以管理员身份运行，这样系统缓存、回收站和右键菜单等功能权限更完整。

## 主要功能

- 磁盘扫描：统计文件数量、大小、大文件和文件类型分布。
- 安全清理：清理临时文件、浏览器缓存、Windows 更新缓存、Prefetch、缩略图缓存和系统日志。
- 重复文件：按大小和哈希查找重复文件，支持选择、移动和删除。
- 磁盘可视化：使用 matplotlib 展示目录占用、文件扩展名和分类分布。
- 历史记录：保存扫描历史和清理日志。
- 文件恢复：从备份目录恢复清理前备份的文件。
- 设置：主题切换、定时清理、白名单、右键菜单、依赖检查和打包入口。

## 项目结构

```text
main.py              主界面和交互逻辑
scanner.py           磁盘扫描、重复文件和统计逻辑
cleaner.py           清理规则、白名单、备份和删除逻辑
build.py             PyInstaller 打包脚本
run_tests.py         自动化测试入口
tests/test_core.py   核心行为测试
help/                应用帮助文本
启动.bat             Windows 快速启动脚本
```

## 可再生成目录

以下目录不是源码，可以删除：

```text
build/
dist/
__pycache__/
tests/__pycache__/
tmp/
```

其中 `tmp/` 是测试失败时的临时目录。如果遇到权限拒绝，需要用管理员权限删除或重新获取目录所有权。

## 测试

运行：

```powershell
.\.venv\Scripts\python.exe run_tests.py
```

如果当前系统临时目录权限异常，可以先指定项目内临时目录：

```powershell
New-Item -ItemType Directory -Force -Path .\test_tmp | Out-Null
$env:TEMP=(Resolve-Path .\test_tmp).Path
$env:TMP=$env:TEMP
.\.venv\Scripts\python.exe run_tests.py
```

## 打包

运行：

```powershell
.\.venv\Scripts\python.exe build.py
```

打包产物会生成到 `dist/`，构建中间文件生成到 `build/`。这些目录不需要提交或长期保留。

## 安全建议

- 先预览或计算可清理空间，再执行清理。
- 删除大文件或重复文件前请确认不再需要。
- 对重要文件启用白名单或备份。
- 深度清理项目请谨慎启用。
- 系统目录清理建议使用管理员权限。

## 定时清理

定时清理支持“每 N 天”执行一次。常用设置：

- 每天：间隔填 `1`。
- 每周：间隔填 `7`，或点击“每周”快捷按钮。
- 每 10 天：间隔填 `10`。
- 半个月：间隔填 `15`，或点击“半月”快捷按钮。

计划会保存到 `app_settings.json`，重启后会自动恢复。
