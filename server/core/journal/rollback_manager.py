from common.file_ops import is_ignored_path
# -*- coding: utf-8 -*-
"""
وحدة إدارة التراجع عن التعديلات والـ Rollback المتقدم وشلال التراجع (Cascade Revert).
Handles file reverts, hunk rejections, pattern rollbacks, and cascade token removals.
"""

import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

from core.journal.backup_verifier import compute_normalized_hash, compute_deep_normalized_hash

class RollbackMixin:
    """Mixin class providing rollback and rejection logic for PatternJournal."""

    def reject_change(self, file_path: str, change_id: str) -> Dict:
        """Reject a single granular change (hunk) in file."""
        from core.diff_engine import reject_change
        return reject_change(file_path, change_id, self.project_root)


    def _handle_cascade_token_reject(self, file_path: str, file_changes: list) -> Dict[str, Any]:
        """
        Inspect whether the rejected file was part of a larger token creation or pattern operation.
        If a token was added in the session and linked to this file:
        - If other pending files in the journal still use this token, generates an informative warning.
        - If NO other pending files use this token, safely removes the token definition from the
          registry file (e.g. DesignSystem.kt / AppColors.kt).
        - If the registry file has no further changes after token removal, cleans up its backup and journal.
        """
        result = {
            "removed_tokens": [],
            "cleaned_files": [],
            "warning": None,
        }
        if not self.journal_file.exists():
            return result

        try:
            all_entries = []
            with open(self.journal_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        all_entries.append(json.loads(line.strip()))
                    except Exception:
                        continue

            import re
            pattern_ids = set()
            tokens_in_changes = set()
            target_name = Path(file_path).name

            for c in (file_changes or []):
                pid = c.get("pattern_id")
                if pid:
                    pattern_ids.add(str(pid))
                new_val = str(c.get("new", "") or c.get("new_line", ""))
                found_tokens = re.findall(r'\b(?:AppColors|AppDimens|DesignSystem|Theme)\.(\w+)\b', new_val)
                tokens_in_changes.update(found_tokens)

            candidate_tokens = []
            for entry in all_entries:
                etype = entry.get("type")
                if etype == "token_added":
                    tname = entry.get("token_name")
                    pid = entry.get("pattern_id", "")
                    reg_file = entry.get("file", "")
                    ttype = entry.get("token_type", "color")
                    if pid in pattern_ids or tname in tokens_in_changes or f"create_token_{tname}" in pattern_ids:
                        candidate_tokens.append((tname, pid, reg_file, ttype))
                elif etype == "pattern_summary":
                    tname = entry.get("token_name")
                    pid = entry.get("pattern_id", "")
                    reg_file = entry.get("token_file", "")
                    ttype = "color"
                    if pid in pattern_ids or tname in tokens_in_changes:
                        candidate_tokens.append((tname, pid, reg_file, ttype))
                else:
                    pid = entry.get("pattern_id", "")
                    if pid.startswith("create_token_"):
                        tname = pid.replace("create_token_", "")
                        if pid in pattern_ids or tname in tokens_in_changes:
                            reg_file = entry.get("file", "")
                            candidate_tokens.append((tname, pid, reg_file, "color"))

            unique_candidates = {}
            for tname, pid, reg_file, ttype in candidate_tokens:
                if tname and tname not in unique_candidates:
                    unique_candidates[tname] = (pid, reg_file, ttype)

            if not unique_candidates:
                return result

            warnings = []
            tokens_to_remove = []

            from core.token_baseline import is_pre_existing, check_token_usages_in_project

            for tname, (pid, reg_file, ttype) in unique_candidates.items():
                # 1. BASELINE IMMUNITY CHECK:
                # If the token is pre-existing in baseline, it MUST NEVER be cascade-deleted!
                if is_pre_existing(tname, self.project_root):
                    warnings.append(
                        f"🛡️ حماية التوكن الأساسي: التوكن '{tname}' مسجل في الفهرس الأساسي للمشروع (Baseline) ولا يمكن حذفه تلقائياً."
                    )
                    continue

                other_files_using_token = set()
                for entry in all_entries:
                    efile = str(entry.get("file", "")).replace("\\", "/")
                    if not efile:
                        continue
                    if efile == file_path or Path(efile).name == target_name:
                        continue
                    if reg_file and (efile == reg_file or Path(efile).name == Path(reg_file).name):
                        continue
                    
                    entry_pid = str(entry.get("pattern_id", ""))
                    entry_content = str(entry.get("new", "") or entry.get("new_line", ""))
                    if (pid and entry_pid == pid) or (tname in entry_content):
                        other_files_using_token.add(Path(efile).name)

                # Check usages via token_baseline index & PROJECT_CACHE
                try:
                    baseline_usages = check_token_usages_in_project(tname, self.project_root, exclude_file=file_path)
                    for bu in baseline_usages:
                        b_name = Path(bu).name
                        if b_name != target_name and b_name != Path(file_path).name:
                            other_files_using_token.add(b_name)
                except Exception:
                    pass

                # Check remaining disk usages across all kotlin files in the project
                try:
                    disk_usages = self.check_remaining_token_usages(tname)
                    for du in disk_usages:
                        if du != target_name and du != Path(file_path).name:
                            other_files_using_token.add(du)
                except Exception:
                    pass

                # Atomic check: verify target_file actually no longer contains the token on disk!
                target_still_uses_token = False
                try:
                    target_full = self.project_root / file_path
                    if not target_full.exists():
                        matches = [m for m in self.project_root.rglob(Path(file_path).name) if not is_ignored_path(m, self.project_root)]
                        if matches:
                            target_full = matches[0]
                    if target_full.exists():
                        target_code = target_full.read_text(encoding="utf-8")
                        if re.search(rf'\b(?:AppColors|AppDimens|DesignSystem|Theme)\.{re.escape(tname)}\b', target_code):
                            target_still_uses_token = True
                except Exception:
                    pass

                if target_still_uses_token:
                    warnings.append(
                        f"⚠️ تحذير: التوكن '{tname}' لم يُحذف من ملف التصميم لأن الملف '{target_name}' ما زال يحتوي عليه على القرص."
                    )
                    continue

                if other_files_using_token:
                    files_str = ", ".join(sorted(other_files_using_token))
                    warnings.append(
                        f"⚠️ تحذير: التوكن '{tname}' ما زال موجوداً في ملف التصميم لأنه مستخدم في ملفات أخرى ({files_str})."
                    )
                else:
                    tokens_to_remove.append((tname, pid, reg_file, ttype))

            if tokens_to_remove:
                from core.token_migrator import TokenMigrator
                migrator = TokenMigrator(self.project_root)
                affected_reg_files = set()

                for tname, pid, reg_file, ttype in tokens_to_remove:
                    removed = migrator.remove_token(tname, "color")
                    if not removed:
                        removed = migrator.remove_token(tname, "dimension")
                    if removed:
                        result["removed_tokens"].append(tname)
                        if reg_file:
                            affected_reg_files.add(reg_file)

                removed_set = set(result["removed_tokens"])
                clean_lines = []
                with open(self.journal_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            ent = json.loads(line.strip())
                            tn = ent.get("token_name")
                            pid = ent.get("pattern_id", "")
                            if tn in removed_set or pid.replace("create_token_", "").replace("remove_token_", "") in removed_set:
                                continue
                            clean_lines.append(line)
                        except Exception:
                            clean_lines.append(line)
                with open(self.journal_file, "w", encoding="utf-8") as f:
                    f.writelines(clean_lines)

                remaining_journal_entries = []
                if self.journal_file.exists():
                    with open(self.journal_file, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                remaining_journal_entries.append(json.loads(line.strip()))
                            except Exception:
                                pass

                for rf in affected_reg_files:
                    rf_path = self.project_root / rf
                    if not rf_path.exists():
                        matches = [m for m in self.project_root.rglob(Path(rf).name) if not is_ignored_path(m, self.project_root)]
                        if matches:
                            rf_path = matches[0]
                    if rf_path.exists():
                        bak = rf_path.with_name(rf_path.name + ".bridge.bak")
                        rf_norm = str(rf_path).replace("\\", "/").lower()
                        rf_name = rf_path.name.lower()
                        has_other_changes = any(
                            (str(e.get("file", "")).replace("\\", "/").lower() == rf_norm or Path(e.get("file", "")).name.lower() == rf_name)
                            and e.get("type") not in ("token_added", "pattern_summary")
                            for e in remaining_journal_entries
                        )
                        has_other_changes = any(
                            (str(e.get("file", "")).replace("\\", "/").lower() == rf_norm or Path(e.get("file", "")).name.lower() == rf_name)
                            for e in remaining_journal_entries
                        )
                        if not has_other_changes and bak.exists():
                            try:
                                orig_c = bak.read_text(encoding="utf-8")
                                rf_path.write_text(orig_c, encoding="utf-8")
                                bak.unlink()
                                rel_rf = str(rf_path.relative_to(self.project_root)).replace("\\", "/")
                                self._clean_pending_edits(rel_rf)
                                self._clean_journal_for_file(rel_rf)
                                result["cleaned_files"].append(rf_path.name)
                            except Exception:
                                pass

            if warnings:
                result["warning"] = "\n".join(warnings)

        except Exception:
            pass

        return result


    def reject_file_changes(self, file_path: str, force: bool = False) -> Dict:
        """Revert all changes for a specific file with external modification guard."""
        changes = self.get_file_changes(file_path)
        full_path = self.project_root / file_path
        if not full_path.exists():
            matches = [m for m in self.project_root.rglob(Path(file_path).name) if not is_ignored_path(m, self.project_root)]
            if matches:
                full_path = matches[0]
            else:
                return {"success": False, "error": f"File '{file_path}' not found"}

        backup_path = Path(str(full_path) + ".bridge.bak")
        if not backup_path.exists():
            alt_matches = [m for m in self.project_root.rglob(full_path.name + ".bridge.bak") if "build" not in str(m) and ".composebridge-state" not in str(m)]
            if alt_matches:
                backup_path = alt_matches[0]
        if not backup_path.exists():
            mb_dir = self.project_root / ".composebridge-state" / "migration_backups"
            if mb_dir.exists():
                mb_candidates = sorted(mb_dir.glob(f"{full_path.stem}_*.kt.bak"), key=lambda x: x.stat().st_mtime, reverse=True)
                if mb_candidates:
                    backup_path = mb_candidates[0]

        # ═══ Dependency Guard: Refuse rejecting DesignSystem if its tokens are used by other files ═══
        target_name = Path(file_path).name
        registry_names = {
            "designsystem.kt", "appcolors.kt", "theme.kt", "appdimens.kt",
            "appstrings.kt", "themetokens.kt", "colors.kt", "dimens.kt", "strings.kt"
        }
        if target_name.lower() in registry_names and full_path.exists() and not force:
            try:
                curr_text = full_path.read_text(encoding="utf-8", errors="ignore")
                bak_text = ""
                if backup_path.exists():
                    bak_text = backup_path.read_text(encoding="utf-8", errors="ignore")

                import re
                curr_tokens = set(re.findall(r'\bval\s+([A-Za-z0-9_]+)\b', curr_text))
                bak_tokens = set(re.findall(r'\bval\s+([A-Za-z0-9_]+)\b', bak_text)) if bak_text else set()
                lost_tokens = curr_tokens - bak_tokens

                for entry in changes:
                    tname = entry.get("token") or entry.get("token_name")
                    if tname:
                        lost_tokens.add(tname)
                    pid = str(entry.get("pattern_id", ""))
                    if pid.startswith("create_token_"):
                        lost_tokens.add(pid.replace("create_token_", ""))
                    new_val = str(entry.get("new", "") or entry.get("new_line", ""))
                    for t in re.findall(r'\bval\s+([A-Za-z0-9_]+)\b', new_val):
                        lost_tokens.add(t)

                if lost_tokens:
                    for kt in self.project_root.rglob("*.kt"):
                        if is_ignored_path(kt, self.project_root):
                            continue
                        try:
                            if kt.resolve() == full_path.resolve():
                                continue
                            kt_content = kt.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            continue

                        for t in lost_tokens:
                            pattern = rf'\b(?:AppColors|AppDimens|AppStrings|DesignSystem|Theme)\.{re.escape(t)}\b'
                            if re.search(pattern, kt_content) or f".{t}" in kt_content:
                                try:
                                    rel_kt = str(kt.relative_to(self.project_root)).replace("\\", "/")
                                except Exception:
                                    rel_kt = str(kt).replace("\\", "/")
                                return {
                                    "success": False,
                                    "error": f"Cannot reject registry files directly. Reject the UI files that use them instead. Cannot reject {target_name} because its tokens are used by other approved files (file '{rel_kt}' uses token '{t}').",
                                    "message": f"Cannot reject registry files directly. Reject the UI files that use them instead. Cannot reject {target_name} because its tokens are used by other approved files (file '{rel_kt}' uses token '{t}').",
                                    "error_code": "DEPENDENCY_BLOCK",
                                    "blocking_file": rel_kt,
                                    "blocking_token": t
                                }
            except Exception:
                pass

        is_git_tracked = False
        try:
            rel_file = str(full_path.relative_to(self.project_root)).replace("\\", "/")
            chk = subprocess.run(
                ["git", "ls-files", "--error-unmatch", rel_file],
                cwd=str(self.project_root),
                capture_output=True,
                text=True
            )
            is_git_tracked = (chk.returncode == 0)
        except Exception:
            is_git_tracked = False

        if not backup_path.exists() and not changes and not is_git_tracked:
            return {"success": False, "error": f"No changes or backup found for {file_path}"}

        curr_content = full_path.read_text(encoding="utf-8")
        curr_bytes = full_path.read_bytes()
        import hashlib
        curr_checksum_bytes = hashlib.sha256(curr_bytes).hexdigest()
        curr_checksum_text = hashlib.sha256(curr_content.encode("utf-8")).hexdigest()
        curr_checksum_norm = compute_normalized_hash(curr_bytes)
        curr_checksum_deep = compute_deep_normalized_hash(curr_bytes)

        # Check for external modifications (verify against the latest change state)
        external_modified = False
        mismatch_reason = ""

        latest_change = changes[-1] if changes else None
        if latest_change and latest_change.get("checksum_after"):
            expected_chk = latest_change["checksum_after"]
            valid_hashes = (curr_checksum_bytes, curr_checksum_text, curr_checksum_norm, curr_checksum_deep)
            if expected_chk not in valid_hashes:
                # Secondary verification: Check if the change made by the tool is still intact in the file.
                # If the code still contains the target change, the difference is only whitespace / formatting by the IDE!
                is_actually_modified = True
                if latest_change.get("new"):
                    curr_norm = "\n".join(l.rstrip() for l in curr_content.replace("\r\n", "\n").replace("\r", "\n").splitlines())
                    target_norm = "\n".join(l.rstrip() for l in str(latest_change["new"]).replace("\r\n", "\n").replace("\r", "\n").splitlines()).strip()
                    if target_norm in curr_norm or target_norm.strip() in curr_norm:
                        is_actually_modified = False
                
                if is_actually_modified:
                    external_modified = True
                    mismatch_reason = "checksum_mismatch"

        if not external_modified and latest_change and latest_change.get("new"):
            curr_norm = curr_content.replace("\r\n", "\n").replace("\r", "\n")
            target_norm = str(latest_change["new"]).replace("\r\n", "\n").replace("\r", "\n")
            if target_norm not in curr_norm and target_norm.strip() not in curr_norm:
                external_modified = True
                mismatch_reason = "content_missing" 

        if not external_modified and backup_path.exists() and not changes:
            # Check if file is already identical to backup under deep normalization
            try:
                bak_bytes = backup_path.read_bytes()
                if compute_deep_normalized_hash(curr_bytes) == compute_deep_normalized_hash(bak_bytes):
                    pass # Identical to backup, no external modification
                else:
                    external_modified = True
                    mismatch_reason = "orphan_backup_modified"
            except Exception:
                external_modified = True
                mismatch_reason = "orphan_backup_modified"

        from common.file_ops import is_file_dirty_in_ide
        if is_file_dirty_in_ide(full_path, self.project_root):
            external_modified = True
            mismatch_reason = "dirty_buffer"

        file_name = Path(file_path).name
        msg_en = (
            f"⚠️ Warning: File '{file_name}' was modified externally (manually or by another agent).\n"
            f"Restoring the backup will overwrite these changes.\n"
            f"Are you sure?"
        )

        if external_modified and not force:
            try:
                from core.sync_client import send_warning_to_bridge
                send_warning_to_bridge(
                    warning_type="external_modification_detected",
                    file_path=str(file_path),
                    message=msg_en,
                    error_code="EXTERNAL_MODIFICATION_DETECTED",
                    suggested_action="confirm_restore",
                )
            except Exception:
                pass

            return {
                "success": False,
                "error_code": "EXTERNAL_MODIFICATION_DETECTED",
                "file": file_path,
                "message": msg_en,
                "error": msg_en,
                "mismatch_reason": mismatch_reason,
                "suggested_action": "confirm_restore",
                "can_force": True,
            }

        reverted = 0
        errors = []

        # 1. Primary rollback: Git checkout (if file is tracked in Git)
        if is_git_tracked:
            try:
                rel_file = str(full_path.relative_to(self.project_root)).replace("\\", "/")
                res = subprocess.run(
                    ["git", "-C", str(self.project_root), "checkout", "--", rel_file],
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True
                )
                if res.returncode == 0:
                    from core.ast_finder import validate_kotlin_syntax
                    is_valid, err_msg = validate_kotlin_syntax(full_path)
                    if not is_valid:
                        return {
                            "success": False,
                            "file": file_path,
                            "error": f"❌ فشل التراجع: الملف المسترجع يحتوي على أخطاء برمجية ({err_msg}). يرجى التحقق من Git أو إصلاح الملف يدوياً.",
                            "message": f"❌ فشل التراجع: الملف المسترجع يحتوي على أخطاء برمجية ({err_msg}). يرجى التحقق من Git أو إصلاح الملف يدوياً.",
                        }
                    if backup_path.exists():
                        try:
                            backup_path.unlink()
                        except Exception:
                            pass
                    self._clean_pending_edits(file_path)
                    self._clean_journal_for_file(file_path)
                    cascade_info = self._handle_cascade_token_reject(file_path, changes)
                    msg = f"تمت استعادة الملف '{file_path}' بنجاح عبر Git."
                    if cascade_info.get("removed_tokens"):
                        msg += f" وتم حذف التوكنات اليتيمة تلقائياً: {', '.join(cascade_info['removed_tokens'])}."
                    if cascade_info.get("cleaned_files"):
                        msg += f" وتنظيف ملفات التسجيل: {', '.join(cascade_info['cleaned_files'])}."
                    if cascade_info.get("warning"):
                        msg += f"\n{cascade_info['warning']}"
                    return {
                        "success": True,
                        "file": file_path,
                        "reverted_count": 1,
                        "cascade_removed_tokens": cascade_info.get("removed_tokens", []),
                        "cascade_cleaned_files": cascade_info.get("cleaned_files", []),
                        "warning": cascade_info.get("warning"),
                        "message": msg,
                    }
                else:
                    errors.append({"file": file_path, "error": f"Git checkout returned code {res.returncode}: {res.stderr}"})
            except Exception as e:
                errors.append({"file": file_path, "error": f"Git checkout error: {e}"})

        # 2. Secondary rollback: .bridge.bak backup (holds true session baseline if not tracked in Git)
        if backup_path.exists():
            try:
                from core.ast_finder import validate_kotlin_syntax
                is_valid_bak, bak_err = validate_kotlin_syntax(backup_path)
            except Exception:
                is_valid_bak = True

            if is_valid_bak:
                try:
                    orig_content = full_path.read_text(encoding="utf-8")
                    shutil.copy2(str(backup_path), str(full_path))
                    from core.ast_finder import validate_kotlin_syntax
                    is_valid, err_msg = validate_kotlin_syntax(full_path)
                    if not is_valid:
                        full_path.write_text(orig_content, encoding="utf-8")
                        return {
                            "success": False,
                            "file": file_path,
                            "error": f"❌ فشل التراجع: الملف المسترجع يحتوي على أخطاء برمجية ({err_msg}). يرجى التحقق من الملف يدوياً.",
                            "message": f"❌ فشل التراجع: الملف المسترجع يحتوي على أخطاء برمجية ({err_msg}). يرجى التحقق من الملف يدوياً.",
                        }
                    try:
                        backup_path.unlink()
                    except Exception:
                        pass
                    reverted += 1
                    self._clean_pending_edits(file_path)
                    self._clean_journal_for_file(file_path)
                    cascade_info = self._handle_cascade_token_reject(file_path, changes)
                    msg = f"تمت استعادة الملف '{file_path}' بنجاح من النسخة الاحتياطية الأصلية (.bridge.bak)."
                    if cascade_info.get("removed_tokens"):
                        msg += f" وتم حذف التوكنات اليتيمة تلقائياً: {', '.join(cascade_info['removed_tokens'])}."
                    if cascade_info.get("cleaned_files"):
                        msg += f" وتنظيف ملفات التسجيل: {', '.join(cascade_info['cleaned_files'])}."
                    if cascade_info.get("warning"):
                        msg += f"\n{cascade_info['warning']}"
                    return {
                        "success": True,
                        "file": file_path,
                        "reverted_count": reverted,
                        "cascade_removed_tokens": cascade_info.get("removed_tokens", []),
                        "cascade_cleaned_files": cascade_info.get("cleaned_files", []),
                        "warning": cascade_info.get("warning"),
                        "message": msg,
                    }
                except Exception as e:
                    errors.append({"file": file_path, "error": f"Failed to restore backup: {e}"})
            else:
                return {
                    "success": False,
                    "file": file_path,
                    "error": f"❌ فشل التراجع: النسخة الاحتياطية تحتوي على أخطاء برمجية ({bak_err}). يرجى التحقق من Git أو إصلاح الملف يدوياً.",
                    "message": f"❌ فشل التراجع: النسخة الاحتياطية تحتوي على أخطاء برمجية ({bak_err}). يرجى التحقق من Git أو إصلاح الملف يدوياً.",
                }

        # 3. Tertiary check: If no backup and not tracked in Git, fail with clear error
        if not backup_path.exists() and not is_git_tracked:
            return {"success": False, "file": file_path, "error": f"❌ لا توجد نسخة احتياطية (.bridge.bak) ولا تتبع Git للملف '{file_path}' للتراجع عنها."}
        # Skip obsolete fuzzy text replacement
        if False:
            try:
                from core.ast_finder import validate_kotlin_syntax
                is_valid_bak, bak_err = validate_kotlin_syntax(backup_path)
            except Exception:
                is_valid_bak = True

            if is_valid_bak:
                try:
                    orig_content = full_path.read_text(encoding="utf-8")
                    shutil.copy2(str(backup_path), str(full_path))
                    from core.ast_finder import validate_kotlin_syntax
                    is_valid, err_msg = validate_kotlin_syntax(full_path)
                    if not is_valid:
                        full_path.write_text(orig_content, encoding="utf-8")
                        return {
                            "success": False,
                            "file": file_path,
                            "error": f"❌ فشل التراجع: الملف المسترجع يحتوي على أخطاء برمجية ({err_msg}). يرجى التحقق من الملف يدوياً.",
                            "message": f"❌ فشل التراجع: الملف المسترجع يحتوي على أخطاء برمجية ({err_msg}). يرجى التحقق من الملف يدوياً.",
                        }
                    try:
                        backup_path.unlink()
                    except Exception:
                        pass
                    reverted += 1
                    self._clean_pending_edits(file_path)
                    self._clean_journal_for_file(file_path)
                    cascade_info = self._handle_cascade_token_reject(file_path, changes)
                    msg = f"تمت استعادة الملف '{file_path}' بنجاح من النسخة الاحتياطية."
                    if cascade_info.get("removed_tokens"):
                        msg += f" وتم حذف التوكنات اليتيمة تلقائياً: {', '.join(cascade_info['removed_tokens'])}."
                    if cascade_info.get("cleaned_files"):
                        msg += f" وتنظيف ملفات التسجيل: {', '.join(cascade_info['cleaned_files'])}."
                    if cascade_info.get("warning"):
                        msg += f"\n{cascade_info['warning']}"
                    return {
                        "success": True,
                        "file": file_path,
                        "reverted_count": reverted,
                        "cascade_removed_tokens": cascade_info.get("removed_tokens", []),
                        "cascade_cleaned_files": cascade_info.get("cleaned_files", []),
                        "warning": cascade_info.get("warning"),
                        "message": msg,
                    }
                except Exception as e:
                    errors.append({"file": file_path, "error": f"Failed to restore backup: {e}"})
            else:
                return {
                    "success": False,
                    "file": file_path,
                    "error": f"❌ فشل التراجع: النسخة الاحتياطية تحتوي على أخطاء برمجية ({bak_err}). يرجى التحقق من Git أو إصلاح الملف يدوياً.",
                    "message": f"❌ فشل التراجع: النسخة الاحتياطية تحتوي على أخطاء برمجية ({bak_err}). يرجى التحقق من Git أو إصلاح الملف يدوياً.",
                }
            try:
                rel_file = str(full_path.relative_to(self.project_root)).replace("\\", "/")
                res = subprocess.run(
                    ["git", "-C", str(self.project_root), "checkout", "--", rel_file],
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True
                )
                if res.returncode == 0:
                    from core.ast_finder import validate_kotlin_syntax
                    is_valid, err_msg = validate_kotlin_syntax(full_path)
                    if not is_valid:
                        return {
                            "success": False,
                            "file": file_path,
                            "error": f"❌ فشل التراجع: الملف المسترجع يحتوي على أخطاء برمجية ({err_msg}). يرجى التحقق من Git أو إصلاح الملف يدوياً.",
                            "message": f"❌ فشل التراجع: الملف المسترجع يحتوي على أخطاء برمجية ({err_msg}). يرجى التحقق من Git أو إصلاح الملف يدوياً.",
                        }
                    self._clean_pending_edits(file_path)
                    self._clean_journal_for_file(file_path)
                    cascade_info = self._handle_cascade_token_reject(file_path, changes)
                    msg = f"تمت استعادة الملف '{file_path}' بنجاح عبر Git."
                    if cascade_info.get("removed_tokens"):
                        msg += f" وتم حذف التوكنات اليتيمة تلقائياً: {', '.join(cascade_info['removed_tokens'])}."
                    if cascade_info.get("cleaned_files"):
                        msg += f" وتنظيف ملفات التسجيل: {', '.join(cascade_info['cleaned_files'])}."
                    if cascade_info.get("warning"):
                        msg += f"\n{cascade_info['warning']}"
                    return {
                        "success": True,
                        "file": file_path,
                        "reverted_count": 1,
                        "cascade_removed_tokens": cascade_info.get("removed_tokens", []),
                        "cascade_cleaned_files": cascade_info.get("cleaned_files", []),
                        "warning": cascade_info.get("warning"),
                        "message": msg,
                    }
                else:
                    errors.append({"file": file_path, "error": f"Git checkout returned code {res.returncode}: {res.stderr}"})
            except Exception as e:
                errors.append({"file": file_path, "error": f"Git checkout error: {e}"})

        # 3. Tertiary fallback: Only if NO backup and NO Git, try text replacement
        if False:
            try:
                from core.ast_finder import validate_kotlin_syntax
                is_valid_bak, bak_err = validate_kotlin_syntax(backup_path)
            except Exception:
                is_valid_bak = True

            if is_valid_bak:
                try:
                    orig_content = full_path.read_text(encoding="utf-8")
                    shutil.copy2(str(backup_path), str(full_path))
                    from core.ast_finder import validate_kotlin_syntax
                    is_valid, err_msg = validate_kotlin_syntax(full_path)
                    if not is_valid:
                        full_path.write_text(orig_content, encoding="utf-8")
                        return {
                            "success": False,
                            "file": file_path,
                            "error": f"❌ فشل التراجع: الملف المسترجع يحتوي على أخطاء برمجية ({err_msg}). يرجى التحقق من Git أو إصلاح الملف يدوياً.",
                            "message": f"❌ فشل التراجع: الملف المسترجع يحتوي على أخطاء برمجية ({err_msg}). يرجى التحقق من Git أو إصلاح الملف يدوياً.",
                        }
                    try:
                        backup_path.unlink()
                    except Exception:
                        pass
                    reverted += 1
                    self._clean_pending_edits(file_path)
                    self._clean_journal_for_file(file_path)
                    cascade_info = self._handle_cascade_token_reject(file_path, changes)
                    msg = f"تمت استعادة الملف '{file_path}' بنجاح من النسخة الاحتياطية."
                    if cascade_info.get("removed_tokens"):
                        msg += f" وتم حذف التوكنات اليتيمة تلقائياً: {', '.join(cascade_info['removed_tokens'])}."
                    if cascade_info.get("cleaned_files"):
                        msg += f" وتنظيف ملفات التسجيل: {', '.join(cascade_info['cleaned_files'])}."
                    if cascade_info.get("warning"):
                        msg += f"\n{cascade_info['warning']}"
                    return {
                        "success": True,
                        "file": file_path,
                        "reverted_count": reverted,
                        "cascade_removed_tokens": cascade_info.get("removed_tokens", []),
                        "cascade_cleaned_files": cascade_info.get("cleaned_files", []),
                        "warning": cascade_info.get("warning"),
                        "message": msg,
                    }
                except Exception as e:
                    errors.append({"file": file_path, "error": f"Failed to restore backup: {e}"})
            else:
                return {
                    "success": False,
                    "file": file_path,
                    "error": f"❌ فشل التراجع: النسخة الاحتياطية تحتوي على أخطاء برمجية ({bak_err}). يرجى التحقق من Git أو إصلاح الملف يدوياً.",
                    "message": f"❌ فشل التراجع: النسخة الاحتياطية تحتوي على أخطاء برمجية ({bak_err}). يرجى التحقق من Git أو إصلاح الملف يدوياً.",
                }
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


    def reject_all_files(self, force: bool = False) -> Dict:
        """
        Revert all pending changes in REVERSE order (latest edit first).
        """
        try:
            # 1. Restore any *.bridge.bak files on disk
            disk_reverted = 0
            restored_from_backup_files = set()
            try:
                for bak in list(self.project_root.rglob("*.bridge.bak")):
                    if any(ign in bak.parts for ign in ["build", ".gradle", ".git", ".composebridge-state"]):
                        continue
                    orig_str = str(bak)[:-len(".bridge.bak")]
                    orig_path = Path(orig_str)
                    try:
                        from core.ast_finder import validate_kotlin_syntax
                        is_valid_bak, _ = validate_kotlin_syntax(bak)
                        if is_valid_bak:
                            shutil.copy2(str(bak), str(orig_path))
                            bak.unlink()
                            disk_reverted += 1
                            try:
                                rel_b = str(orig_path.relative_to(self.project_root)).replace("\\", "/")
                            except Exception:
                                rel_b = orig_path.name
                            restored_from_backup_files.add(rel_b)
                            restored_from_backup_files.add(orig_path.name)
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
                # Do not apply reverse text replacements to files already restored from disk backup!
                if file_rel in restored_from_backup_files or Path(str(file_rel)).name in restored_from_backup_files:
                    continue
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
        from core.token_migrator import TokenMigrator
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
            if not file_name or not str(file_name).strip():
                continue
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

