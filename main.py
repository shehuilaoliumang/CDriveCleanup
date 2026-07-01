# pyright: reportGeneralTypeIssues=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportUnknownVariableType=false

from typing import Any, cast
import importlib.util
from pathlib import Path

import tkinter as _tk
import tkinter.ttk as _ttk
from tkinter import messagebox as _messagebox, scrolledtext as _scrolledtext, filedialog as _filedialog, simpledialog as _simpledialog
import threading
import datetime
import os
import shutil
import json
import ctypes
import hashlib
import sys
from queue import Queue
from scanner import DiskScanner
from cleaner import DiskCleaner

tk = cast(Any, _tk)
ttk = cast(Any, _ttk)
messagebox = cast(Any, _messagebox)
scrolledtext = cast(Any, _scrolledtext)
filedialog = cast(Any, _filedialog)
simpledialog = cast(Any, _simpledialog)

HAS_MATPLOTLIB = importlib.util.find_spec('matplotlib') is not None
HAS_PYSTRAY = importlib.util.find_spec('pystray') is not None and importlib.util.find_spec('PIL') is not None
HAS_PSUTIL = importlib.util.find_spec('psutil') is not None

if not HAS_MATPLOTLIB:
    print("警告: matplotlib未安装，磁盘可视化功能将不可用")

if not HAS_PYSTRAY:
    print("警告: pystray未安装，系统托盘功能将不可用")

if not HAS_PSUTIL:
    print("警告: psutil未安装，性能监控功能将不可用")


def _load_matplotlib_backend():
    if not HAS_MATPLOTLIB:
        return None, None, None
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    return matplotlib, FigureCanvasTkAgg, Figure


def _setup_chinese_font():
    """配置matplotlib中文字体显示，避免方块乱码"""
    if not HAS_MATPLOTLIB:
        return None
    try:
        import os
        import glob
        import matplotlib
        from matplotlib import font_manager
        import matplotlib.pyplot as plt

        # 1. 清除matplotlib字体缓存，强制重建
        try:
            cache_dir = matplotlib.get_cachedir()
            for cache_file in glob.glob(os.path.join(cache_dir, 'fontlist*.json')):
                try:
                    os.remove(cache_file)
                except Exception:
                    pass
        except Exception:
            pass

        # 2. 强制从Windows字体目录加载中文字体文件
        win_fonts_dir = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
        loaded_fonts = []
        if os.path.exists(win_fonts_dir):
            font_files_to_try = [
                ('msyh.ttc', 'Microsoft YaHei'),
                ('msyhbd.ttc', 'Microsoft YaHei'),
                ('msyh.ttf', 'Microsoft YaHei'),
                ('simhei.ttf', 'SimHei'),
                ('simsun.ttc', 'SimSun'),
                ('simfang.ttf', 'FangSong'),
                ('simkai.ttf', 'KaiTi'),
                ('msyh_light.ttc', 'Microsoft YaHei Light'),
            ]
            for font_file, font_name in font_files_to_try:
                font_path = os.path.join(win_fonts_dir, font_file)
                if os.path.exists(font_path):
                    try:
                        font_manager.fontManager.addfont(font_path)
                        loaded_fonts.append(font_name)
                    except Exception:
                        pass

        # 3. 强制重新构建字体管理器（关键步骤）
        try:
            font_manager.fontManager.__init__()
        except Exception:
            pass

        # 4. 查找所有可用的字体名称
        available = sorted({f.name for f in font_manager.fontManager.ttflist})

        # 5. 优先级匹配最佳中文字体
        chosen = None
        priority_fonts = [
            'Microsoft YaHei UI',
            'Microsoft YaHei',
            '微软雅黑',
            'SimHei',
            '黑体',
            'SimSun',
            '宋体',
            'NSimSun',
            '新宋体',
            'Microsoft JhengHei',
            'PingFang SC',
            'Heiti SC',
            'STHeiti',
            'STSong',
            'WenQuanYi Micro Hei',
            'Noto Sans CJK SC',
            'Arial Unicode MS',
        ]
        for name in priority_fonts:
            if name in available:
                chosen = name
                break

        # 6. 模糊匹配作为备选
        if chosen is None:
            for name in available:
                lower = name.lower()
                if any(kw in lower for kw in ['yahei', 'simhei', 'simsun', 'heiti', 'songti', 'cjk', 'noto sans cjk', 'microsoft']):
                    chosen = name
                    break

        # 7. 最后的备选
        if chosen is None:
            for name in available:
                lower = name.lower()
                if any(kw in lower for kw in ['unicode', 'noto', 'wqy', 'arphic']):
                    chosen = name
                    break

        if chosen:
            # 关键：完整设置所有相关rcParams
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.sans-serif'] = [chosen, 'DejaVu Sans', 'Bitstream Vera Sans', 'sans-serif']
            plt.rcParams['font.serif'] = [chosen, 'DejaVu Serif', 'Bitstream Vera Serif', 'serif']
            plt.rcParams['axes.unicode_minus'] = False
            plt.rcParams['pdf.fonttype'] = 42
            plt.rcParams['ps.fonttype'] = 42
            return chosen
        return None
    except Exception:
        return None


def _load_tray_modules():
    if not HAS_PYSTRAY:
        return None, None, None
    from PIL import Image, ImageDraw
    import pystray
    return Image, ImageDraw, pystray


def is_admin():
    try:
        shell32 = getattr(ctypes.windll, 'shell32', None)
        if shell32 is None:
            return False
        checker = getattr(shell32, 'IsUserAnAdmin', None)
        return bool(checker()) if callable(checker) else False
    except:
        return False


def get_file_hash(filepath):
    try:
        hash_obj = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except:
        return None


def load_app_settings(settings_file):
    try:
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except:
        pass
    return {}


def save_app_settings(settings_file, settings):
    try:
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except:
        pass


def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


class CDriveCleanupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("C盘扫描和安全清理工具 v2.5")
        # 设置窗口位置在屏幕中央
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - 1200) // 2
        y = (screen_height - 900) // 2
        self.root.geometry(f"1200x900+{x}+{y}")
        # 强制窗口显示
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 1.0)  # 完全不透明
        self.root.deiconify()  # 确保窗口未被最小化
        self.root.after(1000, lambda: self.root.attributes('-topmost', False))
        self.root.update_idletasks()
        print(f"Window created at position ({x}, {y})")
        print(f"Window geometry: {self.root.winfo_geometry()}")
        print(f"Window visible: {self.root.winfo_viewable()}")
        self.scanner = DiskScanner()
        self.app_dir = get_app_dir()
        self.cleaner = DiskCleaner(self.app_dir)
        self.scan_results = None
        self.is_scanning = False
        self.current_scan_path = 'C:\\'
        self.large_files = []
        self.scan_history = []
        self.cleanup_log = []
        self.duplicate_results = None
        self.selected_duplicates = set()
        self.history_file = os.path.join(self.app_dir, 'scan_history.json')
        self.cleanup_log_file = os.path.join(self.app_dir, 'cleanup_log.json')
        self.scan_state_file = os.path.join(self.app_dir, 'scan_state.json')
        self.file_hashes_file = os.path.join(self.app_dir, 'file_hashes.json')
        self.settings_file = os.path.join(self.app_dir, 'app_settings.json')
        self.file_hashes = {}
        self.scan_state = None
        self.dark_mode = False
        self.schedule_timer = None
        self.schedule_running = False
        self._scheduled_cleanup_active = False
        self.saved_schedule_enabled = False
        self.saved_schedule_hour = "02"
        self.saved_schedule_minute = "00"
        self.saved_schedule_interval_days = "1"
        self.saved_schedule_categories = {'temp': True, 'browser_cache': True}
        self.last_schedule_run_date = ""
        self.tray_icon = None
        self.tray_thread = None
        self._suggestions_loading = False
        self._latest_suggestions = None
        self._light_theme_widget_bg = '#ffffff'
        self._dark_theme_widget_bg = '#2b2b2b'
        
        self._load_settings()
        self._create_widgets()
        self._setup_theme()
        self._setup_tray()
        self._check_dependencies()
        
        # 将耗时操作移到后台线程
        def load_data():
            self._load_history()
            self._load_cleanup_log()
            self._load_file_hashes()
            self._load_scan_state()
            self.dark_mode = bool(self.dark_mode)
            # 在主线程中更新UI
            self.root.after(0, self._check_context_menu_status)
        
        import threading
        threading.Thread(target=load_data, daemon=True).start()
        self._setup_keyboard_shortcuts()
        
        if not is_admin():
            self.status_label.config(text="警告: 建议以管理员身份运行以获得完整功能")

    def _setup_keyboard_shortcuts(self):
        self.root.bind('<F5>', lambda e: self._start_scan())
        self.root.bind('<Control-s>', lambda e: self._save_settings())
        self.root.bind('<Control-h>', lambda e: self._toggle_theme())
        self.root.bind('<Control-f>', lambda e: self.search_var.set('') or self.search_entry.focus_set())
        self.root.bind('<Escape>', lambda e: self._clear_search())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
        self.root.bind('<F1>', lambda e: self._show_help())

    def _load_history(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.scan_history = json.load(f)
        except:
            self.scan_history = []

    def _save_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.scan_history, f, ensure_ascii=False, indent=2)
        except:
            pass

    def _load_cleanup_log(self):
        try:
            if os.path.exists(self.cleanup_log_file):
                with open(self.cleanup_log_file, 'r', encoding='utf-8') as f:
                    self.cleanup_log = json.load(f)
        except:
            self.cleanup_log = []

    def _save_cleanup_log(self):
        try:
            with open(self.cleanup_log_file, 'w', encoding='utf-8') as f:
                json.dump(self.cleanup_log, f, ensure_ascii=False, indent=2)
        except:
            pass

    def _load_file_hashes(self):
        try:
            if os.path.exists(self.file_hashes_file):
                with open(self.file_hashes_file, 'r', encoding='utf-8') as f:
                    self.file_hashes = json.load(f)
        except:
            self.file_hashes = {}

    def _save_file_hashes(self):
        try:
            with open(self.file_hashes_file, 'w', encoding='utf-8') as f:
                json.dump(self.file_hashes, f, ensure_ascii=False, indent=2)
        except:
            pass

    def _load_scan_state(self):
        try:
            if os.path.exists(self.scan_state_file):
                with open(self.scan_state_file, 'r', encoding='utf-8') as f:
                    self.scan_state = json.load(f)
        except:
            self.scan_state = None

    def _load_settings(self):
        settings = load_app_settings(self.settings_file)
        self.dark_mode = bool(settings.get('dark_mode', False))
        schedule = settings.get('schedule', {})
        if isinstance(schedule, dict):
            self.saved_schedule_enabled = bool(schedule.get('enabled', False))
            self.saved_schedule_hour = str(schedule.get('hour', "02")).zfill(2)
            self.saved_schedule_minute = str(schedule.get('minute', "00")).zfill(2)
            self.saved_schedule_interval_days = str(schedule.get('interval_days', "1"))
            categories = schedule.get('categories', {})
            if isinstance(categories, dict):
                self.saved_schedule_categories = {
                    'temp': bool(categories.get('temp', True)),
                    'browser_cache': bool(categories.get('browser_cache', True)),
                }
            self.last_schedule_run_date = str(schedule.get('last_run_date', ""))

    def _save_settings(self):
        schedule_categories = {}
        if hasattr(self, 'schedule_categories'):
            schedule_categories = {cat: bool(var.get()) for cat, var in self.schedule_categories.items()}
        else:
            schedule_categories = dict(self.saved_schedule_categories)

        save_app_settings(self.settings_file, {
            'dark_mode': bool(self.dark_mode),
            'schedule': {
                'enabled': bool(self.schedule_enabled.get()) if hasattr(self, 'schedule_enabled') else bool(self.saved_schedule_enabled),
                'hour': self.schedule_hour.get() if hasattr(self, 'schedule_hour') else self.saved_schedule_hour,
                'minute': self.schedule_minute.get() if hasattr(self, 'schedule_minute') else self.saved_schedule_minute,
                'interval_days': self.schedule_interval_days.get() if hasattr(self, 'schedule_interval_days') else self.saved_schedule_interval_days,
                'categories': schedule_categories,
                'last_run_date': self.last_schedule_run_date,
            }
        })

    def _save_scan_state(self, state):
        try:
            with open(self.scan_state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except:
            pass

    def _clear_scan_state(self):
        try:
            if os.path.exists(self.scan_state_file):
                os.remove(self.scan_state_file)
            self.scan_state = None
        except:
            pass

    def _add_cleanup_log_entry(self, categories, deleted_count, freed_size, backup):
        entry = {
            'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'categories': categories,
            'deleted_count': deleted_count,
            'freed_size': freed_size,
            'freed_size_formatted': self.cleaner.format_size(freed_size),
            'backup': backup
        }
        self.cleanup_log.insert(0, entry)
        if len(self.cleanup_log) > 100:
            self.cleanup_log = self.cleanup_log[:100]
        self._save_cleanup_log()

    def _setup_theme(self):
        self.style = ttk.Style()
        try:
            if 'clam' in self.style.theme_names():
                self.style.theme_use('clam')
        except:
            pass
        if self.dark_mode:
            self._apply_dark_theme()
        else:
            self._apply_light_theme()

    def _update_theme_button_text(self):
        if hasattr(self, 'theme_button'):
            self.theme_button.config(text="☀️ 浅色模式" if self.dark_mode else "🌙 深色模式")

    def _theme_palette(self):
         if self.dark_mode:
             return {
                 'window_bg': '#232323',
                 'dialog_bg': '#282828',
                 'panel_bg': '#2d2d2d',
                 'text_bg': '#1f1f1f',
                 'text_fg': '#f2f2f2',
                 'muted_fg': '#dcdcdc',
                 'button_bg': '#3c3c3c',
                 'button_fg': '#f2f2f2',
                 'button_active_bg': '#4e4e4e',
                 'button_pressed_bg': '#5a5a5a',
                 'button_disabled_fg': '#808080',
                 'tree_hover_bg': '#3a3a3a',
                 'tab_bg': '#343434',
                 'tab_selected_bg': '#454545',
                 'tree_bg': '#2f2f2f',
                 'tree_fg': '#f2f2f2',
                 'tree_heading_bg': '#3f3f3f',
                 'tree_heading_fg': '#ffffff',
                 'selection_bg': '#005a9e',
                 'selection_fg': '#ffffff',
                 'focus_bg': '#0078d4',
                 'entry_bg': '#2a2a2a',
                 'entry_fg': '#f2f2f2',
                 'entry_focus_bg': '#2f2f2f',
                 'progress_bg': '#2196F3',
                 'scrollbar_bg': '#4a4a4a',
                 'scrollbar_trough': '#1f1f1f',
                 'scrollbar_active': '#5c5c5c',
             }
         return {
             'window_bg': '#f0f0f0',
             'dialog_bg': '#f5f5f5',
             'panel_bg': '#f0f0f0',
             'text_bg': '#ffffff',
             'text_fg': '#000000',
             'muted_fg': '#111111',
             'button_bg': '#e0e0e0',
             'button_fg': '#000000',
             'button_active_bg': '#d0d0d0',
             'button_pressed_bg': '#b0b0b0',
             'button_disabled_fg': '#a0a0a0',
             'tree_hover_bg': '#f5f5f5',
             'tab_bg': '#e0e0e0',
             'tab_selected_bg': '#ffffff',
             'tree_bg': '#ffffff',
             'tree_fg': '#000000',
             'tree_heading_bg': '#d0d0d0',
             'tree_heading_fg': '#000000',
             'selection_bg': '#0078d4',
             'selection_fg': '#ffffff',
             'focus_bg': '#0078d4',
             'entry_bg': '#ffffff',
             'entry_fg': '#000000',
             'entry_focus_bg': '#f9f9f9',
             'progress_bg': '#4CAF50',
             'scrollbar_bg': '#d0d0d0',
             'scrollbar_trough': '#f0f0f0',
             'scrollbar_active': '#b0b0b0',
         }

    def _apply_theme_styles(self, palette):
        self.root.configure(bg=palette['window_bg'])
        self.style.configure('TFrame', background=palette['panel_bg'])
        self.style.configure('TLabel', background=palette['panel_bg'], foreground=palette['text_fg'])
        self.style.configure('TLabelframe', background=palette['panel_bg'], foreground=palette['text_fg'])
        self.style.configure('TLabelframe.Label', background=palette['panel_bg'], foreground=palette['text_fg'])
        self.style.configure('TButton', background=palette['button_bg'], foreground=palette['button_fg'], padding=(8, 4))
        self.style.map('TButton',
            background=[('pressed', palette['button_pressed_bg']), ('active', palette['button_active_bg']), ('disabled', palette['button_bg'])],
            foreground=[('disabled', palette['button_disabled_fg'])]
        )
        self.style.configure('TCheckbutton', background=palette['panel_bg'], foreground=palette['text_fg'])
        self.style.map('TCheckbutton', background=[('active', palette['panel_bg']), ('disabled', palette['panel_bg'])], foreground=[('disabled', palette['button_disabled_fg'])])
        self.style.configure('TNotebook', background=palette['panel_bg'])
        self.style.configure('TNotebook.Tab', background=palette['tab_bg'], foreground=palette['text_fg'], padding=(10, 6))
        self.style.map('TNotebook.Tab', background=[('selected', palette['tab_selected_bg'])], foreground=[('selected', palette['text_fg'])])
        self.style.configure('Treeview', background=palette['tree_bg'], foreground=palette['tree_fg'], fieldbackground=palette['tree_bg'], rowheight=24)
        self.style.configure('Treeview.Heading', background=palette['tree_heading_bg'], foreground=palette['tree_heading_fg'])
        self.style.map('Treeview',
            background=[('selected', palette['selection_bg']), ('focus', palette['focus_bg'])],
            foreground=[('selected', palette['selection_fg'])],
        )
        self.style.configure('TProgressbar', background=palette['progress_bg'])
        self.style.configure('TEntry', fieldbackground=palette['entry_bg'], foreground=palette['entry_fg'])
        self.style.map('TEntry', fieldbackground=[('focus', palette['entry_focus_bg'])], foreground=[('disabled', palette['button_disabled_fg'])])
        self.style.configure('TSpinbox', fieldbackground=palette['entry_bg'], foreground=palette['entry_fg'])
        self.style.map('TSpinbox', fieldbackground=[('focus', palette['entry_focus_bg'])], foreground=[('disabled', palette['button_disabled_fg'])])
        self.style.configure('TCombobox', fieldbackground=palette['entry_bg'], foreground=palette['entry_fg'])
        self.style.map('TCombobox', fieldbackground=[('focus', palette['entry_focus_bg'])], foreground=[('disabled', palette['button_disabled_fg'])])
        self.style.configure('TMenubutton', background=palette['button_bg'], foreground=palette['button_fg'])
        self.style.configure('TSeparator', background=palette['muted_fg'])
        self.style.configure('Vertical.TScrollbar', background=palette['scrollbar_bg'], troughcolor=palette['scrollbar_trough'], arrowcolor=palette['text_fg'])
        self.style.configure('Horizontal.TScrollbar', background=palette['scrollbar_bg'], troughcolor=palette['scrollbar_trough'], arrowcolor=palette['text_fg'])

    def _apply_text_widget_theme(self, widget, palette):
        try:
            widget.configure(
                bg=palette['text_bg'],
                fg=palette['text_fg'],
                insertbackground=palette['text_fg'],
                selectbackground=palette['selection_bg'],
                selectforeground=palette['selection_fg'],
                highlightbackground=palette['panel_bg'],
                highlightcolor=palette['selection_bg'],
                relief='flat',
                bd=0,
            )
        except:
            pass

    def _apply_scrollbar_theme(self, widget, palette):
        try:
            widget.configure(
                bg=palette['scrollbar_bg'],
                troughcolor=palette['scrollbar_trough'],
                activebackground=palette['scrollbar_active'],
                highlightthickness=0,
                relief='flat',
            )
        except:
            pass

    def _refresh_dynamic_theme(self):
        palette = self._theme_palette()

        def walk(widget):
            try:
                class_name = widget.winfo_class()
            except:
                class_name = ''

            if class_name == 'Text':
                self._apply_text_widget_theme(widget, palette)
            elif class_name == 'Scrollbar':
                self._apply_scrollbar_theme(widget, palette)
            elif class_name == 'Toplevel':
                try:
                    widget.configure(bg=palette.get('dialog_bg', palette['window_bg']))
                except:
                    pass

            for child in getattr(widget, 'winfo_children', lambda: [])():
                walk(child)

        walk(self.root)

    def _apply_light_theme(self):
        self.dark_mode = False
        palette = self._theme_palette()
        self._apply_theme_styles(palette)
        self._refresh_dynamic_theme()
        self._update_theme_button_text()

    def _apply_dark_theme(self):
        self.dark_mode = True
        palette = self._theme_palette()
        self._apply_theme_styles(palette)
        self._refresh_dynamic_theme()
        self._update_theme_button_text()

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self._apply_dark_theme()
        else:
            self._apply_light_theme()
        self._save_settings()

    def _set_light_theme(self):
        self._apply_light_theme()
        self._save_settings()

    def _show_help(self):
        help_window = tk.Toplevel(self.root)
        help_window.title("快捷键帮助")
        help_window.geometry("400x300")
        help_window.transient(self.root)
        
        help_text = """
快捷键说明:
═══════════════════════════
F5      - 开始扫描
Ctrl+S  - 保存设置
Ctrl+H  - 切换深色/浅色主题
Ctrl+F  - 聚焦到搜索框
Escape  - 清除搜索
Ctrl+Q  - 退出程序
F1      - 显示此帮助
═══════════════════════════

交互功能:
• 点击饼图扇形可打开对应文件夹
• 点击柱状图条可打开对应文件夹
• 按扩展名筛选大文件列表
"""
        help_label = ttk.Label(help_window, text=help_text, font=('Consolas', 10), justify=tk.LEFT)
        help_label.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        close_btn = ttk.Button(help_window, text="关闭", command=help_window.destroy)
        close_btn.pack(pady=5)

    def _get_windows_theme(self):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return value == 0
        except Exception:
            return False

    def _toggle_auto_theme(self):
        if self.auto_theme_var.get():
            self._apply_system_theme()

    def _apply_system_theme(self):
        is_dark = self._get_windows_theme()
        if is_dark != self.dark_mode:
            self.dark_mode = is_dark
            if self.dark_mode:
                self._apply_dark_theme()
            else:
                self._apply_light_theme()

    def _start_theme_watcher(self):
        self._check_system_theme()

    def _check_system_theme(self):
        if self.auto_theme_var.get():
            self._apply_system_theme()
        self.root.after(5000, self._check_system_theme)

    def _create_performance_panel(self):
        perf_frame = ttk.LabelFrame(self.main_frame, text="📊 系统性能", padding=5)
        perf_frame.pack(fill=tk.X, padx=10, pady=5)

        self.cpu_label = ttk.Label(perf_frame, text="CPU: --%")
        self.cpu_label.pack(side=tk.LEFT, padx=10)

        self.memory_label = ttk.Label(perf_frame, text="内存: --")
        self.memory_label.pack(side=tk.LEFT, padx=10)

        self.disk_label = ttk.Label(perf_frame, text="磁盘: --")
        self.disk_label.pack(side=tk.LEFT, padx=10)

        self.cpu_bar = ttk.Progressbar(perf_frame, mode='determinate', length=100)
        self.cpu_bar.pack(side=tk.LEFT, padx=5)

        self.memory_bar = ttk.Progressbar(perf_frame, mode='determinate', length=100)
        self.memory_bar.pack(side=tk.LEFT, padx=5)

        self._update_performance()

    def _update_performance(self):
        if not HAS_PSUTIL:
            return
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return

        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=0)
            self.cpu_label.config(text=f"CPU: {cpu_percent}%")
            self.cpu_bar['value'] = cpu_percent

            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used = self._format_bytes(memory.used)
            memory_total = self._format_bytes(memory.total)
            self.memory_label.config(text=f"内存: {memory_used}/{memory_total} ({memory_percent}%)")
            self.memory_bar['value'] = memory_percent

            disk_path = self.current_scan_path if os.path.exists(self.current_scan_path) else os.path.abspath(os.sep)
            disk = psutil.disk_usage(disk_path)
            disk_percent = disk.percent
            disk_used = self._format_bytes(disk.used)
            disk_total = self._format_bytes(disk.total)
            self.disk_label.config(text=f"磁盘: {disk_used}/{disk_total} ({disk_percent}%)")

        except Exception:
            pass

        try:
            self.root.after(1000, self._update_performance)
        except Exception:
            pass

    def _format_bytes(self, bytes_value):
        if bytes_value < 1024:
            return f"{bytes_value} B"
        elif bytes_value < 1024 * 1024:
            return f"{bytes_value / 1024:.1f} KB"
        elif bytes_value < 1024 * 1024 * 1024:
            return f"{bytes_value / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_value / (1024 * 1024 * 1024):.2f} GB"

    def _create_widgets(self):
        # 优化主画布尺寸更新策略，避免构建过程频繁触发布局回流
        self._main_canvas_update_job = None
        self._main_canvas_last_width = 0

        # 创建主滚动条
        self.main_scrollbar = ttk.Scrollbar(self.root, orient=tk.VERTICAL)
        self.main_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.main_h_scrollbar = ttk.Scrollbar(self.root, orient=tk.HORIZONTAL)
        self.main_h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 创建主画布
        self.main_canvas = tk.Canvas(
            self.root,
            yscrollcommand=self.main_scrollbar.set,
            xscrollcommand=self.main_h_scrollbar.set,
            highlightthickness=0,
            borderwidth=0
        )
        self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.main_scrollbar.config(command=self.main_canvas.yview)
        self.main_h_scrollbar.config(command=self.main_canvas.xview)
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.main_canvas)
        self.main_canvas_window = self.main_canvas.create_window((0, 0), window=self.main_frame, anchor=tk.NW)

        # 统一延迟更新主画布滚动区域，避免每次控件配置都触发布局计算
        def schedule_canvas_reflow(*_):
            if self._main_canvas_update_job is not None:
                return
            self._main_canvas_update_job = self.root.after_idle(self._refresh_main_canvas_layout)

        self.main_frame.bind('<Configure>', schedule_canvas_reflow)
        self.main_canvas.bind('<Configure>', schedule_canvas_reflow)
        
        def on_mousewheel(event):
            self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        self.root.bind('<MouseWheel>', on_mousewheel)
        
        # 创建头部框架
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 标题
        title_label = ttk.Label(header_frame, text="C盘扫描和安全清理工具 v2.5", font=('Microsoft YaHei', 14, 'bold'))
        title_label.pack(side=tk.LEFT, padx=5)
        
        # 主题切换按钮
        self.theme_button = ttk.Button(header_frame, text="🌙 深色模式", command=self._toggle_theme)
        self.theme_button.pack(side=tk.RIGHT, padx=5)
        
        # 性能监控面板（如果有psutil）
        if HAS_PSUTIL:
            self._create_performance_panel()
        
        # 创建标签页
        notebook = ttk.Notebook(self.main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建所有标签页
        self._create_scan_tab(notebook)
        self._create_cleanup_tab(notebook)
        self._create_duplicate_tab(notebook)
        self._create_visualization_tab(notebook)
        self._create_history_tab(notebook)
        self._create_restore_tab(notebook)
        self._create_settings_tab(notebook)
        
        # 强制刷新UI
        self.root.update_idletasks()
        self._refresh_main_canvas_layout()

    def _create_tree_with_scrollbars(self, parent, tree, pack_args=None):
        container = ttk.Frame(parent)
        if pack_args is None:
            pack_args = {"fill": tk.BOTH, "expand": True}
        v_scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        h_scrollbar = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        tree.pack(side=tk.LEFT, fill=pack_args.get("fill", tk.BOTH), expand=pack_args.get("expand", True))
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        return container

    def _refresh_main_canvas_layout(self):
        self._main_canvas_update_job = None
        try:
            bbox = self.main_canvas.bbox('all')
            if bbox:
                self.main_canvas.configure(scrollregion=bbox)
        except Exception:
            return

        try:
            viewport_width = self.main_canvas.winfo_width()
            if viewport_width <= 0:
                return
            content_width = self.main_frame.winfo_reqwidth()
            target_width = max(viewport_width, content_width)
            if target_width != self._main_canvas_last_width:
                self.main_canvas.itemconfigure(self.main_canvas_window, width=target_width)
                self._main_canvas_last_width = target_width
        except Exception:
            return
    
    def _on_mousewheel(self, event):
        self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _create_scan_tab(self, notebook):
        scan_frame = ttk.Frame(notebook)
        notebook.add(scan_frame, text="📁 磁盘扫描")

        path_frame = ttk.LabelFrame(scan_frame, text="选择扫描目录", padding=10)
        path_frame.pack(fill=tk.X, padx=10, pady=5)

        self.path_var = tk.StringVar(value='C:\\')
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        browse_btn = ttk.Button(path_frame, text="📂 浏览...", command=self._browse_directory)
        browse_btn.pack(side=tk.LEFT, padx=5)

        search_frame = ttk.LabelFrame(scan_frame, text="文件搜索", padding=10)
        search_frame.pack(fill=tk.X, padx=10, pady=5)

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        search_btn = ttk.Button(search_frame, text="🔍 搜索", command=self._search_files)
        search_btn.pack(side=tk.LEFT, padx=5)

        clear_search_btn = ttk.Button(search_frame, text="❌ 清除搜索", command=self._clear_search)
        clear_search_btn.pack(side=tk.LEFT, padx=5)

        button_frame = ttk.Frame(scan_frame)
        button_frame.pack(fill=tk.X, pady=5, padx=10)

        self.scan_btn = ttk.Button(button_frame, text="▶️ 开始扫描", command=self._start_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=5)

        self.incremental_scan_btn = ttk.Button(button_frame, text="🔄 增量扫描", command=self._start_incremental_scan)
        self.incremental_scan_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(button_frame, text="⏹️ 停止扫描", command=self._stop_scan, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.resume_btn = ttk.Button(button_frame, text="▶️ 恢复扫描", command=self._resume_scan, state=tk.DISABLED)
        self.resume_btn.pack(side=tk.LEFT, padx=5)

        self.export_btn = ttk.Button(button_frame, text="💾 导出结果", command=self._export_results, state=tk.DISABLED)
        self.export_btn.pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(scan_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, padx=10, pady=5)

        self.status_label = ttk.Label(scan_frame, text="准备就绪")
        self.status_label.pack(anchor=tk.W, padx=10)

        self.result_text = scrolledtext.ScrolledText(scan_frame, wrap=tk.WORD, height=6)
        self.result_text.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)

        if HAS_MATPLOTLIB:
            self.scan_speed_frame = ttk.LabelFrame(scan_frame, text="📈 扫描速度监控", padding=10)
            self.scan_speed_frame.pack(fill=tk.X, padx=10, pady=5)
            self.scan_speed_canvas = None
            self.scan_speed_fig = None
            self.scan_speed_ax = None
            self.scan_speed_data = []
            self.scan_speed_times = []
        
        large_file_frame = ttk.LabelFrame(scan_frame, text="📄 文件列表（支持删除/移动操作）", padding=10)
        large_file_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        lf_button_frame = ttk.Frame(large_file_frame)
        lf_button_frame.pack(fill=tk.X, pady=5)

        self.delete_lf_btn = ttk.Button(lf_button_frame, text="🗑️ 删除选中文件", command=self._delete_selected_large_files, state=tk.DISABLED)
        self.delete_lf_btn.pack(side=tk.LEFT, padx=5)

        self.move_lf_btn = ttk.Button(lf_button_frame, text="📦 移动选中文件", command=self._move_selected_large_files, state=tk.DISABLED)
        self.move_lf_btn.pack(side=tk.LEFT, padx=5)

        self.select_all_btn = ttk.Button(lf_button_frame, text="✅ 全选", command=self._select_all_large_files, state=tk.DISABLED)
        self.select_all_btn.pack(side=tk.LEFT, padx=5)

        self.deselect_all_btn = ttk.Button(lf_button_frame, text="❎ 取消全选", command=self._deselect_all_large_files, state=tk.DISABLED)
        self.deselect_all_btn.pack(side=tk.LEFT, padx=5)

        filter_frame = ttk.Frame(large_file_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(filter_frame, text="按扩展名筛选:").pack(side=tk.LEFT, padx=5)
        self.ext_filter_var = tk.StringVar(value="全部")
        self.ext_filter_combo = ttk.Combobox(filter_frame, textvariable=self.ext_filter_var, state='readonly', width=15)
        self.ext_filter_combo['values'] = ["全部"]
        self.ext_filter_combo.pack(side=tk.LEFT, padx=5)
        self.ext_filter_combo.bind('<<ComboboxSelected>>', self._on_extension_filter_changed)

        ttk.Label(filter_frame, text="按大小筛选:").pack(side=tk.LEFT, padx=10)
        self.size_filter_var = tk.StringVar(value="全部")
        size_options = ["全部", "100MB以下", "100MB-500MB", "500MB-1GB", "1GB以上"]
        self.size_filter_combo = ttk.Combobox(filter_frame, textvariable=self.size_filter_var, state='readonly', width=15)
        self.size_filter_combo['values'] = size_options
        self.size_filter_combo.pack(side=tk.LEFT, padx=5)
        self.size_filter_combo.bind('<<ComboboxSelected>>', self._on_size_filter_changed)

        self.ext_filter_count_label = ttk.Label(filter_frame, text="")
        self.ext_filter_count_label.pack(side=tk.LEFT, padx=10)

        select_btn_frame = ttk.Frame(large_file_frame)
        select_btn_frame.pack(fill=tk.X, pady=(0, 5))

        self.select_by_type_btn = ttk.Button(select_btn_frame, text="📁 按类型选择", command=self._select_by_category, state=tk.DISABLED)
        self.select_by_type_btn.pack(side=tk.LEFT, padx=5)

        self.invert_select_btn = ttk.Button(select_btn_frame, text="🔄 反选", command=self._invert_large_file_selection, state=tk.DISABLED)
        self.invert_select_btn.pack(side=tk.LEFT, padx=5)

        columns = ("file_path", "file_size", "formatted_size")
        self.lf_tree = ttk.Treeview(large_file_frame, columns=columns, show="headings", selectmode="extended")
        self.lf_tree.heading("file_path", text="文件路径")
        self.lf_tree.heading("file_size", text="大小（字节）")
        self.lf_tree.heading("formatted_size", text="大小")
        self.lf_tree.column("file_path", width=650)
        self.lf_tree.column("file_size", width=120)
        self.lf_tree.column("formatted_size", width=120)
        lf_tree_frame = ttk.Frame(large_file_frame)
        lf_tree_frame.pack(fill=tk.BOTH, expand=True)

        lf_scroll_container = self._create_tree_with_scrollbars(lf_tree_frame, self.lf_tree, pack_args={"fill": tk.BOTH, "expand": True})
        lf_scroll_container.pack(fill=tk.BOTH, expand=True)
        
        if self.scan_state:
            self.resume_btn.config(state=tk.NORMAL)

    def _create_cleanup_tab(self, notebook):
        cleanup_frame = ttk.Frame(notebook)
        notebook.add(cleanup_frame, text="🧹 安全清理")

        info_frame = ttk.LabelFrame(cleanup_frame, text="可清理项目", padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.cleanup_vars = {
            'temp': tk.BooleanVar(value=True),
            'windows_update_cache': tk.BooleanVar(value=True),
            'browser_cache': tk.BooleanVar(value=True),
            'prefetch': tk.BooleanVar(value=False),
            'thumbnails': tk.BooleanVar(value=False),
            'log_files': tk.BooleanVar(value=False)
        }

        ttk.Checkbutton(info_frame, text="📄 临时文件（系统和用户临时目录）", variable=self.cleanup_vars['temp']).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(info_frame, text="💿 Windows更新缓存", variable=self.cleanup_vars['windows_update_cache']).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(info_frame, text="🌐 浏览器缓存（Chrome/Edge/Firefox）", variable=self.cleanup_vars['browser_cache']).pack(anchor=tk.W, pady=2)

        ttk.Separator(info_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        ttk.Label(info_frame, text="⚙️ 深度清理（谨慎使用）", font=('Microsoft YaHei', 9, 'bold')).pack(anchor=tk.W, pady=5)
        ttk.Checkbutton(info_frame, text="⚡ Prefetch预读取文件", variable=self.cleanup_vars['prefetch']).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(info_frame, text="🖼️ 缩略图缓存", variable=self.cleanup_vars['thumbnails']).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(info_frame, text="📝 系统日志文件", variable=self.cleanup_vars['log_files']).pack(anchor=tk.W, pady=2)

        ttk.Separator(info_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        self.backup_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(info_frame, text="💾 清理前备份文件（推荐）", variable=self.backup_var).pack(anchor=tk.W, pady=2)

        self.simulate_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(info_frame, text="🧪 模拟模式（只预览不删除）", variable=self.simulate_var).pack(anchor=tk.W, pady=2)

        ttk.Separator(info_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        action_frame = ttk.Frame(info_frame)
        action_frame.pack(fill=tk.X, pady=5)

        self.preview_btn = ttk.Button(action_frame, text="👁️ 预览文件列表", command=self._preview_cleanup_files)
        self.preview_btn.pack(side=tk.LEFT, padx=5)

        self.calculate_size_btn = ttk.Button(action_frame, text="📊 计算可清理空间", command=self._calculate_cleanup_size)
        self.calculate_size_btn.pack(side=tk.LEFT, padx=5)
        self.cleanup_size_label = ttk.Label(action_frame, text="可清理空间: --")
        self.cleanup_size_label.pack(side=tk.LEFT, padx=5)

        ttk.Separator(info_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        self.cleanup_progress = ttk.Progressbar(info_frame, mode='determinate')
        self.cleanup_progress.pack(fill=tk.X, pady=5)
        self.cleanup_progress['value'] = 0

        self.cleanup_status_label = ttk.Label(info_frame, text="")
        self.cleanup_status_label.pack(anchor=tk.W, pady=2)

        ttk.Button(info_frame, text="🧹 开始清理", command=self._start_cleanup).pack(pady=5)

        ttk.Separator(info_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        ttk.Button(info_frame, text="🗑️ 清空回收站", command=self._empty_recycle_bin).pack(pady=5)

        ttk.Separator(info_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        
        smart_frame = ttk.LabelFrame(info_frame, text="🧠 智能清理建议", padding=10)
        smart_frame.pack(fill=tk.X, pady=5)
        
        self.refresh_suggestions_btn = ttk.Button(smart_frame, text="🔄 刷新建议", command=self._refresh_smart_suggestions)
        self.refresh_suggestions_btn.pack(side=tk.LEFT, padx=5)
        
        self.apply_safe_btn = ttk.Button(smart_frame, text="✅ 一键清理安全项", command=self._apply_safe_suggestions)
        self.apply_safe_btn.pack(side=tk.LEFT, padx=5)
        
        self.suggestions_text = scrolledtext.ScrolledText(smart_frame, wrap=tk.WORD, height=8)
        self.suggestions_text.pack(fill=tk.X, pady=5)
        
        self.cleanup_log_display = scrolledtext.ScrolledText(cleanup_frame, wrap=tk.WORD, height=8)
        self.cleanup_log_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._refresh_cleanup_log_display()
        self.suggestions_text.insert(tk.END, "智能清理建议尚未计算。点击“刷新建议”后将在后台计算可清理空间。\n")

    def _create_duplicate_tab(self, notebook):
        duplicate_frame = ttk.Frame(notebook)
        notebook.add(duplicate_frame, text="📋 重复文件")

        path_frame = ttk.LabelFrame(duplicate_frame, text="选择扫描目录", padding=10)
        path_frame.pack(fill=tk.X, padx=10, pady=5)

        self.duplicate_path_var = tk.StringVar(value='C:\\')
        duplicate_path_entry = ttk.Entry(path_frame, textvariable=self.duplicate_path_var)
        duplicate_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        duplicate_browse_btn = ttk.Button(path_frame, text="📂 浏览...", command=self._browse_duplicate_directory)
        duplicate_browse_btn.pack(side=tk.LEFT, padx=5)

        button_frame = ttk.Frame(duplicate_frame)
        button_frame.pack(fill=tk.X, pady=5, padx=10)

        self.find_dup_btn = ttk.Button(button_frame, text="🔍 查找重复文件", command=self._start_find_duplicates)
        self.find_dup_btn.pack(side=tk.LEFT, padx=5)

        self.select_all_dup_btn = ttk.Button(button_frame, text="✅ 全选重复项", command=self._select_all_duplicates, state=tk.DISABLED)
        self.select_all_dup_btn.pack(side=tk.LEFT, padx=5)

        self.deselect_all_dup_btn = ttk.Button(button_frame, text="❎ 取消全选", command=self._deselect_all_duplicates, state=tk.DISABLED)
        self.deselect_all_dup_btn.pack(side=tk.LEFT, padx=5)

        self.invert_dup_btn = ttk.Button(button_frame, text="🔄 反选", command=self._invert_duplicate_selection, state=tk.DISABLED)
        self.invert_dup_btn.pack(side=tk.LEFT, padx=5)

        self.move_dup_btn = ttk.Button(button_frame, text="📦 移动重复文件", command=self._move_selected_duplicates, state=tk.DISABLED)
        self.move_dup_btn.pack(side=tk.LEFT, padx=5)

        self.delete_dup_btn = ttk.Button(button_frame, text="🗑️ 删除选中的重复文件", command=self._delete_selected_duplicates, state=tk.DISABLED)
        self.delete_dup_btn.pack(side=tk.LEFT, padx=5)

        dup_filter_frame = ttk.Frame(duplicate_frame)
        dup_filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(dup_filter_frame, text="按大小筛选:").pack(side=tk.LEFT, padx=5)
        self.dup_size_filter_var = tk.StringVar(value="全部")
        dup_size_options = ["全部", "10MB以下", "10MB-100MB", "100MB-500MB", "500MB以上"]
        self.dup_size_filter_combo = ttk.Combobox(dup_filter_frame, textvariable=self.dup_size_filter_var, state='readonly', width=15)
        self.dup_size_filter_combo['values'] = dup_size_options
        self.dup_size_filter_combo.pack(side=tk.LEFT, padx=5)
        self.dup_size_filter_combo.bind('<<ComboboxSelected>>', self._on_dup_size_filter_changed)

        self.duplicate_status_label = ttk.Label(duplicate_frame, text="准备就绪")
        self.duplicate_status_label.pack(anchor=tk.W, padx=10)

        self.duplicate_result_text = scrolledtext.ScrolledText(duplicate_frame, wrap=tk.WORD, height=5)
        self.duplicate_result_text.pack(fill=tk.X, padx=10, pady=5)

        dup_list_frame = ttk.LabelFrame(duplicate_frame, text="📋 重复文件列表", padding=10)
        dup_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        dup_columns = ("hash", "size", "count", "files")
        self.dup_tree = ttk.Treeview(dup_list_frame, columns=dup_columns, show="headings", selectmode="extended")
        self.dup_tree.heading("hash", text="文件哈希")
        self.dup_tree.heading("size", text="单文件大小")
        self.dup_tree.heading("count", text="重复数量")
        self.dup_tree.heading("files", text="文件路径")
        self.dup_tree.column("hash", width=200)
        self.dup_tree.column("size", width=120)
        self.dup_tree.column("count", width=100)
        self.dup_tree.column("files", width=600)
        dup_tree_frame = ttk.Frame(dup_list_frame)
        dup_tree_frame.pack(fill=tk.BOTH, expand=True)
        dup_scroll_container = self._create_tree_with_scrollbars(dup_tree_frame, self.dup_tree, pack_args={"fill": tk.BOTH, "expand": True})
        dup_scroll_container.pack(fill=tk.BOTH, expand=True)

    def _browse_duplicate_directory(self):
        directory = filedialog.askdirectory(initialdir='C:\\', title="选择要扫描的目录")
        if directory:
            self.duplicate_path_var.set(directory)

    def _start_find_duplicates(self):
        if self.is_scanning:
            return
        self.is_scanning = True
        self.find_dup_btn.config(state=tk.DISABLED)
        self.select_all_dup_btn.config(state=tk.DISABLED)
        self.deselect_all_dup_btn.config(state=tk.DISABLED)
        self.delete_dup_btn.config(state=tk.DISABLED)

        self.duplicate_result_text.delete(1.0, tk.END)
        self._append_duplicate_result("正在查找重复文件...\n")

        thread = threading.Thread(target=self._find_duplicates_thread)
        thread.daemon = True
        thread.start()

    def _find_duplicates_thread(self):
        try:
            scan_path = self.duplicate_path_var.get()
            
            def progress_callback(data):
                if not data:
                    return self.is_scanning
                processed = data.get('processed', 0)
                current_file = data.get('current_file', '')
                self.root.after(0, lambda: self.duplicate_status_label.config(
                    text=f"已处理: {processed} 个文件, 当前: {current_file}"
                ))
                return self.is_scanning
            
            self.duplicate_results = self.scanner.find_duplicate_files(scan_path, progress_callback)
            
            self._append_duplicate_result(f"\n查找完成!\n")
            if self.duplicate_results and isinstance(self.duplicate_results, dict):
                duplicates = self.duplicate_results.get('duplicates', [])
                total_wasted_formatted = self.duplicate_results.get('total_wasted_formatted', '')
                scan_time = self.duplicate_results.get('scan_time', 0)
                self._append_duplicate_result(f"找到 {len(duplicates)} 组重复文件\n")
                self._append_duplicate_result(f"可释放空间: {total_wasted_formatted}\n")
                self._append_duplicate_result(f"耗时: {scan_time:.2f} 秒\n")
            
            self.root.after(0, self._populate_duplicates)
            
        except Exception as e:
            self._append_duplicate_result(f"\n出错: {e}")
        finally:
            self.is_scanning = False
            self.root.after(0, self._find_duplicates_finished)

    def _populate_duplicates(self):
        for item in self.dup_tree.get_children():
            self.dup_tree.delete(item)
        
        if self.duplicate_results and isinstance(self.duplicate_results, dict):
            duplicates = self.duplicate_results.get('duplicates', [])
            for i, dup in enumerate(duplicates):
                if not isinstance(dup, dict):
                    continue
                files = dup.get('files', [])
                files_str = "; ".join(files) if files else ""
                hash_val = dup.get('hash', '')
                size_formatted = dup.get('size_formatted', '')
                file_count = len(files) if files else 0
                self.dup_tree.insert("", tk.END, values=(hash_val, size_formatted, file_count, files_str))

    def _select_all_duplicates(self):
        for item in self.dup_tree.get_children():
            self.dup_tree.selection_add(item)

    def _deselect_all_duplicates(self):
        for item in self.dup_tree.get_children():
            self.dup_tree.selection_remove(item)

    def _invert_duplicate_selection(self):
        """反选重复文件"""
        all_items = self.dup_tree.get_children()
        selected = set(self.dup_tree.selection())
        
        new_selection = [item for item in all_items if item not in selected]
        self.dup_tree.selection_set(new_selection)

    def _move_selected_duplicates(self):
        """移动选中的重复文件"""
        selected_items = self.dup_tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选择要移动的重复文件")
            return

        target_dir = filedialog.askdirectory(title="选择目标目录")
        if not target_dir:
            return

        files_to_move = []
        if self.duplicate_results and isinstance(self.duplicate_results, dict):
            duplicates = self.duplicate_results.get('duplicates', [])
            for item in selected_items:
                values = self.dup_tree.item(item, "values")
                if not values or len(values) < 1:
                    continue
                hash_val = values[0]
                for dup in duplicates:
                    if dup.get('hash') == hash_val:
                        files_to_move.extend(dup.get('files', []))
                        break

        if not files_to_move:
            messagebox.showwarning("提示", "没有找到要移动的文件")
            return

        if messagebox.askyesno("确认", f"确定要移动 {len(files_to_move)} 个重复文件吗？"):
            moved_count = 0
            for filepath in files_to_move:
                try:
                    filename = os.path.basename(filepath)
                    target_path = os.path.join(target_dir, filename)
                    counter = 1
                    while os.path.exists(target_path):
                        name, ext = os.path.splitext(filename)
                        target_path = os.path.join(target_dir, f"{name}_{counter}{ext}")
                        counter += 1
                    shutil.move(filepath, target_path)
                    moved_count += 1
                except Exception as e:
                    continue

            messagebox.showinfo("完成", f"成功移动 {moved_count} 个文件")
            self._start_find_duplicates()

    def _on_dup_size_filter_changed(self, event=None):
        """按大小筛选重复文件"""
        if not self.duplicate_results or not isinstance(self.duplicate_results, dict):
            return

        selected = self.dup_size_filter_var.get()
        
        size_ranges = {
            "全部": (0, float('inf')),
            "10MB以下": (0, 10 * 1024 * 1024),
            "10MB-100MB": (10 * 1024 * 1024, 100 * 1024 * 1024),
            "100MB-500MB": (100 * 1024 * 1024, 500 * 1024 * 1024),
            "500MB以上": (500 * 1024 * 1024, float('inf'))
        }
        
        min_size, max_size = size_ranges[selected]
        duplicates = self.duplicate_results.get('duplicates', [])

        for item in self.dup_tree.get_children():
            self.dup_tree.delete(item)

        for dup in duplicates:
            size = dup.get('size', 0)
            if min_size <= size < max_size:
                self.dup_tree.insert("", tk.END, values=(
                    dup['hash'],
                    dup['size_formatted'],
                    len(dup['files']),
                    '\n'.join(dup['files'])
                ))

    def _delete_selected_duplicates(self):
        selected_items = self.dup_tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选择要删除的重复文件")
            return
        
        files_to_delete = []
        if self.duplicate_results and isinstance(self.duplicate_results, dict):
            duplicates = self.duplicate_results.get('duplicates', [])
            for item in selected_items:
                values = self.dup_tree.item(item, "values")
                if not values or len(values) < 1:
                    continue
                file_hash = values[0]
                
                for dup in duplicates:
                    if not isinstance(dup, dict):
                        continue
                    if dup.get('hash') == file_hash:
                        files = dup.get('files', [])
                        if len(files) > 1:
                            files_to_delete.extend(files[1:])
        
        if not files_to_delete:
            messagebox.showinfo("提示", "没有要删除的文件")
            return
        
        total_size = sum(os.path.getsize(f) for f in files_to_delete if os.path.exists(f))
        confirm_msg = f"确定要删除 {len(files_to_delete)} 个重复文件吗？\n可释放: {self.scanner.format_size(total_size)}"
        
        if not messagebox.askyesno("确认删除", confirm_msg):
            return
        
        deleted_count = 0
        failed_count = 0
        freed_size = 0
        
        for filepath in files_to_delete:
            try:
                if os.path.exists(filepath):
                    size = os.path.getsize(filepath)
                    os.remove(filepath)
                    deleted_count += 1
                    freed_size += size
            except Exception as e:
                failed_count += 1
        
        messagebox.showinfo("完成", f"删除完成!\n成功: {deleted_count} 个\n释放: {self.scanner.format_size(freed_size)}\n失败: {failed_count} 个")
        
        self._start_find_duplicates()

    def _append_duplicate_result(self, text):
        def append():
            self.duplicate_result_text.insert(tk.END, text)
            self.duplicate_result_text.see(tk.END)
        self.root.after(0, append)

    def _find_duplicates_finished(self):
        self.find_dup_btn.config(state=tk.NORMAL)
        self.duplicate_status_label.config(text="查找完成")
        if self.duplicate_results and len(self.duplicate_results['duplicates']) > 0:
            self.select_all_dup_btn.config(state=tk.NORMAL)
            self.deselect_all_dup_btn.config(state=tk.NORMAL)
            self.invert_dup_btn.config(state=tk.NORMAL)
            self.move_dup_btn.config(state=tk.NORMAL)
            self.delete_dup_btn.config(state=tk.NORMAL)

    def _create_visualization_tab(self, notebook):
        viz_frame = ttk.Frame(notebook)
        notebook.add(viz_frame, text="📊 磁盘可视化")
        
        if not HAS_MATPLOTLIB:
            warning_label = ttk.Label(viz_frame, text="matplotlib未安装，请先运行: pip install matplotlib", foreground="red", font=("Microsoft YaHei", 12))
            warning_label.pack(pady=100)
            return
        
        path_frame = ttk.LabelFrame(viz_frame, text="选择分析目录", padding=10)
        path_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.viz_path_var = tk.StringVar(value='C:\\')
        viz_path_entry = ttk.Entry(path_frame, textvariable=self.viz_path_var)
        viz_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        viz_browse_btn = ttk.Button(path_frame, text="📂 浏览...", command=self._browse_viz_directory)
        viz_browse_btn.pack(side=tk.LEFT, padx=5)
        
        button_frame = ttk.Frame(viz_frame)
        button_frame.pack(fill=tk.X, pady=5, padx=10)
        
        self.analyze_btn = ttk.Button(button_frame, text="🔍 分析磁盘", command=self._start_analyze_disk)
        self.analyze_btn.pack(side=tk.LEFT, padx=5)
        
        self.show_pie_btn = ttk.Button(button_frame, text="🥧 显示饼图", command=self._show_pie_chart, state=tk.DISABLED)
        self.show_pie_btn.pack(side=tk.LEFT, padx=5)
        
        self.show_tree_btn = ttk.Button(button_frame, text="🌳 显示树状图", command=self._show_tree_chart, state=tk.DISABLED)
        self.show_tree_btn.pack(side=tk.LEFT, padx=5)
        
        self.show_extension_btn = ttk.Button(button_frame, text="📁 文件类型分布", command=self._show_extension_chart, state=tk.DISABLED)
        self.show_extension_btn.pack(side=tk.LEFT, padx=5)
        
        self.show_category_btn = ttk.Button(button_frame, text="🏷️ 文件分类统计", command=self._show_category_chart, state=tk.DISABLED)
        self.show_category_btn.pack(side=tk.LEFT, padx=5)
        
        self.viz_status_label = ttk.Label(viz_frame, text="准备就绪")
        self.viz_status_label.pack(anchor=tk.W, padx=10)
        
        self.viz_result_text = scrolledtext.ScrolledText(viz_frame, wrap=tk.WORD, height=5)
        self.viz_result_text.pack(fill=tk.X, padx=10, pady=5)
        
        chart_frame = ttk.LabelFrame(viz_frame, text="📈 图表区域", padding=10)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.chart_frame = chart_frame
        self.visualization_data = None

    def _browse_viz_directory(self):
        directory = filedialog.askdirectory(initialdir='C:\\', title="选择要分析的目录")
        if directory:
            self.viz_path_var.set(directory)

    def _start_analyze_disk(self):
        if self.is_scanning:
            return
        self.is_scanning = True
        self.analyze_btn.config(state=tk.DISABLED)
        
        self.viz_result_text.delete(1.0, tk.END)
        self._append_viz_result("正在分析磁盘...\n")
        
        thread = threading.Thread(target=self._analyze_disk_thread)
        thread.daemon = True
        thread.start()

    def _analyze_disk_thread(self):
        try:
            scan_path = self.viz_path_var.get()
            
            def progress_callback(data):
                if not data:
                    return self.is_scanning
                processed = data.get('processed', 0)
                self.root.after(0, lambda: self.viz_status_label.config(
                    text=f"已处理: {processed} 个文件夹"
                ))
                return self.is_scanning
            
            self.visualization_data = self.scanner.get_folder_size_distribution(scan_path, progress_callback)
            
            self._append_viz_result(f"\n分析完成!\n")
            if self.visualization_data and isinstance(self.visualization_data, dict):
                total_folders = self.visualization_data.get('total_folders', 0)
                self._append_viz_result(f"共分析 {total_folders} 个文件夹\n")
            
            self.root.after(0, self._analyze_finished)
            
        except Exception as e:
            self._append_viz_result(f"\n出错: {e}")
        finally:
            self.is_scanning = False
            self.root.after(0, lambda: self.analyze_btn.config(state=tk.NORMAL))

    def _append_viz_result(self, text):
        def append():
            self.viz_result_text.insert(tk.END, text)
            self.viz_result_text.see(tk.END)
        self.root.after(0, append)

    def _analyze_finished(self):
        self.show_pie_btn.config(state=tk.NORMAL)
        self.show_tree_btn.config(state=tk.NORMAL)
        self.show_extension_btn.config(state=tk.NORMAL)
        self.show_category_btn.config(state=tk.NORMAL)
        self.viz_status_label.config(text="分析完成")

    def _show_pie_chart(self):
        if not HAS_MATPLOTLIB:
            messagebox.showwarning("提示", "matplotlib未安装，无法显示图表")
            return
        _, FigureCanvasTkAgg, Figure = _load_matplotlib_backend()
        if not FigureCanvasTkAgg or not Figure:
            return
        chosen_font = _setup_chinese_font()
        if not self.visualization_data:
            return
        if not isinstance(self.visualization_data, dict) or 'folders' not in self.visualization_data:
            return
        if len(self.visualization_data['folders']) == 0:
            return

        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        folders = self.visualization_data['folders'][:10]
        labels = []
        sizes = []
        folder_paths = []
        colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#ff99cc', '#99ccff', '#ccff99', '#ffccff', '#ffff99', '#99ffff']

        for item in folders:
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            folder, size = item[0], item[1]
            if size > 0:
                label = os.path.basename(folder) or folder
                labels.append(label)
                sizes.append(size)
                folder_paths.append(folder)

        if len(labels) == 0:
            return

        try:
            from matplotlib import font_manager as _fm
            from matplotlib.font_manager import FontProperties as _FP
            chinese_fp = _FP(fname=_fm.findfont(_FP(family=chosen_font or 'Microsoft YaHei')))
        except Exception:
            chinese_fp = None

        fig = Figure(figsize=(8, 6), dpi=100)
        ax = fig.add_subplot(111)

        if chinese_fp is not None:
            result = ax.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors[:len(labels)],
                            textprops={'fontproperties': chinese_fp, 'fontsize': 8})
        else:
            result = ax.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors[:len(labels)],
                            textprops={'fontsize': 8})

        wedges = result[0]
        texts = result[1]
        autotexts = result[2] if len(result) > 2 else []

        if chinese_fp is not None:
            ax.set_title('Top 10 文件夹大小分布 (点击扇形打开文件夹)', fontproperties=chinese_fp, fontsize=14)
            for text in autotexts:
                text.set_fontproperties(chinese_fp)
                text.set_fontsize(8)
            for text in texts:
                text.set_fontproperties(chinese_fp)
                text.set_fontsize(8)
        else:
            ax.set_title('Top 10 文件夹大小分布 (点击扇形打开文件夹)', fontsize=14)
            for text in texts:
                text.set_fontsize(8)

        for i, wedge in enumerate(wedges):
            wedge.folder_path = folder_paths[i]
            wedge.original_transform = wedge.get_transform()
            wedge.original_r = 1.0

        hover_annotation = ax.annotate("", xy=(0, 0), xytext=(20, 20),
                                       textcoords="offset points",
                                       bbox=dict(boxstyle="round", fc="w", ec="k", alpha=0.9),
                                       fontsize=10,
                                       arrowprops=dict(arrowstyle="->"))
        hover_annotation.set_visible(False)

        def on_hover(event):
            if event.inaxes != ax:
                hover_annotation.set_visible(False)
                for wedge in wedges:
                    wedge.set_radius(wedge.original_r)
                fig.canvas.draw_idle()
                return

            for wedge in wedges:
                if wedge.contains(event)[0]:
                    wedge.set_radius(1.08)
                    folder_path = wedge.folder_path
                    size = sizes[wedges.index(wedge)]
                    info_text = f"{os.path.basename(folder_path)}\n{self.scanner.format_size(size)}\n{folder_path}"
                    hover_annotation.set_text(info_text)
                    hover_annotation.xy = event.xdata, event.ydata
                    hover_annotation.set_visible(True)
                else:
                    wedge.set_radius(wedge.original_r)
            fig.canvas.draw_idle()

        def on_pick(event):
            artist = event.artist
            if hasattr(artist, 'folder_path'):
                folder_path = artist.folder_path
                if os.path.exists(folder_path):
                    try:
                        os.startfile(folder_path)
                    except Exception as e:
                        messagebox.showerror("错误", f"无法打开文件夹: {e}")

        fig.canvas.mpl_connect('motion_notify_event', on_hover)
        fig.canvas.mpl_connect('pick_event', on_pick)

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        tip_label = ttk.Label(self.chart_frame, text="💡 提示：鼠标悬停放大，点击饼图扇形可直接打开对应文件夹", font=('Microsoft YaHei', 9))
        tip_label.pack(anchor=tk.W, pady=2)

    def _show_tree_chart(self):
        if not HAS_MATPLOTLIB:
            messagebox.showwarning("提示", "matplotlib未安装，无法显示图表")
            return
        _, FigureCanvasTkAgg, Figure = _load_matplotlib_backend()
        if not FigureCanvasTkAgg or not Figure:
            return
        chosen_font = _setup_chinese_font()
        if not self.visualization_data:
            return
        if not isinstance(self.visualization_data, dict) or 'folders' not in self.visualization_data:
            return
        if len(self.visualization_data['folders']) == 0:
            return

        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        folders = self.visualization_data['folders'][:15]
        folder_names = []
        folder_sizes = []
        valid_folders = []

        for item in folders:
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            folder, size = item[0], item[1]
            if size > 0:
                name = os.path.basename(folder) or folder
                folder_names.append(name[:30])
                folder_sizes.append(size / (1024*1024))
                valid_folders.append(item)

        if len(folder_names) == 0:
            return

        try:
            from matplotlib import font_manager as _fm
            from matplotlib.font_manager import FontProperties as _FP
            chinese_fp = _FP(fname=_fm.findfont(_FP(family=chosen_font or 'Microsoft YaHei')))
        except Exception:
            chinese_fp = None

        fig = Figure(figsize=(10, 6), dpi=100)
        ax = fig.add_subplot(111)
        bars = ax.barh(range(len(folder_names)), folder_sizes, picker=True)

        for i, bar in enumerate(bars):
            bar.folder_path = valid_folders[i][0]
            bar.original_width = bar.get_width()
            bar.original_color = bar.get_facecolor()

        if chinese_fp is not None:
            ax.set_yticks(range(len(folder_names)))
            ax.set_yticklabels(folder_names, fontproperties=chinese_fp, fontsize=9)
            ax.set_xlabel('大小 (MB)', fontproperties=chinese_fp, fontsize=11)
            ax.set_title('Top 15 文件夹大小排行 (点击柱条打开文件夹)', fontproperties=chinese_fp, fontsize=14)
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax.text(width, bar.get_y() + bar.get_height()/2,
                       f' {self.scanner.format_size(valid_folders[i][1])}',
                       va='center', fontsize=8, fontproperties=chinese_fp)
        else:
            ax.set_yticks(range(len(folder_names)))
            ax.set_yticklabels(folder_names, fontsize=9)
            ax.set_xlabel('大小 (MB)', fontsize=11)
            ax.set_title('Top 15 文件夹大小排行 (点击柱条打开文件夹)', fontsize=14)
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax.text(width, bar.get_y() + bar.get_height()/2,
                       f' {self.scanner.format_size(valid_folders[i][1])}',
                       va='center', fontsize=8)

        hover_annotation = ax.annotate("", xy=(0, 0), xytext=(20, 20),
                                       textcoords="offset points",
                                       bbox=dict(boxstyle="round", fc="w", ec="k", alpha=0.9),
                                       fontsize=10,
                                       arrowprops=dict(arrowstyle="->"))
        hover_annotation.set_visible(False)

        def on_hover(event):
            if event.inaxes != ax:
                hover_annotation.set_visible(False)
                for bar in bars:
                    bar.set_width(bar.original_width)
                    bar.set_facecolor(bar.original_color)
                fig.canvas.draw_idle()
                return

            for bar in bars:
                if bar.contains(event)[0]:
                    bar.set_width(bar.original_width * 1.05)
                    bar.set_facecolor((0.2, 0.6, 1.0, 0.8))
                    folder_path = bar.folder_path
                    size = next((f[1] for f in valid_folders if f[0] == folder_path), 0)
                    info_text = f"{os.path.basename(folder_path)}\n{self.scanner.format_size(size)}\n{folder_path}"
                    hover_annotation.set_text(info_text)
                    hover_annotation.xy = event.xdata, event.ydata
                    hover_annotation.set_visible(True)
                else:
                    bar.set_width(bar.original_width)
                    bar.set_facecolor(bar.original_color)
            fig.canvas.draw_idle()

        def on_pick(event):
            artist = event.artist
            if hasattr(artist, 'folder_path'):
                folder_path = artist.folder_path
                if os.path.exists(folder_path):
                    try:
                        os.startfile(folder_path)
                    except Exception as e:
                        messagebox.showerror("错误", f"无法打开文件夹: {e}")

        fig.canvas.mpl_connect('motion_notify_event', on_hover)
        fig.canvas.mpl_connect('pick_event', on_pick)

        ax.invert_yaxis()
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        tip_label = ttk.Label(self.chart_frame, text="💡 提示：鼠标悬停放大，点击柱状条可直接打开对应文件夹", font=('Microsoft YaHei', 9))
        tip_label.pack(anchor=tk.W, pady=2)

    def _show_extension_chart(self):
        if not HAS_MATPLOTLIB:
            messagebox.showwarning("提示", "matplotlib未安装，无法显示图表")
            return
        _, FigureCanvasTkAgg, Figure = _load_matplotlib_backend()
        if not FigureCanvasTkAgg or not Figure:
            return
        chosen_font = _setup_chinese_font()
        if not self.visualization_data:
            return
        if not isinstance(self.visualization_data, dict) or 'folders' not in self.visualization_data:
            return
        if len(self.visualization_data['folders']) == 0:
            return

        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        scan_path = self.viz_path_var.get()
        extension_stats = {}
        total_files = 0
        total_size = 0

        def scan_extensions(path):
            nonlocal total_files, total_size
            try:
                for entry in os.listdir(path):
                    full_path = os.path.join(path, entry)
                    if os.path.isfile(full_path):
                        try:
                            ext = os.path.splitext(entry)[1].lower() or '无扩展名'
                            size = os.path.getsize(full_path)
                            if ext not in extension_stats:
                                extension_stats[ext] = {'count': 0, 'size': 0}
                            extension_stats[ext]['count'] += 1
                            extension_stats[ext]['size'] += size
                            total_files += 1
                            total_size += size
                        except:
                            continue
                    elif os.path.isdir(full_path):
                        try:
                            scan_extensions(full_path)
                        except:
                            continue
            except:
                pass

        scan_extensions(scan_path)

        if not extension_stats:
            messagebox.showinfo("提示", "未找到文件")
            return

        sorted_extensions = sorted(extension_stats.items(), key=lambda x: x[1]['size'], reverse=True)[:15]
        labels = []
        sizes = []
        counts = []

        for ext, stats in sorted_extensions:
            labels.append(ext if ext != '无扩展名' else '(无扩展名)')
            sizes.append(stats['size'])
            counts.append(stats['count'])

        try:
            from matplotlib import font_manager as _fm
            from matplotlib.font_manager import FontProperties as _FP
            chinese_fp = _FP(fname=_fm.findfont(_FP(family=chosen_font or 'Microsoft YaHei')))
        except Exception:
            chinese_fp = None

        colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#ff99cc', '#99ccff', '#ccff99', '#ffccff', '#ffff99', '#99ffff', '#ff9966', '#66ff99', '#9966ff', '#ff6666', '#66ffff']

        fig = Figure(figsize=(10, 6), dpi=100)
        ax = fig.add_subplot(111)
        bars = ax.barh(range(len(labels)), sizes, color=colors[:len(labels)], picker=True)

        for i, bar in enumerate(bars):
            bar.extension = labels[i]
            bar.original_width = bar.get_width()
            bar.original_color = bar.get_facecolor()

        if chinese_fp is not None:
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels, fontproperties=chinese_fp, fontsize=10)
            ax.set_xlabel('大小 (字节)', fontproperties=chinese_fp, fontsize=11)
            ax.set_title('文件类型分布 (按大小排序，显示前15种)', fontproperties=chinese_fp, fontsize=14)
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax.text(width, bar.get_y() + bar.get_height()/2,
                       f' {self.scanner.format_size(sizes[i])} ({counts[i]}个)',
                       va='center', fontsize=8, fontproperties=chinese_fp)
        else:
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels, fontsize=10)
            ax.set_xlabel('大小 (字节)', fontsize=11)
            ax.set_title('文件类型分布 (按大小排序，显示前15种)', fontsize=14)
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax.text(width, bar.get_y() + bar.get_height()/2,
                       f' {self.scanner.format_size(sizes[i])} ({counts[i]}个)',
                       va='center', fontsize=8)

        hover_annotation = ax.annotate("", xy=(0, 0), xytext=(20, 20),
                                       textcoords="offset points",
                                       bbox=dict(boxstyle="round", fc="w", ec="k", alpha=0.9),
                                       fontsize=10,
                                       arrowprops=dict(arrowstyle="->"))
        hover_annotation.set_visible(False)

        def on_hover(event):
            if event.inaxes != ax:
                hover_annotation.set_visible(False)
                for bar in bars:
                    bar.set_width(bar.original_width)
                    bar.set_facecolor(bar.original_color)
                fig.canvas.draw_idle()
                return

            for bar in bars:
                if bar.contains(event)[0]:
                    bar.set_width(bar.original_width * 1.05)
                    bar.set_facecolor((0.2, 0.6, 1.0, 0.8))
                    ext = bar.extension
                    idx = labels.index(ext)
                    info_text = f"扩展名: {ext}\n文件数量: {counts[idx]} 个\n总大小: {self.scanner.format_size(sizes[idx])}\n占比: {sizes[idx]/total_size*100:.1f}%"
                    hover_annotation.set_text(info_text)
                    hover_annotation.xy = event.xdata, event.ydata
                    hover_annotation.set_visible(True)
                else:
                    bar.set_width(bar.original_width)
                    bar.set_facecolor(bar.original_color)
            fig.canvas.draw_idle()

        fig.canvas.mpl_connect('motion_notify_event', on_hover)

        ax.invert_yaxis()
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        summary_text = f"总计: {total_files} 个文件, {self.scanner.format_size(total_size)}"
        summary_label = ttk.Label(self.chart_frame, text=summary_text, font=('Microsoft YaHei', 10))
        summary_label.pack(anchor=tk.W, pady=2)

        tip_label = ttk.Label(self.chart_frame, text="💡 提示：鼠标悬停查看详细信息", font=('Microsoft YaHei', 9))
        tip_label.pack(anchor=tk.W, pady=2)

    def _show_category_chart(self):
        if not HAS_MATPLOTLIB:
            messagebox.showwarning("提示", "matplotlib未安装，无法显示图表")
            return
        _, FigureCanvasTkAgg, Figure = _load_matplotlib_backend()
        if not FigureCanvasTkAgg or not Figure:
            return
        chosen_font = _setup_chinese_font()

        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        scan_path = self.viz_path_var.get()
        category_stats = {}
        total_files = 0
        total_size = 0

        def scan_categories(path):
            nonlocal total_files, total_size
            try:
                for entry in os.listdir(path):
                    full_path = os.path.join(path, entry)
                    if os.path.isfile(full_path):
                        try:
                            category = self.scanner.get_file_category(entry)
                            size = os.path.getsize(full_path)
                            if category not in category_stats:
                                category_stats[category] = {'count': 0, 'size': 0}
                            category_stats[category]['count'] += 1
                            category_stats[category]['size'] += size
                            total_files += 1
                            total_size += size
                        except:
                            continue
                    elif os.path.isdir(full_path):
                        try:
                            scan_categories(full_path)
                        except:
                            continue
            except:
                pass

        scan_categories(scan_path)

        if not category_stats:
            messagebox.showinfo("提示", "未找到文件")
            return

        labels = []
        sizes = []
        counts = []
        icons = []

        for category, stats in category_stats.items():
            info = self.scanner.get_category_info(category)
            labels.append(f"{info['icon']} {info['name']}")
            sizes.append(stats['size'])
            counts.append(stats['count'])

        colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#ff99cc', '#99ccff', '#ccff99', '#ffccff']

        fig = Figure(figsize=(10, 6), dpi=100)
        ax = fig.add_subplot(111)
        bars = ax.barh(range(len(labels)), sizes, color=colors[:len(labels)], picker=True)

        for i, bar in enumerate(bars):
            bar.category = labels[i]
            bar.original_width = bar.get_width()
            bar.original_color = bar.get_facecolor()

        try:
            from matplotlib import font_manager as _fm
            from matplotlib.font_manager import FontProperties as _FP
            chinese_fp = _FP(fname=_fm.findfont(_FP(family=chosen_font or 'Microsoft YaHei')))
        except Exception:
            chinese_fp = None

        if chinese_fp is not None:
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels, fontproperties=chinese_fp, fontsize=12)
            ax.set_xlabel('大小 (字节)', fontproperties=chinese_fp, fontsize=11)
            ax.set_title('文件分类统计', fontproperties=chinese_fp, fontsize=14)
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax.text(width, bar.get_y() + bar.get_height()/2,
                       f' {self.scanner.format_size(sizes[i])} ({counts[i]}个)',
                       va='center', fontsize=10, fontproperties=chinese_fp)
        else:
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels, fontsize=12)
            ax.set_xlabel('大小 (字节)', fontsize=11)
            ax.set_title('文件分类统计', fontsize=14)
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax.text(width, bar.get_y() + bar.get_height()/2,
                       f' {self.scanner.format_size(sizes[i])} ({counts[i]}个)',
                       va='center', fontsize=10)

        hover_annotation = ax.annotate("", xy=(0, 0), xytext=(20, 20),
                                       textcoords="offset points",
                                       bbox=dict(boxstyle="round", fc="w", ec="k", alpha=0.9),
                                       fontsize=10,
                                       arrowprops=dict(arrowstyle="->"))
        hover_annotation.set_visible(False)

        def on_hover(event):
            if event.inaxes != ax:
                hover_annotation.set_visible(False)
                for bar in bars:
                    bar.set_width(bar.original_width)
                    bar.set_facecolor(bar.original_color)
                fig.canvas.draw_idle()
                return

            for bar in bars:
                if bar.contains(event)[0]:
                    bar.set_width(bar.original_width * 1.05)
                    bar.set_facecolor((0.2, 0.6, 1.0, 0.8))
                    cat = bar.category
                    idx = labels.index(cat)
                    info_text = f"分类: {cat}\n文件数量: {counts[idx]} 个\n总大小: {self.scanner.format_size(sizes[idx])}\n占比: {sizes[idx]/total_size*100:.1f}%"
                    hover_annotation.set_text(info_text)
                    hover_annotation.xy = event.xdata, event.ydata
                    hover_annotation.set_visible(True)
                else:
                    bar.set_width(bar.original_width)
                    bar.set_facecolor(bar.original_color)
            fig.canvas.draw_idle()

        fig.canvas.mpl_connect('motion_notify_event', on_hover)

        ax.invert_yaxis()
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        summary_text = f"总计: {total_files} 个文件, {self.scanner.format_size(total_size)}"
        summary_label = ttk.Label(self.chart_frame, text=summary_text, font=('Microsoft YaHei', 10))
        summary_label.pack(anchor=tk.W, pady=2)

        tip_label = ttk.Label(self.chart_frame, text="💡 提示：鼠标悬停查看详细信息", font=('Microsoft YaHei', 9))
        tip_label.pack(anchor=tk.W, pady=2)

    def _create_restore_tab(self, notebook):
        restore_frame = ttk.Frame(notebook)
        notebook.add(restore_frame, text="🔄 文件恢复")

        restore_notebook = ttk.Notebook(restore_frame)
        restore_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        backup_frame = ttk.Frame(restore_notebook)
        restore_notebook.add(backup_frame, text="📁 备份文件")

        backup_btn_frame = ttk.Frame(backup_frame)
        backup_btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(backup_btn_frame, text="🔄 刷新列表", command=self._refresh_backup_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(backup_btn_frame, text="📂 打开备份目录", command=self._open_backup_dir).pack(side=tk.LEFT, padx=5)

        self.backup_tree = ttk.Treeview(backup_frame, columns=('name', 'original', 'size', 'date'), show='headings')
        self.backup_tree.heading('name', text='备份文件名')
        self.backup_tree.heading('original', text='原始文件名')
        self.backup_tree.heading('size', text='大小')
        self.backup_tree.heading('date', text='备份时间')
        self.backup_tree.column('name', width=200)
        self.backup_tree.column('original', width=150)
        self.backup_tree.column('size', width=80)
        self.backup_tree.column('date', width=150)
        backup_tree_frame = ttk.Frame(backup_frame)
        backup_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        backup_scroll_container = self._create_tree_with_scrollbars(backup_tree_frame, self.backup_tree, pack_args={"fill": tk.BOTH, "expand": True})
        backup_scroll_container.pack(fill=tk.BOTH, expand=True)

        backup_action_frame = ttk.Frame(backup_frame)
        backup_action_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(backup_action_frame, text="🔄 恢复选中文件", command=self._restore_selected_backup).pack(side=tk.LEFT, padx=5)
        ttk.Button(backup_action_frame, text="🗑️ 删除选中备份", command=self._delete_selected_backup).pack(side=tk.LEFT, padx=5)

        self._refresh_backup_list()

    def _refresh_backup_list(self):
        """刷新备份文件列表"""
        for item in self.backup_tree.get_children():
            self.backup_tree.delete(item)

        backup_files = self.cleaner.get_backup_files()
        
        if not backup_files:
            self.backup_tree.insert('', tk.END, values=('暂无备份文件', '', '', ''))
            return

        for backup in backup_files:
            self.backup_tree.insert('', tk.END, values=(
                backup['filename'],
                backup['original_name'],
                backup['size_formatted'],
                backup['mtime_str']
            ), tags=(backup['filepath'],))

    def _open_backup_dir(self):
        """打开备份目录"""
        backup_dir = os.path.join(self.cleaner.base_dir, 'backups')
        if os.path.exists(backup_dir):
            try:
                os.startfile(backup_dir)
            except Exception as e:
                messagebox.showerror("错误", f"无法打开目录: {e}")
        else:
            messagebox.showinfo("提示", "备份目录不存在")

    def _restore_selected_backup(self):
        """恢复选中的备份文件"""
        selected_items = self.backup_tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选择要恢复的文件")
            return

        selected_item = selected_items[0]
        tags = self.backup_tree.item(selected_item, 'tags')
        
        if tags:
            backup_path = tags[0]
            success, msg = self.cleaner.restore_backup_file(backup_path)
            if success:
                messagebox.showinfo("成功", msg)
                self._refresh_backup_list()
            else:
                messagebox.showerror("失败", msg)

    def _delete_selected_backup(self):
        """删除选中的备份文件"""
        selected_items = self.backup_tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选择要删除的备份")
            return

        if not messagebox.askyesno("确认", "确定要删除选中的备份文件吗？"):
            return

        selected_item = selected_items[0]
        tags = self.backup_tree.item(selected_item, 'tags')
        
        if tags:
            backup_path = tags[0]
            success, msg = self.cleaner.delete_backup_file(backup_path)
            if success:
                messagebox.showinfo("成功", msg)
                self._refresh_backup_list()
            else:
                messagebox.showerror("失败", msg)

    def _create_history_tab(self, notebook):
        history_frame = ttk.Frame(notebook)
        notebook.add(history_frame, text="📋 历史记录")

        history_notebook = ttk.Notebook(history_frame)
        history_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scan_history_frame = ttk.Frame(history_notebook)
        history_notebook.add(scan_history_frame, text="📁 扫描历史")

        scan_history_btn_frame = ttk.Frame(scan_history_frame)
        scan_history_btn_frame.pack(fill=tk.X, pady=5, padx=10)

        ttk.Button(scan_history_btn_frame, text="🔄 刷新历史", command=self._refresh_scan_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(scan_history_btn_frame, text="🗑️ 清空历史", command=self._clear_scan_history).pack(side=tk.LEFT, padx=5)

        scan_history_list_frame = ttk.LabelFrame(scan_history_frame, text="📁 扫描历史", padding=10)
        scan_history_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        scan_columns = ("scan_time", "scan_path", "file_count", "total_size")
        self.scan_history_tree = ttk.Treeview(scan_history_list_frame, columns=scan_columns, show="headings", selectmode="browse")
        self.scan_history_tree.heading("scan_time", text="扫描时间")
        self.scan_history_tree.heading("scan_path", text="扫描路径")
        self.scan_history_tree.heading("file_count", text="文件数量")
        self.scan_history_tree.heading("total_size", text="总大小")
        self.scan_history_tree.column("scan_time", width=180)
        self.scan_history_tree.column("scan_path", width=400)
        self.scan_history_tree.column("file_count", width=120)
        self.scan_history_tree.column("total_size", width=150)

        scan_tree_frame = ttk.Frame(scan_history_list_frame)
        scan_tree_frame.pack(fill=tk.BOTH, expand=True)
        scan_scroll_container = self._create_tree_with_scrollbars(scan_tree_frame, self.scan_history_tree, pack_args={"fill": tk.BOTH, "expand": True})
        scan_scroll_container.pack(fill=tk.BOTH, expand=True)
        self._refresh_scan_history()

        cleanup_history_frame = ttk.Frame(history_notebook)
        history_notebook.add(cleanup_history_frame, text="🧹 清理历史")

        cleanup_history_btn_frame = ttk.Frame(cleanup_history_frame)
        cleanup_history_btn_frame.pack(fill=tk.X, pady=5, padx=10)

        ttk.Button(cleanup_history_btn_frame, text="🔄 刷新历史", command=self._refresh_cleanup_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(cleanup_history_btn_frame, text="🗑️ 清空历史", command=self._clear_cleanup_history).pack(side=tk.LEFT, padx=5)

        cleanup_history_list_frame = ttk.LabelFrame(cleanup_history_frame, text="🧹 清理历史", padding=10)
        cleanup_history_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        cleanup_columns = ("time", "categories", "deleted_count", "freed_size", "backup")
        self.cleanup_history_tree = ttk.Treeview(cleanup_history_list_frame, columns=cleanup_columns, show="headings", selectmode="browse")
        self.cleanup_history_tree.heading("time", text="清理时间")
        self.cleanup_history_tree.heading("categories", text="清理项目")
        self.cleanup_history_tree.heading("deleted_count", text="删除文件数")
        self.cleanup_history_tree.heading("freed_size", text="释放空间")
        self.cleanup_history_tree.heading("backup", text="是否备份")
        self.cleanup_history_tree.column("time", width=180)
        self.cleanup_history_tree.column("categories", width=300)
        self.cleanup_history_tree.column("deleted_count", width=100)
        self.cleanup_history_tree.column("freed_size", width=120)
        self.cleanup_history_tree.column("backup", width=80)

        cleanup_tree_frame = ttk.Frame(cleanup_history_list_frame)
        cleanup_tree_frame.pack(fill=tk.BOTH, expand=True)
        cleanup_scroll_container = self._create_tree_with_scrollbars(cleanup_tree_frame, self.cleanup_history_tree, pack_args={"fill": tk.BOTH, "expand": True})
        cleanup_scroll_container.pack(fill=tk.BOTH, expand=True)
        self._refresh_cleanup_history()

    def _create_settings_tab(self, notebook):
        settings_frame = ttk.Frame(notebook)
        notebook.add(settings_frame, text="⚙️ 设置")

        theme_frame = ttk.LabelFrame(settings_frame, text="🎨 主题设置", padding=10)
        theme_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(theme_frame, text="🌙 深色模式", command=self._toggle_theme).pack(side=tk.LEFT, padx=5)
        ttk.Button(theme_frame, text="☀️ 浅色模式", command=self._set_light_theme).pack(side=tk.LEFT, padx=5)

        self.auto_theme_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(theme_frame, text="🔄 跟随系统主题", variable=self.auto_theme_var, command=self._toggle_auto_theme).pack(side=tk.LEFT, padx=10)
        self._start_theme_watcher()

        schedule_frame = ttk.LabelFrame(settings_frame, text="⏰ 定时清理计划", padding=10)
        schedule_frame.pack(fill=tk.X, padx=10, pady=5)

        self.schedule_enabled = tk.BooleanVar(value=self.saved_schedule_enabled)
        ttk.Checkbutton(schedule_frame, text="启用定时清理", variable=self.schedule_enabled, command=self._toggle_schedule).pack(anchor=tk.W)

        time_frame = ttk.Frame(schedule_frame)
        time_frame.pack(fill=tk.X, pady=5)

        ttk.Label(time_frame, text="清理时间:").pack(side=tk.LEFT)
        self.schedule_hour = tk.StringVar(value=self.saved_schedule_hour)
        self.schedule_minute = tk.StringVar(value=self.saved_schedule_minute)
        hour_spin = ttk.Spinbox(time_frame, from_=0, to=23, width=3, textvariable=self.schedule_hour, format="%02.0f")
        hour_spin.pack(side=tk.LEFT, padx=2)
        ttk.Label(time_frame, text=":").pack(side=tk.LEFT)
        minute_spin = ttk.Spinbox(time_frame, from_=0, to=59, width=3, textvariable=self.schedule_minute, format="%02.0f")
        minute_spin.pack(side=tk.LEFT, padx=2)

        ttk.Label(time_frame, text="  执行间隔: ").pack(side=tk.LEFT, padx=(12, 2))
        self.schedule_interval_days = tk.StringVar(value=self.saved_schedule_interval_days)
        interval_spin = ttk.Spinbox(time_frame, from_=1, to=365, width=4, textvariable=self.schedule_interval_days)
        interval_spin.pack(side=tk.LEFT, padx=2)
        ttk.Label(time_frame, text="天").pack(side=tk.LEFT, padx=2)

        ttk.Button(time_frame, text="每周", command=lambda: self.schedule_interval_days.set("7")).pack(side=tk.LEFT, padx=(10, 2))
        ttk.Button(time_frame, text="10天", command=lambda: self.schedule_interval_days.set("10")).pack(side=tk.LEFT, padx=2)
        ttk.Button(time_frame, text="半月", command=lambda: self.schedule_interval_days.set("15")).pack(side=tk.LEFT, padx=2)
        self.schedule_categories = {
            'temp': tk.BooleanVar(value=self.saved_schedule_categories.get('temp', True)),
            'browser_cache': tk.BooleanVar(value=self.saved_schedule_categories.get('browser_cache', True)),
        }
        ttk.Label(schedule_frame, text="定时清理项目:").pack(anchor=tk.W, pady=(5, 0))
        cat_frame = ttk.Frame(schedule_frame)
        cat_frame.pack(fill=tk.X)
        ttk.Checkbutton(cat_frame, text="临时文件", variable=self.schedule_categories['temp']).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(cat_frame, text="浏览器缓存", variable=self.schedule_categories['browser_cache']).pack(side=tk.LEFT, padx=5)

        self.schedule_status_label = ttk.Label(schedule_frame, text="定时清理: 未启用")
        self.schedule_status_label.pack(anchor=tk.W, pady=5)
        for var in (self.schedule_hour, self.schedule_minute, self.schedule_interval_days):
            var.trace_add('write', lambda *_: self._schedule_settings_changed())
        for var in self.schedule_categories.values():
            var.trace_add('write', lambda *_: self._schedule_settings_changed())
        if self.schedule_enabled.get():
            self.root.after(1000, self._start_schedule)

        tray_frame = ttk.LabelFrame(settings_frame, text="🖥️ 系统托盘设置", padding=10)
        tray_frame.pack(fill=tk.X, padx=10, pady=5)

        if HAS_PYSTRAY:
            self.tray_enabled = tk.BooleanVar(value=False)
            ttk.Checkbutton(tray_frame, text="启用系统托盘", variable=self.tray_enabled, command=self._toggle_tray).pack(anchor=tk.W)
            ttk.Label(tray_frame, text="关闭窗口时最小化到系统托盘").pack(anchor=tk.W, padx=5, pady=2)
        else:
            ttk.Label(tray_frame, text="⚠️ 系统托盘功能不可用，请安装: pip install pystray pillow", foreground="red").pack(anchor=tk.W)

        context_menu_frame = ttk.LabelFrame(settings_frame, text="📂 右键菜单集成", padding=10)
        context_menu_frame.pack(fill=tk.X, padx=10, pady=5)

        self.context_menu_status = ttk.Label(context_menu_frame, text="状态: 未安装")
        self.context_menu_status.pack(anchor=tk.W, pady=2)
        
        context_btn_frame = ttk.Frame(context_menu_frame)
        context_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(context_btn_frame, text="➕ 安装右键菜单", command=self._install_context_menu).pack(side=tk.LEFT, padx=5)
        ttk.Button(context_btn_frame, text="➖ 卸载右键菜单", command=self._uninstall_context_menu).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(context_menu_frame, text="右键菜单将添加到文件夹，提供快速扫描功能", font=("Microsoft YaHei", 9)).pack(anchor=tk.W, padx=5)

        deps_frame = ttk.LabelFrame(settings_frame, text="🔧 依赖管理", padding=10)
        deps_frame.pack(fill=tk.X, padx=10, pady=5)

        self.deps_status_label = ttk.Label(deps_frame, text="正在检查依赖状态...")
        self.deps_status_label.pack(anchor=tk.W, pady=2)
        
        deps_btn_frame = ttk.Frame(deps_frame)
        deps_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(deps_btn_frame, text="⬇️ 一键安装所有依赖", command=self._install_dependencies).pack(side=tk.LEFT, padx=5)
        ttk.Button(deps_btn_frame, text="🔍 检查依赖状态", command=self._check_dependencies).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(deps_frame, text="依赖说明：matplotlib(可视化), pystray/pillow(系统托盘), pyinstaller(打包)", font=("Microsoft YaHei", 9)).pack(anchor=tk.W, padx=5)

        build_frame = ttk.LabelFrame(settings_frame, text="📦 一键打包", padding=10)
        build_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(build_frame, text="🚀 打包为EXE文件", command=self._build_executable).pack(side=tk.LEFT, padx=5)
        ttk.Label(build_frame, text="将程序打包为独立的exe可执行文件（需要管理员权限）", font=("Microsoft YaHei", 9)).pack(anchor=tk.W, padx=5, pady=2)

        whitelist_frame = ttk.LabelFrame(settings_frame, text="📋 白名单（这些文件不会被清理）", padding=10)
        whitelist_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        whitelist_btn_frame = ttk.Frame(whitelist_frame)
        whitelist_btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(whitelist_btn_frame, text="📄 添加文件", command=self._add_whitelist_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(whitelist_btn_frame, text="📁 添加文件夹", command=self._add_whitelist_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(whitelist_btn_frame, text="🗑️ 删除选中", command=self._remove_whitelist_item).pack(side=tk.LEFT, padx=5)

        whitelist_columns = ("path",)
        self.whitelist_tree = ttk.Treeview(whitelist_frame, columns=whitelist_columns, show="headings", selectmode="extended")
        self.whitelist_tree.heading("path", text="路径")
        self.whitelist_tree.column("path", width=700)
        whitelist_tree_frame = ttk.Frame(whitelist_frame)
        whitelist_tree_frame.pack(fill=tk.BOTH, expand=True)
        whitelist_scroll_container = self._create_tree_with_scrollbars(whitelist_tree_frame, self.whitelist_tree, pack_args={"fill": tk.BOTH, "expand": True})
        whitelist_scroll_container.pack(fill=tk.BOTH, expand=True)
        self._refresh_whitelist_display()

    def _browse_directory(self):
        directory = filedialog.askdirectory(initialdir='C:\\', title="选择要扫描的目录")
        if directory:
            self.path_var.set(directory)
            self.current_scan_path = directory

    def _search_files(self):
        if not self.scan_results or not self.large_files:
            messagebox.showwarning("提示", "请先扫描目录")
            return

        search_text = self.search_var.get().lower().strip()
        if not search_text:
            self._populate_large_files()
            return

        for item in self.lf_tree.get_children():
            self.lf_tree.delete(item)

        matched_files = [f for f in self.large_files if search_text in f['path'].lower()]
        for file_info in matched_files:
            self.lf_tree.insert("", tk.END, values=(file_info['path'], file_info['size'], file_info['formatted_size']))

        self._append_result(f"\n搜索完成！找到 {len(matched_files)} 个匹配的文件")

    def _clear_search(self):
        self.search_var.set("")
        if self.scan_results:
            self._populate_large_files()

    def _preview_cleanup_files(self):
        selected_categories = [cat for cat, var in self.cleanup_vars.items() if var.get()]
        if not selected_categories:
            messagebox.showwarning("提示", "请先选择要清理的项目")
            return

        preview_window = tk.Toplevel(self.root)
        preview_window.title("👁️ 文件预览 - 勾选要清理的文件")
        preview_window.geometry("900x600")

        top_frame = ttk.Frame(preview_window)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(top_frame, text="勾选要清理的文件，然后点击\"清理选中\"按钮").pack(side=tk.LEFT)

        self.preview_selected_files = []
        self.preview_all_files = []

        paths = self.cleaner.cleanup_paths
        for category in selected_categories:
            if category in paths:
                for path in paths[category]:
                    if os.path.exists(path):
                        if os.path.isfile(path):
                            if not self.cleaner.is_in_whitelist(path):
                                try:
                                    size = os.path.getsize(path)
                                    self.preview_all_files.append({'path': path, 'size': size, 'category': category})
                                except:
                                    pass
                        elif os.path.isdir(path):
                            try:
                                for root_dir, dirnames, filenames in os.walk(path):
                                    for filename in filenames:
                                        file_path = str(Path(str(root_dir)) / str(filename))
                                        if not self.cleaner.is_in_whitelist(file_path):
                                            try:
                                                size = os.path.getsize(file_path)
                                                self.preview_all_files.append({'path': file_path, 'size': size, 'category': category})
                                            except:
                                                pass
                            except:
                                pass

        tree_frame = ttk.Frame(preview_window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("select", "category", "size", "path")
        preview_tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", height=20)

        preview_tree.heading("#0", text="")
        preview_tree.heading("select", text="选择")
        preview_tree.heading("category", text="类别")
        preview_tree.heading("size", text="大小")
        preview_tree.heading("path", text="文件路径")

        preview_tree.column("#0", width=30)
        preview_tree.column("select", width=60, anchor=tk.CENTER)
        preview_tree.column("category", width=120)
        preview_tree.column("size", width=100)
        preview_tree.column("path", width=550)

        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=preview_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=preview_tree.xview)
        preview_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.preview_vars = {}
        category_icons = {
            'temp': '📄',
            'windows_update_cache': '💿',
            'browser_cache': '🌐',
            'prefetch': '⚡',
            'thumbnails': '🖼️',
            'log_files': '📝'
        }

        for file_info in self.preview_all_files:
            file_path = file_info['path']
            category = file_info['category']
            size = file_info['size']
            icon = category_icons.get(category, '📁')
            size_str = self.cleaner.format_size(size)

            item_id = preview_tree.insert("", tk.END, text=icon, values=("☐", category, size_str, file_path))
            self.preview_vars[item_id] = {'path': file_path, 'size': size}

        total_size = sum(f['size'] for f in self.preview_all_files)
        total_count = len(self.preview_all_files)

        bottom_frame = ttk.Frame(preview_window)
        bottom_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(bottom_frame, text=f"共 {total_count} 个文件, 总计: {self.cleaner.format_size(total_size)}").pack(side=tk.LEFT)

        self.selected_count_label = ttk.Label(bottom_frame, text="已选择: 0 个文件, 0 B")
        self.selected_count_label.pack(side=tk.LEFT, padx=20)

        button_frame = ttk.Frame(preview_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        def on_checkbox_click(item_id):
            current_val = preview_tree.item(item_id, "values")[0]
            if current_val == "☐":
                preview_tree.item(item_id, values=("☑", self.preview_vars[item_id]['category'], self.cleaner.format_size(self.preview_vars[item_id]['size']), self.preview_vars[item_id]['path']))
                self.preview_selected_files.append(self.preview_vars[item_id]['path'])
            else:
                preview_tree.item(item_id, values=("☐", self.preview_vars[item_id]['category'], self.cleaner.format_size(self.preview_vars[item_id]['size']), self.preview_vars[item_id]['path']))
                if self.preview_vars[item_id]['path'] in self.preview_selected_files:
                    self.preview_selected_files.remove(self.preview_vars[item_id]['path'])
            update_selected_count()

        def update_selected_count():
            selected_size = sum(self.preview_vars[i]['size'] for i in self.preview_vars if self.preview_vars[i]['path'] in self.preview_selected_files)
            self.selected_count_label.config(text=f"已选择: {len(self.preview_selected_files)} 个文件, {self.cleaner.format_size(selected_size)}")

        def on_tree_select(event):
            region = preview_tree.identify_region(event.x, event.y)
            if region == "cell":
                column = preview_tree.identify_column(event.x)
                if column == "#1" or column == "#2":
                    item_id = preview_tree.identify_row(event.y)
                    if item_id in self.preview_vars:
                        on_checkbox_click(item_id)

        preview_tree.bind("<Button-1>", on_tree_select)

        def select_all():
            self.preview_selected_files = [self.preview_vars[i]['path'] for i in self.preview_vars]
            for item_id in self.preview_vars:
                preview_tree.item(item_id, values=("☑", self.preview_vars[item_id]['category'], self.cleaner.format_size(self.preview_vars[item_id]['size']), self.preview_vars[item_id]['path']))
            update_selected_count()

        def deselect_all():
            self.preview_selected_files = []
            for item_id in self.preview_vars:
                preview_tree.item(item_id, values=("☐", self.preview_vars[item_id]['category'], self.cleaner.format_size(self.preview_vars[item_id]['size']), self.preview_vars[item_id]['path']))
            update_selected_count()

        ttk.Button(button_frame, text="✅ 全选", command=select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❎ 取消全选", command=deselect_all).pack(side=tk.LEFT, padx=5)

        def do_clean_selected():
            if not self.preview_selected_files:
                messagebox.showwarning("提示", "请先选择要清理的文件")
                return

            selected_size = sum(self.preview_vars[i]['size'] for i in self.preview_vars if self.preview_vars[i]['path'] in self.preview_selected_files)

            if not messagebox.askyesno("确认", f"确定要删除选中的 {len(self.preview_selected_files)} 个文件吗？\n将释放: {self.cleaner.format_size(selected_size)}\n\n建议先备份重要数据！"):
                return

            backup = self.backup_var.get()
            deleted_count = 0
            freed_size = 0
            failed_count = 0

            for file_path in self.preview_selected_files:
                try:
                    if os.path.exists(file_path):
                        size = os.path.getsize(file_path)
                        if backup:
                            backup_path = self.cleaner.backup_file(file_path)
                            if not backup_path:
                                failed_count += 1
                                continue
                        os.remove(file_path)
                        deleted_count += 1
                        freed_size += size
                except Exception:
                    failed_count += 1

            messagebox.showinfo("完成", f"清理完成！\n成功删除: {deleted_count} 个文件\n释放空间: {self.cleaner.format_size(freed_size)}\n失败: {failed_count} 个")

            self._add_cleanup_log_entry(['选择性清理'], deleted_count, freed_size, backup)
            self._refresh_cleanup_log_display()
            self._refresh_cleanup_history()
            preview_window.destroy()

        ttk.Button(button_frame, text="🧹 清理选中", command=do_clean_selected).pack(side=tk.LEFT, padx=20)
        ttk.Button(button_frame, text="关闭", command=preview_window.destroy).pack(side=tk.RIGHT, padx=5)

    def _start_scan(self):
        if self.is_scanning:
            return
        self.is_scanning = True
        self.current_scan_path = self.path_var.get()
        self.scan_btn.config(state=tk.DISABLED)
        self.incremental_scan_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.DISABLED)
        self.export_btn.config(state=tk.DISABLED)
        self.delete_lf_btn.config(state=tk.DISABLED)
        self.move_lf_btn.config(state=tk.DISABLED)
        self.select_all_btn.config(state=tk.DISABLED)
        self.deselect_all_btn.config(state=tk.DISABLED)

        for item in self.lf_tree.get_children():
            self.lf_tree.delete(item)
        self.large_files = []
        self._clear_scan_state()

        self.progress.start()
        self.result_text.delete(1.0, tk.END)
        self._append_result(f"正在扫描: {self.current_scan_path}\n")

        thread = threading.Thread(target=lambda: self._scan_thread(False))
        thread.daemon = True
        thread.start()

    def _start_incremental_scan(self):
        if self.is_scanning:
            return
        self.is_scanning = True
        self.current_scan_path = self.path_var.get()
        self.scan_btn.config(state=tk.DISABLED)
        self.incremental_scan_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.DISABLED)
        self.export_btn.config(state=tk.DISABLED)
        self.delete_lf_btn.config(state=tk.DISABLED)
        self.move_lf_btn.config(state=tk.DISABLED)
        self.select_all_btn.config(state=tk.DISABLED)
        self.deselect_all_btn.config(state=tk.DISABLED)

        self.progress.start()
        self.result_text.delete(1.0, tk.END)
        self._append_result(f"正在增量扫描: {self.current_scan_path}\n")

        thread = threading.Thread(target=lambda: self._scan_thread(True))
        thread.daemon = True
        thread.start()

    def _stop_scan(self):
        self.is_scanning = False

    def _resume_scan(self):
        if not self.scan_state:
            messagebox.showwarning("提示", "没有可恢复的扫描状态")
            return
        
        if self.is_scanning:
            return
        
        self.is_scanning = True
        self.scan_btn.config(state=tk.DISABLED)
        self.incremental_scan_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.DISABLED)
        self.export_btn.config(state=tk.DISABLED)
        self.delete_lf_btn.config(state=tk.DISABLED)
        self.move_lf_btn.config(state=tk.DISABLED)
        self.select_all_btn.config(state=tk.DISABLED)
        self.deselect_all_btn.config(state=tk.DISABLED)

        self.progress.start()
        self._append_result(f"正在恢复扫描: {self.scan_state['scan_path']}\n")

        thread = threading.Thread(target=lambda: self._scan_thread(False, resume=True))
        thread.daemon = True
        thread.start()

    def _scan_thread(self, incremental, resume=False):
        try:
            if resume and self.scan_state:
                scan_path = self.scan_state['scan_path']
                start_dir = self.scan_state.get('current_dir', '')
                file_count = self.scan_state.get('file_count', 0)
                total_size = self.scan_state.get('total_size', 0)
                large_files = self.scan_state.get('large_files', [])
                file_types = self.scan_state.get('file_types', {})
                
                disk_info = self.scanner.get_disk_space_info(scan_path)
                if disk_info:
                    self._append_result("\n磁盘空间信息:")
                    self._append_result(f"路径: {disk_info['path']}")
                    self._append_result(f"总空间: {disk_info['total_formatted']}")
                    self._append_result(f"已使用: {disk_info['used_formatted']}")
                    self._append_result(f"剩余: {disk_info['free_formatted']}\n")
                
                results = self._scan_from_directory(scan_path, start_dir, file_count, total_size, large_files, file_types)
            else:
                disk_info = self.scanner.get_disk_space_info(self.current_scan_path)
                if disk_info:
                    self._append_result("\n磁盘空间信息:")
                    self._append_result(f"路径: {disk_info['path']}")
                    self._append_result(f"总空间: {disk_info['total_formatted']}")
                    self._append_result(f"已使用: {disk_info['used_formatted']}")
                    self._append_result(f"剩余: {disk_info['free_formatted']}\n")
                
                if incremental:
                    results = self._incremental_scan_drive(self.current_scan_path)
                else:
                    results = self.scanner.scan_drive(self.current_scan_path, progress_callback=self._update_scan_progress)

            self.scan_results = results
            self._append_result("\n扫描完成!")
            self._append_result(f"扫描路径: {results['scan_path']}")
            self._append_result(f"扫描文件数: {results['file_count']}")
            self._append_result(f"总大小: {self.scanner.format_size(results['total_size'])}")
            self._append_result(f"耗时: {results['scan_time']:.2f} 秒\n")

            self._append_result("\n文件类型分布 (前10个):")
            sorted_types = sorted(results['file_types'].items(), key=lambda x: x[1], reverse=True)
            for ext, size in sorted_types[:10]:
                self._append_result(f"{ext}: {self.scanner.format_size(size)}")

            history_entry = {
                'scan_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'scan_path': results['scan_path'],
                'file_count': results['file_count'],
                'total_size': results['total_size'],
                'formatted_size': self.scanner.format_size(results['total_size'])
            }
            self.scan_history.insert(0, history_entry)
            if len(self.scan_history) > 50:
                self.scan_history = self.scan_history[:50]
            self._save_history()
            self.root.after(0, self._refresh_scan_history)

            self.large_files = results['large_files']
            self.root.after(0, self._populate_large_files)
            self._clear_scan_state()

        except Exception as e:
            self._append_result(f"\n扫描出错: {e}")
        finally:
            self.is_scanning = False
            self.root.after(0, self._scan_finished)

    def _scan_from_directory(self, scan_path, start_dir, file_count, total_size, large_files, file_types):
        start_time = datetime.datetime.now()
        
        current_dir = start_dir
        should_save_state = False
        
        def progress_callback(results):
            nonlocal current_dir, should_save_state
            if not self.is_scanning:
                self._save_scan_state({
                    'scan_path': scan_path,
                    'current_dir': current_dir,
                    'file_count': results['file_count'],
                    'total_size': results['total_size'],
                    'large_files': large_files,
                    'file_types': file_types
                })
                return False
            current_dir = results.get('current_dir', '')
            should_save_state = not should_save_state
            if should_save_state:
                self._save_scan_state({
                    'scan_path': scan_path,
                    'current_dir': current_dir,
                    'file_count': results['file_count'],
                    'total_size': results['total_size'],
                    'large_files': large_files,
                    'file_types': file_types
                })
            self._update_scan_progress(results)
            return True
        
        final_results = self.scanner.scan_drive(scan_path, progress_callback=progress_callback, 
                                               start_file_count=file_count, start_total_size=total_size,
                                               start_large_files=large_files, start_file_types=file_types)
        
        final_results['scan_time'] = (datetime.datetime.now() - start_time).total_seconds()
        return final_results

    def _incremental_scan_drive(self, scan_path):
        start_time = datetime.datetime.now()
        file_count = 0
        total_size = 0
        large_files = []
        file_types = {}
        skipped_files = 0
        new_files = 0
        updated_files = 0
        
        def incremental_progress(path, is_dir):
            nonlocal file_count, total_size, skipped_files, new_files, updated_files
            if not self.is_scanning:
                return False
            
            if is_dir:
                return True
            
            try:
                file_size = os.path.getsize(path)
                current_hash = get_file_hash(path)
                old_hash = self.file_hashes.get(path, None)
                
                if old_hash == current_hash:
                    skipped_files += 1
                else:
                    if old_hash is None:
                        new_files += 1
                    else:
                        updated_files += 1
                    self.file_hashes[path] = current_hash
                    file_count += 1
                    total_size += file_size
                    
                    if file_size > 100 * 1024 * 1024:
                        large_files.append({
                            'path': path,
                            'size': file_size,
                            'formatted_size': self.scanner.format_size(file_size)
                        })
                    
                    ext = os.path.splitext(path)[1].lower() or '无扩展名'
                    file_types[ext] = file_types.get(ext, 0) + file_size
                
                if file_count % 100 == 0:
                    self._update_scan_progress({
                        'file_count': file_count,
                        'total_size': total_size,
                        'current_dir': os.path.dirname(path)
                    })
                    self._append_result(f"已扫描 {file_count} 个文件 (新: {new_files}, 更新: {updated_files}, 跳过: {skipped_files})")
                
            except:
                pass
            
            return True
        
        self.scanner.scan_with_callback(scan_path, incremental_progress)
        
        self._save_file_hashes()
        
        scan_time = (datetime.datetime.now() - start_time).total_seconds()
        
        self._append_result(f"\n增量扫描完成!")
        self._append_result(f"新文件: {new_files}")
        self._append_result(f"更新文件: {updated_files}")
        self._append_result(f"跳过文件: {skipped_files}")
        
        return {
            'scan_path': scan_path,
            'file_count': file_count,
            'total_size': total_size,
            'large_files': large_files,
            'file_types': file_types,
            'scan_time': scan_time
        }

    def _populate_large_files(self):
        for file_info in self.large_files:
            self.lf_tree.insert("", tk.END, values=(file_info['path'], file_info['size'], file_info['formatted_size']))

        ext_counts = {}
        for f in self.large_files:
            ext = os.path.splitext(f['path'])[1].lower()
            if not ext:
                ext = '(无扩展名)'
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

        sorted_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)
        ext_values = ["全部"] + [f"{ext} ({count})" for ext, count in sorted_exts[:20]]
        self.ext_filter_combo['values'] = ext_values
        self.ext_filter_var.set("全部")

        total_count = len(self.large_files)
        total_size = sum(f['size'] for f in self.large_files)
        self.ext_filter_count_label.config(text=f"共 {total_count} 个文件, 总计 {self.scanner.format_size(total_size)}")

    def _on_extension_filter_changed(self, event=None):
        selected = self.ext_filter_var.get()
        if selected == "全部":
            self._populate_large_files()
            return

        ext = selected.rsplit(' (', 1)[0]

        for item in self.lf_tree.get_children():
            self.lf_tree.delete(item)

        filtered = [f for f in self.large_files if os.path.splitext(f['path'])[1].lower() == ext or (not ext and not os.path.splitext(f['path'])[1])]

        for file_info in filtered:
            self.lf_tree.insert("", tk.END, values=(file_info['path'], file_info['size'], file_info['formatted_size']))

        total_size = sum(f['size'] for f in filtered)
        self.ext_filter_count_label.config(text=f"扩展名 '{ext}': {len(filtered)} 个文件, {self.scanner.format_size(total_size)}")

    def _on_size_filter_changed(self, event=None):
        """按大小筛选大文件"""
        selected = self.size_filter_var.get()
        ext_filter = self.ext_filter_var.get()
        
        if selected == "全部" and ext_filter == "全部":
            self._populate_large_files()
            return

        size_ranges = {
            "全部": (0, float('inf')),
            "100MB以下": (0, 100 * 1024 * 1024),
            "100MB-500MB": (100 * 1024 * 1024, 500 * 1024 * 1024),
            "500MB-1GB": (500 * 1024 * 1024, 1024 * 1024 * 1024),
            "1GB以上": (1024 * 1024 * 1024, float('inf'))
        }
        
        min_size, max_size = size_ranges[selected]
        
        filtered = []
        for f in self.large_files:
            if min_size <= f['size'] < max_size:
                if ext_filter == "全部":
                    filtered.append(f)
                else:
                    ext = ext_filter.rsplit(' (', 1)[0]
                    if os.path.splitext(f['path'])[1].lower() == ext or (not ext and not os.path.splitext(f['path'])[1]):
                        filtered.append(f)

        for item in self.lf_tree.get_children():
            self.lf_tree.delete(item)

        for file_info in filtered:
            self.lf_tree.insert("", tk.END, values=(file_info['path'], file_info['size'], file_info['formatted_size']))

        total_size = sum(f['size'] for f in filtered)
        self.ext_filter_count_label.config(text=f"筛选结果: {len(filtered)} 个文件, {self.scanner.format_size(total_size)}")

    def _select_by_category(self):
        """按文件类型批量选择"""
        categories = list(self.scanner.FILE_CATEGORIES.keys())
        category_names = [f"{self.scanner.FILE_CATEGORIES[c]['icon']} {self.scanner.FILE_CATEGORIES[c]['name']}" for c in categories]
        
        result = simpledialog.askstring("选择文件类型", f"请输入要选择的文件类型序号（用逗号分隔）:\n" + "\n".join([f"{i+1}. {name}" for i, name in enumerate(category_names)]))
        
        if not result:
            return
        
        try:
            selected_indices = [int(x.strip()) - 1 for x in result.split(',')]
            selected_categories = [categories[i] for i in selected_indices if 0 <= i < len(categories)]
            
            selected_items = []
            for item in self.lf_tree.get_children():
                path = self.lf_tree.item(item, 'values')[0]
                category = self.scanner.get_file_category(os.path.basename(path))
                if category in selected_categories:
                    selected_items.append(item)
            
            self.lf_tree.selection_set(selected_items)
            self._update_lf_button_states()
            
        except Exception as e:
            messagebox.showerror("错误", f"选择失败: {e}")

    def _invert_large_file_selection(self):
        """反选所有文件"""
        all_items = self.lf_tree.get_children()
        selected = set(self.lf_tree.selection())
        
        new_selection = [item for item in all_items if item not in selected]
        self.lf_tree.selection_set(new_selection)
        self._update_lf_button_states()

    def _select_all_large_files(self):
        for item in self.lf_tree.get_children():
            self.lf_tree.selection_add(item)

    def _deselect_all_large_files(self):
        for item in self.lf_tree.get_children():
            self.lf_tree.selection_remove(item)

    def _delete_selected_large_files(self):
        selected_items = self.lf_tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选择要删除的文件")
            return

        total_size = 0
        files_to_delete = []
        for item in selected_items:
            values = self.lf_tree.item(item, "values")
            file_path = values[0]
            file_size = int(values[1])
            files_to_delete.append(file_path)
            total_size += file_size

        confirm_msg = f"确定要删除选中的 {len(files_to_delete)} 个文件吗？\n总共将释放: {self.scanner.format_size(total_size)}\n\n"
        confirm_msg += "\n".join([os.path.basename(str(f)) for f in files_to_delete[:5]]) + ("..." if len(files_to_delete) > 5 else "")

        if not messagebox.askyesno("确认删除", confirm_msg):
            return

        deleted_count = 0
        failed_count = 0
        freed_size = 0

        for item in selected_items:
            values = self.lf_tree.item(item, "values")
            file_path = values[0]
            file_size = int(values[1])

            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
                    freed_size += file_size
                    self.lf_tree.delete(item)
            except Exception as e:
                failed_count += 1
                self._append_result(f"\n删除文件失败: {file_path} - {e}")

        remaining_files = []
        for item in self.lf_tree.get_children():
            values = self.lf_tree.item(item, "values")
            remaining_files.append({
                'path': values[0],
                'size': int(values[1]),
                'formatted_size': values[2]
            })
        self.large_files = remaining_files

        messagebox.showinfo("完成", f"删除完成！\n成功删除: {deleted_count} 个文件\n释放空间: {self.scanner.format_size(freed_size)}\n失败: {failed_count} 个")

    def _move_selected_large_files(self):
        selected_items = self.lf_tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选择要移动的文件")
            return

        dest_dir = filedialog.askdirectory(title="选择目标目录")
        if not dest_dir:
            return

        moved_count = 0
        failed_count = 0

        for item in selected_items:
            values = self.lf_tree.item(item, "values")
            file_path = values[0]

            try:
                if os.path.exists(file_path):
                    dest_path = str(Path(dest_dir) / Path(file_path).name)
                    shutil.move(file_path, dest_path)
                    moved_count += 1
                    self.lf_tree.delete(item)
            except Exception as e:
                failed_count += 1
                self._append_result(f"\n移动文件失败: {file_path} - {e}")

        remaining_files = []
        for item in self.lf_tree.get_children():
            values = self.lf_tree.item(item, "values")
            remaining_files.append({
                'path': values[0],
                'size': int(values[1]),
                'formatted_size': values[2]
            })
        self.large_files = remaining_files

        messagebox.showinfo("完成", f"移动完成！\n成功移动: {moved_count} 个文件\n目标目录: {dest_dir}\n失败: {failed_count} 个")

    def _refresh_scan_history(self):
        for item in self.scan_history_tree.get_children():
            self.scan_history_tree.delete(item)
        for entry in self.scan_history:
            self.scan_history_tree.insert("", tk.END, values=(
                entry['scan_time'],
                entry['scan_path'],
                entry['file_count'],
                entry['formatted_size']
            ))

    def _clear_scan_history(self):
        if messagebox.askyesno("确认", "确定要清空扫描历史吗？"):
            self.scan_history = []
            self._save_history()
            self._refresh_scan_history()
            messagebox.showinfo("完成", "历史记录已清空")

    def _refresh_cleanup_history(self):
        for item in self.cleanup_history_tree.get_children():
            self.cleanup_history_tree.delete(item)
        for entry in self.cleanup_log:
            self.cleanup_history_tree.insert("", tk.END, values=(
                entry['time'],
                ', '.join(entry['categories']),
                entry['deleted_count'],
                entry['freed_size_formatted'],
                '是' if entry['backup'] else '否'
            ))

    def _clear_cleanup_history(self):
        if messagebox.askyesno("确认", "确定要清空清理历史吗？"):
            self.cleanup_log = []
            self._save_cleanup_log()
            self._refresh_cleanup_history()
            messagebox.showinfo("完成", "历史记录已清空")

    def _refresh_cleanup_log_display(self):
        self.cleanup_log_display.delete(1.0, tk.END)
        self.cleanup_log_display.insert(tk.END, "=== 最近清理记录 ===\n\n")
        for entry in self.cleanup_log[:10]:
            self.cleanup_log_display.insert(tk.END, f"时间: {entry['time']}\n")
            self.cleanup_log_display.insert(tk.END, f"清理项目: {', '.join(entry['categories'])}\n")
            self.cleanup_log_display.insert(tk.END, f"删除文件: {entry['deleted_count']} 个\n")
            self.cleanup_log_display.insert(tk.END, f"释放空间: {entry['freed_size_formatted']}\n")
            self.cleanup_log_display.insert(tk.END, f"备份: {'是' if entry['backup'] else '否'}\n")
            self.cleanup_log_display.insert(tk.END, f"{'-' * 60}\n\n")

    def _refresh_whitelist_display(self):
        for item in self.whitelist_tree.get_children():
            self.whitelist_tree.delete(item)
        for path in self.cleaner.whitelist:
            self.whitelist_tree.insert("", tk.END, values=(path,))

    def _refresh_smart_suggestions(self):
        if getattr(self, '_suggestions_loading', False):
            return
        self._suggestions_loading = True
        try:
            self.refresh_suggestions_btn.config(state=tk.DISABLED)
        except Exception:
            pass
        self.suggestions_text.delete(1.0, tk.END)
        self.suggestions_text.insert(tk.END, "正在计算可清理空间，请稍候...\n")

        def worker():
            try:
                suggestions = self.cleaner.get_smart_cleanup_suggestions()
                self.root.after(0, lambda: self._refresh_smart_suggestions_sync(suggestions))
            except Exception as exc:
                self.root.after(0, lambda exc=exc: self._refresh_smart_suggestions_error(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_smart_suggestions_sync(self, suggestions=None):
        self._suggestions_loading = False
        self._latest_suggestions = suggestions
        try:
            self.refresh_suggestions_btn.config(state=tk.NORMAL)
        except Exception:
            pass
        self.suggestions_text.delete(1.0, tk.END)
        if suggestions is None:
            suggestions = self.cleaner.get_smart_cleanup_suggestions()
            self._latest_suggestions = suggestions
        
        self.suggestions_text.insert(tk.END, f"=== 智能清理建议 ===\n\n")
        self.suggestions_text.insert(tk.END, f"总计可释放: {suggestions['total_recoverable_formatted']}\n\n")
        
        priority_labels = {'high': '🔴 高优先级', 'medium': '🟡 中优先级', 'low': '🟢 低优先级'}
        
        for i, suggestion in enumerate(suggestions['suggestions']):
            safe_mark = "✅ 安全" if suggestion['safe'] else "⚠️ 谨慎"
            self.suggestions_text.insert(tk.END, f"{i+1}. {suggestion['category']} ({safe_mark})\n")
            self.suggestions_text.insert(tk.END, f"   优先级: {priority_labels[suggestion['priority']]}\n")
            self.suggestions_text.insert(tk.END, f"   描述: {suggestion['description']}\n")
            self.suggestions_text.insert(tk.END, f"   可释放: {suggestion['recoverable_size_formatted']}\n\n")
        
        self.suggestions_text.insert(tk.END, "提示: 点击'一键清理安全项'将清理所有标记为安全的项目\n")

    def _refresh_smart_suggestions_error(self, exc):
        self._suggestions_loading = False
        self._latest_suggestions = None
        try:
            self.refresh_suggestions_btn.config(state=tk.NORMAL)
        except Exception:
            pass
        self.suggestions_text.delete(1.0, tk.END)
        self.suggestions_text.insert(tk.END, f"智能清理建议加载失败: {exc}\n")

    def _apply_safe_suggestions(self):
        suggestions = self._latest_suggestions
        if suggestions is None:
            messagebox.showinfo("提示", "请先刷新智能清理建议，计算完成后再执行安全清理。")
            self._refresh_smart_suggestions()
            return

        categories_map = {
            '临时文件': 'temp',
            '浏览器缓存': 'browser_cache',
            'Windows更新缓存': 'windows_update_cache',
            '预读取文件': 'prefetch',
            '缩略图缓存': 'thumbnails',
            '系统日志': 'log_files'
        }

        selected_categories = []
        for suggestion in suggestions['suggestions']:
            if suggestion['safe'] and suggestion['recoverable_size'] > 0:
                cat_key = categories_map.get(suggestion['category'])
                if cat_key:
                    selected_categories.append(cat_key)

        if not selected_categories:
            messagebox.showinfo("提示", "没有可清理的安全项目")
            return

        confirm_msg = f"确定要清理以下安全项目吗？\n{', '.join(selected_categories)}"
        if not messagebox.askyesno("确认清理", confirm_msg):
            return

        self._init_cleanup_progress(len(selected_categories))
        backup = bool(self.backup_var.get())
        thread = threading.Thread(
            target=self._safe_cleanup_thread,
            args=(selected_categories, backup),
        )
        thread.daemon = True
        thread.start()

    def _safe_cleanup_thread(self, selected_categories, backup):
        total_deleted = 0
        total_freed = 0
        total = len(selected_categories)

        for i, category in enumerate(selected_categories):
            self.root.after(0, lambda ci=i, cat=category: self._update_cleanup_progress(
                ci, total, f"正在清理安全项: {cat}..."
            ))
            result = self.cleaner.cleanup(category, backup=backup)
            total_deleted += result['deleted_count']
            total_freed += result['freed_size']
            self.root.after(0, lambda r=result, c=category: self._append_cleanup_log(
                f"{c}: 删除 {r['deleted_count']} 个文件, 释放 {r['freed_size_formatted']}"
            ))
            self.root.after(0, lambda ci=i+1: self.cleanup_progress.config(value=(ci / total) * 100))

        self.root.after(0, lambda: self._append_cleanup_log(
            f"\n总计: 删除 {total_deleted} 个文件, 释放 {self.cleaner.format_size(total_freed)}"
        ))
        self._add_cleanup_log_entry(selected_categories, total_deleted, total_freed, backup)

        self.root.after(0, self._safe_cleanup_finished)
        self.root.after(0, lambda: messagebox.showinfo("完成", f"清理完成!\n删除: {total_deleted} 个文件\n释放: {self.cleaner.format_size(total_freed)}"))

    def _safe_cleanup_finished(self):
        self.cleanup_progress['value'] = 100
        self.cleanup_status_label.config(text="清理完成")
        self._refresh_cleanup_log_display()
        self._refresh_cleanup_history()
        self._refresh_smart_suggestions()

    def _toggle_schedule(self):
        if self.schedule_enabled.get():
            self._start_schedule()
        else:
            self._stop_schedule()
        self._save_settings()

    def _schedule_settings_changed(self):
        if hasattr(self, 'schedule_status_label') and self.schedule_running:
            self.schedule_status_label.config(text=self._schedule_status_text())
        self._save_settings()

    def _start_schedule(self):
        if self.schedule_running:
            return
        self.schedule_running = True
        self.schedule_status_label.config(text=self._schedule_status_text())
        self._save_settings()
        self._check_schedule()

    def _stop_schedule(self):
        self.schedule_running = False
        if self.schedule_timer:
            self.root.after_cancel(self.schedule_timer)
            self.schedule_timer = None
        self.schedule_status_label.config(text="定时清理: 未启用")
        self._save_settings()

    def _check_schedule(self):
        if not self.schedule_running:
            return
        
        now = datetime.datetime.now()
        target_hour, target_minute = self._get_schedule_time()
        target_time = datetime.datetime(now.year, now.month, now.day, target_hour, target_minute)

        if now >= target_time and self._schedule_due(now.date()):
            self._run_scheduled_cleanup()
        
        self.schedule_timer = self.root.after(60000, self._check_schedule)

    def _get_schedule_time(self):
        try:
            hour = max(0, min(23, int(self.schedule_hour.get())))
        except Exception:
            hour = 2
        try:
            minute = max(0, min(59, int(self.schedule_minute.get())))
        except Exception:
            minute = 0
        return hour, minute

    def _get_schedule_interval_days(self):
        try:
            return max(1, min(365, int(self.schedule_interval_days.get())))
        except Exception:
            return 1

    def _schedule_due(self, today):
        today_text = today.isoformat()
        if self.last_schedule_run_date == today_text:
            return False
        if not self.last_schedule_run_date:
            return True
        try:
            last_run = datetime.date.fromisoformat(self.last_schedule_run_date)
        except Exception:
            return True
        return (today - last_run).days >= self._get_schedule_interval_days()

    def _schedule_status_text(self):
        hour, minute = self._get_schedule_time()
        interval = self._get_schedule_interval_days()
        if interval == 1:
            interval_text = "每天"
        elif interval == 7:
            interval_text = "每周"
        elif interval == 10:
            interval_text = "每10天"
        elif interval == 15:
            interval_text = "半月"
        else:
            interval_text = f"每{interval}天"
        return f"定时清理: {interval_text}，执行时间 {hour:02d}:{minute:02d}"

    def _run_scheduled_cleanup(self):
        if self._scheduled_cleanup_active:
            return
        categories = [cat for cat, var in self.schedule_categories.items() if var.get()]
        if not categories:
            return

        self._scheduled_cleanup_active = True
        thread = threading.Thread(target=self._scheduled_cleanup_thread, args=(categories,), daemon=True)
        thread.start()

    def _scheduled_cleanup_thread(self, categories):
        total_deleted = 0
        total_freed = 0
        error_message = None

        try:
            for category in categories:
                result = self.cleaner.cleanup(category, backup=True)
                total_deleted += result['deleted_count']
                total_freed += result['freed_size']
                self.root.after(0, lambda r=result, c=category: self._append_cleanup_log(
                    f"[定时清理] {c}: 删除 {r['deleted_count']} 个文件，释放 {r['freed_size_formatted']}"
                ))
        except Exception as exc:
            error_message = str(exc)

        self.root.after(
            0,
            lambda cs=categories, td=total_deleted, tf=total_freed, er=error_message:
            self._finish_scheduled_cleanup(cs, td, tf, er)
        )

    def _finish_scheduled_cleanup(self, categories, total_deleted, total_freed, error_message=None):
        if error_message:
            self._append_cleanup_log(f"[定时清理] 执行异常: {error_message}")
        else:
            self._add_cleanup_log_entry(categories, total_deleted, total_freed, True)
            self.last_schedule_run_date = datetime.date.today().isoformat()
            self._save_settings()
            self._append_cleanup_log(
                f"[定时清理] 汇总: 删除 {total_deleted} 个文件，释放 {self.cleaner.format_size(total_freed)}"
            )
        self._scheduled_cleanup_active = False

    def _add_whitelist_file(self):
        file_path = filedialog.askopenfilename(title="选择要添加到白名单的文件")
        if file_path:
            if self.cleaner.add_to_whitelist(file_path):
                self._refresh_whitelist_display()
                messagebox.showinfo("成功", "文件已添加到白名单")
            else:
                messagebox.showwarning("提示", "该文件已在白名单中")

    def _add_whitelist_folder(self):
        folder_path = filedialog.askdirectory(title="选择要添加到白名单的文件夹")
        if folder_path:
            if self.cleaner.add_to_whitelist(folder_path):
                self._refresh_whitelist_display()
                messagebox.showinfo("成功", "文件夹已添加到白名单")
            else:
                messagebox.showwarning("提示", "该文件夹已在白名单中")

    def _remove_whitelist_item(self):
        selected_items = self.whitelist_tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选择要删除的白名单项目")
            return

        for item in selected_items:
            values = self.whitelist_tree.item(item, "values")
            path = values[0]
            self.cleaner.remove_from_whitelist(path)

        self._refresh_whitelist_display()
        messagebox.showinfo("完成", "已从白名单中删除")

    def _update_scan_progress(self, results):
        self.root.after(0, lambda: self.status_label.config(
            text=f"已扫描 {results['file_count']} 个文件, 总大小 {self.scanner.format_size(results['total_size'])}"
        ))
        self._update_scan_speed_chart(results)

    def _update_scan_speed_chart(self, results):
        if not HAS_MATPLOTLIB or not hasattr(self, 'scan_speed_frame'):
            return
        
        current_time = datetime.datetime.now()
        file_count = results.get('file_count', 0)
        
        if self.scan_speed_times:
            time_diff = (current_time - self.scan_speed_times[-1]).total_seconds()
            if time_diff > 0:
                if self.scan_speed_data:
                    files_diff = file_count - self.scan_speed_data[-1]
                    speed = files_diff / time_diff
                else:
                    speed = 0
            else:
                speed = 0
        else:
            speed = 0
        
        self.scan_speed_data.append(file_count)
        self.scan_speed_times.append(current_time)
        
        max_points = 50
        if len(self.scan_speed_data) > max_points:
            self.scan_speed_data = self.scan_speed_data[-max_points:]
            self.scan_speed_times = self.scan_speed_times[-max_points:]
        
        self.root.after(0, self._draw_scan_speed_chart)

    def _draw_scan_speed_chart(self):
        if not HAS_MATPLOTLIB or not hasattr(self, 'scan_speed_frame'):
            return
        
        for widget in self.scan_speed_frame.winfo_children():
            widget.destroy()
        
        _, FigureCanvasTkAgg, Figure = _load_matplotlib_backend()
        if not FigureCanvasTkAgg or not Figure:
            return
        
        fig = Figure(figsize=(10, 2), dpi=100)
        ax = fig.add_subplot(111)
        
        if len(self.scan_speed_data) > 1:
            times_relative = [(t - self.scan_speed_times[0]).total_seconds() for t in self.scan_speed_times]
            ax.plot(times_relative, self.scan_speed_data, color='#2196F3', linewidth=2)
            
            speeds = []
            for i in range(1, len(self.scan_speed_data)):
                time_diff = times_relative[i] - times_relative[i-1]
                if time_diff > 0:
                    speeds.append((self.scan_speed_data[i] - self.scan_speed_data[i-1]) / time_diff)
            
            if speeds:
                avg_speed = sum(speeds) / len(speeds)
                ax.set_title(f'扫描进度 - 平均速度: {avg_speed:.1f} 文件/秒', fontsize=10)
            else:
                ax.set_title('扫描进度', fontsize=10)
            
            ax.set_xlabel('时间 (秒)', fontsize=8)
            ax.set_ylabel('文件数', fontsize=8)
            ax.tick_params(axis='both', labelsize=7)
            ax.grid(True, alpha=0.3)
        
        fig.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=self.scan_speed_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _append_result(self, text):
        self.root.after(0, lambda: self.result_text.insert(tk.END, text + "\n"))
        self.root.after(0, lambda: self.result_text.see(tk.END))

    def _scan_finished(self):
        self.progress.stop()
        self.scan_btn.config(state=tk.NORMAL)
        self.incremental_scan_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.export_btn.config(state=tk.NORMAL)
        self.delete_lf_btn.config(state=tk.NORMAL)
        self.move_lf_btn.config(state=tk.NORMAL)
        self.select_all_btn.config(state=tk.NORMAL)
        self.deselect_all_btn.config(state=tk.NORMAL)
        self.select_by_type_btn.config(state=tk.NORMAL)
        self.invert_select_btn.config(state=tk.NORMAL)
        if self.scan_state:
            self.resume_btn.config(state=tk.NORMAL)
        self.status_label.config(text="扫描完成")

    def _export_results(self):
        if not self.scan_results:
            messagebox.showwarning("提示", "没有可导出的扫描结果")
            return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"扫描结果_{timestamp}.txt"

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=default_filename,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    content = self.result_text.get(1.0, tk.END)
                    f.write("C盘扫描和安全清理工具 - 扫描结果\n")
                    f.write(f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(content)
                messagebox.showinfo("成功", f"扫描结果已导出到: {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")

    def _calculate_cleanup_size(self):
        selected_categories = [cat for cat, var in self.cleanup_vars.items() if var.get()]
        if not selected_categories:
            self.cleanup_size_label.config(text="可清理空间: --")
            return

        self.calculate_size_btn.config(state=tk.DISABLED)
        self.cleanup_size_label.config(text="正在计算可清理空间...")

        def worker():
            try:
                total_size = 0
                for category in selected_categories:
                    total_size += self.cleaner.calculate_cleanup_size(category)
                self.root.after(0, lambda: self._cleanup_size_calculated(total_size))
            except Exception as exc:
                self.root.after(0, lambda exc=exc: self._cleanup_size_failed(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _cleanup_size_calculated(self, total_size):
        self.calculate_size_btn.config(state=tk.NORMAL)
        self.cleanup_size_label.config(text=f"可清理空间: {self.cleaner.format_size(total_size)}")

    def _cleanup_size_failed(self, exc):
        self.calculate_size_btn.config(state=tk.NORMAL)
        self.cleanup_size_label.config(text=f"计算失败: {exc}")

    def _start_cleanup(self):
        selected_categories = [cat for cat, var in self.cleanup_vars.items() if var.get()]
        if not selected_categories:
            messagebox.showwarning("提示", "请先选择要清理的项目")
            return

        if not messagebox.askyesno("确认", f"确定要开始清理吗？\n清理项目: {', '.join(selected_categories)}\n建议先备份重要数据！"):
            return

        self._init_cleanup_progress(len(selected_categories))

        backup = bool(self.backup_var.get())
        simulate = bool(self.simulate_var.get())
        thread = threading.Thread(
            target=self._cleanup_thread,
            args=(selected_categories, backup, simulate),
        )
        thread.daemon = True
        thread.start()

    def _init_cleanup_progress(self, total_steps):
        self.cleanup_progress['maximum'] = total_steps
        self.cleanup_progress['value'] = 0
        self.cleanup_status_label.config(text="准备开始清理...")

    def _update_cleanup_progress(self, current, total, status_text):
        progress_value = (current / total) * 100 if total > 0 else 0
        self.root.after(0, lambda: self.cleanup_progress.config(value=progress_value))
        self.root.after(0, lambda: self.cleanup_status_label.config(text=status_text))

    def _cleanup_thread(self, selected_categories, backup, simulate):
        total_deleted = 0
        total_freed = 0
        total = len(selected_categories)

        for i, category in enumerate(selected_categories):
            status_text = f"正在{'模拟' if simulate else '清理'}: {category}..."
            self.root.after(0, lambda ci=i, ct=category, st=status_text: self._update_cleanup_progress(
                ci, total, st
            ))
            result = self.cleaner.cleanup(category, backup=backup, simulate=simulate)
            total_deleted += result['deleted_count']
            total_freed += result['freed_size']
            action_text = "模拟删除" if simulate else "删除"
            self.root.after(0, lambda r=result, c=category, at=action_text: self._append_cleanup_log(
                f"{c}: {at} {r['deleted_count']} 个文件，释放 {r['freed_size_formatted']}"
            ))
            self.root.after(0, lambda ci=i+1: self.cleanup_progress.config(value=(ci / total) * 100))

        mode_text = "[模拟模式]" if simulate else ""
        self.root.after(0, lambda mt=mode_text: self._append_cleanup_log(
            f"\n总计{mt}: 删除 {total_deleted} 个文件，释放 {self.cleaner.format_size(total_freed)}"
        ))

        if not simulate:
            self._add_cleanup_log_entry(selected_categories, total_deleted, total_freed, backup)

        self.root.after(0, self._cleanup_finished)
        result_title = "模拟完成" if simulate else "清理完成"
        result_text = f"{result_title}！\n{'【模拟模式】' if simulate else ''}删除文件: {total_deleted} 个\n释放空间: {self.cleaner.format_size(total_freed)}"
        self.root.after(0, lambda rt=result_text: messagebox.showinfo(result_title, rt))

    def _cleanup_finished(self):
        self.cleanup_progress['value'] = 100
        self.cleanup_status_label.config(text="清理完成")
        self._refresh_cleanup_log_display()
        self._refresh_cleanup_history()

    def _empty_recycle_bin(self):
        if not messagebox.askyesno("确认", "确定要清空回收站吗？"):
            return
        if self.cleaner.empty_recycle_bin():
            self._append_cleanup_log("回收站已清空")
            messagebox.showinfo("完成", "回收站已清空！")
        else:
            messagebox.showerror("错误", "清空回收站失败")

    def _append_cleanup_log(self, text):
        self.cleanup_log_display.insert(tk.END, text + "\n")
        self.cleanup_log_display.see(tk.END)

    def _setup_tray(self):
        if not HAS_PYSTRAY:
            return
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_tray_image(self):
        Image, ImageDraw, _ = _load_tray_modules()
        if not Image or not ImageDraw:
            return None
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), color='#0078d4')
        dc = ImageDraw.Draw(image)
        
        dc.ellipse([8, 8, width-8, height-8], outline='white', width=4)
        dc.rectangle([20, 20, 44, 48], fill='white')
        dc.rectangle([28, 16, 36, 20], fill='white')
        
        return image

    def _toggle_tray(self):
        if self.tray_enabled.get():
            self._start_tray()
        else:
            self._stop_tray()

    def _start_tray(self):
        if not HAS_PYSTRAY or self.tray_icon:
            return
        Image, ImageDraw, pystray = _load_tray_modules()
        if not Image or not ImageDraw or not pystray:
            return

        def on_tray_show(icon, item):
            icon.stop()
            self.root.deiconify()

        def on_tray_quit(icon, item):
            icon.stop()
            self.root.quit()

        image = self._create_tray_image()
        if image is None:
            return
        menu = (
            pystray.MenuItem('显示主窗口', on_tray_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('退出程序', on_tray_quit)
        )
        self.tray_icon = pystray.Icon("CDriveCleanup", image, "C盘扫描和安全清理工具 v2.5", menu)
        
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self.tray_thread.start()

    def _stop_tray(self):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
            self.tray_thread = None

    def _on_close(self):
        if HAS_PYSTRAY and self.tray_enabled.get():
            self.root.withdraw()
            if not self.tray_icon:
                self._start_tray()
        else:
            self._stop_tray()
            self.root.destroy()

    def _install_context_menu(self):
        if not is_admin():
            messagebox.showwarning("警告", "需要管理员权限来安装右键菜单！\n请以管理员身份运行程序。")
            return
        
        try:
            import winreg
            
            if getattr(sys, 'frozen', False):
                command = f'"{sys.executable}" "%1"'
            else:
                script_path = os.path.abspath(__file__)
                python_exe = sys.executable
                command = f'"{python_exe}" "{script_path}" "%1"'
            
            key_path = r"Directory\\shell\\CDriveCleanup"
            command_path = r"Directory\\shell\\CDriveCleanup\\command"
            
            key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, key_path)
            winreg.SetValue(key, "", winreg.REG_SZ, "🔍 用C盘清理工具扫描")
            winreg.CloseKey(key)
            
            command_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, command_path)
            winreg.SetValue(command_key, "", winreg.REG_SZ, command)
            winreg.CloseKey(command_key)
            
            self.context_menu_status.config(text="状态: 已安装", foreground="green")
            messagebox.showinfo("成功", "右键菜单已安装！\n现在可以在文件夹上右键选择扫描。")
        except Exception as e:
            messagebox.showerror("错误", f"安装右键菜单失败: {e}")

    def _uninstall_context_menu(self):
        if not is_admin():
            messagebox.showwarning("警告", "需要管理员权限来卸载右键菜单！\n请以管理员身份运行程序。")
            return
        
        try:
            import winreg
            
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"Directory\\shell\\CDriveCleanup\\command")
            except:
                pass
            
            try:
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"Directory\\shell\\CDriveCleanup")
            except:
                pass
            
            self.context_menu_status.config(text="状态: 未安装", foreground="black")
            messagebox.showinfo("成功", "右键菜单已卸载！")
        except Exception as e:
            messagebox.showerror("错误", f"卸载右键菜单失败: {e}")

    def _check_context_menu_status(self):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Directory\\shell\\CDriveCleanup", 0, winreg.KEY_READ)
            winreg.CloseKey(key)
            self.context_menu_status.config(text="状态: 已安装", foreground="green")
        except:
            self.context_menu_status.config(text="状态: 未安装", foreground="black")

    def _build_executable(self):
        if not is_admin():
            messagebox.showwarning("警告", "需要管理员权限来打包！\n请以管理员身份运行程序。")
            return
        
        build_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build.py')
        if not os.path.exists(build_script):
            messagebox.showerror("错误", "找不到打包脚本 build.py！")
            return
        
        if not messagebox.askyesno("确认", "开始打包程序？\n这可能需要几分钟时间，请耐心等待...\n\n提示：\n- 确保有足够的磁盘空间（至少500MB）\n- 打包过程中请勿关闭程序"):
            return
        
        try:
            import subprocess
            import threading
            
            build_window = tk.Toplevel(self.root)
            build_window.title("📦 打包中...")
            build_window.geometry("700x500")
            build_window.transient(self.root)
            build_window.grab_set()
            
            build_text = scrolledtext.ScrolledText(build_window, wrap=tk.WORD)
            build_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            self._refresh_dynamic_theme()
            build_text.insert(tk.END, "开始打包...\n\n")
            
            state: dict[str, Any] = {
                'cancel_pressed': False,
                'window_alive': True,
                'process': None,
            }
            message_queue = Queue()
            
            def on_window_close():
                state['window_alive'] = False
            
            build_window.protocol("WM_DELETE_WINDOW", on_window_close)
            
            def append_text(text):
                """线程安全的文本添加方法"""
                message_queue.put(text)
            
            def process_queue():
                """处理消息队列并更新UI"""
                if not state['window_alive']:
                    return
                try:
                    while not message_queue.empty() and state['window_alive']:
                        text = message_queue.get_nowait()
                        build_text.insert(tk.END, text)
                        build_text.see(tk.END)
                except:
                    pass
                if state['window_alive']:
                    build_window.after(50, lambda: process_queue())
            
            process_queue()
            
            def cancel_build():
                if messagebox.askyesno("确认", "确定要取消打包吗？"):
                    state['cancel_pressed'] = True
                    try:
                        if state['process']:
                            state['process'].terminate()
                    except:
                        pass
            
            cancel_btn = ttk.Button(build_window, text="取消", command=cancel_build)
            cancel_btn.pack(pady=5)
            
            def run_build():
                try:
                    proc = subprocess.Popen(
                        [sys.executable, build_script],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )
                    state['process'] = proc
                    
                    while True:
                        if state['cancel_pressed'] or not state['window_alive']:
                            break
                        output = proc.stdout.readline()
                        if output == '' and proc.poll() is not None:
                            break
                        if output:
                            append_text(output)
                    
                    return proc.poll()
                except Exception as e:
                    if state['window_alive']:
                        append_text(f"\n错误: {e}\n")
                    return -1
            
            thread = threading.Thread(target=run_build)
            thread.daemon = True
            thread.start()
            
            def check_done():
                if not state['window_alive']:
                    return
                if not thread.is_alive():
                    if state['cancel_pressed']:
                        messagebox.showinfo("取消", "打包已取消！")
                    else:
                        return_code = state['process'].poll() if state['process'] else -1
                        if return_code == 0:
                            exe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist', 'CDriveCleanup.exe')
                            if os.path.exists(exe_path):
                                size = os.path.getsize(exe_path)
                                size_mb = size / (1024 * 1024)
                                messagebox.showinfo("成功", f"打包完成！\n\n可执行文件位置:\n{exe_path}\n\n文件大小: {size_mb:.2f} MB\n\n建议以管理员身份运行以获得完整功能。")
                            else:
                                messagebox.showinfo("成功", "打包完成！\n可执行文件位于 dist 文件夹中。")
                        else:
                            messagebox.showerror("错误", f"打包失败，返回码: {return_code}\n\n请检查上述错误信息。\n\n常见问题：\n1. 确保有足够的磁盘空间\n2. 尝试手动运行: python build.py\n3. 检查防火墙是否阻止了PyInstaller")
                    state['window_alive'] = False
                    build_window.destroy()
                else:
                    build_window.after(100, lambda: check_done())
            
            check_done()
            
        except Exception as e:
            messagebox.showerror("错误", f"打包过程出错: {e}")

    def _check_dependencies(self):
        """检查依赖状态"""
        deps = {
            'matplotlib': {'name': 'matplotlib', 'desc': '磁盘可视化', 'required': False},
            'pystray': {'name': 'pystray', 'desc': '系统托盘', 'required': False},
            'PIL': {'name': 'pillow', 'desc': '系统托盘(图像库)', 'required': False},
            'PyInstaller': {'name': 'pyinstaller', 'desc': '打包工具', 'required': False},
            'psutil': {'name': 'psutil', 'desc': '性能监控', 'required': False},
        }
        
        status_text = []
        all_ok = True
        
        for module, info in deps.items():
            try:
                if importlib.util.find_spec(module) is None:
                    raise ImportError(module)
                status_text.append(f"✅ {info['name']} - {info['desc']} (已安装)")
            except ImportError:
                status_text.append(f"❌ {info['name']} - {info['desc']} (未安装)")
                all_ok = False
        
        if all_ok:
            status_text.append("\n🎉 所有可选依赖已安装！")
        else:
            status_text.append("\n💡 点击「一键安装所有依赖」安装缺失的依赖")
        
        self.deps_status_label.config(text="\n".join(status_text))

    def _install_dependencies(self):
        """一键安装所有依赖"""
        if not messagebox.askyesno("确认", "即将安装以下依赖：\n- matplotlib (磁盘可视化)\n- pystray (系统托盘)\n- pillow (图像处理)\n- pyinstaller (打包工具)\n- psutil (性能监控)\n\n是否继续？"):
            return
        
        try:
            import subprocess
            import threading
            
            install_window = tk.Toplevel(self.root)
            install_window.title("🔧 正在安装依赖...")
            install_window.geometry("600x450")
            install_window.transient(self.root)
            install_window.grab_set()
            
            install_text = scrolledtext.ScrolledText(install_window, wrap=tk.WORD)
            install_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            self._refresh_dynamic_theme()
            install_text.insert(tk.END, "开始安装依赖...\n\n")
            
            packages = ['matplotlib', 'pystray', 'pillow', 'pyinstaller', 'psutil']
            success_count = 0
            message_queue = Queue()
            state: dict[str, Any] = {
                'window_alive': True,
                'success_count': 0,
            }
            
            def on_window_close():
                state['window_alive'] = False
            
            install_window.protocol("WM_DELETE_WINDOW", on_window_close)
            
            def append_text(text):
                """线程安全的文本添加方法"""
                message_queue.put(text)
            
            def process_queue():
                """处理消息队列并更新UI"""
                if not state['window_alive']:
                    return
                try:
                    while not message_queue.empty() and state['window_alive']:
                        text = message_queue.get_nowait()
                        install_text.insert(tk.END, text)
                        install_text.see(tk.END)
                except:
                    pass
                if state['window_alive']:
                    install_window.after(50, lambda: process_queue())
            
            process_queue()
            
            def install_packages():
                for package in packages:
                    if not state['window_alive']:
                        break
                    try:
                        append_text(f"正在安装 {package}...\n")
                        
                        result = subprocess.run(
                            [sys.executable, '-m', 'pip', 'install', package],
                            capture_output=True,
                            text=True
                        )
                        
                        if result.stdout:
                            append_text(result.stdout)
                        if result.stderr:
                            append_text(result.stderr)
                        
                        if result.returncode == 0:
                            append_text(f"✅ {package} 安装成功！\n\n")
                            state['success_count'] += 1
                        else:
                            append_text(f"❌ {package} 安装失败！\n\n")
                        
                    except Exception as e:
                            if state['window_alive']:
                                append_text(f"❌ 安装 {package} 时出错: {e}\n\n")
                
                if state['window_alive']:
                    append_text(f"\n安装完成！成功 {state['success_count']}/{len(packages)} 个\n")
            
            thread = threading.Thread(target=install_packages)
            thread.daemon = True
            thread.start()
            
            def check_done():
                if not state['window_alive']:
                    return
                if not thread.is_alive():
                    append_text("\n点击关闭窗口继续...")
                    
                    def on_close():
                        state['window_alive'] = False
                        install_window.destroy()
                        self._check_dependencies()
                    
                    close_btn = ttk.Button(install_window, text="关闭", command=on_close)
                    close_btn.pack(pady=10)
                else:
                    install_window.after(100, lambda: check_done())
            
            check_done()
            
        except Exception as e:
            messagebox.showerror("错误", f"安装依赖时出错: {e}")





def main():
    root = tk.Tk()
    root.title("C盘扫描和安全清理工具 v2.5")
    root.geometry("1200x900")
    root.lift()
    app = CDriveCleanupApp(root)
    
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if os.path.exists(path) and os.path.isdir(path):
            app.current_scan_path = path
            app.path_var.set(path)
            app._start_scan()
    
    root.mainloop()


if __name__ == "__main__":
    main()
