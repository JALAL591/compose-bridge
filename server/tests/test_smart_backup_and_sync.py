# -*- coding: utf-8 -*-
"""
Test Smart Backup Logic and Cross-Platform Sync.

Tests:
1. Scenario 1: Clean manual edit / Git pull -> ComposeBridge edit -> Reject.
   Verifies the file reverts to the clean manual edit (preserving developer's work).
2. Scenario 2: Approve file removes it from journal and list_modified_files (IDE & Phone sync).
3. Scenario 3: Reject file from computer restores original code and clears pending modified files for Phone.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

from core.pattern_journal import PatternJournal
from core.ast_finder import validate_kotlin_syntax, safe_create_backup
from editor.color_editor import update_theme_color
from mcp.tools.files import reject_file_changes, approve_file_changes


class TestSmartBackupAndSync(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_smart_sync_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_scenario_1_manual_edit_then_tool_edit_then_revert(self):
        theme_file = self.root / "DesignSystem.kt"
        initial_content = """package com.example.theme

import com.composebridge.agent.BridgeThemeRegistry
import androidx.compose.ui.graphics.Color

object AppColors {
    val Primary: Color get() = BridgeThemeRegistry.getColor("Primary", Color(0xFF14B8A6))
}
"""
        theme_file.write_text(initial_content, encoding="utf-8")

        # 1. Edit 1 via tool: #14B8A6 -> #00AA55
        ok1, msg1, _ = update_theme_color("Primary", "0xFF00AA55")
        self.assertTrue(ok1, f"Edit 1 failed: {msg1}")

        # 2. Developer manually edits the file (or does git pull), adding clean new code:
        manual_edit_content = """package com.example.theme

import com.composebridge.agent.BridgeThemeRegistry
import androidx.compose.ui.graphics.Color

object AppColors {
    val CustomHeader = "My Clean Developer Header"
    val Primary: Color get() = BridgeThemeRegistry.getColor("Primary", Color(0xFF223344))
}
"""
        theme_file.write_text(manual_edit_content, encoding="utf-8")

        # Verify manual edit is valid Kotlin syntax
        is_valid, err_syntax = validate_kotlin_syntax(theme_file)
        self.assertTrue(is_valid, f"Manual edit should be valid syntax: {err_syntax}")

        # 3. Tool performs Edit 2: change color to #FF0000
        ok2, msg2, _ = update_theme_color("Primary", "0xFFFF0000")
        self.assertTrue(ok2, f"Edit 2 on clean manual code should succeed: {msg2}")

        # Verify tool edit applied on top of developer's code
        curr = theme_file.read_text(encoding="utf-8")
        self.assertIn("0xFFFF0000", curr)
        self.assertIn("CustomHeader", curr)

        # 4. Developer clicks "Reject" (تراجع)
        pj = PatternJournal(self.root)
        res = pj.reject_file_changes("DesignSystem.kt", force=False)
        self.assertTrue(res.get("success"), f"Reject failed: {res}")

        # 5. VERIFY: The file MUST revert to the developer's clean manual edit, NOT the old #14B8A6!
        final_text = theme_file.read_text(encoding="utf-8")
        self.assertIn("CustomHeader", final_text, "Developer's manual function/property must NOT be lost!")
        self.assertIn("0xFF223344", final_text, "Developer's manual color must be restored!")
        self.assertNotIn("0xFFFF0000", final_text, "Tool edit must be removed!")

    def test_scenario_2_approve_sync_across_platforms(self):
        theme_file = self.root / "DesignSystem.kt"
        content = """package com.example.theme

import com.composebridge.agent.BridgeThemeRegistry
import androidx.compose.ui.graphics.Color

object AppColors {
    val Primary: Color get() = BridgeThemeRegistry.getColor("Primary", Color(0xFF14B8A6))
}
"""
        theme_file.write_text(content, encoding="utf-8")

        # Tool modifies file
        ok, msg, _ = update_theme_color("Primary", "0xFF00AA55")
        self.assertTrue(ok)

        pj = PatternJournal(self.root)
        modified_before = pj.list_modified_files()
        self.assertEqual(len(modified_before), 1, "Should have 1 modified file before approve")

        # Simulate Phone or IDE approving the file
        res = pj.approve_file_changes("DesignSystem.kt")
        self.assertTrue(res.get("success"))

        # Single source of truth (PatternJournal) must now show 0 modified files
        modified_after = pj.list_modified_files()
        self.assertEqual(len(modified_after), 0, "File must disappear from modified files list in all platforms")

        # The backup must be cleaned up
        bak = self.root / "DesignSystem.kt.bridge.bak"
        self.assertFalse(bak.exists(), "Backup must be deleted on approval")

    def test_scenario_3_computer_revert_restores_code_and_clears_list(self):
        theme_file = self.root / "DesignSystem.kt"
        orig_color = "0xFF14B8A6"
        content = f"""package com.example.theme

import com.composebridge.agent.BridgeThemeRegistry
import androidx.compose.ui.graphics.Color

object AppColors {{
    val Primary: Color get() = BridgeThemeRegistry.getColor("Primary", Color({orig_color}))
}}
"""
        theme_file.write_text(content, encoding="utf-8")

        # Tool modifies file
        ok, msg, _ = update_theme_color("Primary", "0xFF990000")
        self.assertTrue(ok)

        # Computer (MCP / IDE) calls reject_file_changes
        res_str = reject_file_changes("DesignSystem.kt")
        res = json.loads(res_str)
        self.assertTrue(res.get("success"), f"Rejection should succeed: {res}")

        # Verify file restored on disk
        self.assertIn(orig_color, theme_file.read_text(encoding="utf-8"))

        # Verify pattern journal cleared for this file
        pj = PatternJournal(self.root)
        self.assertEqual(len(pj.list_modified_files()), 0, "Modified list must be empty after reject")


if __name__ == "__main__":
    unittest.main()
