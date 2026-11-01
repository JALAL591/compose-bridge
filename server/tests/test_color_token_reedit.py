# -*- coding: utf-8 -*-
import unittest
import tempfile
import shutil
from pathlib import Path
from analysis.color_analyzer import global_color_edit
from core.pattern_journal import PatternJournal


class TestColorTokenReedit(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_color_reedit_")
        self.root = Path(self.test_dir)

        # Setup directory structure
        self.theme_dir = self.root / "ui" / "theme"
        self.theme_dir.mkdir(parents=True, exist_ok=True)

        self.ds_file = self.theme_dir / "DesignSystem.kt"
        self.ds_file.write_text(
            """package com.example.app.ui.theme

import androidx.compose.ui.graphics.Color
import com.composebridge.agent.BridgeThemeRegistry

object AppColors {
    val AdaptiveCardPink: Color get() = BridgeThemeRegistry.getColor("AdaptiveCardPink", Color(0xFFF59E0B))
}
""",
            encoding="utf-8",
        )

        self.widget_dir = self.root / "ui" / "widgets"
        self.widget_dir.mkdir(parents=True, exist_ok=True)
        self.widget_file = self.widget_dir / "QuickActionsWidget.kt"
        self.widget_file.write_text(
            """package com.example.app.ui.widgets

import androidx.compose.runtime.Composable
import com.example.app.ui.theme.AppColors

@Composable
fun QuickActionsWidget() {
    val c = AppColors.AdaptiveCardPink
}
""",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_reedit_color_token_after_approval(self):
        # Initial check: no backup file exists initially
        bak_file = self.ds_file.with_name(self.ds_file.name + ".bridge.bak")
        self.assertFalse(bak_file.exists())

        # 1. Edit the existing token from phone (sending old_value as 0xFFF59E0B hex literal)
        res1 = global_color_edit(
            file="ui/widgets/QuickActionsWidget.kt",
            line=8,
            property_name="all",
            old_value="0xFFF59E0B",
            new_value="#10B981",
            token_name="AdaptiveCardPink",
            project_root=self.root,
        )

        self.assertTrue(res1.get("success"), f"First re-edit must succeed: {res1}")
        self.assertTrue(res1.get("updated"), "Must be recognized as an existing token update")

        # Verify .bridge.bak was created for DesignSystem.kt
        self.assertTrue(bak_file.exists(), "DesignSystem.kt.bridge.bak must be created before edit")

        # Verify journal recorded change and list_modified_files includes DesignSystem.kt
        journal = PatternJournal(self.root)
        modified_files = journal.list_modified_files()
        mod_names = [Path(m["file"]).name for m in modified_files]
        self.assertIn("DesignSystem.kt", mod_names, "DesignSystem.kt must appear in list_modified_files")

        # 2. Simulate User clicking "Approve" in IDE
        approve_res = journal.approve_file_changes(str(self.ds_file.relative_to(self.root)))
        self.assertTrue(approve_res.get("success"))
        # After approval, backup is unlinked and changes are cleared
        self.assertFalse(bak_file.exists(), ".bridge.bak must be deleted upon approval")
        self.assertEqual(len(journal.list_modified_files()), 0, "No modified files should remain after approval")

        # 3. User edits the SAME token AGAIN from phone
        res2 = global_color_edit(
            file="ui/widgets/QuickActionsWidget.kt",
            line=8,
            property_name="all",
            old_value="0xFF10B981",
            new_value="#EF4444",
            token_name="AdaptiveCardPink",
            project_root=self.root,
        )

        self.assertTrue(res2.get("success"), f"Second re-edit must succeed: {res2}")
        self.assertTrue(res2.get("updated"), "Must be recognized as token update on second edit")

        # Verify new .bridge.bak was created again
        self.assertTrue(bak_file.exists(), "A new DesignSystem.kt.bridge.bak must be created on repeated edit")

        # Verify list_modified_files shows DesignSystem.kt again!
        modified_files_2 = journal.list_modified_files()
        mod_names_2 = [Path(m["file"]).name for m in modified_files_2]
        self.assertIn("DesignSystem.kt", mod_names_2, "DesignSystem.kt must appear in list_modified_files on second edit")


if __name__ == "__main__":
    unittest.main()

