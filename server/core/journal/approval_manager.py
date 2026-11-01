from common.file_ops import is_ignored_path
# -*- coding: utf-8 -*-
"""
وحدة اعتماد التعديلات وحساب الفروقات (Diffs & Approvals).
Handles approving file changes, hunk approvals, and diff loading.
"""

import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

class ApprovalMixin:
    """Mixin class providing approval and diff inspection logic for PatternJournal."""

    def approve_change(self, file_path: str, change_id: str) -> Dict:
        """Approve a single granular change (hunk) in file."""
        from core.diff_engine import approve_change
        return approve_change(file_path, change_id, self.project_root)


    def keep_current_file_changes(self, file_path: str) -> Dict:
        """Keep current on-disk modifications, discard backup, and remove from journal."""
        res = self.approve_file_changes(file_path)
        if res.get("success"):
            res["message"] = f"تم الاحتفاظ بالتعديلات الحالية للملف '{file_path}' بنجاح."
        return res

    def approve_file_changes(self, file_path: str) -> Dict:
        """Mark file changes as approved (just remove from journal)."""
        changes = self.get_file_changes(file_path)
        count = len(changes)
        
        full_path = self.project_root / file_path
        if not full_path.exists():
            matches = [m for m in self.project_root.rglob(Path(file_path).name) if not is_ignored_path(m, self.project_root)]
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

        # ═══ Dependency Guard: Auto-approve DesignSystem / AppColors if referenced ═══
        registry_names = {"designsystem.kt", "appcolors.kt", "appdimens.kt", "appstrings.kt"}
        if target_name.lower() not in registry_names and full_path.exists():
            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
                needs_registry = bool(
                    "AppColors." in content
                    or "AppDimens." in content
                    or "AppStrings." in content
                    or "DesignSystem." in content
                    or "BridgeThemeRegistry." in content
                )
                if needs_registry:
                    # Check modified files list
                    for mf in self.list_modified_files():
                        m_file = mf.get("file", "")
                        if Path(m_file).name.lower() in registry_names:
                            self.approve_file_changes(m_file)
                    # Also check for any registry files with active .bridge.bak on disk
                    for rname in ["DesignSystem.kt", "AppColors.kt", "AppDimens.kt", "AppStrings.kt"]:
                        for rfile in self.project_root.rglob(rname):
                            if is_ignored_path(rfile, self.project_root):
                                continue
                            bak = Path(str(rfile) + ".bridge.bak")
                            if bak.exists():
                                try:
                                    rel_rfile = str(rfile.relative_to(self.project_root)).replace("\\", "/")
                                except Exception:
                                    rel_rfile = str(rfile).replace("\\", "/")
                                self.approve_file_changes(rel_rfile)
            except Exception:
                pass

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
                matches = [m for m in self.project_root.rglob(Path(f_data["file"]).name) if not is_ignored_path(m, self.project_root)]
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


    def get_file_diff(self, file_path: str) -> Dict:
        """Get before/after content and diff for a modified file."""
        changes = self.get_file_changes(file_path)
        full_path = self.project_root / file_path
        if not full_path.exists():
            matches = [m for m in self.project_root.rglob(Path(file_path).name) if not is_ignored_path(m, self.project_root)]
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

