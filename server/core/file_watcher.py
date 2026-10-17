# -*- coding: utf-8 -*-
"""
File Watcher — Polling-based .kt file change detector.

Watches for changes in Kotlin files with debounce + hash check.
No external dependencies — pure Python.
"""

import hashlib
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Set


class FileWatcher:
    """
    Polls .kt files every N seconds.
    Detects changes with debounce + hash verification.
    """
    
    def __init__(
        self,
        project_root: Path,
        extensions: Set[str] = None,
        poll_interval: float = 1.0,
        debounce_seconds: float = 0.5,
    ):
        self.project_root = project_root
        self.extensions = extensions or {".kt"}
        self.poll_interval = poll_interval
        self.debounce_seconds = debounce_seconds
        
        # State: {file_path_str: hash}
        self.known_hashes: Dict[str, str] = {}
        
        # Pending changes: {file_path_str: (first_seen, last_seen)}
        self.pending: Dict[str, tuple] = {}
    
    def scan_files(self) -> list:
        """Return all .kt files (excluding build/)."""
        files = []
        for ext in self.extensions:
            for f in self.project_root.rglob(f"*{ext}"):
                if "build" in str(f) or "\\build\\" in str(f):
                    continue
                if ".composebridge-state" in str(f):
                    continue
                files.append(f)
        return files
    
    def hash_file(self, path: Path) -> Optional[str]:
        """Compute SHA256 of file content. None if error."""
        try:
            content = path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except Exception:
            return None
    
    def initial_scan(self):
        """Capture baseline hashes for all files."""
        self.known_hashes.clear()
        for f in self.scan_files():
            h = self.hash_file(f)
            if h:
                self.known_hashes[str(f)] = h
    
    def check_once(self) -> list:
        """
        One polling cycle.
        
        Returns list of stable-changed files:
        [
            {"path": Path, "old_hash": str, "new_hash": str, "deleted": bool}
        ]
        """
        now = time.time()
        current_files = self.scan_files()
        current_paths = {str(f) for f in current_files}
        
        changes = []
        
        # Check for modified or new files
        for f in current_files:
            path_str = str(f)
            new_hash = self.hash_file(f)
            if new_hash is None:
                continue
            
            old_hash = self.known_hashes.get(path_str)
            
            if old_hash != new_hash:
                try:
                    mtime = f.stat().st_mtime
                except Exception:
                    mtime = now
                
                # If file has been untouched on disk for >= debounce_seconds, it is stable
                if (now - mtime) >= self.debounce_seconds:
                    changes.append({
                        "path": f,
                        "old_hash": old_hash,
                        "new_hash": new_hash,
                        "deleted": False,
                    })
                    self.known_hashes[path_str] = new_hash
                    if path_str in self.pending:
                        del self.pending[path_str]
                else:
                    # First detection or in debounce window
                    if path_str in self.pending:
                        first_seen, _ = self.pending[path_str]
                        self.pending[path_str] = (first_seen, now)
                    else:
                        self.pending[path_str] = (now, now)
        
        # Check for deleted files
        for old_path in list(self.known_hashes.keys()):
            if old_path not in current_paths:
                changes.append({
                    "path": Path(old_path),
                    "old_hash": self.known_hashes[old_path],
                    "new_hash": None,
                    "deleted": True,
                })
                del self.known_hashes[old_path]
                if old_path in self.pending:
                    del self.pending[old_path]
        
        # Process pending — check if stable
        for path_str, (first_seen, last_seen) in list(self.pending.items()):
            elapsed = now - last_seen
            if elapsed >= self.debounce_seconds:
                f = Path(path_str)
                if f.exists():
                    new_hash = self.hash_file(f)
                    old_hash = self.known_hashes.get(path_str)
                    if new_hash and new_hash != old_hash:
                        changes.append({
                            "path": f,
                            "old_hash": old_hash,
                            "new_hash": new_hash,
                            "deleted": False,
                        })
                        self.known_hashes[path_str] = new_hash
                del self.pending[path_str]
        
        return changes
    
    def watch(
        self,
        callback: Callable[[list], None],
        max_iterations: Optional[int] = None,
    ):
        """
        Continuous watching loop.
        
        Args:
            callback: function that receives list of changes
            max_iterations: stop after N iterations (for testing)
        """
        self.initial_scan()
        iteration = 0
        while True:
            if max_iterations and iteration >= max_iterations:
                break
            time.sleep(self.poll_interval)
            changes = self.check_once()
            if changes:
                callback(changes)
            iteration += 1
