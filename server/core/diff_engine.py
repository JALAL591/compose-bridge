import re
from common.file_ops import is_ignored_path
# -*- coding: utf-8 -*-
"""
Diff Engine for ComposeBridge.
Computes granular diffs (hunks) line-by-line and provides granular approve/reject control.
"""

import difflib
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

from core.ast_finder import validate_kotlin_syntax, safe_create_backup

def get_original_content(file_path: Path, project_root: Path) -> Tuple[str, Optional[Path]]:
    """
    Retrieves original baseline content for a modified file.
    Order of precedence:
    1. Local .bridge.bak backup alongside file.
    2. Git HEAD version if file is tracked.
    3. Reconstruct from current file content if no other baseline exists.
    """
    backup_path = file_path.with_name(file_path.name + ".bridge.bak")
    if backup_path.exists():
        try:
            return backup_path.read_text(encoding="utf-8", errors="replace"), backup_path
        except Exception:
            pass

    # Check Git HEAD
    try:
        rel_file = str(file_path.relative_to(project_root)).replace("\\", "/")
        res = subprocess.run(
            ["git", "-C", str(project_root), "show", f"HEAD:{rel_file}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if res.returncode == 0:
            return res.stdout, None
    except Exception:
        pass

    if file_path.exists():
        return file_path.read_text(encoding="utf-8", errors="replace"), None

    return "", None


def compute_file_hunks(orig_text: str, curr_text: str) -> List[Dict[str, Any]]:
    """
    Computes list of discrete hunks/changes between orig_text and curr_text using difflib.
    Each hunk contains:
    - id: "h1", "h2", ...
    - line_start: 1-indexed start line in modified (current) file
    - line_end: 1-indexed end line in modified (current) file
    - old: text from original
    - new: text from current
    - orig_range: (start, end) 0-indexed line slice
    - curr_range: (start, end) 0-indexed line slice
    """
    orig_lines = orig_text.splitlines()
    curr_lines = curr_text.splitlines()
    matcher = difflib.SequenceMatcher(None, orig_lines, curr_lines)
    hunks = []
    idx = 1
    for tag, alo, ahi, blo, bhi in matcher.get_opcodes():
        if tag == "equal":
            continue
        old_slice = orig_lines[alo:ahi]
        new_slice = curr_lines[blo:bhi]
        line_start = blo + 1 if blo < len(curr_lines) else max(1, len(curr_lines))
        line_end = max(line_start, bhi)
        hunk_id = f"h{idx}"
        hunks.append({
            "id": hunk_id,
            "line_start": line_start,
            "line_end": line_end,
            "old": "\n".join(old_slice),
            "new": "\n".join(new_slice),
            "tag": tag,
            "orig_range": (alo, ahi),
            "curr_range": (blo, bhi),
        })
        idx += 1
    return hunks


def _find_target_hunk(hunks: List[Dict[str, Any]], change_id: str) -> Optional[Dict[str, Any]]:
    """Finds hunk by ID, line number, or content."""
    # 1. Exact ID match
    for h in hunks:
        if h["id"] == change_id:
            return h
    # 2. Line number match
    for h in hunks:
        if str(h.get("line_start")) == str(change_id) or f"line_{h.get('line_start')}" == str(change_id):
            return h
    # 3. Fallback: single remaining hunk
    if len(hunks) == 1 and change_id in ("h1", "h2", "h3", "first", "last"):
        return hunks[0]
    return None


def get_file_diff_report(file_path: Path, project_root: Path) -> Dict[str, Any]:
    """
    Returns full diff report and hunks for a file.
    """
    if not file_path.exists():
        matches = [m for m in project_root.rglob(file_path.name)
                   if not is_ignored_path(m, project_root)]
        if matches:
            file_path = matches[0]
        else:
            return {"file": str(file_path), "name": file_path.name, "status": "not_found", "changes": [], "change_count": 0}

    try:
        rel_file = str(file_path.relative_to(project_root)).replace("\\", "/")
    except Exception:
        rel_file = str(file_path).replace("\\", "/")

    curr_text = file_path.read_text(encoding="utf-8", errors="replace")
    orig_text, bak_path = get_original_content(file_path, project_root)

    hunks = compute_file_hunks(orig_text, curr_text)
    return {
        "file": rel_file,
        "name": file_path.name,
        "status": "modified" if hunks else "unmodified",
        "change_count": len(hunks),
        "changes": hunks,
        "has_backup": bak_path is not None and bak_path.exists(),
    }


KNOWN_REGISTRIES = [
    "BridgeTextRegistry",
    "BridgeThemeRegistry",
    "BridgeDimensionRegistry",
    "AppColors",
    "AppDimens",
    "AppStrings",
]

def _find_associated_import_hunks(target_hunk: Dict[str, Any], all_hunks: List[Dict[str, Any]], mode: str = "approve") -> List[Dict[str, Any]]:
    """
    Finds import hunks associated with the target hunk to ensure atomic approve/reject.
    - If mode == "approve":
        If target_hunk uses a registry, find import hunks in the same file that introduce that registry.
    - If mode == "reject":
        If target_hunk uses a registry, and no other hunk in all_hunks uses that registry,
        the import hunk should be reverted atomically as well.
    """
    associated = []
    text_to_check = target_hunk.get("new", "")

    for reg in KNOWN_REGISTRIES:
        if reg in text_to_check:
            for h in all_hunks:
                if h["id"] == target_hunk["id"]:
                    continue
                h_new = h.get("new", "")
                if "import " in h_new and reg in h_new:
                    if mode == "approve":
                        if h not in associated:
                            associated.append(h)
                    elif mode == "reject":
                        other_usages = any(
                            oh["id"] not in (target_hunk["id"], h["id"]) and reg in oh.get("new", "")
                            for oh in all_hunks
                        )
                        if not other_usages and h not in associated:
                            associated.append(h)
    return associated


def reject_change(file_path_str: str, change_id: str, project_root: Path) -> Dict[str, Any]:
    """
    Reverts a single granular change (hunk) in file_path while keeping other changes intact.
    """
    full_path = project_root / file_path_str
    if not full_path.exists():
        matches = [m for m in project_root.rglob(Path(file_path_str).name)
                   if not is_ignored_path(m, project_root)]
        if matches:
            full_path = matches[0]
        else:
            return {"success": False, "error": f"File '{file_path_str}' not found"}

    try:
        rel_file = str(full_path.relative_to(project_root)).replace("\\", "/")
    except Exception:
        rel_file = file_path_str

    curr_text = full_path.read_text(encoding="utf-8")
    orig_text, bak_path = get_original_content(full_path, project_root)
    hunks = compute_file_hunks(orig_text, curr_text)

    target_hunk = _find_target_hunk(hunks, change_id)
    if not target_hunk:
        return {"success": False, "error": f"Change '{change_id}' not found in '{rel_file}'"}

    # ═══ Dependency Guard: Refuse rejecting registry hunk if its tokens are used elsewhere ═══
    target_name_lower = full_path.name.lower()
    if target_name_lower in {"designsystem.kt", "appcolors.kt", "appdimens.kt", "appstrings.kt"}:
        removed_tokens = set(re.findall(r'\bval\s+([A-Za-z0-9_]+)\b', target_hunk.get("new", "")))
        for t in removed_tokens:
            for kt in project_root.rglob("*.kt"):
                if is_ignored_path(kt, project_root):
                    continue
                try:
                    if kt.resolve() == full_path.resolve():
                        continue
                    kt_code = kt.read_text(encoding="utf-8", errors="ignore")
                    if f".{t}" in kt_code or re.search(rf'\b(?:AppColors|AppDimens|DesignSystem)\.{re.escape(t)}\b', kt_code):
                        try:
                            rel_kt = str(kt.relative_to(project_root)).replace("\\", "/")
                        except Exception:
                            rel_kt = str(kt).replace("\\", "/")
                        return {
                            "success": False,
                            "error": f"Cannot reject change in {full_path.name}: token '{t}' is used by '{rel_kt}'. Reverting this change would break the build.",
                            "error_code": "DEPENDENCY_BLOCK",
                            "blocking_file": rel_kt,
                            "blocking_token": t
                        }
                except Exception:
                    continue

    # Atomic Rejection: find any associated import hunks
    hunks_to_reject = [target_hunk]
    for assoc in _find_associated_import_hunks(target_hunk, hunks, mode="reject"):
        if assoc not in hunks_to_reject:
            hunks_to_reject.append(assoc)

    curr_lines = curr_text.splitlines()
    orig_lines = orig_text.splitlines()

    # Apply rejection in reverse order of current line positions to keep slices stable
    new_curr_lines = list(curr_lines)
    for h in sorted(hunks_to_reject, key=lambda x: x["curr_range"][0], reverse=True):
        blo, bhi = h["curr_range"]
        alo, ahi = h["orig_range"]
        new_curr_lines[blo:bhi] = orig_lines[alo:ahi]
    new_curr_text = "\n".join(new_curr_lines)
    if curr_text.endswith("\n"):
        new_curr_text += "\n"

    # Validate syntax before writing
    is_valid, err_msg = validate_kotlin_syntax(new_curr_text)
    if not is_valid:
        return {
            "success": False,
            "error": f"❌ لا يمكن التراجع عن هذا التعديل لأنه سيسبب خطأ برمجياً: {err_msg}",
            "file": rel_file,
            "change_id": change_id,
        }

    full_path.write_text(new_curr_text, encoding="utf-8")

    # Re-evaluate remaining hunks
    remaining = compute_file_hunks(orig_text, new_curr_text)

    # If no remaining hunks, file is identical to baseline! Clean up backup
    if not remaining:
        if bak_path and bak_path.exists():
            try:
                bak_path.unlink()
            except Exception:
                pass
        try:
            from core.pattern_journal import PatternJournal
            journal = PatternJournal(project_root)
            changes_before = journal.get_file_changes(rel_file)
            journal._clean_pending_edits(rel_file)
            journal._clean_journal_for_file(rel_file)
            journal._handle_cascade_token_reject(rel_file, changes_before)
        except Exception:
            pass

    return {
        "success": True,
        "file": rel_file,
        "change_id": change_id,
        "remaining_count": len(remaining),
        "changes": remaining,
        "message": f"تم التراجع عن التعديل '{change_id}' بنجاح في '{full_path.name}'.",
    }


def approve_change(file_path_str: str, change_id: str, project_root: Path) -> Dict[str, Any]:
    """
    Approves a single granular change (hunk) by incorporating it into the baseline backup,
    so that it is no longer considered a pending change.
    """
    full_path = project_root / file_path_str
    if not full_path.exists():
        matches = [m for m in project_root.rglob(Path(file_path_str).name)
                   if not is_ignored_path(m, project_root)]
        if matches:
            full_path = matches[0]
        else:
            return {"success": False, "error": f"File '{file_path_str}' not found"}

    try:
        rel_file = str(full_path.relative_to(project_root)).replace("\\", "/")
    except Exception:
        rel_file = file_path_str

    curr_text = full_path.read_text(encoding="utf-8")
    orig_text, bak_path = get_original_content(full_path, project_root)
    hunks = compute_file_hunks(orig_text, curr_text)

    target_hunk = _find_target_hunk(hunks, change_id)
    if not target_hunk:
        return {"success": False, "error": f"Change '{change_id}' not found in '{rel_file}'"}

    # ═══ Dependency Guard: Refuse rejecting registry hunk if its tokens are used elsewhere ═══
    target_name_lower = full_path.name.lower()
    if target_name_lower in {"designsystem.kt", "appcolors.kt", "appdimens.kt", "appstrings.kt"}:
        removed_tokens = set(re.findall(r'\bval\s+([A-Za-z0-9_]+)\b', target_hunk.get("new", "")))
        for t in removed_tokens:
            for kt in project_root.rglob("*.kt"):
                if is_ignored_path(kt, project_root):
                    continue
                try:
                    if kt.resolve() == full_path.resolve():
                        continue
                    kt_code = kt.read_text(encoding="utf-8", errors="ignore")
                    if f".{t}" in kt_code or re.search(rf'\b(?:AppColors|AppDimens|DesignSystem)\.{re.escape(t)}\b', kt_code):
                        try:
                            rel_kt = str(kt.relative_to(project_root)).replace("\\", "/")
                        except Exception:
                            rel_kt = str(kt).replace("\\", "/")
                        return {
                            "success": False,
                            "error": f"Cannot reject change in {full_path.name}: token '{t}' is used by '{rel_kt}'. Reverting this change would break the build.",
                            "error_code": "DEPENDENCY_BLOCK",
                            "blocking_file": rel_kt,
                            "blocking_token": t
                        }
                except Exception:
                    continue

    # Atomic Approval: find any associated import hunks that must be approved with this code
    hunks_to_approve = [target_hunk]
    for assoc in _find_associated_import_hunks(target_hunk, hunks, mode="approve"):
        if assoc not in hunks_to_approve:
            hunks_to_approve.append(assoc)

    curr_lines = curr_text.splitlines()
    orig_lines = orig_text.splitlines()

    # Apply approval in reverse order of original line positions to keep slices stable
    new_orig_lines = list(orig_lines)
    for h in sorted(hunks_to_approve, key=lambda x: x["orig_range"][0], reverse=True):
        blo, bhi = h["curr_range"]
        alo, ahi = h["orig_range"]
        new_orig_lines[alo:ahi] = curr_lines[blo:bhi]
    new_orig_text = "\n".join(new_orig_lines)
    if orig_text.endswith("\n"):
        new_orig_text += "\n"

    # Ensure .bridge.bak exists and update it with new baseline
    backup_file = bak_path or full_path.with_name(full_path.name + ".bridge.bak")
    backup_file.write_text(new_orig_text, encoding="utf-8")

    # Re-evaluate remaining hunks
    remaining = compute_file_hunks(new_orig_text, curr_text)

    # If all hunks in this file have been approved, clean up backup and journal!
    if not remaining:
        if backup_file.exists():
            try:
                backup_file.unlink()
            except Exception:
                pass
        try:
            from core.pattern_journal import PatternJournal
            journal = PatternJournal(project_root)
            journal._clean_pending_edits(rel_file)
            journal._clean_journal_for_file(rel_file)
        except Exception:
            pass

    return {
        "success": True,
        "file": rel_file,
        "change_id": change_id,
        "remaining_count": len(remaining),
        "changes": remaining,
        "message": f"تم قبول التعديل '{change_id}' بنجاح وتحديث الأساس للملف '{full_path.name}'.",
    }

# ═══ Aliases for atomic approve / reject ═══
approve_hunk = approve_change
reject_hunk = reject_change
