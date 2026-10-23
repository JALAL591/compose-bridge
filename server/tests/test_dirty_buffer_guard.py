# -*- coding: utf-8 -*-
"""
Tests for Dirty Buffer Guard, Checksum Mismatch Detection, and Reject Confirmation.
"""

import os
import sys
import json
import shutil
import hashlib
import tempfile
import unittest
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(r"C:\Users\thinkpad\StudioProjects\compose-bridge\server")
sys.path.insert(0, str(PROJECT_ROOT))

from common.file_ops import (
    is_file_dirty_in_ide,
    mark_file_dirty_in_ide,
    DIRTY_BUFFER_WARNING_AR,
    EXTERNAL_MODIFICATION_WARNING_TEMPLATE_AR,
)
from core.pattern_journal import PatternJournal
from editor.text_editor import update_text_in_source
from editor.color_editor import update_theme_color


class TestDirtyBufferGuard(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_dirty_guard_test_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dirty_buffer_detection(self):
        test_file = self.root / "TestScreen.kt"
        test_file.write_text('val title = "Hello World"\n', encoding="utf-8")

        # Initially not dirty
        self.assertFalse(is_file_dirty_in_ide(test_file, self.root))

        # Mark dirty
        mark_file_dirty_in_ide(test_file, is_dirty=True, project_root=self.root)
        self.assertTrue(is_file_dirty_in_ide(test_file, self.root))

        # Check relative path resolution
        self.assertTrue(is_file_dirty_in_ide("TestScreen.kt", self.root))

        # Unmark dirty
        mark_file_dirty_in_ide(test_file, is_dirty=False, project_root=self.root)
        self.assertFalse(is_file_dirty_in_ide(test_file, self.root))

    def test_text_editor_rejects_dirty_buffer(self):
        test_file = self.root / "TestScreen.kt"
        test_file.write_text('val title = "Old Text"\n', encoding="utf-8")

        # Mark file as dirty in IDE
        mark_file_dirty_in_ide(test_file, is_dirty=True, project_root=self.root)

        # Attempt edit
        ok, msg, info = update_text_in_source(
            file_path=str(test_file),
            line=1,
            old_text="Old Text",
            new_text="New Text",
            project_root=self.root,
        )

        self.assertFalse(ok)
        self.assertIn("الملف", msg)
        self.assertIn("مفتوح في IDE وفيه تعديلات غير محفوظة", msg)
        self.assertEqual(info.get("error_code"), "DIRTY_BUFFER_DETECTED")

        # Unmark and ensure edit succeeds
        mark_file_dirty_in_ide(test_file, is_dirty=False, project_root=self.root)
        ok2, msg2, info2 = update_text_in_source(
            file_path=str(test_file),
            line=1,
            old_text="Old Text",
            new_text="New Text",
            project_root=self.root,
        )
        self.assertTrue(ok2)

    def test_text_editor_checksum_mismatch(self):
        test_file = self.root / "TestScreen.kt"
        test_file.write_text('val title = "Original Text"\n', encoding="utf-8")

        wrong_checksum = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

        ok, msg, info = update_text_in_source(
            file_path=str(test_file),
            line=1,
            old_text="Original Text",
            new_text="New Text",
            project_root=self.root,
            expected_checksum=wrong_checksum,
        )

        self.assertFalse(ok)
        self.assertIn("تحذير", msg)
        self.assertIn("تم تعديله خارج الأداة", msg)
        self.assertEqual(info.get("error_code"), "EXTERNAL_MODIFICATION_DETECTED")
        self.assertEqual(info.get("suggested_action"), "confirm_restore")

    def test_pattern_journal_reject_with_external_modification_guard(self):
        test_file = self.root / "Dashboard.kt"
        original_code = 'val primaryColor = Color(0xFF112233)\nval title = "Dashboard"\n'
        test_file.write_text(original_code, encoding="utf-8")

        # 1. Create backup
        backup_file = self.root / "Dashboard.kt.bridge.bak"
        backup_file.write_text(original_code, encoding="utf-8")

        # 2. Record change in journal
        pj = PatternJournal(self.root)
        pj.record_change(
            file="Dashboard.kt",
            line=1,
            old_line="val primaryColor = Color(0xFF112233)",
            new_line="val primaryColor = Color(0xFF000000)",
            pattern_id="test_pat_1",
        )

        # 3. Simulate tool edit on disk
        tool_edited_code = 'val primaryColor = Color(0xFF000000)\nval title = "Dashboard"\n'
        test_file.write_text(tool_edited_code, encoding="utf-8")

        # 4. Now simulate external modification (user modified code externally)
        externally_modified_code = 'val primaryColor = Color(0xFF999999)\nval title = "Dashboard Edited by Human"\n'
        test_file.write_text(externally_modified_code, encoding="utf-8")

        # 5. Attempt reject without force -> should be rejected with warning
        res = pj.reject_file_changes("Dashboard.kt", force=False)
        self.assertFalse(res["success"])
        self.assertEqual(res["error_code"], "EXTERNAL_MODIFICATION_DETECTED")
        self.assertTrue(res["can_force"])
        self.assertIn("تحذير", res["message"])
        self.assertIn("تم تعديله خارج الأداة", res["message"])
        self.assertEqual(res["suggested_action"], "confirm_restore")

        # Verify backup was NOT destroyed and file on disk was NOT overwritten
        self.assertTrue(backup_file.exists())
        self.assertEqual(test_file.read_text(encoding="utf-8"), externally_modified_code)

        # 6. User chooses "Restore anyway" (force=True)
        res_force = pj.reject_file_changes("Dashboard.kt", force=True)
        self.assertTrue(res_force["success"])
        self.assertEqual(test_file.read_text(encoding="utf-8"), original_code)
        self.assertFalse(backup_file.exists())

    def test_pattern_journal_keep_current(self):
        test_file = self.root / "Settings.kt"
        original_code = 'val x = 1\n'
        test_file.write_text(original_code, encoding="utf-8")

        backup_file = self.root / "Settings.kt.bridge.bak"
        backup_file.write_text(original_code, encoding="utf-8")

        pj = PatternJournal(self.root)
        pj.record_change(file="Settings.kt", line=1, old_line="val x = 1", new_line="val x = 2", pattern_id="p2")

        current_code = 'val x = 100 // keep this external edit\n'
        test_file.write_text(current_code, encoding="utf-8")

        # Keep current modifications
        res = pj.keep_current_file_changes("Settings.kt")
        self.assertTrue(res["success"])

        # File remains as is, backup is removed
        self.assertEqual(test_file.read_text(encoding="utf-8"), current_code)
        self.assertFalse(backup_file.exists())


if __name__ == "__main__":
    unittest.main()
