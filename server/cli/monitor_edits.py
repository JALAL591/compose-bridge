# -*- coding: utf-8 -*-
import sys
from pathlib import Path
_bridge_dir = Path(__file__).resolve().parent.parent
if str(_bridge_dir) not in sys.path:
    sys.path.insert(0, str(_bridge_dir))
# -*- coding: utf-8 -*-
"""
ComposeBridge Live Audit & Monitor CLI
Monitors in real time:
1. When an edit command is received (via WebSocket or Agent).
2. When a backup (.bridge.bak) is created or preserved.
3. When the source file (.kt) is modified.
4. When changes are approved or rejected.
"""

import os
import sys
import time
import json
import asyncio
from datetime import datetime
from pathlib import Path

# ANSI Colors
C_GREEN = "\033[92m"
C_BLUE = "\033[94m"
C_CYAN = "\033[96m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_PURPLE = "\033[95m"
C_BOLD = "\033[1m"
C_RESET = "\033[0m"


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def get_project_root():
    if "COMPOSEBRIDGE_ROOT" in os.environ:
        return Path(os.environ["COMPOSEBRIDGE_ROOT"])
    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parent.parent.parent,
        Path(".").resolve(),
    ]
    for c in candidates:
        if (c / ".composebridge-state").exists() or (c / "build.gradle.kts").exists():
            return c
    return Path(".").resolve()


