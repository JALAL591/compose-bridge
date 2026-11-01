# -*- coding: utf-8 -*-
"""
Tests for Baseline Drift Fix (P0):
Verifies that the session baseline is immutable:
- When a file undergoes stacked/accumulated edits (A -> B -> C):
- The backup (.bridge.bak) preserves original state A.
- The journal preserves original state A.
- Upon Reject, the file restores to A (NOT to intermediate state B).
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(r"C:\Users\thinkpad\StudioProjects\compose-bridge\server")
sys.path.insert(0, str(SERVER_DIR))

from core.pattern_journal import PatternJournal
from core.ast_finder import safe_create_backup, clear_session_baseline
from common.file_ops import apply_safe_edit


class TestBaselineDrift(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_baseline_drift_test_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_accumulated_edits_a_to_b_to_c_reverts_to_a(self):
        """
        Critical Scenario:
        1. Original file has value A: c1 = Color(0xFF10B981)
        2. Edit 1: changes A to B: c1 = AppColors.AdaptiveActionCardRedAccent
        3. Edit 2: changes B to C: c1 = AppColors.AdaptiveActionCardBlueAccent4
        4. User clicks Reject.
        5. Must revert to A (Color(0xFF10B981)), NOT to B!
        """
        file_path = self.root / "SampleWidget.kt"
        orig_content = """package com.edu.teacher.ui.widgets

import androidx.compose.ui.graphics.Color

fun SampleWidget() {
    val card = Card(
        c1 = Color(0xFF10B981),
        c2 = Color(0xFF059669)
    )
}
"""
        file_path.write_text(orig_content, encoding="utf-8")

        # Step 1: Edit 1 (A -> B)
        content_b = orig_content.replace(
            "c1 = Color(0xFF10B981)",
            "c1 = AppColors.AdaptiveActionCardRedAccent"
        )
        ok1, msg1, bak1 = apply_safe_edit(
            file_path=file_path,
            new_content=content_b,
            original_content=orig_content,
            pattern_id="edit_1",
            project_root=self.root,
        )
        self.assertTrue(ok1, f"Edit 1 failed: {msg1}")
        self.assertIn("AdaptiveActionCardRedAccent", file_path.read_text(encoding="utf-8"))

        # Verify .bridge.bak was created and contains A
        bak_file = file_path.with_name(file_path.name + ".bridge.bak")
        self.assertTrue(bak_file.exists())
        self.assertIn("Color(0xFF10B981)", bak_file.read_text(encoding="utf-8"))

        # Step 2: Edit 2 (B -> C) on the dirty file
        content_c = content_b.replace(
            "c1 = AppColors.AdaptiveActionCardRedAccent",
            "c1 = AppColors.AdaptiveActionCardBlueAccent4"
        )
        ok2, msg2, bak2 = apply_safe_edit(
            file_path=file_path,
            new_content=content_c,
            original_content=content_b,
            pattern_id="edit_2",
            project_root=self.root,
        )
        self.assertTrue(ok2, f"Edit 2 failed: {msg2}")
        self.assertIn("AdaptiveActionCardBlueAccent4", file_path.read_text(encoding="utf-8"))

        # 🌟 CRITICAL: .bridge.bak MUST STILL CONTAIN A (NOT B)!
        self.assertTrue(bak_file.exists())
        bak_content = bak_file.read_text(encoding="utf-8")
        self.assertIn("Color(0xFF10B981)", bak_content, "Baseline drift detected! .bridge.bak was overwritten with B!")
        self.assertNotIn("AdaptiveActionCardRedAccent", bak_content, "Baseline drift! B leaked into .bridge.bak!")

        # Step 3: Reject Changes
        journal = PatternJournal(self.root)
        reject_res = journal.reject_file_changes(str(file_path))
        self.assertTrue(reject_res.get("success"), f"Reject failed: {reject_res}")

        # Step 4: VERIFY RESTORATION TO A (NOT B)
        final_content = file_path.read_text(encoding="utf-8")
        self.assertIn("c1 = Color(0xFF10B981)", final_content, "❌ FAILED: File did NOT restore to original A!")
        self.assertNotIn("AdaptiveActionCardRedAccent", final_content, "❌ FAILED: Intermediate value B remained!")
        self.assertNotIn("AdaptiveActionCardBlueAccent4", final_content, "❌ FAILED: Value C remained!")
        self.assertEqual(final_content.strip(), orig_content.strip(), "❌ FAILED: Restored content differs from original A!")

    def test_immutable_backup_not_overwritten_by_safe_create_backup(self):
        """
        Verify safe_create_backup refuses to overwrite an existing .bridge.bak.
        """
        file_path = self.root / "TestFile.kt"
        file_path.write_text("val A = 1\n", encoding="utf-8")

        # First call creates backup with A
        ok, msg, bak = safe_create_backup(file_path, project_root=self.root)
        self.assertTrue(ok)
        self.assertEqual(bak.read_text(encoding="utf-8"), "val A = 1\n")

        # File is modified to B
        file_path.write_text("val B = 2\n", encoding="utf-8")

        # Second call to safe_create_backup MUST NOT overwrite backup with B
        ok2, msg2, bak2 = safe_create_backup(file_path, project_root=self.root)
        self.assertTrue(ok2)
        self.assertEqual(bak.read_text(encoding="utf-8"), "val A = 1\n", "Backup was overwritten with intermediate B!")


if __name__ == "__main__":
    unittest.main()

