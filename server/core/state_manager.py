# -*- coding: utf-8 -*-
"""
State Manager — Coordinates all state modules.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from .state_snapshot import TokenSnapshot
from .state_queue import UserQueue
from .state_history import StateHistory
from .state_events import EventLog
from .state_failures import FailureTracker
from .file_watcher import FileWatcher


class StateManager:
    """
    Main coordinator.
    
    Combines: snapshot, queue, histories, events, failures, file watcher.
    """
    
    def __init__(self, project_root: Path, state_dir: Optional[Path] = None):
        self.project_root = project_root
        self.state_dir = state_dir or (project_root / ".composebridge-state")
        self.state_dir.mkdir(exist_ok=True)
        
        # Initialize modules
        self.snapshot = TokenSnapshot(project_root)
        self.queue = UserQueue(self.state_dir / "user_queue.json")
        self.history = StateHistory(self.state_dir / "history.json")
        self.events = EventLog(self.state_dir / "events.jsonl")
        self.failures = FailureTracker(self.state_dir / "failures.json")
        self.watcher = FileWatcher(project_root)
        
        # Runtime state
        self.environment: str = "unknown"  # accept_reject | direct_edit
        self.agent_busy: bool = False
    
    def init(self):
        """Load existing state or capture new snapshot."""
        self.queue.load()
        self.history.load()
        self.failures.load()
        self.watcher.initial_scan()
        
        # Load or capture snapshot
        snapshot_path = self.state_dir / "snapshot.json"
        if snapshot_path.exists():
            self.snapshot.load(snapshot_path)
            if not self.snapshot.tokens:
                self.capture_snapshot()
        else:
            self.capture_snapshot()
    
    def capture_snapshot(self):
        """Capture and persist a fresh snapshot."""
        self.snapshot.capture()
        self.snapshot.save(self.state_dir / "snapshot.json")
        self.events.log(
            "snapshot_captured",
            {"version": self.snapshot.version, "tokens": len(self.snapshot.tokens)},
        )
    
    def save_all(self):
        """Persist all state."""
        self.snapshot.save(self.state_dir / "snapshot.json")
        self.queue.save()
        self.history.save()
        self.failures.save()
    
    def reset(self):
        """Full reset — clear everything."""
        self.snapshot = TokenSnapshot(self.project_root)
        self.queue.clear()
        self.history = StateHistory(self.state_dir / "history.json")
        self.failures = FailureTracker(self.state_dir / "failures.json")
        self.events.clear()
        self.agent_busy = False
        self.capture_snapshot()
        self.save_all()
        self.events.log("full_reset", {})
    
    def set_agent_busy(self, busy: bool):
        """Update agent busy state."""
        self.agent_busy = busy
        self.events.log(
            "agent_start" if busy else "agent_end",
            {"environment": self.environment},
        )
    
    def check_for_external_changes(self) -> list:
        """
        Check for external file changes since last scan.
        Returns list of changes and updates history.
        """
        changes = self.watcher.check_once()
        
        for change in changes:
            # Record in event log
            self.events.log(
                "external_file_change",
                {
                    "file": str(change["path"]),
                    "old_hash": change.get("old_hash"),
                    "new_hash": change.get("new_hash"),
                    "deleted": change.get("deleted", False),
                },
                source="watcher",
            )
        
        return changes

    def apply_user_sync(self, dry_run: bool = False) -> dict:
        """
        Apply all queued user edits to their files.
        
        Re-anchors by token NAME (not location).
        
        Args:
            dry_run: if True, don't actually write files
        
        Returns:
            {
                "applied": [edit, ...],
                "skipped": [{"edit": edit, "reason": str}],
                "errors": [{"edit": edit, "error": str}],
            }
        """
        from core.write_lock import acquire_write_lock
        from .priority_resolver import PriorityResolver
        from .state_editor_helpers import find_token_in_project, apply_value_to_token
        
        result = {
            "applied": [],
            "skipped": [],
            "errors": [],
        }
        
        with acquire_write_lock():
            # ⭐ الفحص داخل الـ lock
            if self.agent_busy:
                return {
                    "applied": [],
                    "skipped": [],
                    "errors": [],
                    "refused": True,
                    "reason": "agent_busy",
                }
            
            resolver = PriorityResolver(self)
            
            for edit in self.queue.get_all():
                token = edit["token"]
                value = edit["value"]
                kind = edit.get("kind", "dimension")  # افتراضي للتوافق

                # ⭐ Re-anchor: find token location by NAME
                location = find_token_in_project(self.project_root, token)

                if location is None:
                    result["skipped"].append({
                        "edit": edit,
                        "reason": f"Token '{token}' not found in project",
                        "code": "TOKEN_NOT_FOUND",
                        "token": token,
                        "value": value,
                    })
                    self.failures.record(
                        operation="sync",
                        token=token,
                        location="unknown",
                        error=f"Token '{token}' not found (renamed or deleted?)",
                        severity="warning",
                    )
                    self.events.log(
                        "sync_token_not_found",
                        {"token": token, "value": value},
                        source="system",
                    )
                    continue

                if dry_run:
                    result["applied"].append({**edit, "location": location, "dry_run": True})
                    continue

                try:
                    if kind == "color":
                        # ⭐ استخدم update_color لـ الألوان
                        from core.state_editor import update_color
                        res = update_color(token, value)
                        success = res[0]
                        msg = res[1]
                    else:
                        # dimension
                        success, msg = apply_value_to_token(location, token, value)

                    if success:
                        self.history.record_value(
                            token=token,
                            old_value="",
                            new_value=value,
                            source="user",
                        )
                        self.events.log(
                            "user_sync_applied",
                            {"token": token, "value": value, "location": location, "kind": kind},
                            source="user",
                        )
                        result["applied"].append({**edit, "location": location})
                    else:
                        result["errors"].append({"edit": edit, "error": msg})
                        self.failures.record(
                            operation="sync",
                            token=token,
                            location=location,
                            error=msg,
                            severity="error",
                        )
                except Exception as e:
                    result["errors"].append({"edit": edit, "error": str(e)})

            # Clear queue on success
            if not dry_run and not result["errors"]:
                self.queue.clear()

            self.save_all()
            return result
    
    def accept_agent_location(self, token: str) -> bool:
        """Mark the latest agent location proposal as accepted."""
        history = self.history.location_history.get(token, [])
        for entry in reversed(history):
            if entry["status"] == "pending":
                entry["status"] = "accepted"
                self.events.log(
                    "location_accepted",
                    {"token": token, "location": entry["new"]},
                    source="user",
                )
                self.save_all()
                return True
        return False
    
    def reject_agent_location(self, token: str) -> bool:
        """Mark the latest agent location proposal as rejected."""
        history = self.history.location_history.get(token, [])
        for entry in reversed(history):
            if entry["status"] == "pending":
                entry["status"] = "rejected"
                self.events.log(
                    "location_rejected",
                    {"token": token, "location": entry["new"]},
                    source="user",
                )
                self.save_all()
                return True
        return False
    
    def get_pending_agent_proposals(self) -> list:
        """Get all pending agent location proposals."""
        pending = []
        for token, history in self.history.location_history.items():
            for entry in history:
                if entry["status"] == "pending" and entry["source"] == "agent":
                    pending.append({
                        "token": token,
                        "from": entry["old"],
                        "to": entry["new"],
                        "at": entry["at"],
                    })
        return pending

