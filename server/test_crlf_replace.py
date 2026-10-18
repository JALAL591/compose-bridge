# -*- coding: utf-8 -*-
"""
Unit Test: CRLF Line Endings in Surgical Edit & Pattern Replacement
Verifies that files with \\r\\n (Windows CRLF) have exact byte offsets
and are edited without byte mismatch errors.
"""

import unittest
import shutil
import tempfile
from pathlib import Path
import sys

BRIDGE_DIR = Path(r"C:\Users\thinkpad\StudioProjects\compose-bridge\server")
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

from core.ast_finder import surgical_edit


class TestCRLFReplacement(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="cb_crlf_test_")
        self.test_file = Path(self.temp_dir) / "TestCRLFScreen.kt"

        # Generate a multi-line file with explicit Windows \r\n line endings
        lines = [
            "package com.test.ui\r\n",
            "\r\n",
            "import androidx.compose.ui.graphics.Color\r\n",
            "import androidx.compose.runtime.Composable\r\n",
        ]
        # Pad with 100 lines containing \r\n
        for i in range(100):
            lines.append(f"// padding line {i:03d} to shift offsets\r\n")

        lines.append("val targetColor = Color.White\r\n")
        lines.append("val afterColor = Color.Black\r\n")

        self.crlf_content = "".join(lines)
        with open(self.test_file, "wb") as f:
            f.write(self.crlf_content.encode("utf-8"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_crlf_exact_byte_offset_surgical_edit(self):
        """Verify surgical_edit succeeds on a file with 100+ CRLF lines."""
        source_bytes = self.test_file.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="replace")

        # Must use keepends=True to preserve \r\n byte count
        lines_with_ends = source_text.splitlines(keepends=True)

        # Find target line (line 104)
        target_line_idx = -1
        for idx, line in enumerate(lines_with_ends):
            if "val targetColor = Color.White" in line:
                target_line_idx = idx
                break

        self.assertNotEqual(target_line_idx, -1, "Target line must be found")

        target_line = lines_with_ends[target_line_idx]
        col_in_line = target_line.find("Color.White")
        self.assertNotEqual(col_in_line, -1)

        # Precise byte calculation preserving \r\n
        line_byte_start = len("".join(lines_with_ends[:target_line_idx]).encode("utf-8"))
        byte_start = line_byte_start + len(target_line[:col_in_line].encode("utf-8"))
        byte_end = byte_start + len("Color.White".encode("utf-8"))

        # Verify raw bytes at calculated range
        actual_val = source_bytes[byte_start:byte_end].decode("utf-8")
        self.assertEqual(actual_val, "Color.White", f"Expected 'Color.White', found '{actual_val}'")

        # Perform surgical edit
        ok, msg, backup = surgical_edit(
            file_path=str(self.test_file),
            byte_start=byte_start,
            byte_end=byte_end,
            expected_old_value="Color.White",
            new_value="AppColors.TextPrimary",
        )

        self.assertTrue(ok, f"Surgical edit must succeed: {msg}")

        # Verify edited content preserves CRLF
        edited_bytes = self.test_file.read_bytes()
        self.assertIn(b"\r\n", edited_bytes, "Line endings must still be CRLF")
        self.assertIn(b"val targetColor = AppColors.TextPrimary\r\n", edited_bytes)
        self.assertNotIn(b"Color.White", edited_bytes)


if __name__ == "__main__":
    unittest.main()
