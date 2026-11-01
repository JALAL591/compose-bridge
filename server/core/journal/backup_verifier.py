# -*- coding: utf-8 -*-
"""
وحدة التحقق من النسخ الاحتياطية ومطابقة بصمات الملفات (Checksums).
Handles backup verification, drift detection, and checksum tracking.
"""

import hashlib
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List

def compute_normalized_hash(content_or_bytes) -> str:
    """Compute SHA-256 hash with normalized line endings to prevent platform CRLF/LF mismatches."""
    if isinstance(content_or_bytes, bytes):
        text = content_or_bytes.decode("utf-8", errors="replace")
    else:
        text = str(content_or_bytes)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def compute_deep_normalized_hash(content_or_bytes) -> str:
    """Compute SHA-256 hash with normalized line endings and stripped whitespace to prevent editor auto-format mismatches."""
    if isinstance(content_or_bytes, bytes):
        text = content_or_bytes.decode("utf-8", errors="replace")
    else:
        text = str(content_or_bytes)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    normalized = "\n".join(lines).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class BackupVerifierMixin:
    """Mixin class providing backup verification and checksum operations for PatternJournal."""

    def verify_before_reject(self) -> dict:
        """
        Verify occurrences and token definitions before executing reject.
        Checks if occurrences match what is on disk.
        """
        if not self.journal_file.exists():
            return {"can_reject": True, "mismatches": [], "warnings": []}

        mismatches = []
        warnings = []
        files = self.list_modified_files()

        for f_data in files:
            f_name = f_data["file"]
            full_path = self.project_root / f_name
            if not full_path.exists():
                matches = [m for m in self.project_root.rglob(Path(f_name).name) if "build" not in str(m) and ".composebridge-state" not in str(m)]
                if matches:
                    full_path = matches[0]
                else:
                    mismatches.append({"file": f_name, "error": "File does not exist"})
                    continue

            content = full_path.read_text(encoding="utf-8")
            changes = self.get_file_changes(f_name)
            for ch in changes:
                if ch["new"] not in content and ch["new"].strip() not in content:
                    mismatches.append({
                        "file": f_name,
                        "line": ch.get("line"),
                        "error": "New content modified or missing",
                    })

        # Check token definitions
        added_tokens = []
        try:
            with open(self.journal_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get("type") in ("token_added", "pattern_summary"):
                            tname = entry.get("token_name")
                            if tname and tname not in added_tokens:
                                added_tokens.append(tname)
                    except Exception:
                        pass
            if added_tokens:
                from core.token_migrator import TokenMigrator
                migrator = TokenMigrator(self.project_root)
                registry_file = migrator._find_registry_file()
                if registry_file and registry_file.exists():
                    reg_content = registry_file.read_text(encoding="utf-8")
                    for tname in added_tokens:
                        if tname not in reg_content:
                            warnings.append({
                                "token": tname,
                                "warning": f"Token '{tname}' definition missing from registry",
                            })
        except Exception:
            pass

        return {
            "can_reject": len(mismatches) == 0,
            "mismatches": mismatches,
            "warnings": warnings,
        }


    def get_latest_checksum_for_file(self, file_path) -> Optional[str]:
        """Get the latest recorded checksum_after for a given file."""
        entries = self._read_entries()
        fname = Path(str(file_path)).name.lower()
        norm_path = str(file_path).replace("\\", "/").lower()
        for entry in reversed(entries):
            ef = str(entry.get("file", "")).replace("\\", "/").lower()
            if ef == norm_path or Path(ef).name.lower() == fname:
                if entry.get("checksum_after"):
                    return entry["checksum_after"]
        return None


    def reset_file_baseline(self, file_path, new_checksum: str = ""):
        """Reset journal baseline for a file when a valid external modification occurs."""
        self._clean_journal_for_file(str(file_path))
        self._clean_pending_edits(str(file_path))


    def _save_backups_to_disk(self, files: List[str]) -> str:
        """Save backup snapshot to disk before revert."""
        import time
        backups_dir = self.project_root / ".composebridge-state" / "reject_backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        
        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "files": {},
        }
        
        for file in files:
            file_path = self.project_root / file
            if not file_path.exists():
                matches = [m for m in self.project_root.rglob(Path(file).name) if "build" not in str(m) and ".composebridge-state" not in str(m)]
                if matches:
                    file_path = matches[0]
            if file_path.exists():
                snapshot["files"][str(file)] = file_path.read_text(encoding="utf-8")
        
        snapshot_file = backups_dir / f"snapshot_{int(time.time())}.json"
        snapshot_file.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        return str(snapshot_file)

