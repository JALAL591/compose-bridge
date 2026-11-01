# -*- coding: utf-8 -*-
import unittest
import tempfile
import shutil
import json
from pathlib import Path
from core.project_root import clean_temp_files
from core.auth_manager import get_or_create_auth_token, verify_token, set_dev_token


class TestTokenPersistence(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_token_persist_")
        self.root = Path(self.test_dir)
        set_dev_token(None)

    def tearDown(self):
        set_dev_token(None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_clean_temp_files_preserves_auth_token(self):
        state_dir = self.root / ".composebridge-state"
        state_dir.mkdir(parents=True, exist_ok=True)

        token_file = state_dir / "auth_token.txt"
        initial_token = "abcd1234ef567890abcd1234ef567890abcd1234ef567890abcd1234ef567890"
        token_file.write_text(initial_token, encoding="utf-8")

        auth_json = state_dir / "auth.json"
        auth_json.write_text(json.dumps({"token": initial_token}), encoding="utf-8")

        # Create temporary files that should be cleaned
        cache_file = state_dir / "temp_cache.json"
        cache_file.write_text("{}", encoding="utf-8")

        tmp_file = self.root / "test.tmp"
        tmp_file.write_text("temp", encoding="utf-8")

        # Run clean_temp_files
        res = clean_temp_files(self.root)
        self.assertTrue(res.get("success"))

        # Verify auth_token.txt and auth.json STILL EXIST and UNTOUCHED
        self.assertTrue(token_file.exists(), "auth_token.txt must NEVER be deleted by clean_temp_files")
        self.assertEqual(token_file.read_text(encoding="utf-8").strip(), initial_token)
        self.assertTrue(auth_json.exists(), "auth.json must NEVER be deleted by clean_temp_files")

        # Verify temporary files WERE deleted
        self.assertFalse(cache_file.exists(), "Temporary cache inside state_dir must be cleaned")
        self.assertFalse(tmp_file.exists(), "*.tmp files must be cleaned")

        # Verify token retrieval returns the exact same persisted token
        retrieved_token = get_or_create_auth_token(self.root)
        self.assertEqual(retrieved_token, initial_token)
        self.assertTrue(verify_token(initial_token, self.root))


if __name__ == "__main__":
    unittest.main()

