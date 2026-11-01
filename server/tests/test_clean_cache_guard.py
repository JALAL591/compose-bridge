# -*- coding: utf-8 -*-
"""
Unit tests for Clean Cache Guard.
Validates:
1. When no pending edits exist, clean cache is allowed.
2. When pending edits exist in the journal, clean cache is refused with PENDING_EDITS_EXIST.
3. Journal and backups are preserved on disk when clean cache is refused.
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

from core.clean_cache_guard import should_allow_clean_cache
from core.project_root import clean_temp_files


class TestCleanCacheGuard(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_clean_cache_guard_test_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_clean_cache_allowed_when_no_pending_edits(self):
        """Clean cache should be permitted when the journal is empty or absent."""
        can_clean, msg = should_allow_clean_cache(self.root)
        self.assertTrue(can_clean)
        self.assertEqual(msg, "Safe to clean.")

        res = clean_temp_files(self.root)
        self.assertTrue(res.get("success"))
        self.assertIn("cleaned safely", res.get("message", "").lower())

    def test_clean_cache_refused_when_pending_edits_exist(self):
        """Clean cache must be blocked if pending edits are found in pattern_journal.jsonl."""
        state_dir = self.root / ".composebridge-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        journal = state_dir / "pattern_journal.jsonl"

        entry1 = {"file": "ui/widgets/Card.kt", "line": 10, "old": "Color.Red", "new": "AppColors.Primary"}
        entry2 = {"file": "ui/widgets/Button.kt", "line": 20, "old": "12.dp", "new": "AppDimens.PaddingSmall"}

        with open(journal, "w", encoding="utf-8") as f:
            f.write(json.dumps(entry1) + "\n")
            f.write(json.dumps(entry2) + "\n")

        # 1. Guard function check
        can_clean, msg = should_allow_clean_cache(self.root)
        self.assertFalse(can_clean)
        self.assertIn("There are 2 pending edit(s)", msg)
        self.assertIn("Approve or Reject", msg)

        # 2. clean_temp_files execution check
        res = clean_temp_files(self.root)
        self.assertFalse(res.get("success"))
        self.assertEqual(res.get("error_code"), "PENDING_EDITS_EXIST")
        self.assertIn("Please Approve or Reject", res.get("error", ""))

        # 3. Verify journal file was NOT deleted!
        self.assertTrue(journal.exists(), "pattern_journal.jsonl should be preserved when clean cache is refused")
        lines = journal.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)

    def test_clean_cache_allowed_after_journal_cleared(self):
        """Once pending edits are cleared, clean cache should succeed immediately."""
        state_dir = self.root / ".composebridge-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        journal = state_dir / "pattern_journal.jsonl"
        journal.write_text("", encoding="utf-8")

        can_clean, msg = should_allow_clean_cache(self.root)
        self.assertTrue(can_clean)

        res = clean_temp_files(self.root)
        self.assertTrue(res.get("success"))


if __name__ == "__main__":
    unittest.main()

