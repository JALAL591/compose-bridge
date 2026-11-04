# -*- coding: utf-8 -*-
"""
Unit tests for Token Baseline indexing and protection architecture.

Verifies:
1. TokenBaselineManager accurately indexes pre-existing tokens across ALL Kotlin files.
2. Baseline tokens are completely immune from cascade-rejection.
3. Newly created tokens used across multiple files (or on disk) are preserved on reject.
4. Approving files or changes promotes newly added tokens into the baseline.
5. Moving a token from DesignSystem.kt to Theme.kt is recognized across the project.
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
from core.token_migrator import TokenMigrator
from core.token_baseline import (
    TokenBaselineManager,
    build_baseline,
    is_pre_existing,
    add_to_baseline,
    check_token_usages_in_project,
)


class TestTokenBaseline(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_baseline_test_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)

        # Baseline DesignSystem.kt with an existing token
        self.ds_file = self.root / "DesignSystem.kt"
        self.ds_file.write_text("""package com.example.theme

import androidx.compose.ui.graphics.Color

object AppColors {
    val Primary = Color(0xFF14B8A6)
    val BaselineSecondary = Color(0xFF6366F1)
}
""", encoding="utf-8")

        self.qa_file = self.root / "QuickActionsWidget.kt"
        self.qa_file.write_text("""package com.example.ui

import androidx.compose.ui.graphics.Color
import com.example.theme.AppColors

fun QuickActions() {
    val c = Color(0xFF112233)
}
""", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_build_baseline_indexes_existing_tokens(self):
        tokens = build_baseline(self.root, force=True)
        self.assertIn("Primary", tokens)
        self.assertIn("BaselineSecondary", tokens)
        self.assertFalse(is_pre_existing("NonExistentToken", self.root))
        self.assertTrue(is_pre_existing("Primary", self.root))

        # Check baseline disk file
        baseline_file = self.root / ".composebridge" / "token_baseline.json"
        self.assertTrue(baseline_file.exists())
        data = json.loads(baseline_file.read_text(encoding="utf-8"))
        self.assertIn("Primary", data)

    def test_baseline_token_is_immune_from_cascade_reject(self):
        # 1. Initialize baseline
        build_baseline(self.root, force=True)
        self.assertTrue(is_pre_existing("Primary", self.root))

        # Setup QuickActionsWidget with backup
        qa_bak = self.qa_file.with_name(self.qa_file.name + ".bridge.bak")
        qa_bak.write_text("""package com.example.ui

import androidx.compose.ui.graphics.Color
import com.example.theme.AppColors

fun QuickActions() {
    val c = Color(0xFF112233)
}
""", encoding="utf-8")

        self.qa_file.write_text("""package com.example.ui

import androidx.compose.ui.graphics.Color
import com.example.theme.AppColors

fun QuickActions() {
    val c = AppColors.Primary
}
""", encoding="utf-8")

        # 2. Modify QuickActionsWidget.kt to reference Primary in journal
        pj = PatternJournal(self.root)
        pj.record_token_added(
            pattern_id="pattern_qa",
            token_name="Primary",
            token_value="0xFF14B8A6",
            file="DesignSystem.kt"
        )
        pj.record_change(
            file="QuickActionsWidget.kt",
            line=7,
            old_line="    val c = Color(0xFF112233)",
            new_line="    val c = AppColors.Primary",
            pattern_id="pattern_qa"
        )

        # 3. Reject QuickActionsWidget.kt
        res = pj.reject_file_changes("QuickActionsWidget.kt")
        self.assertTrue(res.get("success", False))

        # 4. Verify Primary was NOT cascade-deleted from DesignSystem.kt
        ds_code = self.ds_file.read_text(encoding="utf-8")
        self.assertIn("val Primary = Color(0xFF14B8A6)", ds_code)
        self.assertNotIn("Primary", res.get("cascade_removed_tokens", []))
        self.assertIn("حماية التوكن الأساسي", res.get("message", "") + (res.get("warning") or ""))

    def test_new_token_cascade_rejected_when_unused(self):
        # 1. Initialize baseline (does not contain NewUnsharedToken)
        build_baseline(self.root, force=True)
        self.assertFalse(is_pre_existing("NewUnsharedToken", self.root))

        # 2. Migrate new token into QuickActionsWidget
        migrator = TokenMigrator(self.root)
        ok, msg, _ = migrator.migrate(
            file_name="QuickActionsWidget.kt",
            line=7,
            value="0xFF112233",
            token_name="NewUnsharedToken",
            token_type="color",
            force_create=True
        )
        self.assertTrue(ok, f"Migrate failed: {msg}")
        self.assertIn("NewUnsharedToken", self.ds_file.read_text(encoding="utf-8"))

        # Record in journal
        pj = PatternJournal(self.root)
        pj.record_token_added(
            pattern_id="pat_new",
            token_name="NewUnsharedToken",
            token_value="0xFF112233",
            file="DesignSystem.kt"
        )
        pj.record_change(
            file="QuickActionsWidget.kt",
            line=7,
            old_line="    val c = Color(0xFF112233)",
            new_line="    val c = AppColors.NewUnsharedToken",
            pattern_id="pat_new"
        )

        # 3. Reject QuickActionsWidget
        res = pj.reject_file_changes("QuickActionsWidget.kt")
        self.assertTrue(res.get("success", False))

        # 4. As it's NOT in baseline and unused elsewhere, it should be cleanly cascade removed
        ds_code = self.ds_file.read_text(encoding="utf-8")
        self.assertNotIn("NewUnsharedToken", ds_code)
        self.assertIn("NewUnsharedToken", res.get("cascade_removed_tokens", []))

    def test_new_token_preserved_when_used_by_another_file(self):
        build_baseline(self.root, force=True)

        # Migrate new token into QuickActionsWidget
        migrator = TokenMigrator(self.root)
        ok, msg, _ = migrator.migrate(
            file_name="QuickActionsWidget.kt",
            line=7,
            value="0xFF112233",
            token_name="SharedNewToken",
            token_type="color",
            force_create=True
        )
        self.assertTrue(ok, f"Migrate failed: {msg}")

        # File A and File B both use it
        other_file = self.root / "OtherWidget.kt"
        other_file.write_text("""package com.example.ui
