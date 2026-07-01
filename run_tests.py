#!/usr/bin/env python3
"""Run the project's automated tests."""

from __future__ import annotations

import pathlib
import os
import random
import shutil
import string
import tempfile
import sys
import unittest


def _make_token(length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def _safe_mkdtemp(suffix: str = "", prefix: str = "tmp", dir: str | None = None) -> str:
    """Create temporary directories without triggering restrictive ACL side effects.

    The default `tempfile.mkdtemp` implementation may create folders that some
    security modules reject at cleanup time on Windows. We create directories with
    explicit normal permissions and deterministic fallback retries.
    """
    base_dir = pathlib.Path(dir or tempfile.tempdir or tempfile.gettempdir())
    base_dir.mkdir(parents=True, exist_ok=True)

    suffix = "" if suffix is None else suffix
    prefix = "tmp" if prefix is None else prefix

    while True:
        token = _make_token()
        candidate = base_dir / f"{prefix}{token}{suffix}"
        try:
            candidate.mkdir()
            return str(candidate)
        except FileExistsError:
            continue


if __name__ == "__main__":
    root = pathlib.Path(__file__).resolve().parent
    original_tmp = (
        os.environ.get("TMP"),
        os.environ.get("TEMP"),
        tempfile.tempdir,
        tempfile.mkdtemp,
    )

    candidates = [
        root / "_run_test_workspace",
        pathlib.Path(os.environ.get("TEMP") or tempfile.gettempdir()),
        pathlib.Path(os.environ.get("TMP") or tempfile.gettempdir()),
        pathlib.Path(tempfile.gettempdir()),
    ]

    test_base = None
    for base in candidates:
        try:
            base_dir = base / "CDriveCleanup" / "test_tmp"
            base_dir.mkdir(parents=True, exist_ok=True)
            test_base = base_dir
            break
        except Exception:
            continue

    if not test_base:
        raise RuntimeError("无法创建测试临时目录，请检查 TEMP/TMP 权限。")

    # Create a controlled root temp dir without touching default tempfile internals.
    test_tmp = pathlib.Path(_safe_mkdtemp(prefix="run_tests_", dir=str(test_base)))
    if test_tmp.exists():
        shutil.rmtree(test_tmp, ignore_errors=True)
    test_tmp.mkdir(parents=True, exist_ok=True)

    # Force test runtime temp folders to controlled directory.
    tempfile.mkdtemp = _safe_mkdtemp
    os.environ["TMP"] = str(test_tmp)
    os.environ["TEMP"] = str(test_tmp)
    tempfile.tempdir = str(test_tmp)

    sys.path.insert(0, str(root))
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    try:
        result = runner.run(suite)
        raise SystemExit(0 if result.wasSuccessful() else 1)
    finally:
        if original_tmp[0] is None:
            os.environ.pop("TMP", None)
        else:
            os.environ["TMP"] = original_tmp[0]

        if original_tmp[1] is None:
            os.environ.pop("TEMP", None)
        else:
            os.environ["TEMP"] = original_tmp[1]

        tempfile.tempdir = original_tmp[2]
        tempfile.mkdtemp = original_tmp[3]
        try:
            shutil.rmtree(test_tmp, ignore_errors=True)
        except Exception:
            pass
