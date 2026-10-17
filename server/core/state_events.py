# -*- coding: utf-8 -*-
"""
State Events — Append-only event log.
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime


class EventLog:
    """Append-only log of all state events."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.session_id = f"session_{int(datetime.utcnow().timestamp())}"
    
    def log(
        self,
        event_type: str,
        details: dict,
        source: str = "system",
    ):
        """
        Append an event.
        
        Types:
        - snapshot_captured
        - agent_start / agent_end
        - user_edit_queued
        - user_sync_start / user_sync_end
        - value_changed
        - location_moved
        - accept / reject
        - failure
        - build_reset
        """
        entry = {
            "t": datetime.utcnow().isoformat(),
            "session": self.session_id,
            "type": event_type,
            "source": source,
            "details": details,
        }
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def read_all(self, limit: Optional[int] = None) -> list:
        """Read all events (or last N)."""
        if not self.file_path.exists():
            return []
        lines = self.file_path.read_text(encoding="utf-8").splitlines()
        if limit:
            lines = lines[-limit:]
        return [json.loads(l) for l in lines if l.strip()]
    
    def clear(self):
        if self.file_path.exists():
            self.file_path.unlink()
