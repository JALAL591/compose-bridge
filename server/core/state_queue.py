# -*- coding: utf-8 -*-
"""
State Queue — User pending edits.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class UserQueue:
    """Manages user queued edits."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.edits: List[dict] = []
    
    def add(self, token: str, value: str, source: str = "user",
            kind: str = "dimension") -> dict:
        """
        Add an edit to the queue.
        
        Args:
            token: Token name (e.g., "welcomeCardHeight" or "Primary")
            value: New value (e.g., "240" or "#EF4444")
            source: "user" | "agent"
            kind: "dimension" | "color"
        """
        entry = {
            "token": token,
            "value": value,
            "source": source,
            "kind": kind,  # ⭐ جديد
            "queued_at": datetime.utcnow().isoformat(),
            "id": f"edit_{len(self.edits) + 1}_{int(datetime.utcnow().timestamp())}",
        }
        self.edits.append(entry)
        return entry
    
    def remove(self, edit_id: str) -> bool:
        """Remove an edit by ID."""
        for i, e in enumerate(self.edits):
            if e["id"] == edit_id:
                self.edits.pop(i)
                return True
        return False
    
    def remove_by_token(self, token: str) -> int:
        """Remove all edits for a specific token. Returns count removed."""
        before = len(self.edits)
        self.edits = [e for e in self.edits if e["token"] != token]
        return before - len(self.edits)
    
    def clear(self):
        """Clear all edits."""
        self.edits = []
    
    def count(self) -> int:
        return len(self.edits)
    
    def get_all(self) -> List[dict]:
        return list(self.edits)
    
    def save(self):
        self.file_path.write_text(
            json.dumps(self.edits, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    
    def load(self):
        if not self.file_path.exists():
            return
        try:
            self.edits = json.loads(self.file_path.read_text(encoding="utf-8"))
        except Exception:
            self.edits = []
