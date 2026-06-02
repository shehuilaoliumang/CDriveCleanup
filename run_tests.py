#!/usr/bin/env python3
"""Run the project's automated tests."""

import pathlib
import sys
import unittest


if __name__ == "__main__":
    root = pathlib.Path(__file__).resolve().parent
    sys.path.insert(0, str(root))
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)

