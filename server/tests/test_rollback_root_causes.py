# -*- coding: utf-8 -*-
"""
Tests for Rollback Engine Root Cause Fixes:
1. Stop Line Merging: consecutive line edits (e.g. c1, c2) are kept strictly separate.
2. Safe Reject: restores file to original without duplicate parameters or lost arguments.
3. Cascade Reject disk check: tokens used across multiple files on disk are preserved.
4. Record All Changed Lines: diff hunks (imports + parameters) recorded without early break.
5. No Double Patching: reject_all_files does not mangle files already restored from backup.
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

from core.pattern_journal import PatternJournal
from editor.journal_helpers import _journal_save


class TestRollbackRootCauses(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_rollback_rc_test_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_consecutive_lines_no_merging_and_clean_rollback(self):
        """
        Verify that consecutive edits on lines 2 and 3:
        c1 = Color(0xFF10B981) -> c1 = AppColors.AdaptiveActionCardRedAccent
        c2 = Color(0xFF059669) -> c2 = AppColors.AdaptiveActionCardRedAccent
        are recorded as TWO distinct journal entries (not merged into one),
        and rollback restores both c1 and c2 cleanly without duplicating c1.
        """
        orig_content = """package com.edu.teacher.ui.widgets

import androidx.compose.ui.graphics.Color

fun SampleWidget() {
    val card = Card(
        c1 = Color(0xFF10B981),
        c2 = Color(0xFF059669)
    )
}
"""
        target_file = self.root / "QuickActionsWidget.kt"
        target_file.write_text(orig_content, encoding="utf-8")

        # Create .bridge.bak before edit
        bak_file = target_file.with_name(target_file.name + ".bridge.bak")
        bak_file.write_text(orig_content, encoding="utf-8")

        # New content with both c1 and c2 modified
        modified_content = """package com.edu.teacher.ui.widgets

import androidx.compose.ui.graphics.Color
import com.edu.teacher.ui.theme.AppColors

fun SampleWidget() {
    val card = Card(
        c1 = AppColors.AdaptiveActionCardRedAccent,
        c2 = AppColors.AdaptiveActionCardRedAccent
    )
}
"""
        target_file.write_text(modified_content, encoding="utf-8")

        pj = PatternJournal(self.root)
        pj.record_change(
            file="QuickActionsWidget.kt",
            line=8,
            old_line="        c1 = Color(0xFF10B981),",
            new_line="        c1 = AppColors.AdaptiveActionCardRedAccent,",
            pattern_id="pat_c1",
        )
        pj.record_change(
            file="QuickActionsWidget.kt",
            line=9,
            old_line="        c2 = Color(0xFF059669)",
            new_line="        c2 = AppColors.AdaptiveActionCardRedAccent",
            pattern_id="pat_c2",
        )

        entries = pj.get_file_changes("QuickActionsWidget.kt")
        # Line merging must NOT have occurred:
        self.assertEqual(len(entries), 2, "Consecutive line changes must be recorded as 2 separate entries")
        lines = [e["line"] for e in entries]
        self.assertIn(8, lines)
        self.assertIn(9, lines)

        # Rollback via reject_file_changes
        res = pj.reject_file_changes("QuickActionsWidget.kt")
        self.assertTrue(res.get("success"), f"Rollback failed: {res}")

        restored_content = target_file.read_text(encoding="utf-8")
        self.assertIn("c1 = Color(0xFF10B981),", restored_content)
        self.assertIn("c2 = Color(0xFF059669)", restored_content)
        self.assertNotIn("c1 = Color(0xFF10B981),\n        c1 =", restored_content)
        self.assertEqual(restored_content.count("c1 ="), 1)
        self.assertEqual(restored_content.count("c2 ="), 1)

    def test_cascade_preserves_token_used_in_other_file_on_disk(self):
        """
        Verify that if token AdaptiveActionCardRedAccent is used in HomeScreen.kt on disk,
        rejecting QuickActionsWidget.kt does NOT remove the token from DesignSystem.kt.
        """
        ds_file = self.root / "DesignSystem.kt"
        ds_file.write_text("""package com.edu.teacher.ui.theme

import androidx.compose.ui.graphics.Color

object AppColors {
    val AdaptiveActionCardRedAccent = Color(0xFFEF4444)
}
""", encoding="utf-8")

        home_file = self.root / "HomeScreen.kt"
        home_file.write_text("""package com.edu.teacher.ui

import androidx.compose.ui.graphics.Color
import com.edu.teacher.ui.theme.AppColors

