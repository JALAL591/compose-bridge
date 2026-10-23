# -*- coding: utf-8 -*-
"""
Unit tests for P0 fixes:
1. set_token routing for colors (#, 0x, Color) vs dimensions (.dp).
2. add_token ensuring BridgeDimensionRegistry and Dp imports in registry file.
3. rollback_pattern ignoring empty file entries without permission errors.
4. add_token physically writing token to DesignSystem.kt and set_token modifying it.
5. add_token auto-detecting DesignSystem.kt when preferred_token_file is None.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(r"C:\Users\thinkpad\StudioProjects\compose-bridge\server")
sys.path.insert(0, str(PROJECT_ROOT))

from core.pattern_journal import PatternJournal
import mcp.tools.tokens as mtt
from mcp.tools.tokens import set_token, add_token


class TestP0Fixes(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_p0_fixes_test_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)
        self._orig_root = mtt.PROJECT_ROOT
        mtt.PROJECT_ROOT = self.root

    def tearDown(self):
        mtt.PROJECT_ROOT = self._orig_root
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_set_token_with_color_hex(self):
        """Verify set_token routes colors to update_theme_color, not update_token_default."""
        ds_file = self.root / "DesignSystem.kt"
        ds_file.write_text(
            'package com.example.ui\n\n'
            'import androidx.compose.ui.graphics.Color\n\n'
            'val PrimaryColor = Color(0xFF6366F1)\n',
            encoding="utf-8"
        )

        res_str = set_token("PrimaryColor", "0xFF000000")
        res = json.loads(res_str)

        self.assertTrue(res.get("success"), f"set_token failed: {res}")
        content = ds_file.read_text(encoding="utf-8")
        self.assertIn("0xFF000000", content)
        self.assertNotIn("0xFF6366F1", content)

    def test_set_token_with_color_hash(self):
        """Verify set_token handles #RRGGBB format for colors."""
        ds_file = self.root / "DesignSystem.kt"
        ds_file.write_text(
            'package com.example.ui\n\n'
            'import androidx.compose.ui.graphics.Color\n\n'
            'val AccentColor = Color(0xFF10B981)\n',
            encoding="utf-8"
        )

        res_str = set_token("AccentColor", "#E11D48")
        res = json.loads(res_str)

        self.assertTrue(res.get("success"), f"set_token failed: {res}")
        content = ds_file.read_text(encoding="utf-8")
        self.assertIn("0xFFE11D48", content)

    def test_set_token_with_dimension(self):
        """Verify set_token routes dimensions (.dp) to update_token_default."""
        dim_file = self.root / "AppDimens.kt"
        dim_file.write_text(
            'package com.example.ui\n\n'
            'import androidx.compose.ui.unit.dp\n'
            'import androidx.compose.ui.unit.Dp\n'
            'import com.composebridge.agent.BridgeDimensionRegistry\n\n'
            'object AppDimens {\n'
            '    val cardPadding: Dp get() = BridgeDimensionRegistry.get("cardPadding", 16.dp)\n'
            '}\n',
            encoding="utf-8"
        )

        res_str = set_token("cardPadding", "24.dp")
        res = json.loads(res_str)

        self.assertTrue(res.get("success"), f"set_token failed: {res}")
        content = dim_file.read_text(encoding="utf-8")
        self.assertIn('get("cardPadding", 24.dp)', content)

    def test_add_token_dimension_adds_required_imports(self):
        """Verify add_token ensures BridgeDimensionRegistry and Dp imports for dimensions."""
        ds_file = self.root / "DesignSystem.kt"
        ds_file.write_text(
            'package com.example.ui\n\n'
            'object DesignSystem {\n'
            '    val dummy = 1\n'
            '}\n',
            encoding="utf-8"
        )

        widget_file = self.root / "TestWidget.kt"
        widget_file.write_text(
            'package com.example.ui\n\n'
            'import androidx.compose.foundation.layout.padding\n'
            'import androidx.compose.ui.unit.dp\n\n'
            'fun Widget() {\n'
            '    val pad = 12.dp\n'
            '}\n',
            encoding="utf-8"
        )

        res_str = add_token(
            file="TestWidget.kt",
            line=7,
            value="12.dp",
            token_name="WidgetPadding",
            token_type="dimension",
            preferred_token_file="DesignSystem.kt",
            force_create=True,
        )
        res = json.loads(res_str)
        self.assertTrue(res.get("success"), f"add_token failed: {res}")

        ds_content = ds_file.read_text(encoding="utf-8")
        self.assertIn("import com.composebridge.agent.BridgeDimensionRegistry", ds_content)
        self.assertIn("import androidx.compose.ui.unit.Dp", ds_content)
        self.assertIn("import androidx.compose.ui.unit.dp", ds_content)

    def test_add_token_writes_physically_to_design_system_and_set_token_finds_it(self):
        """Verify add_token physically writes token to DesignSystem.kt and set_token modifies it."""
        ds_file = self.root / "DesignSystem.kt"
        ds_file.write_text(
            'package com.example.ui\n\n'
            'import androidx.compose.ui.graphics.Color\n\n'
            'object AppColors {\n'
            '    val Primary = Color(0xFF14B8A6)\n'
            '}\n',
            encoding="utf-8"
        )

        screen_file = self.root / "DashboardScreen.kt"
        screen_file.write_text(
            'package com.example.ui\n\n'
            'import androidx.compose.ui.graphics.Color\n\n'
            'fun Screen() {\n'
            '    val bg = Color(0xFA060B1F)\n'
            '}\n',
            encoding="utf-8"
        )

        # 1. Call add_token
        res_str = add_token(
            file="DashboardScreen.kt",
            line=6,
            value="Color(0xFA060B1F)",
            token_name="QAMcpTestColor",
            token_type="color",
            preferred_token_file="DesignSystem.kt",
            force_create=True,
        )
        res = json.loads(res_str)
        self.assertTrue(res.get("success"), f"add_token failed: {res}")

        # 2. Assert physical content in DesignSystem.kt
        ds_content = ds_file.read_text(encoding="utf-8")
        self.assertIn("QAMcpTestColor", ds_content)
        self.assertIn('BridgeThemeRegistry.getColor("QAMcpTestColor", Color(0xFA060B1F))', ds_content)
        self.assertIn("import com.composebridge.agent.BridgeThemeRegistry", ds_content)

        # 3. Assert target file replacement
        screen_content = screen_file.read_text(encoding="utf-8")
        self.assertIn("AppColors.QAMcpTestColor", screen_content)

        # 4. Modify with set_token (bare name)
        set_res_str = set_token("QAMcpTestColor", "0xFF112233")
        set_res = json.loads(set_res_str)
        self.assertTrue(set_res.get("success"), f"set_token bare failed: {set_res}")
        ds_content = ds_file.read_text(encoding="utf-8")
        self.assertIn("0xFF112233", ds_content)

        # 5. Modify with set_token (scoped name: AppColors.QAMcpTestColor)
        set_scoped_str = set_token("AppColors.QAMcpTestColor", "0xFF445566")
        set_scoped = json.loads(set_scoped_str)
        self.assertTrue(set_scoped.get("success"), f"set_token scoped failed: {set_scoped}")
        ds_content = ds_file.read_text(encoding="utf-8")
        self.assertIn("0xFF445566", ds_content)

    def test_add_token_auto_detects_design_system_when_none(self):
        """Verify add_token auto-detects DesignSystem.kt when preferred_token_file is None."""
        ds_file = self.root / "DesignSystem.kt"
        ds_file.write_text(
            'package com.example.ui\n\n'
            'import androidx.compose.ui.graphics.Color\n\n'
            'object AppColors {\n'
            '    val Primary = Color(0xFF14B8A6)\n'
            '}\n',
            encoding="utf-8"
        )

        screen_file = self.root / "SampleScreen.kt"
        screen_file.write_text(
            'package com.example.ui\n\n'
            'import androidx.compose.ui.graphics.Color\n\n'
            'fun Sample() {\n'
            '    val c = Color(0xFFEF4444)\n'
            '}\n',
            encoding="utf-8"
        )

        # preferred_token_file is not specified (None)
        res_str = add_token(
            file="SampleScreen.kt",
            line=6,
            value="Color(0xFFEF4444)",
            token_name="AutoDetectedColor",
            token_type="color",
            force_create=True,
        )
        res = json.loads(res_str)
        self.assertTrue(res.get("success"), f"add_token auto-detect failed: {res}")

        ds_content = ds_file.read_text(encoding="utf-8")
        self.assertIn("AutoDetectedColor", ds_content)
        self.assertIn('BridgeThemeRegistry.getColor("AutoDetectedColor", Color(0xFFEF4444))', ds_content)

    def test_rollback_pattern_handles_empty_file_entries(self):
        """Verify rollback_pattern ignores summary entries with empty file path without crashing."""
        state_dir = self.root / ".composebridge-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        journal_file = state_dir / "pattern_journal.jsonl"

        widget_file = self.root / "SampleWidget.kt"
        widget_file.write_text('val color = DesignSystem.TestColor\n', encoding="utf-8")

        # Write replacement entry + pattern_summary entry with empty file
        entries = [
            {
                "pattern_id": "pat_test_123",
                "type": "file_replacement",
                "file": "SampleWidget.kt",
                "line": 1,
                "old": "val color = Color.White",
                "new": "val color = DesignSystem.TestColor",
            },
            {
                "pattern_id": "pat_test_123",
                "type": "pattern_summary",
                "file": "",
                "total_replacements": 1,
            }
        ]
        with open(journal_file, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        pj = PatternJournal(self.root)
        changes = pj.get_pattern_changes("pat_test_123")
        self.assertEqual(len(changes), 1, "get_pattern_changes should filter out empty file entries")

        res = pj.rollback_pattern("pat_test_123")
        self.assertTrue(res.get("success"), f"rollback_pattern failed: {res}")
        widget_content = widget_file.read_text(encoding="utf-8")
        self.assertIn("Color.White", widget_content)


if __name__ == "__main__":
    unittest.main()
