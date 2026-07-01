import os
import tempfile
import shutil
import datetime
from collections import defaultdict


class DiskCleaner:
    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.cleanup_paths = self._get_cleanup_paths()
        self.whitelist = self._load_whitelist()

    def _get_cleanup_paths(self):
        paths = {
            'temp': [],
            'recycle_bin': [],
            'windows_update_cache': [],
            'browser_cache': [],
            'prefetch': [],
            'thumbnails': [],
            'log_files': []
        }

        temp_dir = tempfile.gettempdir()
        paths['temp'].append(temp_dir)

        user_profile = os.environ.get('USERPROFILE', '')
        windir = os.environ.get('WINDIR', '')
        local_app_data = os.path.join(user_profile, 'AppData', 'Local') if user_profile else ''
        app_data = os.path.join(user_profile, 'AppData', 'Roaming') if user_profile else ''

        if user_profile:
            paths['temp'].append(os.path.join(user_profile, 'AppData', 'Local', 'Temp'))

        if windir:
            paths['temp'].append(os.path.join(windir, 'Temp'))
            paths['windows_update_cache'].append(os.path.join(windir, 'SoftwareDistribution', 'Download'))
            paths['prefetch'].append(os.path.join(windir, 'Prefetch'))
            paths['log_files'].append(os.path.join(windir, 'Logs'))

        if local_app_data:
            # Chrome
            chrome_path = os.path.join(local_app_data, 'Google', 'Chrome', 'User Data', 'Default', 'Cache')
            if os.path.exists(chrome_path):
                paths['browser_cache'].append(chrome_path)
            
            # Edge
            edge_path = os.path.join(local_app_data, 'Microsoft', 'Edge', 'User Data', 'Default', 'Cache')
            if os.path.exists(edge_path):
                paths['browser_cache'].append(edge_path)
            
            # Firefox
            firefox_profiles_path = os.path.join(app_data, 'Mozilla', 'Firefox', 'Profiles')
            if os.path.exists(firefox_profiles_path):
                for profile in os.listdir(firefox_profiles_path):
                    profile_cache = os.path.join(firefox_profiles_path, profile, 'cache2')
                    if os.path.exists(profile_cache):
                        paths['browser_cache'].append(profile_cache)
            
            paths['thumbnails'].append(os.path.join(local_app_data, 'Microsoft', 'Windows', 'Explorer'))

        return paths

    def _load_whitelist(self):
        whitelist = []
        whitelist_file = os.path.join(self.base_dir, 'whitelist.txt')
        if os.path.exists(whitelist_file):
            try:
                with open(whitelist_file, 'r', encoding='utf-8') as f:
                    whitelist = [line.strip() for line in f if line.strip()]
            except:
                pass
        return whitelist

    def _save_whitelist(self):
        whitelist_file = os.path.join(self.base_dir, 'whitelist.txt')
        try:
            with open(whitelist_file, 'w', encoding='utf-8') as f:
                for path in self.whitelist:
                    f.write(path + '\n')
        except:
            pass

    def add_to_whitelist(self, path):
        path = os.path.abspath(path)
        if path not in self.whitelist:
            self.whitelist.append(path)
            self._save_whitelist()
            return True
        return False

    def remove_from_whitelist(self, path):
        path = os.path.abspath(path)
        if path in self.whitelist:
            self.whitelist.remove(path)
            self._save_whitelist()
            return True
        return False

    def is_in_whitelist(self, path):
        path = os.path.abspath(path)
        for whitelisted in self.whitelist:
            whitelisted = os.path.abspath(whitelisted)
            if path == whitelisted or path.startswith(whitelisted + os.sep):
                return True
        return False

    def _backup_file(self, filepath, backup_dir=None):
        if not backup_dir:
            backup_dir = os.path.join(self.base_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.basename(filepath)
        backup_path = os.path.join(backup_dir, f"{timestamp}_{filename}")
        
        try:
            shutil.copy2(filepath, backup_path)
            return backup_path
        except:
            return None

    def backup_file(self, filepath, backup_dir=None):
        return self._backup_file(filepath, backup_dir)

    def format_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return "{:.2f} {}".format(size_bytes, unit)
            size_bytes /= 1024.0
        return "{:.2f} PB".format(size_bytes)

    def get_backup_files(self):
        """获取所有备份文件列表"""
        backup_dir = os.path.join(self.base_dir, 'backups')
        backup_files = []
        
        if not os.path.exists(backup_dir):
            return backup_files
        
        for filename in os.listdir(backup_dir):
            filepath = os.path.join(backup_dir, filename)
            if os.path.isfile(filepath):
                try:
                    size = os.path.getsize(filepath)
                    mtime = os.path.getmtime(filepath)
                    mtime_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    
                    if '_' in filename:
                        original_name = '_'.join(filename.split('_')[1:])
                        timestamp_str = filename.split('_')[0]
                    else:
                        original_name = filename
                        timestamp_str = ''
                    
                    backup_files.append({
                        'filepath': filepath,
                        'filename': filename,
                        'original_name': original_name,
                        'timestamp': timestamp_str,
                        'mtime': mtime,
                        'mtime_str': mtime_str,
                        'size': size,
                        'size_formatted': self.format_size(size)
                    })
                except:
                    continue
        
        return sorted(backup_files, key=lambda x: x['mtime'], reverse=True)

    def restore_backup_file(self, backup_filepath, restore_to_original=False):
        """恢复备份文件"""
        if not os.path.exists(backup_filepath):
            return False, "备份文件不存在"
        
        try:
            filename = os.path.basename(backup_filepath)
            
            if '_' in filename:
                original_name = '_'.join(filename.split('_')[1:])
            else:
                original_name = filename
            
            if restore_to_original:
                restore_path = original_name
            else:
                restore_path = os.path.join(os.path.dirname(backup_filepath), 'restored', original_name)
                os.makedirs(os.path.dirname(restore_path), exist_ok=True)
            
            shutil.copy2(backup_filepath, restore_path)
            return True, f"文件已恢复到: {restore_path}"
        except Exception as e:
            return False, str(e)

    def delete_backup_file(self, backup_filepath):
        """删除备份文件"""
        if os.path.exists(backup_filepath):
            try:
                os.remove(backup_filepath)
                return True, "删除成功"
            except Exception as e:
                return False, str(e)
        return False, "文件不存在"

    def calculate_cleanup_size(self, category=None):
        total_size = 0
        paths_to_check = []

        if category:
            paths_to_check = self.cleanup_paths.get(category, [])
        else:
            cat_paths = []
            for paths in self.cleanup_paths.values():
                cat_paths.extend(paths)
            paths_to_check = cat_paths

        for path in paths_to_check:
            if os.path.exists(path):
                try:
                    if os.path.isfile(path):
                        if not self.is_in_whitelist(path):
                            total_size += os.path.getsize(path)
                    elif os.path.isdir(path):
                        for dirpath, dirnames, filenames in os.walk(path):
                            for filename in filenames:
                                try:
                                    filepath = os.path.join(dirpath, filename)
                                    if not self.is_in_whitelist(filepath):
                                        total_size += os.path.getsize(filepath)
                                except (PermissionError, FileNotFoundError):
                                    continue
                except (PermissionError, FileNotFoundError):
                    continue

        return total_size

    def cleanup(self, category=None, backup=False, simulate=False):
        deleted_count = 0
        freed_size = 0
        paths_to_clean = []
        backup_dir = None

        if backup and not simulate:
            backup_dir = os.path.join(self.base_dir, 'backups')
            os.makedirs(backup_dir, exist_ok=True)

        if category:
            paths_to_clean = self.cleanup_paths.get(category, [])
        else:
            for paths in self.cleanup_paths.values():
                paths_to_clean.extend(paths)

        for path in paths_to_clean:
            if os.path.exists(path):
                try:
                    if os.path.isfile(path):
                        if not self.is_in_whitelist(path):
                            file_size = os.path.getsize(path)
                            if backup and not simulate:
                                self._backup_file(path, backup_dir)
                            if not simulate:
                                os.remove(path)
                            deleted_count += 1
                            freed_size += file_size
                    elif os.path.isdir(path):
                        for dirpath, dirnames, filenames in os.walk(path):
                            for filename in filenames:
                                filepath = os.path.join(dirpath, filename)
                                try:
                                    if not self.is_in_whitelist(filepath):
                                        file_size = os.path.getsize(filepath)
                                        if backup and not simulate:
                                            self._backup_file(filepath, backup_dir)
                                        if not simulate:
                                            os.remove(filepath)
                                        deleted_count += 1
                                        freed_size += file_size
                                except (PermissionError, FileNotFoundError, OSError):
                                    continue
                except (PermissionError, FileNotFoundError, OSError):
                    continue

        return {
            'deleted_count': deleted_count,
            'freed_size': freed_size,
            'freed_size_formatted': self.format_size(freed_size)
        }

    def empty_recycle_bin(self):
        try:
            if os.name == 'nt':
                import ctypes
                ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0)
                return True
        except Exception:
            pass
        return False
    
    def get_smart_cleanup_suggestions(self):
        suggestions = []
        total_recoverable = 0
        
        suggestions.append({
            'category': '临时文件',
            'description': '系统和应用程序的临时文件',
            'paths': self.cleanup_paths.get('temp', []),
            'priority': 'high',
            'safe': True
        })
        
        suggestions.append({
            'category': '浏览器缓存',
            'description': 'Chrome、Edge、Firefox等浏览器的缓存文件',
            'paths': self.cleanup_paths.get('browser_cache', []),
            'priority': 'medium',
            'safe': True
        })
        
        suggestions.append({
            'category': 'Windows更新缓存',
            'description': 'Windows系统更新下载的临时文件',
            'paths': self.cleanup_paths.get('windows_update_cache', []),
            'priority': 'medium',
            'safe': True
        })
        
        suggestions.append({
            'category': '预读取文件',
            'description': 'Windows Prefetch预读取文件（谨慎清理）',
            'paths': self.cleanup_paths.get('prefetch', []),
            'priority': 'low',
            'safe': False
        })
        
        suggestions.append({
            'category': '缩略图缓存',
            'description': 'Windows缩略图缓存文件',
            'paths': self.cleanup_paths.get('thumbnails', []),
            'priority': 'low',
            'safe': True
        })
        
        suggestions.append({
            'category': '系统日志',
            'description': 'Windows系统日志文件',
            'paths': self.cleanup_paths.get('log_files', []),
            'priority': 'low',
            'safe': True
        })
        
        for suggestion in suggestions:
            size = 0
            for path in suggestion['paths']:
                if os.path.exists(path):
                    try:
                        if os.path.isfile(path):
                            if not self.is_in_whitelist(path):
                                size += os.path.getsize(path)
                        elif os.path.isdir(path):
                            for dirpath, dirnames, filenames in os.walk(path):
                                for filename in filenames:
                                    filepath = os.path.join(dirpath, filename)
                                    if not self.is_in_whitelist(filepath):
                                        try:
                                            size += os.path.getsize(filepath)
                                        except:
                                            pass
                    except:
                        pass
            suggestion['recoverable_size'] = size
            suggestion['recoverable_size_formatted'] = self.format_size(size)
            total_recoverable += size
        
        suggestions.sort(key=lambda x: x['recoverable_size'], reverse=True)
        
        return {
            'suggestions': suggestions,
            'total_recoverable': total_recoverable,
            'total_recoverable_formatted': self.format_size(total_recoverable)
        }
