import tempfile
import unittest
from pathlib import Path

from cleaner import DiskCleaner
from main import get_file_hash, load_app_settings, save_app_settings
from scanner import DiskScanner


class TestCoreBehaviors(unittest.TestCase):
    def test_file_hash_changes_when_content_changes(self):
        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "sample.txt"
            file_path.write_text("hello", encoding="utf-8")
            first = get_file_hash(str(file_path))
            file_path.write_text("hello world", encoding="utf-8")
            second = get_file_hash(str(file_path))

            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            self.assertNotEqual(first, second)

    def test_scanner_counts_files_and_sizes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.txt").write_text("abc", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "b.log").write_text("12345", encoding="utf-8")

            scanner = DiskScanner()
            result = scanner.scan_drive(str(root))

            self.assertEqual(result["scan_path"], str(root))
            self.assertEqual(result["file_count"], 2)
            self.assertEqual(result["total_size"], 8)
            self.assertEqual(result["file_types"][".txt"], 3)
            self.assertEqual(result["file_types"][".log"], 5)

    def test_duplicate_detection_finds_duplicate_pairs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            content = "duplicate content"
            (root / "one.txt").write_text(content, encoding="utf-8")
            (root / "two.txt").write_text(content, encoding="utf-8")
            (root / "three.txt").write_text("unique", encoding="utf-8")

            scanner = DiskScanner()
            result = scanner.find_duplicate_files(str(root), min_size=1)

            self.assertGreaterEqual(len(result["duplicates"]), 1)
            self.assertGreater(result["total_wasted"], 0)

    def test_cleaner_whitelist_excludes_paths_from_size_calculation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            keep = root / "keep.tmp"
            clean = root / "clean.tmp"
            keep.write_text("keep", encoding="utf-8")
            clean.write_text("clean", encoding="utf-8")

            cleaner = DiskCleaner()
            cleaner.cleanup_paths = {
                "temp": [str(root)],
                "recycle_bin": [],
                "windows_update_cache": [],
                "browser_cache": [],
                "prefetch": [],
                "thumbnails": [],
                "log_files": [],
            }
            cleaner.whitelist = [str(keep)]

            expected = clean.stat().st_size
            self.assertEqual(cleaner.calculate_cleanup_size("temp"), expected)
            self.assertTrue(cleaner.is_in_whitelist(str(keep)))
            self.assertFalse(cleaner.is_in_whitelist(str(clean)))

    def test_smart_cleanup_suggestions_have_expected_shape(self):
        cleaner = DiskCleaner()
        suggestions = cleaner.get_smart_cleanup_suggestions()

        self.assertIn("suggestions", suggestions)
        self.assertIn("total_recoverable_formatted", suggestions)
        self.assertIsInstance(suggestions["suggestions"], list)
        self.assertGreaterEqual(len(suggestions["suggestions"]), 1)

    def test_app_settings_round_trip_theme_flag(self):
        with tempfile.TemporaryDirectory() as td:
            settings_file = Path(td) / "app_settings.json"

            save_app_settings(str(settings_file), {"dark_mode": True})
            loaded = load_app_settings(str(settings_file))

            self.assertEqual(loaded.get("dark_mode"), True)

            save_app_settings(str(settings_file), {"dark_mode": False})
            loaded_again = load_app_settings(str(settings_file))

            self.assertEqual(loaded_again.get("dark_mode"), False)


if __name__ == "__main__":
    unittest.main(verbosity=2)