import com.example.theme.AppColors
fun Other() {
    val x = AppColors.SharedNewToken
}
""", encoding="utf-8")

        pj = PatternJournal(self.root)
        pj.record_token_added(
            pattern_id="pat_shared",
            token_name="SharedNewToken",
            token_value="0xFF112233",
            file="DesignSystem.kt"
        )
        pj.record_change(
            file="QuickActionsWidget.kt",
            line=7,
            old_line="    val c = Color(0xFF112233)",
            new_line="    val c = AppColors.SharedNewToken",
            pattern_id="pat_shared"
        )
        pj.record_change(
            file="OtherWidget.kt",
            line=4,
            old_line="    val x = Color(0xFF112233)",
            new_line="    val x = AppColors.SharedNewToken",
            pattern_id="pat_shared"
        )

        # Reject QuickActionsWidget
        res = pj.reject_file_changes("QuickActionsWidget.kt")
        self.assertTrue(res.get("success", False))

        # Verify SharedNewToken was PRESERVED because OtherWidget uses it
        ds_code = self.ds_file.read_text(encoding="utf-8")
        self.assertIn("SharedNewToken", ds_code)
        self.assertNotIn("SharedNewToken", res.get("cascade_removed_tokens", []))

    def test_approval_promotes_token_to_baseline(self):
        build_baseline(self.root, force=True)
        self.assertFalse(is_pre_existing("ApprovedToken", self.root))

        add_to_baseline("ApprovedToken", "DesignSystem.kt", self.root)
        self.assertTrue(is_pre_existing("ApprovedToken", self.root))

    def test_whole_project_baseline_tracks_moved_token(self):
        """
        Scenario: Token OldColor originally exists in DesignSystem.kt.
        Developer moves OldColor from DesignSystem.kt to Theme.kt.
        Whole-project baseline must detect OldColor in Theme.kt and keep it protected.
        """
        # 1. OldColor in DesignSystem.kt
        self.ds_file.write_text("""package com.example.theme
import androidx.compose.ui.graphics.Color
object AppColors {
    val OldColor = Color(0xFF112233)
}
""", encoding="utf-8")
        tokens_before = build_baseline(self.root, force=True)
        self.assertIn("OldColor", tokens_before)
        self.assertTrue(is_pre_existing("OldColor", self.root))

        # 2. Developer moves OldColor to Theme.kt and removes from DesignSystem.kt
        self.ds_file.write_text("""package com.example.theme
import androidx.compose.ui.graphics.Color
object AppColors {
    // OldColor moved away
}
""", encoding="utf-8")

        theme_file = self.root / "Theme.kt"
        theme_file.write_text("""package com.example.theme
import androidx.compose.ui.graphics.Color
object ThemeTokens {
    val OldColor = Color(0xFF112233)
}
""", encoding="utf-8")

        try:
            from common.project_cache import PROJECT_CACHE
            PROJECT_CACHE.invalidate()
        except Exception:
            pass

        # 3. Whole-project baseline re-index
        tokens_after = build_baseline(self.root, force=True)

        # 4. OldColor must be recognized in Theme.kt and remain pre-existing
        self.assertIn("OldColor", tokens_after)
        self.assertTrue(is_pre_existing("OldColor", self.root))
        self.assertTrue(tokens_after["OldColor"].endswith("Theme.kt"))


if __name__ == "__main__":
    unittest.main()