class RealtimeMonitor:
    def __init__(self, root: Path):
        self.root = root
        self.state_dir = root / ".composebridge-state"
        self.events_file = self.state_dir / "events.jsonl"
        self.journal_file = self.state_dir / "pattern_journal.jsonl"
        
        self.known_backups = {}
        self.known_files = {}
        self.events_pos = 0
        self.journal_pos = 0

        # Snapshot initial state
        if self.events_file.exists():
            self.events_pos = self.events_file.stat().st_size
        if self.journal_file.exists():
            self.journal_pos = self.journal_file.stat().st_size

        self.scan_existing_backups()

    def scan_existing_backups(self):
        for b in self.root.rglob("*.bridge.bak"):
            if "build" not in str(b):
                self.known_backups[str(b)] = b.stat().st_mtime

    def check_events(self):
        if not self.events_file.exists():
            return
        curr_size = self.events_file.stat().st_size
        if curr_size > self.events_pos:
            try:
                with open(self.events_file, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(self.events_pos)
                    new_lines = f.readlines()
                    self.events_pos = f.tell()
                for line in new_lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                        t = ev.get("type", "")
                        details = ev.get("details", {})
                        source = ev.get("source", "system")

                        if "queue" in t or "color" in t or "edit" in t:
                            print(f"{C_BOLD}{C_CYAN}[{ts()}] 📥 [EDIT RECEIVED ({source.upper()})]{C_RESET}")
                            print(f"      🔹 Type:    {t}")
                            print(f"      🔹 Details: {json.dumps(details, ensure_ascii=False)}")
                        elif "reject" in t:
                            print(f"{C_BOLD}{C_RED}[{ts()}] ↩️ [REJECT TRIGGERED]{C_RESET}")
                            print(f"      🔹 Details: {json.dumps(details, ensure_ascii=False)}")
                        elif "accept" in t or "approve" in t:
                            print(f"{C_BOLD}{C_GREEN}[{ts()}] ✅ [APPROVE TRIGGERED]{C_RESET}")
                            print(f"      🔹 Details: {json.dumps(details, ensure_ascii=False)}")
                    except Exception:
                        pass
            except Exception:
                pass

    def check_journal(self):
        if not self.journal_file.exists():
            return
        curr_size = self.journal_file.stat().st_size
        if curr_size > self.journal_pos:
            try:
                with open(self.journal_file, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(self.journal_pos)
                    new_lines = f.readlines()
                    self.journal_pos = f.tell()
                for line in new_lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        f_name = Path(entry.get("file", "")).name
                        print(f"{C_BOLD}{C_PURPLE}[{ts()}] 📝 [JOURNAL RECORDED]{C_RESET}")
                        print(f"      📁 File:     {f_name}")
                        print(f"      📍 Line:     {entry.get('line', '?')}")
                        print(f"      🔴 Old:      {entry.get('old', '').strip()[:80]}")
                        print(f"      🟢 New:      {entry.get('new', '').strip()[:80]}")
                    except Exception:
                        pass
            except Exception:
                pass

    def check_backups_and_sources(self):
        try:
            # Check for new or modified .bridge.bak files
            current_baks = list(self.root.rglob("*.bridge.bak"))
            for b in current_baks:
                if "build" in str(b) or ".composebridge-state" in str(b):
                    continue
                b_str = str(b)
                mtime = b.stat().st_mtime
                if b_str not in self.known_backups:
                    self.known_backups[b_str] = mtime
                    size_kb = b.stat().st_size / 1024
                    orig_file = b.name.replace(".bridge.bak", "")
                    print(f"{C_BOLD}{C_YELLOW}[{ts()}] 📸 [BACKUP CREATED (FIRST BASELINE)]{C_RESET}")
                    print(f"      🛡️ Backup File: {b.name} ({size_kb:.2f} KB)")
                    print(f"      📄 Target File: {orig_file}")
                elif mtime > self.known_backups[b_str]:
                    self.known_backups[b_str] = mtime
                    print(f"{C_BOLD}{C_YELLOW}[{ts()}] ⚠️ [BACKUP TOUCHED / UPDATED]{C_RESET}")
                    print(f"      🛡️ File: {b.name}")

            # Check if any .bridge.bak was deleted (e.g. on Approve / Clean)
            deleted_baks = [b for b in self.known_backups if not Path(b).exists()]
            for d in deleted_baks:
                del self.known_backups[d]
                print(f"{C_BOLD}{C_GREEN}[{ts()}] 🗑️ [BACKUP CLEARED]{C_RESET} -> {Path(d).name} (Baseline reset)")

        except Exception:
            pass


async def ws_listener(root: Path):
    token_file = root / ".composebridge-state" / "auth_token.txt"
    token = token_file.read_text().strip() if token_file.exists() else ""
    uri = f"ws://127.0.0.1:8711?token={token}"
    
    import websockets
    while True:
        try:
            async with websockets.connect(uri) as ws:
                print(f"{C_BOLD}{C_GREEN}[{ts()}] 🔌 [WS CONNECTED]{C_RESET} Connected to ComposeBridge Server on port 8711")
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        m_type = msg.get("type", "")
                        if m_type == "pong":
                            continue
                        if m_type in ("state_update", "update_token_default", "mcp_state_update"):
                            print(f"{C_BOLD}{C_BLUE}[{ts()}] 📡 [LIVE WS TRAFFIC <- INCOMING EDIT]{C_RESET}")
                            print(f"      📦 Raw Msg: {raw[:150]}")
                        elif m_type == "broadcast_changes_updated":
                            print(f"{C_BOLD}{C_CYAN}[{ts()}] 📢 [LIVE WS BROADCAST -> MODIFIED FILES CHANGED]{C_RESET}")
                            print(f"      📦 Files: {msg.get('files', [])}")
                    except Exception:
                        pass
        except Exception:
            await asyncio.sleep(2)


async def main():
    root = get_project_root()
    print()
    print(f"{C_BOLD}{C_GREEN}════════════════════════════════════════════════════════════════════════{C_RESET}")
    print(f"{C_BOLD}{C_GREEN}  🔍 ComposeBridge Real-Time Edit & Backup Auditor{C_RESET}")
    print(f"{C_BOLD}{C_GREEN}════════════════════════════════════════════════════════════════════════{C_RESET}")
    print(f"  📂 Target Project: {root}")
    print(f"  👀 Watching for:  Edit requests (Phone/Agent), .bridge.bak backups, and file writes")
    print(f"  🛑 Press Ctrl+C to stop")
    print(f"{C_BOLD}{C_GREEN}════════════════════════════════════════════════════════════════════════{C_RESET}")
    print()

    monitor = RealtimeMonitor(root)

    # Launch background WS listener
    asyncio.create_task(ws_listener(root))

    while True:
        monitor.check_events()
        monitor.check_journal()
        monitor.check_backups_and_sources()
        await asyncio.sleep(0.08)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}[{ts()}] Auditor stopped.{C_RESET}")

