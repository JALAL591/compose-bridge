# -*- coding: utf-8 -*-
import unittest
import tempfile
import shutil
from pathlib import Path
import sys

server_dir = Path(__file__).resolve().parent.parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from core.project_scanner import ProjectScanner
from core.ast_finder import validate_kotlin_syntax, check_kotlin_syntax


class TestProjectHealthCheck(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.project_root = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_health_check_clean_project(self):
        kt_file = self.project_root / "Main.kt"
        kt_file.write_text("package test\n\nfun main() {\n    val greeting = \"Hello World\"\n}\n", encoding="utf-8")

        scanner = ProjectScanner(self.project_root)
        report = scanner.scan()
        res_dict = report.to_dict()

        self.assertEqual(len(report.broken_files), 0)
        self.assertEqual(res_dict.get("broken_count"), 0)
        self.assertEqual(res_dict.get("broken_files"), [])

    def test_health_check_detects_broken_file(self):
        clean_file = self.project_root / "Clean.kt"
        clean_file.write_text("package test\nval clean = 123\n", encoding="utf-8")

        broken_file = self.project_root / "Broken.kt"
        broken_file.write_text("package test\nfun broken() {\n    val missingVal = \n}\n", encoding="utf-8")

        scanner = ProjectScanner(self.project_root)
        report = scanner.scan()
        res_dict = report.to_dict()

        self.assertEqual(len(report.broken_files), 1)
        self.assertEqual(res_dict.get("broken_count"), 1)
        broken = report.broken_files[0]
        self.assertEqual(broken["file"], "Broken.kt")
        self.assertEqual(broken["line"], 3)
        self.assertTrue(len(broken["error"]) > 0)

        # Also test direct check_health()
        health_res = scanner.check_health()
        self.assertEqual(len(health_res), 1)
        self.assertEqual(health_res[0]["file"], "Broken.kt")
        self.assertEqual(health_res[0]["line"], 3)


if __name__ == "__main__":
    unittest.main()