fun HomeHeader() {
    val bg = AppColors.AdaptiveActionCardRedAccent
}
""", encoding="utf-8")

        qa_file = self.root / "QuickActionsWidget.kt"
        qa_file.write_text("""package com.edu.teacher.ui.widgets

import androidx.compose.ui.graphics.Color
import com.edu.teacher.ui.theme.AppColors

fun QuickActions() {
    val c1 = AppColors.AdaptiveActionCardRedAccent
}
""", encoding="utf-8")
        bak_file = qa_file.with_name(qa_file.name + ".bridge.bak")
        bak_file.write_text("""package com.edu.teacher.ui.widgets

import androidx.compose.ui.graphics.Color

fun QuickActions() {
    val c1 = Color(0xFF10B981)
}
""", encoding="utf-8")

        pj = PatternJournal(self.root)
        pj.record_token_added(
            pattern_id="create_token_AdaptiveActionCardRedAccent",
            token_name="AdaptiveActionCardRedAccent",
            token_value="0xFFEF4444",
            file="DesignSystem.kt"
        )
        pj.record_change(
            file="QuickActionsWidget.kt",
            line=7,
            old_line="    val c1 = Color(0xFF10B981)",
            new_line="    val c1 = AppColors.AdaptiveActionCardRedAccent",
            pattern_id="create_token_AdaptiveActionCardRedAccent"
        )

        res = pj.reject_file_changes("QuickActionsWidget.kt")
        self.assertTrue(res.get("success"), f"Reject failed: {res}")

        # DesignSystem.kt MUST STILL CONTAIN AdaptiveActionCardRedAccent because HomeScreen uses it on disk!
        ds_content = ds_file.read_text(encoding="utf-8")
        self.assertIn("AdaptiveActionCardRedAccent", ds_content)
        if res.get("warning"):
            self.assertIn("HomeScreen.kt", res["warning"])

    def test_journal_helpers_records_all_diff_hunks(self):
        """
        Verify that _journal_save records all modified hunks across the file (e.g. import + parameter)
        rather than stopping at the first difference.
        """
        orig_code = """package com.edu.teacher.ui

fun Screen() {
    val a = 1
    val b = 2
}
"""
        new_code = """package com.edu.teacher.ui

import androidx.compose.ui.graphics.Color

fun Screen() {
    val a = 1
    val b = 999
}
"""
        target = self.root / "Screen.kt"
        target.write_text(new_code, encoding="utf-8")

        _journal_save(target, orig_code, new_code, pattern_id="test_multi_hunk")

        pj = PatternJournal(self.root)
        changes = pj.get_file_changes("Screen.kt")
        # Must have recorded both the import addition and the parameter change:
        self.assertGreaterEqual(len(changes), 2, "Both import and parameter changes should be recorded")
        all_new = " ".join([c.get("new_line", "") or c.get("new", "") for c in changes])
        self.assertIn("import androidx.compose.ui.graphics.Color", all_new)
        self.assertIn("val b = 999", all_new)

    def test_reject_all_files_no_duplicate_patching(self):
        """
        Verify that reject_all_files restores files with .bridge.bak cleanly
        and does not corrupt them with secondary text replacement passes.
        """
        orig_file1 = "fun File1() {\n    val c = Color(0xFF111111)\n}\n"
        orig_file2 = "fun File2() {\n    val d = Color(0xFF222222)\n}\n"

        f1 = self.root / "File1.kt"
        f2 = self.root / "File2.kt"
        f1.write_text("fun File1() {\n    val c = AppColors.Token1\n}\n", encoding="utf-8")
        f2.write_text("fun File2() {\n    val d = AppColors.Token2\n}\n", encoding="utf-8")

        f1.with_name("File1.kt.bridge.bak").write_text(orig_file1, encoding="utf-8")
        f2.with_name("File2.kt.bridge.bak").write_text(orig_file2, encoding="utf-8")

        pj = PatternJournal(self.root)
        pj.record_change(file="File1.kt", line=2, old_line="    val c = Color(0xFF111111)", new_line="    val c = AppColors.Token1")
        pj.record_change(file="File2.kt", line=2, old_line="    val d = Color(0xFF222222)", new_line="    val d = AppColors.Token2")

        res = pj.reject_all_files()
        self.assertTrue(res.get("success"), f"reject_all_files failed: {res}")

        # Both files must match original baseline exactly
        self.assertEqual(f1.read_text(encoding="utf-8"), orig_file1)
        self.assertEqual(f2.read_text(encoding="utf-8"), orig_file2)


    def test_migrate_creates_bridge_bak_and_records_in_journal(self):
        """
        Verify that TokenMigrator.migrate creates .bridge.bak alongside both files
        and records changes in PatternJournal for both DesignSystem.kt and target widget.
        """
        from core.token_migrator import TokenMigrator

        ds = self.root / "DesignSystem.kt"
        ds.write_text("""package com.edu.teacher.ui.theme

