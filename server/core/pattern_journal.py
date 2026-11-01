# -*- coding: utf-8 -*-
"""
سجل الأنماط والتعديلات (Pattern Journal) لخادم ComposeBridge.
Manages persistent recording of pattern replacements, modified files, diffs, and approvals.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from core.journal.backup_verifier import BackupVerifierMixin, compute_normalized_hash
from core.journal.rollback_manager import RollbackMixin
from core.journal.approval_manager import ApprovalMixin

class PatternJournal(RollbackMixin, BackupVerifierMixin, ApprovalMixin):
    """
    سجل تتبع التعديلات والأنماط المعلقة.
    Coordinates pattern journal logging, modified files discovery, diff generation, and approvals.
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.journal_file = project_root / ".composebridge-state" / "pattern_journal.jsonl"
        self.journal_file.parent.mkdir(exist_ok=True)
        self.clean_temp_entries()

    @staticmethod
    def is_temp_path(path_str, project_root: Optional[Path] = None) -> bool:
        if not path_str or not str(path_str).strip():
            return True
        norm = str(path_str).replace("\\", "/").lower()

        # If project_root is provided:
        if project_root:
            norm_root = str(project_root).replace("\\", "/").lower().rstrip("/")
            # Relative paths inside project root (e.g. "DesignSystem.kt")
            if not norm.startswith("/") and not (len(norm) > 1 and norm[1] == ":"):
                return ".tmp_" in norm or norm.endswith(".tmp")
            # Absolute paths inside project root
            if norm.startswith(norm_root):
                return ".tmp_" in norm or norm.endswith(".tmp")

        temp_markers = [
            "/appdata/local/temp/",
            "appdata/local/temp",
            "/tmp/",
            "\\tmp\\",
            "/temp/",
            "\\temp\\",
            ".tmp_",
            ".tmp",
        ]
        if any(marker in norm for marker in temp_markers):
            return True
        if norm.startswith("temp/") or norm.startswith("tmp/"):
            return True
        return False

    def clean_temp_entries(self) -> int:
        """Purge any temporary/test paths from journal and pending_edits."""
        removed_count = 0
        if self.journal_file.exists():
            clean_lines = []
            try:
                with open(self.journal_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if not line_str:
                            continue
                        try:
                            entry = json.loads(line_str)
                            f_path = entry.get("file")
                            if self.is_temp_path(f_path, self.project_root):
                                removed_count += 1
                                continue
                        except Exception:
                            continue
                        clean_lines.append(line_str + "\n")
                with open(self.journal_file, "w", encoding="utf-8") as f:
                    f.writelines(clean_lines)
            except Exception:
                pass

        pending_candidates = [
            self.project_root / ".composebridge-state" / "pending_edits.json",
            self.project_root / "pending_edits.json"
        ]
        for pfile in pending_candidates:
            if pfile.exists():
                try:
                    with open(pfile, "r", encoding="utf-8") as pf:
                        p_entries = json.load(pf)
                    if isinstance(p_entries, list):
                        remaining = [
                            pe for pe in p_entries
                            if not self.is_temp_path(pe.get("file"), self.project_root)
                            and not self.is_temp_path(pe.get("backup"), self.project_root)
                        ]
                        if len(remaining) != len(p_entries):
                            removed_count += (len(p_entries) - len(remaining))
                            with open(pfile, "w", encoding="utf-8") as pf:
                                json.dump(remaining, pf, indent=2, ensure_ascii=False)
                except Exception:
                    pass
        return removed_count

    def record_pattern_summary(
        self,
        pattern_id: str,
        token_name: str,
        token_file: str,
        occurrences: list,
    ):
        """Record explicit relationship between pattern, token, and all occurrences."""
        entry = {
            "t": datetime.utcnow().isoformat(),
            "type": "pattern_summary",
            "pattern_id": pattern_id,
            "token_name": token_name,
            "token_file": token_file,
            "occurrences": [list(occ) if isinstance(occ, tuple) else occ for occ in occurrences],
            "count": len(occurrences),
        }
        with open(self.journal_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def check_remaining_token_usages(self, token_name: str) -> list:
        """Check if any .kt files in the project (excluding theme/registry definitions) still use this token."""
        import re
        remaining = []
        for f in self.project_root.rglob("*.kt"):
            if "build" in str(f) or ".composebridge" in str(f) or "DesignSystem" in f.name or "Registry" in f.name:
                continue
            try:
                content = f.read_text(encoding="utf-8")
                if re.search(rf'\b(?:AppColors|AppDimens)\.{re.escape(token_name)}\b', content):
                    remaining.append(f.name)
            except Exception:
                pass
        return remaining


    def record_token_added(
        self,
        pattern_id: str,
        token_name: str,
        token_value: str,
        file: str,
    ):
        """Record that a token was added by replace_pattern."""
        entry = {
            "t": datetime.utcnow().isoformat(),
            "type": "token_added",
            "pattern_id": pattern_id,
            "token_name": token_name,
            "token_value": token_value,
            "file": file,
        }
        with open(self.journal_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _read_entries(self) -> List[Dict]:
        """Read all entries from journal JSONL file."""
        if not self.journal_file.exists():
            return []
        entries = []
        try:
            with open(self.journal_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        if not self.is_temp_path(item.get("file"), self.project_root):
                            entries.append(item)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            return []
        return entries

    def record(
        self,
        pattern_id: str,
        file: str,
        line: int,
        old_content: str,
        new_content: str,
    ):
        """Record a single change in the journal."""
        return self.record_change(
            file=file,
            line=line,
            old_line=old_content,
            new_line=new_content,
            pattern_id=pattern_id,
        )

    def record_change(
        self,
        file: str,
        line: int,
        old_line: str,
        new_line: str,
        pattern_id: Optional[str] = None,
    ):
        """
        Record change. If entry exists for same (file, line):
        - Keep oldest old_line (original value)
        - Update to latest new_line
        """
        existing_entries = self._read_entries()

        curr_checksum = None
        try:
            full_chk = self.project_root / file
            if not full_chk.exists():
                matches = [m for m in self.project_root.rglob(Path(file).name) if "build" not in str(m) and ".composebridge-state" not in str(m)]
                if matches:
                    full_chk = matches[0]
            if full_chk.exists():
                curr_checksum = compute_normalized_hash(full_chk.read_bytes())
        except Exception:
            pass

        # 🌟 IMMUTABLE BASELINE: Extract true original line from .bridge.bak if available
        baseline_old = old_line
        try:
            full_target = self.project_root / file
            if not full_target.exists():
                matches = [m for m in self.project_root.rglob(Path(file).name) if "build" not in str(m) and ".composebridge-state" not in str(m)]
                if matches:
                    full_target = matches[0]
            bak_path = Path(str(full_target) + ".bridge.bak")
            if bak_path.exists() and line > 0:
                bak_lines = bak_path.read_text(encoding="utf-8").splitlines()
                if 1 <= line <= len(bak_lines):
                    baseline_old = bak_lines[line - 1]
        except Exception:
            pass

        norm_file = str(file).replace("\\", "/").strip().lower()
        file_name = Path(norm_file).name
        merged = False
        for entry in existing_entries:
            if entry.get("type") == "token_added":
                continue
            e_file = str(entry.get("file", "")).replace("\\", "/").strip().lower()
            same_file = (e_file == norm_file or Path(e_file).name == file_name)
            if same_file:
                entry_line = entry.get("line", 0)
                # STRICT line matching: only merge if on the exact same line
                # AND it represents a consecutive modification of that same line
                same_exact_line = (entry_line == line)
                consecutive_match = (
                    entry.get("new_line", "").strip() == old_line.strip()
                    or entry.get("new", "").strip() == old_line.strip()
                )
                if same_exact_line and (consecutive_match or entry_line == line):
                    # Merge: keep earliest original value (old_line and old), update to latest
                    entry["new_line"] = new_line
                    entry["new"] = new_line
                    entry["line"] = line
                    entry["t"] = datetime.utcnow().isoformat()
                    # Ensure old_line is never replaced by intermediate new_line
                    if not entry.get("old_line") or not entry.get("old"):
                        entry["old_line"] = baseline_old
                        entry["old"] = baseline_old
                    if curr_checksum:
                        entry["checksum_after"] = curr_checksum
                    if pattern_id:
                        entry["pattern_id"] = pattern_id
                    merged = True
                    break

        if not merged:
            existing_entries.append({
                "t": datetime.utcnow().isoformat(),
                "type": "replacement",
                "file": file,
                "line": line,
                "old": baseline_old,
                "new": new_line,
                "old_line": baseline_old,
                "new_line": new_line,
                "pattern_id": pattern_id,
                "checksum_after": curr_checksum,
            })

        self.journal_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.journal_file, "w", encoding="utf-8") as f:
            for entry in existing_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_pattern_changes(self, pattern_id: str) -> List[Dict]:
        """Get all file replacement changes for a specific pattern."""
        if not self.journal_file.exists():
            return []
        changes = []
        with open(self.journal_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("pattern_id") == pattern_id and entry.get("type") != "token_added":
                        if entry.get("file") and str(entry.get("file")).strip():
                            changes.append(entry)
                except Exception:
                    continue
        return changes

    def list_patterns(self) -> List[Dict]:
        """List all patterns with their change counts."""
        if not self.journal_file.exists():
            return []
        patterns: Dict[str, Dict] = {}
        with open(self.journal_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    pid = entry.get("pattern_id")
                    if pid:
                        if pid not in patterns:
                            patterns[pid] = {
                                "pattern_id": pid,
                                "count": 0,
                                "first_at": entry["t"],
                                "last_at": entry["t"],
                                "tokens_added": [],
                            }
                        if entry.get("type") == "token_added":
                            tname = entry.get("token_name")
                            if tname and tname not in patterns[pid]["tokens_added"]:
                                patterns[pid]["tokens_added"].append(tname)
                        else:
                            patterns[pid]["count"] += 1
                        patterns[pid]["last_at"] = entry["t"]
                except Exception:
                    continue
        return list(patterns.values())


    def _clean_pending_edits(self, file_path: str):
        target_name = Path(file_path).name
        pending_candidates = [
            self.project_root / ".composebridge-state" / "pending_edits.json",
            self.project_root / "pending_edits.json"
        ]
        for pfile in pending_candidates:
            if pfile.exists():
                try:
                    with open(pfile, "r", encoding="utf-8") as pf:
                        p_entries = json.load(pf)
                    if isinstance(p_entries, list):
                        remaining = [
                            pe for pe in p_entries
                            if pe.get("file") != file_path and Path(pe.get("file", "")).name != target_name
                        ]
                        with open(pfile, "w", encoding="utf-8") as pf:
                            json.dump(remaining, pf, indent=2, ensure_ascii=False)
                except Exception:
                    pass

    def list_modified_files(self) -> List[Dict]:
        """
        Aggregate changes by file.
        Returns list of {file, change_count, pattern_ids, first_line}.
        """
        files: Dict[str, Dict] = {}
        candidate_journals = [
            self.journal_file,
            self.project_root / ".composebridge-state" / "pattern_journal.jsonl",
            self.project_root / "pattern_journal.jsonl",
            self.project_root / ".composebridge-journal.json",
        ]
        seen_journals = set()
        for jfile in candidate_journals:
            if not jfile or not jfile.exists() or jfile in seen_journals:
                continue
            seen_journals.add(jfile)
            try:
                with open(jfile, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            line_str = line.strip()
                            if not line_str:
                                continue
                            entry = json.loads(line_str)
                            if entry.get("type") == "token_added":
                                continue
                            file_path = entry.get("file")
                            if not file_path:
                                continue
                            try:
                                p_abs = Path(file_path)
                                if p_abs.is_absolute():
                                    norm_path = str(p_abs.relative_to(self.project_root)).replace("\\", "/")
                                else:
                                    norm_path = str(file_path).replace("\\", "/")
                            except Exception:
                                norm_path = str(file_path).replace("\\", "/")

                            if self.is_temp_path(norm_path, self.project_root):
                                continue

                            if norm_path not in files:
                                files[norm_path] = {
                                    "file": norm_path,
                                    "change_count": 0,
                                    "pattern_ids": set(),
                                    "first_line": entry.get("line", 0),
                                }
                            files[norm_path]["change_count"] += 1
                            pid = entry.get("pattern_id")
                            if pid:
                                files[norm_path]["pattern_ids"].add(pid)
                        except Exception:
                            continue
            except Exception:
                continue

        # Also check pending_edits.json
        pending_candidates = [
            self.project_root / ".composebridge-state" / "pending_edits.json",
            self.project_root / "pending_edits.json"
        ]
        for pfile in pending_candidates:
            if pfile.exists():
                try:
                    with open(pfile, "r", encoding="utf-8") as pf:
                        p_entries = json.load(pf)
                    if isinstance(p_entries, list):
                        for pe in p_entries:
                            p_path = pe.get("file")
                            if not p_path:
                                continue
                            if p_path not in files:
                                files[p_path] = {
                                    "file": p_path,
                                    "change_count": 0,
                                    "pattern_ids": set(),
                                    "first_line": pe.get("line", 1),
                                }
                            files[p_path]["change_count"] += 1
                            files[p_path]["pattern_ids"].add("pending_cli_edit")
                except Exception:
                    pass

        # Also scan disk for any *.bridge.bak files!
        try:
            for bak in self.project_root.rglob("*.bridge.bak"):
                parts = bak.parts
                if any(ign in parts for ign in ["build", ".gradle", ".git", ".composebridge-state"]):
                    continue
                orig_str = str(bak)[:-len(".bridge.bak")]
                orig_path = Path(orig_str)
                if orig_path.exists():
                    try:
                        rel = str(orig_path.relative_to(self.project_root)).replace("\\", "/")
                    except Exception:
                        rel = str(orig_path).replace("\\", "/")
                    
                    matched_key = None
                    for k in files:
                        if k == rel or Path(k).name == orig_path.name:
                            matched_key = k
                            break
                    
                    orig_lines = []
                    curr_lines = []
                    is_modified_on_disk = False
                    first_line = 1
                    orig_line_text = ""
                    curr_line_text = ""
                    try:
                        orig_lines = bak.read_text(encoding="utf-8", errors="replace").splitlines()
                        curr_lines = orig_path.read_text(encoding="utf-8", errors="replace").splitlines()
                        if orig_lines != curr_lines:
                            is_modified_on_disk = True
                            for idx, (l1, l2) in enumerate(zip(orig_lines, curr_lines)):
                                if l1 != l2:
                                    first_line = idx + 1
                                    orig_line_text = l1
                                    curr_line_text = l2
                                    break
                            if first_line == 1 and not orig_line_text and not curr_line_text and len(orig_lines) != len(curr_lines):
                                first_line = min(len(orig_lines), len(curr_lines)) + 1
                    except Exception:
                        is_modified_on_disk = True
                        first_line = 1

                    if not matched_key:
                        if is_modified_on_disk:
                            files[rel] = {
                                "file": rel,
                                "change_count": 1,
                                "pattern_ids": {"external_edit"},
                                "first_line": first_line,
                            }
                            # Auto-reconcile with journal so it persists across sessions and IDE views
                            try:
                                self.record_change(
                                    file=rel,
                                    line=first_line,
                                    old_line=orig_line_text,
                                    new_line=curr_line_text,
                                    pattern_id="reconciled_disk_edit",
                                )
                            except Exception:
                                pass
                    else:
                        files[matched_key]["pattern_ids"].add("external_edit")
        except Exception:
            pass

        result = []
        for f in files.values():
            full_f = self.project_root / f["file"]
            if not full_f.exists():
                continue
            f["pattern_ids"] = list(f["pattern_ids"])
            try:
                from core.diff_engine import get_file_diff_report
                report = get_file_diff_report(full_f, self.project_root)
                f["changes"] = report.get("changes", [])
                f["change_count"] = report.get("change_count", len(f["changes"]))
                f["has_backup"] = report.get("has_backup", False)
            except Exception:
                f["changes"] = []
                f["change_count"] = 0
                f["has_backup"] = False

            # Only include files that genuinely have pending modifications or backup
            if f.get("change_count", 0) > 0 or f.get("has_backup", False):
                result.append(f)
        return result


    def get_file_changes(self, file_path: str) -> List[Dict]:
        """Get all changes for a specific file."""
        if not self.journal_file.exists():
            return []
        changes = []
        target_name = Path(file_path).name
        with open(self.journal_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("type") == "token_added":
                        continue
                    efile = entry.get("file", "")
                    if efile == file_path or Path(efile).name == target_name:
                        changes.append(entry)
                except Exception:
                    continue
        return changes


    def _clean_journal_for_file(self, file_path: str):
        target_name = Path(file_path).name
        remaining = []
        if self.journal_file.exists():
            try:
                with open(self.journal_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            efile = entry.get("file", "")
                            if efile != file_path and Path(efile).name != target_name:
                                remaining.append(line)
                        except Exception:
                            continue
                with open(self.journal_file, "w", encoding="utf-8") as f:
                    f.writelines(remaining)
            except Exception:
                pass

