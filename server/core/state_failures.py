# -*- coding: utf-8 -*-
"""
State Failures — Track failed operations.
"""

import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime


class FailureTracker:
    """Tracks failed operations for notification."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.failures: List[dict] = []
    
    def record(
        self,
        operation: str,
        token: str,
        location: str,
        error: str,
        severity: str = "error",  # error | warning | info
    ) -> dict:
        """Record a failure."""
        entry = {
            "id": f"fail_{int(datetime.utcnow().timestamp() * 1000)}",
            "operation": operation,
            "token": token,
            "location": location,
            "error": error,
            "severity": severity,
            "at": datetime.utcnow().isoformat(),
            "resolved": False,
        }
        self.failures.append(entry)
        return entry
    
    def mark_resolved(self, failure_id: str) -> bool:
        for f in self.failures:
            if f["id"] == failure_id:
                f["resolved"] = True
                return True
        return False
    
    def get_unresolved(self) -> List[dict]:
        return [f for f in self.failures if not f["resolved"]]
    
    def save(self):
        self.file_path.write_text(
            json.dumps(self.failures, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    
    def load(self):
        if not self.file_path.exists():
            return
        try:
            self.failures = json.loads(
                self.file_path.read_text(encoding="utf-8")
            )
        except Exception:
            self.failures = []
