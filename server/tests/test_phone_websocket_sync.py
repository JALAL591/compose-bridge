
# -*- coding: utf-8 -*-
"""
Unit test for Phone WebSocket synchronization, journal recording, and zero silent modifications.

Verifies:
1. When phone sends a state_update (color), file is modified on disk, .bridge.bak is created,
   the change is recorded in PatternJournal, and refresh_element_request + modified_files_list
   are broadcast to all connected clients.
2. When phone sends update_token_default (dimension), file is updated, recorded in journal,
   and broadcast is triggered.
3. Disk reconciliation: Untracked disk modifications with .bridge.bak are automatically
   reconciled and persisted into pattern_journal.jsonl during list_modified_files().
4. apply_safe_edit pipeline enforces dirty buffer guard, backup, atomic write, and broadcast.
"""

import os
import sys
import json
import shutil
import asyncio
import tempfile
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from network.ws_server import (
    CONNECTED_CLIENTS,
    AUTHENTICATED_CLIENTS,
    broadcast,
    broadcast_refresh,
    broadcast_changes_updated,
)
from network.message_router import handle_message
from core.pattern_journal import PatternJournal
from common.file_ops import apply_safe_edit, mark_file_dirty_in_ide


class MockWebSocket:
    def __init__(self, addr=("192.168.1.50", 54321)):
        self.remote_address = addr
        self.sent_messages = []
        self.state = type("State", (), {"name": "OPEN"})()

    async def send(self, msg):
        self.sent_messages.append(msg)

    async def close(self, code=1000, reason=""):
        self.state.name = "CLOSED"


