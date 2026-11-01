# -*- coding: utf-8 -*-
"""
Test Prevention of Silent Color Writes (P0).
Verifies that:
1. split_token_for_element creates a .bridge.bak backup BEFORE writing any color changes.
2. The created backup contains the pristine original color (not the new color).
3. global_color_edit creates a .bridge.bak backup BEFORE modifying target files.
4. Calling reject_file_changes cleanly restores the pristine original color.
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(r"C:\Users\thinkpad\StudioProjects\compose-bridge\server")
sys.path.insert(0, str(SERVER_DIR))

from analysis.color_analyzer import split_token_for_element, global_color_edit
from core.pattern_journal import PatternJournal


class TestSilentColorWrites(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_col_test_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)

        # Setup DesignSystem.kt
        self.theme_dir = self.root / "theme"
        self.theme_dir.mkdir(parents=True, exist_ok=True)
        self.ds_file = self.theme_dir / "DesignSystem.kt"
        self.ds_file.write_text("""package com.example.theme

import androidx.compose.ui.graphics.Color
import com.composebridge.agent.BridgeThemeRegistry

object AppColors {
    val Primary: Color get() = BridgeThemeRegistry.getColor("Primary", Color(0xFF14B8A6))
}
""", encoding="utf-8")

        # Setup QuickActionsWidget.kt
        self.widgets_dir = self.root / "widgets"
        self.widgets_dir.mkdir(parents=True, exist_ok=True)
        self.widget_file = self.widgets_dir / "QuickActionsWidget.kt"
        self.original_widget_code = """package com.example.widgets

import androidx.compose.ui.graphics.Color

fun QuickActionsWidget() {
    val c1 = Color(0xFFF59E0B)
    val c2 = Color(0xFFD97706)
}
"""
        self.widget_file.write_text(self.original_widget_code, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_split_token_creates_immediate_backup_with_original_color(self):
        """Verify split_token_for_element creates .bridge.bak containing the pristine original color."""
        bak_file = self.widgets_dir / "QuickActionsWidget.kt.bridge.bak"
        self.assertFalse(bak_file.exists(), "Backup should not exist before edit")

        # Execute split_token_for_element on line 6 (c1)
        res = split_token_for_element(
            original_token="Color(0xFFF59E0B)",
            original_value="0xFFF59E0B",
            new_token_name="AdaptiveActionCardPinkAccent",
            new_value="#FF10B981",
            element_file="QuickActionsWidget.kt",
            element_line=6,
            occurrences=[{"line": 6}],
            project_root=self.root,
        )

        self.assertTrue(res.get("success"), f"split_token failed: {res}")

        # 1. Verify backup was created immediately (WITHOUT any dimension edit!)
        self.assertTrue(bak_file.exists(), "Backup MUST be created immediately upon color edit!")

        # 2. Verify backup contains original pristine color
        bak_content = bak_file.read_text(encoding="utf-8")
        self.assertIn("Color(0xFFF59E0B)", bak_content, "Backup MUST contain the original color!")
        self.assertNotIn("AdaptiveActionCardPinkAccent", bak_content, "Backup must NOT contain the new token!")

        # 3. Verify widget file on disk has new color token
        curr_widget = self.widget_file.read_text(encoding="utf-8")
        self.assertIn("AppColors.AdaptiveActionCardPinkAccent", curr_widget)

        # 4. Verify Reject restores the original color
        pj = PatternJournal(self.root)
        rej_res = pj.reject_file_changes(str(self.widget_file.relative_to(self.root)))
        self.assertTrue(rej_res.get("success"), f"Reject failed: {rej_res}")

        restored_widget = self.widget_file.read_text(encoding="utf-8")
        self.assertIn("Color(0xFFF59E0B)", restored_widget, "File MUST be reverted to pristine original color!")
        self.assertNotIn("AdaptiveActionCardPinkAccent", restored_widget)

    def test_global_color_edit_creates_immediate_backup(self):
        """Verify global_color_edit creates backup before writing changes."""
        bak_file = self.widgets_dir / "QuickActionsWidget.kt.bridge.bak"
        self.assertFalse(bak_file.exists())

        res = global_color_edit(
            file="widgets/QuickActionsWidget.kt",
            line=7,
            old_value="0xFFD97706",
            new_value="#FF112233",
            token_name="ActionCardAmberAccent",
            project_root=self.root,
        )

        self.assertTrue(res.get("success"), f"global_color_edit failed: {res}")
        self.assertTrue(bak_file.exists(), "Backup must exist after global color edit!")
        self.assertIn("Color(0xFFD97706)", bak_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
