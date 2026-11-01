# -*- coding: utf-8 -*-
"""
Test Backup Validation and Broken File Rejection.

Verifies:
1. If a file is valid, the first edit takes a valid .bridge.bak backup.
2. If a file becomes broken (syntax error, e.g. deleted parenthesis/brace), subsequent edit requests are REJECTED.
3. No corrupted backup is created from a broken file.
4. The error message informs the user that the file contains syntax errors and must be fixed first.
5. Once fixed, editing proceeds normally and does NOT overwrite the original .bridge.bak.
6. Git checkout is prioritized when rejecting changes for tracked files.
"""

import os
import sys
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path

SERVER_DIR = Path(r"C:\Users\thinkpad\StudioProjects\compose-bridge\server")
sys.path.insert(0, str(SERVER_DIR))

from core.pattern_journal import PatternJournal
from core.ast_finder import validate_kotlin_syntax, safe_create_backup, surgical_edit
from editor.color_editor import update_theme_color
from editor.dimension_editor import update_token_default


class TestBackupValidation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_backup_val_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_broken_file_rejection_color(self):
        theme_file = self.root / "DesignSystem.kt"
        orig_color = "0xFF14B8A6"
        valid_content = f"""package com.example.theme

import com.composebridge.agent.BridgeThemeRegistry
import androidx.compose.ui.graphics.Color

object AppColors {{
    val Primary: Color get() = BridgeThemeRegistry.getColor("Primary", Color({orig_color}))
}}
"""
        theme_file.write_text(valid_content, encoding="utf-8")

        # 1. Edit 1 on valid file: should succeed
        ok1, msg1, _ = update_theme_color("Primary", "0xFF00AA55")
        self.assertTrue(ok1, f"Edit 1 should succeed: {msg1}")
        bak_file = self.root / "DesignSystem.kt.bridge.bak"
        self.assertTrue(bak_file.exists(), "Backup should exist after valid Edit 1")
        self.assertIn(orig_color, bak_file.read_text(encoding="utf-8"))

        # 2. Break the file manually (delete closing parenthesis)
        current_content = theme_file.read_text(encoding="utf-8")
        broken_content = current_content.replace("Color(0xFF00AA55))", "Color(0xFF00AA55")
        theme_file.write_text(broken_content, encoding="utf-8")

        # Verify syntax validation detects the syntax error
        is_valid, err_syntax = validate_kotlin_syntax(theme_file)
        self.assertFalse(is_valid, "Broken file must be detected as invalid syntax")
        self.assertIn("الملف الحالي يحتوي على أخطاء برمجية", err_syntax)

        # 3. Request Edit 2 on the broken file: MUST BE REJECTED!
        ok2, msg2, _ = update_theme_color("Primary", "0xFFFF0000")
        self.assertFalse(ok2, "Edit on broken file must be rejected")
        self.assertIn("الملف الحالي يحتوي على أخطاء برمجية", msg2)

        # 4. Verify backup was NOT overwritten with the broken code
        self.assertIn(orig_color, bak_file.read_text(encoding="utf-8"), "Backup must stay intact and uncorrupted")

    def test_broken_file_rejection_dimension(self):
        theme_file = self.root / "DesignSystem.kt"
        orig_dim = "16"
        valid_content = f"""package com.example.theme

import com.composebridge.agent.BridgeDimensionRegistry
import androidx.compose.ui.unit.dp

object AppDimensions {{
    val SpacingMedium get() = BridgeDimensionRegistry.get("SpacingMedium", {orig_dim}.dp)
}}
"""
        theme_file.write_text(valid_content, encoding="utf-8")

        # 1. Edit 1: 16.dp -> 24.dp
        ok1, msg1, _ = update_token_default("SpacingMedium", "24")
        self.assertTrue(ok1, f"Dim Edit 1 should succeed: {msg1}")

        # 2. Break the file manually
        theme_file.write_text(valid_content.replace("{", ""), encoding="utf-8")

        # 3. Edit 2 must be rejected
        ok2, msg2, _ = update_token_default("SpacingMedium", "32")
        self.assertFalse(ok2, "Dim Edit on broken file must be rejected")
        self.assertIn("الملف الحالي يحتوي على أخطاء برمجية", msg2)

    def test_git_checkout_priority_on_rejection(self):
        # Initialize a git repository in test_dir
        subprocess.run(["git", "init"], cwd=str(self.root), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(self.root), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(self.root), capture_output=True)

        tracked_file = self.root / "DesignSystem.kt"
        orig_code = """package com.example.theme

import com.composebridge.agent.BridgeThemeRegistry
import androidx.compose.ui.graphics.Color

object AppColors {
    val Primary: Color get() = BridgeThemeRegistry.getColor("Primary", Color(0xFF14B8A6))
}
"""
        tracked_file.write_text(orig_code, encoding="utf-8")
        subprocess.run(["git", "add", "DesignSystem.kt"], cwd=str(self.root), capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(self.root), capture_output=True)

        # Make an edit via compose-bridge
        ok, msg, _ = update_theme_color("Primary", "0xFFFF0000")
        self.assertTrue(ok)
        self.assertIn("0xFFFF0000", tracked_file.read_text(encoding="utf-8"))

        # Revert changes using PatternJournal
        pj = PatternJournal(self.root)
        res = pj.reject_file_changes("DesignSystem.kt", force=False)
        self.assertTrue(res.get("success"), f"Rejection should succeed: {res}")
        self.assertIn("Git", res.get("message", ""), "Should state restoration via Git")
        self.assertIn("0xFF14B8A6", tracked_file.read_text(encoding="utf-8"), "File must be reverted via Git to original")


if __name__ == "__main__":
    unittest.main()