class TestPhoneWebSocketSync(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_phone_sync_test_")
        self.root = Path(self.test_dir)
        os.environ["COMPOSEBRIDGE_ROOT"] = str(self.root)

        # Create dummy DesignSystem.kt
        self.ds_file = self.root / "DesignSystem.kt"
        self.ds_file.write_text("""package com.example.theme

import androidx.compose.ui.graphics.Color

object AppColors {
    val Primary = Color(0xFF14B8A6)
}
""", encoding="utf-8")

        # Create dummy AppDimens.kt
        self.dimens_file = self.root / "AppDimens.kt"
        self.dimens_file.write_text("""package com.example.theme

import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

object AppDimens {
    val CardCorner: Dp = 16.dp
}
""", encoding="utf-8")

        # Clear client sets
        CONNECTED_CLIENTS.clear()
        AUTHENTICATED_CLIENTS.clear()

        # Update Project Root in ws_server
        import network.ws_server as ws_mod
        ws_mod.PROJECT_ROOT = self.root

    def tearDown(self):
        CONNECTED_CLIENTS.clear()
        AUTHENTICATED_CLIENTS.clear()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_phone_color_update_records_journal_and_broadcasts(self):
        """Simulates phone WebSocket color edit and verifies zero silent modification."""
        async def _run():
            phone_ws = MockWebSocket(addr=("192.168.1.50", 50001))
            ide_ws = MockWebSocket(addr=("127.0.0.1", 50002))

            CONNECTED_CLIENTS.add(phone_ws)
            AUTHENTICATED_CLIENTS.add(phone_ws)
            CONNECTED_CLIENTS.add(ide_ws)
            AUTHENTICATED_CLIENTS.add(ide_ws)

            # Send state_update message from phone
            msg = json.dumps({
                "type": "state_update",
                "property": "AppColors.Primary",
                "value": "#00FF00"
            })
            await handle_message(phone_ws, msg)

            # 1. Verify file modified on disk
            content = self.ds_file.read_text(encoding="utf-8")
            self.assertIn("0xFF00FF00", content)

            # 2. Verify .bridge.bak exists
            bak_file = self.root / "DesignSystem.kt.bridge.bak"
            self.assertTrue(bak_file.exists())
            self.assertIn("0xFF14B8A6", bak_file.read_text(encoding="utf-8"))

            # 3. Verify modification recorded in PatternJournal
            journal = PatternJournal(self.root)
            modified_files = journal.list_modified_files()
            file_names = [Path(f["file"]).name for f in modified_files]
            self.assertIn("DesignSystem.kt", file_names)

            # 4. Verify broadcast messages sent to IDE client
            ide_msg_types = []
            for raw_m in ide_ws.sent_messages:
                try:
                    parsed = json.loads(raw_m)
                    ide_msg_types.append(parsed.get("type"))
                except Exception:
                    pass

            # IDE must receive refresh signal and modified files list
            self.assertIn("refresh_element_request", ide_msg_types)
            self.assertIn("modified_files_list", ide_msg_types)

            # Check modified_files_list payload
            list_msg = [json.loads(m) for m in ide_ws.sent_messages if '"modified_files_list"' in m][0]
            listed_names = [f["name"] for f in list_msg.get("files", [])]
            self.assertIn("DesignSystem.kt", listed_names)

        asyncio.run(_run())

    def test_02_phone_dimension_update_records_journal_and_broadcasts(self):
        """Simulates phone WebSocket dimension token edit."""
        async def _run():
            phone_ws = MockWebSocket(addr=("192.168.1.50", 50001))
            ide_ws = MockWebSocket(addr=("127.0.0.1", 50002))

            CONNECTED_CLIENTS.add(phone_ws)
            AUTHENTICATED_CLIENTS.add(phone_ws)
            CONNECTED_CLIENTS.add(ide_ws)
            AUTHENTICATED_CLIENTS.add(ide_ws)

            msg = json.dumps({
                "type": "update_token_default",
                "token": "CardCorner",
                "value": "28"
            })
            await handle_message(phone_ws, msg)

            # Verify file modified
            content = self.dimens_file.read_text(encoding="utf-8")
            self.assertIn("28", content)

            # Verify recorded in journal
            journal = PatternJournal(self.root)
            modified_files = journal.list_modified_files()
            file_names = [Path(f["file"]).name for f in modified_files]
            self.assertIn("AppDimens.kt", file_names)

            # Verify IDE received refresh broadcast
            ide_msg_types = [json.loads(m).get("type") for m in ide_ws.sent_messages]
            self.assertIn("refresh_element_request", ide_msg_types)
            self.assertIn("modified_files_list", ide_msg_types)

        asyncio.run(_run())

    def test_03_disk_reconciliation_detects_untracked_bridge_bak(self):
        """Verifies disk reconciliation auto-detects and records untracked modified files."""
        untracked = self.root / "CustomComponent.kt"
        untracked_bak = self.root / "CustomComponent.kt.bridge.bak"

        untracked_bak.write_text("""package com.example.ui
val size = 10.dp
""", encoding="utf-8")

        untracked.write_text("""package com.example.ui
val size = 20.dp
""", encoding="utf-8")

        journal = PatternJournal(self.root)
        # File is not in pattern_journal.jsonl initially
        entries_before = journal._read_entries()
        self.assertFalse(any("CustomComponent.kt" in e.get("file", "") for e in entries_before))

        # Calling list_modified_files() must detect and reconcile it
        modified = journal.list_modified_files()
        file_names = [Path(f["file"]).name for f in modified]
        self.assertIn("CustomComponent.kt", file_names)

        # Must also be persisted into journal entries
        entries_after = journal._read_entries()
        reconciled = [e for e in entries_after if "CustomComponent.kt" in e.get("file", "")]
        self.assertTrue(len(reconciled) > 0)
        self.assertEqual(reconciled[0].get("pattern_id"), "reconciled_disk_edit")

    def test_04_apply_safe_edit_pipeline(self):
        """Verifies unified apply_safe_edit enforces dirty buffer guard and safe editing."""
        test_file = self.root / "SafeTarget.kt"
        test_file.write_text("""package com.example
val number = 1
""", encoding="utf-8")

        # 1. Test dirty buffer guard
        mark_file_dirty_in_ide(test_file, is_dirty=True, project_root=self.root)
        ok, msg, _ = apply_safe_edit(test_file, """package com.example
val number = 2
""", project_root=self.root)
        self.assertFalse(ok)
        self.assertIn("غير محفوظة", msg)

        # 2. Unmark dirty buffer and apply
        mark_file_dirty_in_ide(test_file, is_dirty=False, project_root=self.root)
        ok2, msg2, bak_path = apply_safe_edit(test_file, """package com.example
val number = 2
""", pattern_id="phone_manual_edit", project_root=self.root)
        self.assertTrue(ok2)
        self.assertTrue(bak_path.exists())

        # Check content and journal
        self.assertIn("val number = 2", test_file.read_text(encoding="utf-8"))
        journal = PatternJournal(self.root)
        modified = journal.list_modified_files()
        self.assertIn("SafeTarget.kt", [Path(f["file"]).name for f in modified])


if __name__ == "__main__":
    unittest.main()