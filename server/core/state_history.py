# -*- coding: utf-8 -*-
"""
State History — Value and Location histories (independent).
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class StateHistory:
    """
    Tracks value and location changes separately.
    
    Key insight: Value and Location are independent dimensions.
    Agent changes Location only.
    User changes Value only.
    """
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.value_history: Dict[str, List[dict]] = {}
        self.location_history: Dict[str, List[dict]] = {}
    
    def record_value(
        self,
        token: str,
        old_value: str,
        new_value: str,
        source: str,
    ) -> dict:
        """Record a value change."""
        entry = {
            "old": old_value,
            "new": new_value,
            "source": source,  # "user" | "agent" | "snapshot"
            "at": datetime.utcnow().isoformat(),
            "status": "applied",  # applied | rejected | pending
        }
        self.value_history.setdefault(token, []).append(entry)
        return entry
    
    def record_location(
        self,
        token: str,
        old_loc: str,
        new_loc: str,
        source: str,
    ) -> dict:
        """Record a location change."""
        entry = {
            "old": old_loc,  # "file.kt:line"
            "new": new_loc,
            "source": source,
            "at": datetime.utcnow().isoformat(),
            "status": "pending",  # pending | accepted | rejected
        }
        self.location_history.setdefault(token, []).append(entry)
        return entry
    
    def get_current_value(self, token: str) -> Optional[str]:
        """Get latest applied value."""
        history = self.value_history.get(token, [])
        for entry in reversed(history):
            if entry["status"] == "applied":
                return entry["new"]
        return None
    
    def get_current_location(self, token: str) -> Optional[str]:
        """Get latest non-rejected location."""
        history = self.location_history.get(token, [])
        for entry in reversed(history):
            if entry["status"] != "rejected":
                return entry["new"]
        return None
    
    def save(self):
        data = {
            "value_history": self.value_history,
            "location_history": self.location_history,
        }
        self.file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    
    def load(self):
        if not self.file_path.exists():
            return
        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
            self.value_history = data.get("value_history", {})
            self.location_history = data.get("location_history", {})
        except Exception:
            pass
