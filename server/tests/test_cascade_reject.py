# -*- coding: utf-8 -*-
"""
Test Cascade Reject and Decoupling Prevention.

Verifies:
1. When a file using a newly added token is rejected, the orphan token is automatically
   removed from DesignSystem.kt / registry file (Cascade Reject).
2. If DesignSystem.kt had no other modifications, it is cleanly restored to baseline
   and removed from the journal.
3. If the newly added token is shared across multiple files and only one file is rejected,
   the token is preserved in DesignSystem.kt and a clear warning is returned.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(r"C:\Users\thinkpad\StudioProjects\compose-bridge\server")
sys.path.insert(0, str(SERVER_DIR))

from core.pattern_journal import PatternJournal
from core.token_migrator import TokenMigrator


class TestCascadeReject(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_cascade_test_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)
        
        self.ds_file = self.root / "DesignSystem.kt"
        self.ds_file.write_text("""package com.example.theme

import androidx.compose.ui.graphics.Color

object AppColors {
    val Primary = Color(0xFF14B8A6)
}
""", encoding="utf-8")

        self.qa_file = self.root / "QuickActionsWidget.kt"
        self.qa_file.write_text("""package com.example.ui

import androidx.compose.ui.graphics.Color
import com.example.theme.AppColors

fun QuickActions() {
    val c = Color(0xFF6366F1)
}
""", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_single_file_reject_removes_orphan_token(self):
        migrator = TokenMigrator(self.root)
        ok, msg, info = migrator.migrate(
            file_name="QuickActionsWidget.kt",
            line=7,
            value="0xFF6366F1",
            token_name="AdaptiveActionCardBlueAccent2",
            token_type="color",
            force_create=True
        )
        self.assertTrue(ok, f"Migrate failed: {msg}")
        self.assertIn("AdaptiveActionCardBlueAccent2", self.ds_file.read_text(encoding="utf-8"))
        self.assertIn("AppColors.AdaptiveActionCardBlueAccent2", self.qa_file.read_text(encoding="utf-8"))

        pj = PatternJournal(self.root)
        pj.record_token_added(
            pattern_id="pattern_qa",
            token_name="AdaptiveActionCardBlueAccent2",
            token_value="0xFF6366F1",
            file="DesignSystem.kt"
        )
        pj.record_change(
            file="QuickActionsWidget.kt",
            line=7,
            old_line="    val c = Color(0xFF6366F1)",
            new_line="    val c = AppColors.AdaptiveActionCardBlueAccent2",
            pattern_id="pattern_qa"
        )

        res = pj.reject_file_changes("QuickActionsWidget.kt", force=False)
        self.assertTrue(res.get("success"), f"Reject failed: {res}")
        self.assertIn("AdaptiveActionCardBlueAccent2", res.get("cascade_removed_tokens", []))
        self.assertIn("DesignSystem.kt", res.get("cascade_cleaned_files", []))
        
        # DesignSystem.kt must have orphan token removed and restored cleanly
        self.assertNotIn("AdaptiveActionCardBlueAccent2", self.ds_file.read_text(encoding="utf-8"))
        self.assertNotIn("BridgeThemeRegistry", self.ds_file.read_text(encoding="utf-8"))
        self.assertFalse((self.root / "DesignSystem.kt.bridge.bak").exists())

    def test_shared_token_warning_when_other_file_still_pending(self):
        # Setup files with modified content containing the token
        self.qa_file.write_text("""package com.example.ui

import androidx.compose.ui.graphics.Color
import com.example.theme.AppColors

fun QuickActions() {
    val c = AppColors.SharedColor
}
""", encoding="utf-8")

        qa_bak = self.qa_file.with_name(self.qa_file.name + ".bridge.bak")
        qa_bak.write_text("""package com.example.ui

import androidx.compose.ui.graphics.Color
import com.example.theme.AppColors

fun QuickActions() {
    val c = Color(0xFF6366F1)
}
""", encoding="utf-8")

        pj = PatternJournal(self.root)
        pj.record_token_added(
            pattern_id="pattern_shared",
            token_name="SharedColor",
            token_value="0xFF6366F1",
            file="DesignSystem.kt"
        )
        pj.record_change(
            file="QuickActionsWidget.kt",
            line=7,
            old_line="    val c = Color(0xFF6366F1)",
            new_line="    val c = AppColors.SharedColor",
            pattern_id="pattern_shared"
        )
        pj.record_change(
            file="ProfileCard.kt",
            line=12,
            old_line="    val card = Color(0xFF6366F1)",
            new_line="    val card = AppColors.SharedColor",
            pattern_id="pattern_shared"
        )

        res = pj.reject_file_changes("QuickActionsWidget.kt", force=False)
        self.assertTrue(res.get("success"), f"Reject failed: {res}")
        self.assertEqual(len(res.get("cascade_removed_tokens", [])), 0)
        self.assertIsNotNone(res.get("warning"))
        self.assertIn("SharedColor", res.get("warning", ""))
        self.assertIn("ProfileCard.kt", res.get("warning", ""))


if __name__ == "__main__":
    unittest.main()
