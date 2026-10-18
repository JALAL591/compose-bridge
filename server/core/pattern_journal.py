import shutil
# -*- coding: utf-8 -*-
"""
Pattern Journal — حفظ كل تعديلات replace_pattern للسماح بالتراجع الكامل وإدارة التغييرات (Changes Tab).
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class PatternJournal:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.journal_file = project_root / ".composebridge-state" / "pattern_journal.jsonl"
        self.journal_file.parent.mkdir(exist_ok=True)

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
                from .token_migrator import TokenMigrator
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
                        entries.append(json.loads(line))
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

        norm_file = str(file).replace("\\", "/").strip().lower()
        file_name = Path(norm_file).name
        merged = False
        for entry in existing_entries:
            if entry.get("type") == "token_added":
                continue
            e_file = str(entry.get("file", "")).replace("\\", "/").strip().lower()
            if (e_file == norm_file or Path(e_file).name == file_name) and entry.get("line") == line:
                # دمج: احتفظ بالـ old_line الأصلي، حدّث new_line
                entry["new_line"] = new_line
                entry["new"] = new_line
                entry["t"] = datetime.utcnow().isoformat()
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
                "old": old_line,
                "new": new_line,
                "old_line": old_line,
                "new_line": new_line,
                "pattern_id": pattern_id,
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
        if self.journal_file.exists():
            with open(self.journal_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get("type") == "token_added":
                            continue
                        file_path = entry.get("file")
                        if not file_path:
                            continue
                        if file_path not in files:
                            files[file_path] = {
                                "file": file_path,
                                "change_count": 0,
                                "pattern_ids": set(),
                                "first_line": entry.get("line", 0),
                            }
                        files[file_path]["change_count"] += 1
                        pid = entry.get("pattern_id")
                        if pid:
                            files[file_path]["pattern_ids"].add(pid)
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
                    
                    if not matched_key:
                        first_line = 1
                        try:
                            orig_lines = bak.read_text(encoding="utf-8", errors="replace").splitlines()
                            curr_lines = orig_path.read_text(encoding="utf-8", errors="replace").splitlines()
                            for idx, (l1, l2) in enumerate(zip(orig_lines, curr_lines)):
                                if l1 != l2:
                                    first_line = idx + 1
                                    break
                        except Exception:
                            first_line = 1
                        
                        files[rel] = {
                            "file": rel,
                            "change_count": 1,
                            "pattern_ids": {"external_edit"},
                            "first_line": first_line,
                        }
                    else:
                        files[matched_key]["pattern_ids"].add("external_edit")
        except Exception:
            pass

        result = []
        for f in files.values():
            f["pattern_ids"] = list(f["pattern_ids"])
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

    def reject_file_changes(self, file_path: str) -> Dict:
        """Revert all changes for a specific file."""
        changes = self.get_file_changes(file_path)
        full_path = self.project_root / file_path
        if not full_path.exists():
            matches = [m for m in self.project_root.rglob(Path(file_path).name) if "build" not in str(m) and ".composebridge-state" not in str(m)]
            if matches:
                full_path = matches[0]
            else:
                return {"success": False, "error": f"File '{file_path}' not found"}

        backup_path = Path(str(full_path) + ".bridge.bak")
        if not backup_path.exists():
            alt_matches = [m for m in self.project_root.rglob(full_path.name + ".bridge.bak") if "build" not in str(m) and ".composebridge-state" not in str(m)]
            if alt_matches:
                backup_path = alt_matches[0]

        reverted = 0
        errors = []

        if backup_path.exists():
            try:
                shutil.copy2(str(backup_path), str(full_path))
                backup_path.unlink()
                reverted += 1
            except Exception as e:
                errors.append({"file": file_path, "error": f"Failed to restore backup: {e}"})
        elif not changes:
            return {"success": False, "error": f"No changes or backup found for {file_path}"}
        for change in reversed(changes):
            try:
                content = full_path.read_text(encoding="utf-8")
                target_new = change["new"]
                target_old = change["old"]
                lines = content.splitlines()
                target_line = change.get("line", 0)
                reverted_this = False

                if target_old == "":
                    # Line was inserted (e.g. import). Delete it completely.
                    if 1 <= target_line <= len(lines) + 5:
                        for offset in [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5]:
                            idx = target_line - 1 + offset
                            if 0 <= idx < len(lines):
                                if lines[idx].strip() == target_new.strip():
                                    del lines[idx]
                                    full_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                                    reverted += 1
                                    reverted_this = True
                                    break
                    if not reverted_this:
                        for line_cand in [target_new.strip() + "\r\n", target_new.strip() + "\n"]:
                            if line_cand in content:
                                content = content.replace(line_cand, "", 1)
                                full_path.write_text(content, encoding="utf-8")
                                reverted += 1
                                reverted_this = True
                                break
                    if not reverted_this:
                        errors.append({"file": file_path, "error": "New content not found"})
                    continue

                if 1 <= target_line <= len(lines) + 5:
                    for offset in [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5]:
                        idx = target_line - 1 + offset
                        if 0 <= idx < len(lines):
                            if target_new in lines[idx]:
                                lines[idx] = lines[idx].replace(target_new, target_old, 1)
                                full_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                                reverted += 1
                                reverted_this = True
                                break
                            elif target_new.strip() in lines[idx]:
                                lines[idx] = lines[idx].replace(target_new.strip(), target_old.strip(), 1)
                                full_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                                reverted += 1
                                reverted_this = True
                                break

                if not reverted_this:
                    if target_new in content:
                        content = content.replace(target_new, target_old, 1)
                        full_path.write_text(content, encoding="utf-8")
                        reverted += 1
                    elif target_new.strip() in content:
                        for line_cand in [target_new.strip() + "\r\n", target_new.strip() + "\n", target_new.strip()]:
                            if line_cand in content:
                                content = content.replace(line_cand, target_old, 1)
                                full_path.write_text(content, encoding="utf-8")
                                reverted += 1
                                reverted_this = True
                                break
                        if not reverted_this:
                            errors.append({"file": file_path, "error": "New content not found"})
                    else:
                        errors.append({"file": file_path, "error": "New content not found"})
            except Exception as e:
                errors.append({"file": file_path, "error": str(e)})

        # Remove reverted entries from journal
        target_name = Path(file_path).name
        remaining = []
        if self.journal_file.exists():
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

        self._clean_pending_edits(file_path)
        return {
            "success": len(errors) == 0,
            "file": file_path,
            "reverted_count": reverted,
            "error_count": len(errors),
            "errors": errors,
        }

    def approve_file_changes(self, file_path: str) -> Dict:
        """Mark file changes as approved (just remove from journal)."""
        changes = self.get_file_changes(file_path)
        count = len(changes)
        
        full_path = self.project_root / file_path
        if not full_path.exists():
            matches = [m for m in self.project_root.rglob(Path(file_path).name) if "build" not in str(m) and ".composebridge-state" not in str(m)]
            if matches:
                full_path = matches[0]

        backup_path = Path(str(full_path) + ".bridge.bak")
        if not backup_path.exists() and full_path.exists():
            alt_matches = [m for m in self.project_root.rglob(full_path.name + ".bridge.bak") if "build" not in str(m) and ".composebridge-state" not in str(m)]
            if alt_matches:
                backup_path = alt_matches[0]

        if backup_path.exists():
            try:
                backup_path.unlink()
                if count == 0:
                    count = 1
            except Exception:
                pass

        target_name = Path(file_path).name
        remaining = []
        if self.journal_file.exists():
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
        
        self._clean_pending_edits(file_path)
        return {"success": True, "file": file_path, "approved_count": count}

    def approve_all_files(self) -> Dict:
        """Approve all pending changes only if files were not modified externally."""
        # Delete any *.bridge.bak files on disk
        try:
            for bak in list(self.project_root.rglob("*.bridge.bak")):
                if any(ign in bak.parts for ign in ["build", ".gradle", ".git", ".composebridge-state"]):
                    continue
                try:
                    bak.unlink()
                except Exception:
                    pass
        except Exception:
            pass

        # Clean pending_edits.json
        for pfile in [self.project_root / ".composebridge-state" / "pending_edits.json", self.project_root / "pending_edits.json"]:
            if pfile.exists():
                try:
                    pfile.unlink()
                except Exception:
                    pass
        files = self.list_modified_files()
        errors = []
        
        for f_data in files:
            file_path = self.project_root / f_data["file"]
            if not file_path.exists():
                matches = [m for m in self.project_root.rglob(Path(f_data["file"]).name) if "build" not in str(m) and ".composebridge-state" not in str(m)]
                if matches:
                    file_path = matches[0]
                else:
                    errors.append({"file": f_data["file"], "error": "File not found"})
                    continue
            
            # ⭐ تحقق أن التعديلات لا تزال موجودة
            content = file_path.read_text(encoding="utf-8")
            changes = self.get_file_changes(f_data["file"])
            
            for change in changes:
                if change["new"] not in content and change["new"].strip() not in content:
                    errors.append({
                        "file": f_data["file"],
                        "line": change["line"],
                        "error": "Content changed externally",
                    })
        
        if errors:
            return {
                "success": False,
                "error": "Cannot approve — files modified externally",
                "errors": errors,
            }
        
        # احذف journal
        count = 0
        if self.journal_file.exists():
            with open(self.journal_file, "r", encoding="utf-8") as f:
                count = sum(1 for _ in f)
            try:
                self.journal_file.unlink()
            except Exception:
                pass
        
        return {"success": True, "approved_count": count}

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

    def reject_all_files(self, force: bool = False) -> Dict:
        """
        Revert all pending changes in REVERSE order (latest edit first).
        """
        try:
            # 1. Restore any *.bridge.bak files on disk
            disk_reverted = 0
            try:
                for bak in list(self.project_root.rglob("*.bridge.bak")):
                    if any(ign in bak.parts for ign in ["build", ".gradle", ".git", ".composebridge-state"]):
                        continue
                    orig_str = str(bak)[:-len(".bridge.bak")]
                    orig_path = Path(orig_str)
                    try:
                        shutil.copy2(str(bak), str(orig_path))
                        bak.unlink()
                        disk_reverted += 1
                    except Exception:
                        pass
            except Exception:
                pass

            # Clean pending_edits.json
            for pfile in [self.project_root / ".composebridge-state" / "pending_edits.json", self.project_root / "pending_edits.json"]:
                if pfile.exists():
                    try:
                        pfile.unlink()
                    except Exception:
                        pass

            if not self.journal_file.exists():
                return {
                    "success": True,
                    "reverted_count": disk_reverted,
                    "message": f"Reverted {disk_reverted} file(s) from disk backup",
                }

            entries = self._read_entries()
            if not entries:
                if self.journal_file.exists():
                    try:
                        self.journal_file.unlink()
                    except Exception:
                        pass
                return {
                    "success": True,
                    "reverted_count": 0,
                    "message": "Journal was empty",
                }

            # ⭐ اقرأ في ترتيب عكسي (الأحدث أولاً)
            reversed_entries = list(reversed(entries))

            reverted = 0
            errors = []
            changed_files = set()

            for entry in reversed_entries:
                file_rel = entry.get("file")
                line_no = entry.get("line", 0)
                old_line = entry.get("old_line") or entry.get("old") or entry.get("old_content") or ""
                new_line = entry.get("new_line") or entry.get("new") or entry.get("new_content") or ""

                if not file_rel:
                    continue

                file_path = self.project_root / file_rel
                if not file_path.exists():
                    matches = [m for m in self.project_root.rglob(Path(file_rel).name)
                               if "build" not in str(m) and ".composebridge-state" not in str(m) and ".bak" not in str(m)]
                    if not matches:
                        errors.append({"file": file_rel, "error": f"File not found: {file_rel}"})
                        continue
                    file_path = matches[0]

                try:
                    content = file_path.read_text(encoding="utf-8")
                    lines = content.splitlines()

                    # إذا كان old_line فارغاً و new_line موجوداً -> سطر تمت إضافته (import/token)
                    if old_line == "" and new_line != "":
                        target_idx = -1
                        if 1 <= line_no <= len(lines):
                            for offset in [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5]:
                                idx = line_no - 1 + offset
                                if 0 <= idx < len(lines) and (new_line.strip() == lines[idx].strip() or new_line in lines[idx]):
                                    target_idx = idx
                                    break
                        if target_idx < 0:
                            for idx, l in enumerate(lines):
                                if new_line.strip() == l.strip() or new_line in l:
                                    target_idx = idx
                                    break
                        if target_idx >= 0:
                            del lines[target_idx]
                            file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                            reverted += 1
                            changed_files.add(str(file_path.relative_to(self.project_root)))
                        continue

                    # استبدال new_line -> old_line
                    found = False
                    start_search = max(0, line_no - 6)
                    end_search = min(len(lines), line_no + 5)
                    for i in range(start_search, end_search):
                        if new_line in lines[i]:
                            lines[i] = lines[i].replace(new_line, old_line, 1)
                            found = True
                            break
                        elif new_line.strip() and new_line.strip() == lines[i].strip():
                            lines[i] = old_line
                            found = True
                            break
                        elif new_line.strip() and new_line.strip() in lines[i]:
                            lines[i] = lines[i].replace(new_line.strip(), old_line.strip(), 1)
                            found = True
                            break

                    # Fallback: في كامل الملف
                    if not found and new_line.strip():
                        for i, l in enumerate(lines):
                            if new_line in l:
                                lines[i] = lines[i].replace(new_line, old_line, 1)
                                found = True
                                break
                            elif new_line.strip() == l.strip():
                                lines[i] = old_line
                                found = True
                                break
                            elif new_line.strip() in l:
                                lines[i] = lines[i].replace(new_line.strip(), old_line.strip(), 1)
                                found = True
                                break

                    if found:
                        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                        reverted += 1
                        changed_files.add(str(file_path.relative_to(self.project_root)))
                    else:
                        # قد يكون السطر بالفعل قد استرجع قيمته القديمة
                        if old_line and any(old_line.strip() == l.strip() or old_line in l for l in lines):
                            pass
                        else:
                            errors.append({"file": file_rel, "line": line_no, "error": f"Target content not found: {new_line[:40]}"})

                except Exception as e:
                    errors.append({"file": file_rel, "error": str(e)})

            # ⭐ 4. احذف الـ journal
            if self.journal_file.exists():
                try:
                    self.journal_file.unlink()
                except Exception:
                    pass

            # ⭐ 5. نظّف backups
            backups_dir = self.project_root / ".composebridge-state" / "reject_backups"
            if backups_dir.exists():
                for f in backups_dir.glob("snapshot_*.json"):
                    try:
                        f.unlink()
                    except Exception:
                        pass

            return {
                "success": len(errors) == 0,
                "reverted_count": reverted,
                "files_affected": len(changed_files),
                "errors": errors[:10],
                "forced": force,
            }
        
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()[:500],
            }

    def get_file_diff(self, file_path: str) -> Dict:
        """Get before/after content and diff for a modified file."""
        changes = self.get_file_changes(file_path)
        full_path = self.project_root / file_path
        if not full_path.exists():
            matches = [m for m in self.project_root.rglob(Path(file_path).name) if "build" not in str(m) and ".composebridge-state" not in str(m)]
            if matches:
                full_path = matches[0]
            else:
                return {"success": False, "error": f"File '{file_path}' not found"}

        current_content = full_path.read_text(encoding="utf-8")

        backup_path = Path(str(full_path) + ".bridge.bak")
        if not backup_path.exists():
            alt_matches = [m for m in self.project_root.rglob(full_path.name + ".bridge.bak") if "build" not in str(m) and ".composebridge-state" not in str(m)]
            if alt_matches:
                backup_path = alt_matches[0]

        if backup_path.exists():
            original_content = backup_path.read_text(encoding="utf-8", errors="replace")
        else:
            # Reconstruct original content
            original_content = current_content
            for change in reversed(changes):
                target_new = change.get("new", "")
                target_old = change.get("old", "")
                if target_old == "":
                    for line_cand in [target_new.strip() + "\r\n", target_new.strip() + "\n"]:
                        if line_cand in original_content:
                            original_content = original_content.replace(line_cand, "", 1)
                            break
                elif target_new and target_new in original_content:
                    original_content = original_content.replace(target_new, target_old, 1)
                elif target_new and target_new.strip() in original_content:
                    original_content = original_content.replace(target_new.strip(), target_old.strip(), 1)

        import difflib
        diff_lines = list(difflib.unified_diff(
            original_content.splitlines(keepends=True),
            current_content.splitlines(keepends=True),
            fromfile=f"a/{Path(file_path).name} (original)",
            tofile=f"b/{Path(file_path).name} (modified)",
        ))

        return {
            "success": True,
            "file": file_path,
            "original_content": original_content,
            "current_content": current_content,
            "unified_diff": "".join(diff_lines),
            "change_count": len(changes),
        }

    def rollback_pattern(self, pattern_id: str) -> Dict:
        """
        Rollback all changes for a specific pattern:
        1. Remove any added tokens from registry files.
        2. Revert every file modification in reverse order.
        3. Clean up journal entries.
        """
        if not self.journal_file.exists():
            return {"success": False, "error": f"Pattern '{pattern_id}' not found in journal"}

        # 1. ابحث عن tokens مُضافة
        tokens_added = []
        with open(self.journal_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if (entry.get("pattern_id") == pattern_id and 
                        entry.get("type") == "token_added"):
                        tokens_added.append(entry)
                except Exception:
                    continue

        changes = self.get_pattern_changes(pattern_id)
        if not tokens_added and not changes:
            return {"success": False, "error": f"Pattern '{pattern_id}' not found in journal"}

        errors = []
        tokens_removed = []

        # 2. احذف كل token مُضاف
        from .token_migrator import TokenMigrator
        migrator = TokenMigrator(self.project_root)
        for t in tokens_added:
            token_name = t.get("token_name")
            if not token_name:
                continue
            try:
                success = migrator.remove_token(token_name, "color")
                if success:
                    tokens_removed.append(token_name)
                else:
                    success_dim = migrator.remove_token(token_name, "dimension")
                    if success_dim:
                        tokens_removed.append(token_name)
                    else:
                        errors.append({
                            "token": token_name,
                            "error": f"Token '{token_name}' definition not found in registry file",
                        })
            except Exception as e:
                errors.append({
                    "token": token_name,
                    "error": str(e),
                })

        # 3. اعكس كل الاستبدالات من الأحدث للأقدم
        reverted = []
        for change in reversed(changes):
            file_name = change.get("file", "")
            file_path = self.project_root / file_name
            if not file_path.exists():
                matches = list(self.project_root.rglob(Path(file_name).name))
                matches = [m for m in matches if "build" not in str(m) and ".composebridge-state" not in str(m)]
                if matches:
                    file_path = matches[0]
                else:
                    errors.append({"file": file_name, "line": change.get("line"), "error": "File not found"})
                    continue

            try:
                content = file_path.read_text(encoding="utf-8")
                target_new = change["new"]
                target_old = change["old"]
                lines = content.splitlines()
                target_line = change.get("line", 0)
                reverted_this = False

                # First try line-targeted replacement with local search (+/- 5 lines)
                if 1 <= target_line <= len(lines) + 5:
                    for offset in [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5]:
                        idx = target_line - 1 + offset
                        if 0 <= idx < len(lines):
                            if target_new in lines[idx]:
                                lines[idx] = lines[idx].replace(target_new, target_old, 1)
                                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                                reverted.append({"file": file_name, "line": target_line})
                                reverted_this = True
                                break
                            elif target_new.strip() in lines[idx]:
                                lines[idx] = lines[idx].replace(target_new.strip(), target_old.strip(), 1)
                                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                                reverted.append({"file": file_name, "line": target_line})
                                reverted_this = True
                                break

                # Fallback to whole file replacement
                if not reverted_this:
                    if target_new in content:
                        content = content.replace(target_new, target_old, 1)
                        file_path.write_text(content, encoding="utf-8")
                        reverted.append({"file": file_name, "line": target_line})
                        reverted_this = True
                    elif target_new.strip() in content:
                        for line_cand in [target_new.strip() + "\r\n", target_new.strip() + "\n", target_new.strip()]:
                            if line_cand in content:
                                content = content.replace(line_cand, target_old, 1)
                                file_path.write_text(content, encoding="utf-8")
                                reverted.append({"file": file_name, "line": target_line})
                                reverted_this = True
                                break
                        if not reverted_this:
                            errors.append({
                                "file": file_name,
                                "line": target_line,
                                "error": "New content not found in file",
                            })
                    else:
                        errors.append({
                            "file": file_name,
                            "line": target_line,
                            "error": "New content not found in file",
                        })
            except Exception as e:
                errors.append({"file": file_name, "line": change.get("line"), "error": str(e)})

        # 4. احذف التعديلات من الـ journal
        remaining = []
        with open(self.journal_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("pattern_id") != pattern_id:
                        remaining.append(line)
                except Exception:
                    continue

        with open(self.journal_file, "w", encoding="utf-8") as f:
            f.writelines(remaining)

        is_success = (len(errors) == 0) and (len(reverted) > 0 or len(tokens_removed) > 0)
        return {
            "success": is_success,
            "pattern_id": pattern_id,
            "reverted_count": len(reverted),
            "tokens_removed": tokens_removed,
            "error_count": len(errors),
            "reverted": reverted,
            "errors": errors,
        }