import androidx.compose.ui.graphics.Color

object AppColors {
    val Primary = Color(0xFF14B8A6)
}
""", encoding="utf-8")

        widget = self.root / "MyWidget.kt"
        widget.write_text("""package com.edu.teacher.ui

import androidx.compose.ui.graphics.Color
import com.edu.teacher.ui.theme.AppColors

fun MyWidget() {
    val bg = Color(0xFFABCDEF)
}
""", encoding="utf-8")

        migrator = TokenMigrator(self.root)
        ok, msg, info = migrator.migrate(
            file_name="MyWidget.kt",
            line=7,
            value="Color(0xFFABCDEF)",
            token_name="WidgetBgColor",
            token_type="color",
            force_create=True,
        )
        self.assertTrue(ok, f"Migrate failed: {msg}")

        # 1. Verify .bridge.bak exists alongside BOTH files
        ds_bak = ds.with_name("DesignSystem.kt.bridge.bak")
        widget_bak = widget.with_name("MyWidget.kt.bridge.bak")
        self.assertTrue(ds_bak.exists(), "DesignSystem.kt.bridge.bak must be created")
        self.assertTrue(widget_bak.exists(), "MyWidget.kt.bridge.bak must be created")

        # 2. Verify PatternJournal recorded both files
        pj = PatternJournal(self.root)
        modified = pj.list_modified_files()
        mod_names = [Path(m["file"]).name for m in modified]
        self.assertIn("DesignSystem.kt", mod_names)
        self.assertIn("MyWidget.kt", mod_names)

        # 3. Verify rollbacks work cleanly from backups
        res = pj.reject_file_changes("MyWidget.kt")
        self.assertTrue(res.get("success"), f"Rollback failed: {res}")
        self.assertIn("Color(0xFFABCDEF)", widget.read_text(encoding="utf-8"))

    def test_atomic_cascade_reject_refuses_deletion_if_target_file_not_reverted(self):
        """
        Verify that _handle_cascade_token_reject does NOT delete the token from DesignSystem.kt
        if the target file on disk still contains the token (e.g. because its rollback failed or wasn't done).
        """
        ds = self.root / "DesignSystem.kt"
        ds.write_text("""package com.edu.teacher.ui.theme

import androidx.compose.ui.graphics.Color

object AppColors {
    val FragileToken = Color(0xFF123456)
}
""", encoding="utf-8")

        widget = self.root / "FragileWidget.kt"
        widget.write_text("""package com.edu.teacher.ui

import com.edu.teacher.ui.theme.AppColors

fun FragileWidget() {
    val color = AppColors.FragileToken
}
""", encoding="utf-8")

        pj = PatternJournal(self.root)
        pj.record_token_added(
            pattern_id="create_token_FragileToken",
            token_name="FragileToken",
            token_value="0xFF123456",
            file="DesignSystem.kt",
        )

        # Simulate cascade reject where FragileWidget STILL has AppColors.FragileToken on disk:
        cascade_res = pj._handle_cascade_token_reject(
            file_path="FragileWidget.kt",
            file_changes=[{"pattern_id": "create_token_FragileToken", "new": "AppColors.FragileToken"}]
        )

        # Atomic check MUST refuse to delete FragileToken from DesignSystem.kt!
        self.assertNotIn("FragileToken", cascade_res.get("removed_tokens", []))
        self.assertIn("FragileToken", ds.read_text(encoding="utf-8"))
        self.assertIsNotNone(cascade_res.get("warning"))
        self.assertIn("FragileWidget.kt", cascade_res.get("warning", ""))


    def test_dependency_guard_refuses_reject_of_design_system_if_token_used_by_widget(self):
        """
        Verify that reject_file_changes on DesignSystem.kt is REFUSED if an approved/current
        file (e.g. QuickActionsWidget.kt) on disk uses a token that would be destroyed by the rollback.
        """
        ds_orig = """package com.edu.teacher.ui.theme
import androidx.compose.ui.graphics.Color
object AppColors {
    val BaseRed = Color(0xFFEF4444)
}
"""
        ds_with_token = """package com.edu.teacher.ui.theme
import androidx.compose.ui.graphics.Color
object AppColors {
    val AdaptiveActionCardPinkAccent: Color get() = BridgeThemeRegistry.getColor("AdaptiveActionCardPinkAccent", Color(0xFFEC4899))
    val BaseRed = Color(0xFFEF4444)
}
"""
        ds_file = self.root / "DesignSystem.kt"
        ds_file.write_text(ds_with_token, encoding="utf-8")

        # Backup of DesignSystem.kt does NOT have AdaptiveActionCardPinkAccent
        ds_bak = ds_file.with_name(ds_file.name + ".bridge.bak")
        ds_bak.write_text(ds_orig, encoding="utf-8")

        # QuickActionsWidget on disk uses AdaptiveActionCardPinkAccent
        widget_file = self.root / "QuickActionsWidget.kt"
        widget_file.write_text("""package com.edu.teacher.ui.widgets
import com.edu.teacher.ui.theme.AppColors
fun QuickActions() {
    val c = AppColors.AdaptiveActionCardPinkAccent
}
""", encoding="utf-8")

        pj = PatternJournal(self.root)
        pj.record_token_added(
            pattern_id="create_token_AdaptiveActionCardPinkAccent",
            token_name="AdaptiveActionCardPinkAccent",
            token_value="0xFFEC4899",
            file="DesignSystem.kt",
        )

        # Attempt to reject DesignSystem.kt while QuickActionsWidget.kt depends on it
        res = pj.reject_file_changes("DesignSystem.kt")

        # MUST be refused by Dependency Guard!
        self.assertFalse(res.get("success"), f"Expected rejection to be refused, but got: {res}")
        self.assertIn("Cannot reject DesignSystem.kt because its tokens are used by other approved files", res.get("error", ""))
        self.assertIn("QuickActionsWidget.kt", res.get("error", ""))
        self.assertIn("AdaptiveActionCardPinkAccent", res.get("error", ""))

        # Verify token is STILL in DesignSystem.kt (not reverted!)
        self.assertIn("AdaptiveActionCardPinkAccent", ds_file.read_text(encoding="utf-8"))

    def test_dependency_guard_auto_approves_design_system_when_widget_is_approved(self):
        """
        Verify that approve_file_changes on QuickActionsWidget.kt automatically approves
        DesignSystem.kt as well if it has unapproved changes or an active .bridge.bak.
        """
        ds_file = self.root / "DesignSystem.kt"
        ds_file.write_text("""package com.edu.teacher.ui.theme
import androidx.compose.ui.graphics.Color
object AppColors {
    val AdaptiveActionCardPinkAccent: Color get() = BridgeThemeRegistry.getColor("AdaptiveActionCardPinkAccent", Color(0xFFEC4899))
}
""", encoding="utf-8")
        ds_bak = ds_file.with_name(ds_file.name + ".bridge.bak")
        ds_bak.write_text("""package com.edu.teacher.ui.theme
object AppColors {}
""", encoding="utf-8")

        widget_file = self.root / "QuickActionsWidget.kt"
        widget_file.write_text("""package com.edu.teacher.ui.widgets
import com.edu.teacher.ui.theme.AppColors
fun QuickActions() {
    val c = AppColors.AdaptiveActionCardPinkAccent
}
""", encoding="utf-8")
        widget_bak = widget_file.with_name(widget_file.name + ".bridge.bak")
        widget_bak.write_text("""package com.edu.teacher.ui.widgets
fun QuickActions() {
    val c = Color.Red
}
""", encoding="utf-8")

        pj = PatternJournal(self.root)
        pj.record_change(
            file="QuickActionsWidget.kt",
            line=3,
            old_line="val c = Color.Red",
            new_line="val c = AppColors.AdaptiveActionCardPinkAccent",
            pattern_id="quick_actions_edit",
        )
        pj.record_token_added(
            pattern_id="create_token_AdaptiveActionCardPinkAccent",
            token_name="AdaptiveActionCardPinkAccent",
            token_value="0xFFEC4899",
            file="DesignSystem.kt",
        )

        # Approve QuickActionsWidget.kt
        res = pj.approve_file_changes("QuickActionsWidget.kt")
        self.assertTrue(res.get("success"), f"Approval failed: {res}")

        # Widget backup must be gone
        self.assertFalse(widget_bak.exists(), "QuickActionsWidget.kt.bridge.bak should be deleted")

        # Dependency Guard: DesignSystem.kt backup MUST ALSO be gone (auto-approved!)
        self.assertFalse(ds_bak.exists(), "DesignSystem.kt.bridge.bak should be deleted by auto-approval!")


if __name__ == "__main__":
    unittest.main()


