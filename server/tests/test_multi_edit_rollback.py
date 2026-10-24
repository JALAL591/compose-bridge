# -*- coding: utf-8 -*-
"""
Test Multi-Edit Rollback and CRLF Normalization.

Verifies:
1. Two consecutive edits to the same token do not trigger EXTERNAL_MODIFICATION_DETECTED.
2. .bridge.bak backup is created ONLY on the first edit and not overwritten.
3. reject_file_changes restores the file to the TRUE ORIGINAL value, not the intermediate value.
4. Windows CRLF line endings do not cause false positive checksum mismatches.
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
from editor.color_editor import update_theme_color
from editor.dimension_editor import update_token_default


class TestMultiEditRollback(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_multi_rollback_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_consecutive_color_edits_rollback(self):
        theme_file = self.root / "DesignSystem.kt"
        orig_color = "0xFF14B8A6"
        initial_content = f"""package com.example.theme

import com.composebridge.agent.BridgeThemeRegistry
import androidx.compose.ui.graphics.Color

object AppColors {{
    val Primary: Color get() = BridgeThemeRegistry.getColor("Primary", Color({orig_color}))
}}
"""
        # Write with Windows CRLF line endings
        with open(theme_file, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(initial_content)

        # 1. Edit 1: #14B8A6 -> #00AA55
        val_1 = "0xFF00AA55"
        ok1, msg1, _ = update_theme_color("Primary", val_1)
        self.assertTrue(ok1, f"Edit 1 failed: {msg1}")

        # Verify backup exists and contains original color
        bak_file = self.root / "DesignSystem.kt.bridge.bak"
        self.assertTrue(bak_file.exists(), "Backup file .bridge.bak must exist after Edit 1")
        bak_content_1 = bak_file.read_text(encoding="utf-8")
        self.assertIn(orig_color, bak_content_1, "Backup must contain original color after Edit 1")

        # 2. Edit 2: #00AA55 -> #FF00FF
        val_2 = "0xFFFF00FF"
        ok2, msg2, _ = update_theme_color("Primary", val_2)
        self.assertTrue(ok2, f"Edit 2 failed: {msg2}")

        # Verify backup was NOT overwritten by Edit 2
        bak_content_2 = bak_file.read_text(encoding="utf-8")
        self.assertIn(orig_color, bak_content_2, "Backup must STILL contain original color after Edit 2")
        self.assertNotIn(val_1, bak_content_2, "Backup must NOT be overwritten with intermediate color")

        # 3. Call reject_file_changes(force=False)
        pj = PatternJournal(self.root)
        res = pj.reject_file_changes("DesignSystem.kt", force=False)
        self.assertTrue(res.get("success"), f"Reject failed: {res}")
        self.assertNotEqual(res.get("error_code"), "EXTERNAL_MODIFICATION_DETECTED")

        # 4. Verify file content restored to ORIGINAL color, not intermediate
        final_content = theme_file.read_text(encoding="utf-8")
        self.assertIn(orig_color, final_content, "File must be restored to original color (0xFF14B8A6)")
        self.assertNotIn(val_1, final_content, "File must NOT contain intermediate color (0xFF00AA55)")
        self.assertNotIn(val_2, final_content, "File must NOT contain second edit color (0xFFFF00FF)")

    def test_consecutive_dimension_edits_rollback(self):
        theme_file = self.root / "DesignSystem.kt"
        orig_dim = "16"
        initial_content = f"""package com.example.theme

import com.composebridge.agent.BridgeDimensionRegistry
import androidx.compose.ui.unit.dp

object AppDimensions {{
    val SpacingMedium get() = BridgeDimensionRegistry.get("SpacingMedium", {orig_dim}.dp)
}}
"""
        with open(theme_file, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(initial_content)

        # 1. Edit 1: 16.dp -> 24.dp
        ok1, msg1, _ = update_token_default("SpacingMedium", "24")
        self.assertTrue(ok1, f"Dim Edit 1 failed: {msg1}")

        # 2. Edit 2: 24.dp -> 32.dp
        ok2, msg2, _ = update_token_default("SpacingMedium", "32")
        self.assertTrue(ok2, f"Dim Edit 2 failed: {msg2}")

        # 3. Reject changes
        pj = PatternJournal(self.root)
        res = pj.reject_file_changes("DesignSystem.kt", force=False)
        self.assertTrue(res.get("success"), f"Dim Reject failed: {res}")

        # 4. Verify restored to original 16.dp
        final_content = theme_file.read_text(encoding="utf-8")
        self.assertIn("16.dp", final_content, "Must restore to original 16.dp")
        self.assertNotIn("24.dp", final_content, "Must not be intermediate 24.dp")
        self.assertNotIn("32.dp", final_content, "Must not be second edit 32.dp")


if __name__ == "__main__":
    unittest.main()
