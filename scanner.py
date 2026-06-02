import os
import time
import hashlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed


class DiskScanner:
    FILE_CATEGORIES = {
        'documents': {
            'name': '文档',
            'extensions': ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                          '.pdf', '.txt', '.rtf', '.md', '.xml', '.json',
                          '.csv', '.log', '.ini', '.cfg'],
            'icon': '📄'
        },
        'images': {
            'name': '图片',
            'extensions': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
                          '.svg', '.webp', '.ico', '.raw', '.heic'],
            'icon': '🖼️'
        },
        'videos': {
            'name': '视频',
            'extensions': ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
                          '.webm', '.m4v', '.3gp', '.mpeg'],
            'icon': '🎬'
        },
        'audio': {
            'name': '音频',
            'extensions': ['.mp3', '.wav', '.flac', '.ogg', '.m4a', '.wma',
                          '.aac', '.ape', '.mid'],
            'icon': '🎵'
        },
        'archives': {
            'name': '压缩包',
            'extensions': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
                          '.xz', '.iso', '.cab'],
            'icon': '📦'
        },
        'executables': {
            'name': '可执行文件',
            'extensions': ['.exe', '.dll', '.msi', '.bat', '.cmd', '.ps1',
                          '.com', '.scr'],
            'icon': '⚙️'
        },
        'programming': {
            'name': '源代码',
            'extensions': ['.py', '.java', '.cpp', '.c', '.h', '.cs', '.js',
                          '.ts', '.html', '.css', '.php', '.go', '.rs'],
            'icon': '💻'
        },
        'others': {
            'name': '其他',
            'extensions': [],
            'icon': '📁'
        }
    }

    def __init__(self, drive='C:\\'):
        self.drive = drive
        self.scan_results = {
            'total_size': 0,
            'file_count': 0,
            'folder_count': 0,
            'large_files': [],
            'file_types': defaultdict(int),
            'folder_sizes': {},
            'category_sizes': defaultdict(int),
            'category_counts': defaultdict(int)
        }

    def format_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return "{:.2f} {}".format(size_bytes, unit)
            size_bytes /= 1024.0
        return "{:.2f} PB".format(size_bytes)

    def get_file_category(self, filename):
        """获取文件所属分类"""
        ext = os.path.splitext(filename)[1].lower()
        
        for category, info in self.FILE_CATEGORIES.items():
            if ext in info['extensions']:
                return category
        
        return 'others'

    def get_category_info(self, category):
        """获取分类信息"""
        return self.FILE_CATEGORIES.get(category, {'name': '未知', 'icon': '📁'})

    def get_folder_size(self, folder_path):
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (PermissionError, FileNotFoundError):
                        continue
        except PermissionError:
            pass
        return total_size

    def scan_drive(self, path=None, progress_callback=None, min_large_file_size=100*1024*1024,
                   start_file_count=0, start_total_size=0, start_large_files=None, start_file_types=None):
        scan_path = path if path else self.drive
        
        self.scan_results = {
            'scan_path': scan_path,
            'total_size': start_total_size,
            'file_count': start_file_count,
            'folder_count': 0,
            'large_files': start_large_files if start_large_files is not None else [],
            'file_types': defaultdict(int),
            'folder_sizes': {},
            'category_sizes': defaultdict(int),
            'category_counts': defaultdict(int)
        }
        
        if start_file_types:
            for ext, size in start_file_types.items():
                self.scan_results['file_types'][ext] = size

        start_time = time.time()

        try:
            for dirpath, dirnames, filenames in os.walk(scan_path):
                try:
                    self.scan_results['folder_count'] += len(dirnames)
                    
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        try:
                            file_size = os.path.getsize(filepath)
                            self.scan_results['total_size'] += file_size
                            self.scan_results['file_count'] += 1

                            file_ext = os.path.splitext(filename)[1].lower() or 'no_extension'
                            self.scan_results['file_types'][file_ext] += file_size

                            category = self.get_file_category(filename)
                            self.scan_results['category_sizes'][category] += file_size
                            self.scan_results['category_counts'][category] += 1

                            if file_size >= min_large_file_size:
                                self.scan_results['large_files'].append({
                                    'path': filepath,
                                    'size': file_size,
                                    'formatted_size': self.format_size(file_size)
                                })

                        except (PermissionError, FileNotFoundError, OSError):
                            continue

                    if progress_callback:
                        callback_result = self.scan_results.copy()
                        callback_result['current_dir'] = dirpath
                        should_continue = progress_callback(callback_result)
                        if should_continue is False:
                            break

                except PermissionError:
                    continue

        except Exception as e:
            print("扫描时出错: {}".format(e))

        self.scan_results['large_files'].sort(key=lambda x: x['size'], reverse=True)
        self.scan_results['scan_time'] = time.time() - start_time

        return self.scan_results
    
    def scan_with_callback(self, path=None, callback=None):
        scan_path = path if path else self.drive
        
        try:
            for dirpath, dirnames, filenames in os.walk(scan_path):
                try:
                    if callback:
                        should_continue = callback(dirpath, True)
                        if should_continue is False:
                            return
                    
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        try:
                            if callback:
                                should_continue = callback(filepath, False)
                                if should_continue is False:
                                    return
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
                            
                except PermissionError:
                    continue
                    
        except Exception as e:
            print("扫描时出错: {}".format(e))

    def get_disk_space_info(self, path=None):
        check_path = path if path else self.drive
        try:
            if os.name == 'nt':
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                total_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(check_path),
                    None,
                    ctypes.pointer(total_bytes),
                    ctypes.pointer(free_bytes)
                )
                return {
                    'path': check_path,
                    'total': total_bytes.value,
                    'used': total_bytes.value - free_bytes.value,
                    'free': free_bytes.value,
                    'total_formatted': self.format_size(total_bytes.value),
                    'used_formatted': self.format_size(total_bytes.value - free_bytes.value),
                    'free_formatted': self.format_size(free_bytes.value)
                }
        except Exception:
            pass
        return None
    
    def _get_file_hash(self, filepath):
        try:
            hash_obj = hashlib.md5()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except:
            return None
    
    def find_duplicate_files(self, path=None, progress_callback=None, min_size=1024):
        scan_path = path if path else self.drive
        files_by_size = defaultdict(list)
        duplicates = []
        
        start_time = time.time()
        
        try:
            for dirpath, dirnames, filenames in os.walk(scan_path):
                try:
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        try:
                            file_size = os.path.getsize(filepath)
                            if file_size >= min_size:
                                files_by_size[file_size].append(filepath)
                            
                            if progress_callback and len(files_by_size) % 100 == 0:
                                should_continue = progress_callback({
                                    'processed': len(files_by_size),
                                    'current_file': filepath
                                })
                                if should_continue is False:
                                    break
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
                except PermissionError:
                    continue
        
            potential_duplicates = [f for size, files in files_by_size.items() if len(files) > 1 for f in files]
            processed_count = [0]

            def _hash_file(filepath):
                file_hash = self._get_file_hash(filepath)
                processed_count[0] += 1
                if progress_callback and processed_count[0] % 10 == 0:
                    progress_callback({
                        'processed': processed_count[0],
                        'total': len(potential_duplicates),
                        'current_file': filepath
                    })
                return filepath, file_hash

            files_by_hash = defaultdict(list)
            max_workers = min(8, os.cpu_count() or 4)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_hash_file, fp): fp for fp in potential_duplicates}
                for future in as_completed(futures):
                    try:
                        filepath, file_hash = future.result()
                        if file_hash:
                            files_by_hash[file_hash].append(filepath)
                    except Exception:
                        continue

            for hash_val, dup_files in files_by_hash.items():
                if len(dup_files) > 1:
                    duplicates.append({
                        'hash': hash_val,
                        'size': os.path.getsize(dup_files[0]) if os.path.exists(dup_files[0]) else 0,
                        'size_formatted': self.format_size(os.path.getsize(dup_files[0]) if os.path.exists(dup_files[0]) else 0),
                        'files': dup_files
                    })
        
        except Exception as e:
            print("查找重复文件出错: {}".format(e))
        
        scan_time = time.time() - start_time
        
        duplicates.sort(key=lambda x: x['size'] * len(x['files']), reverse=True)
        
        total_wasted = sum(dup['size'] * (len(dup['files']) - 1) for dup in duplicates)
        
        return {
            'duplicates': duplicates,
            'total_wasted': total_wasted,
            'total_wasted_formatted': self.format_size(total_wasted),
            'scan_time': scan_time
        }
    
    def get_folder_size_distribution(self, path=None, progress_callback=None):
        scan_path = path if path else self.drive
        folder_sizes = {}
        
        try:
            for dirpath, dirnames, filenames in os.walk(scan_path):
                try:
                    dir_size = 0
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        try:
                            dir_size += os.path.getsize(filepath)
                        except:
                            pass
                    
                    parent_dir = os.path.dirname(dirpath)
                    if parent_dir not in folder_sizes:
                        folder_sizes[parent_dir] = 0
                    folder_sizes[parent_dir] += dir_size
                    
                    if dirpath not in folder_sizes:
                        folder_sizes[dirpath] = 0
                    folder_sizes[dirpath] += dir_size
                    
                    if progress_callback and len(folder_sizes) % 100 == 0:
                        should_continue = progress_callback({'processed': len(folder_sizes)})
                        if should_continue is False:
                            break
                except PermissionError:
                    continue
        except Exception as e:
            print(f"获取文件夹分布出错: {e}")
        
        sorted_folders = sorted(folder_sizes.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'folders': sorted_folders,
            'total_folders': len(sorted_folders)
        }
