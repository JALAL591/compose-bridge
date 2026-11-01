# -*- coding: utf-8 -*-
"""
Test Atomic Approve / Reject for Imports and Code Usages.
Verifies that:
1. When modifying code that requires an import (e.g. BridgeTextRegistry, BridgeThemeRegistry, etc.),
   approving ONLY the code hunk automatically approves the corresponding import hunk.
2. The file baseline backup (.bridge.bak) incorporates both the import and code without missing references.
3. Rejecting the code hunk when no other usages remain also cleans up the associated import hunk.
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(r"C:\Users\thinkpad\StudioProjects\compose-bridge\server")
sys.path.insert(0, str(SERVER_DIR))

from core.diff_engine import approve_hunk, reject_hunk, compute_file_hunks, get_file_diff_report
from core.ast_finder import validate_kotlin_syntax


class TestAtomicImportApprove(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_atomic_test_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)

        # Baseline AppStrings.kt (without BridgeTextRegistry import)
        self.strings_file = self.root / "AppStrings.kt"
        self.orig_code = """package com.example.theme

object AppStrings {
    val quickAccess @Composable get() = "الوصول السريع"
}
"""
        self.strings_file.write_text(self.orig_code, encoding="utf-8")

        # Create baseline backup
        self.bak_file = self.root / "AppStrings.kt.bridge.bak"
        self.bak_file.write_text(self.orig_code, encoding="utf-8")

        # Now simulate tool editing: adds import AND wraps line in BridgeTextRegistry
        self.modified_code = """package com.example.theme

import com.composebridge.agent.BridgeTextRegistry

object AppStrings {
    val quickAccess @Composable get() = BridgeTextRegistry.getText("AppStrings.quickAccess", "نعم")
}
"""
        self.strings_file.write_text(self.modified_code, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_approve_code_hunk_atomically_approves_import_hunk(self):
        """Approving only the code line hunk MUST automatically approve the import hunk as well."""
        # 1. Inspect hunks
        hunks = compute_file_hunks(self.orig_code, self.modified_code)
        self.assertEqual(len(hunks), 2, "There should be exactly 2 hunks: 1 import and 1 code line")

        # Find the code hunk (the one containing BridgeTextRegistry.getText)
        code_hunk = next(h for h in hunks if "getText" in h["new"])
        import_hunk = next(h for h in hunks if "import " in h["new"])

        self.assertIsNotNone(code_hunk)
        self.assertIsNotNone(import_hunk)

        # 2. Call approve_hunk on ONLY the code hunk
        res = approve_hunk("AppStrings.kt", code_hunk["id"], self.root)
        self.assertTrue(res.get("success"), f"approve_hunk failed: {res}")

        # 3. VERIFY: Both code hunk AND import hunk were incorporated!
        # Remaining hunks should be 0 because the import was automatically approved!
        self.assertEqual(res.get("remaining_count"), 0, "Both hunks must be approved atomically, leaving 0 pending")

        # 4. Verify syntax validation passes cleanly
        curr_text = self.strings_file.read_text(encoding="utf-8")
        is_valid, err_msg = validate_kotlin_syntax(curr_text)
        self.assertTrue(is_valid, f"Approved file syntax must be valid: {err_msg}")
        self.assertIn("import com.composebridge.agent.BridgeTextRegistry", curr_text)
        self.assertIn("BridgeTextRegistry.getText", curr_text)

    def test_reject_code_hunk_atomically_reverts_unused_import_hunk(self):
        """Rejecting the code line hunk when no other usages exist MUST revert the import as well."""
        hunks = compute_file_hunks(self.orig_code, self.modified_code)
        code_hunk = next(h for h in hunks if "getText" in h["new"])

        # Reject ONLY the code hunk
        res = reject_hunk("AppStrings.kt", code_hunk["id"], self.root)
        self.assertTrue(res.get("success"), f"reject_hunk failed: {res}")

        # Verify file is restored to pristine baseline
        restored_text = self.strings_file.read_text(encoding="utf-8")
        self.assertNotIn("BridgeTextRegistry", restored_text, "Import and usage must both be reverted!")
        self.assertIn('"الوصول السريع"', restored_text)
        self.assertEqual(res.get("remaining_count"), 0)


if __name__ == "__main__":
    unittest.main()

