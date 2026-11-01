# -*- coding: utf-8 -*-
"""
Journal, atomic write locking, and splice history helpers for state editor.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

try:
    from core.project_root import get_project_root
    PROJECT_ROOT = get_project_root()
except Exception:
    PROJECT_ROOT = Path(os.environ.get("COMPOSEBRIDGE_ROOT", "."))

try:
    from common.file_ops import acquire_write_lock, _atomic_write_text
except ImportError:
    try:
        from server.common.file_ops import acquire_write_lock, _atomic_write_text
    except ImportError:
        from ..common.file_ops import acquire_write_lock, _atomic_write_text

JOURNAL_FILE = PROJECT_ROOT / ".composebridge-journal.json"


MAX_JOURNAL = 50


def with_write_lock(func):
    """Decorator to run function inside shared write lock."""
    def wrapper(*args, **kwargs):
        with acquire_write_lock():
            return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


SPLICE_JOURNAL = []


def _journal_save(file_path, original_content, new_content, pattern_id="cli_edit"):
    entry = {
        "file": str(file_path),
        "original": original_content,
        "new": new_content,
        "timestamp": time.time(),
    }

    # In-memory
    SPLICE_JOURNAL.append(entry)
    if len(SPLICE_JOURNAL) > MAX_JOURNAL:
        SPLICE_JOURNAL.pop(0)

    # Disk (.composebridge-journal.json is deprecated; state is kept in PatternJournal)

    # Ensure .bridge.bak is persisted alongside the target file (only from valid content)
    try:
        bak_file = Path(str(file_path) + ".bridge.bak")
        if not bak_file.exists():
            from core.ast_finder import validate_kotlin_syntax
            is_valid, _ = validate_kotlin_syntax(original_content)
            if is_valid:
                bak_file.write_text(original_content, encoding="utf-8")
            else:
                sys.stderr.write(f"[journal] Refused to create .bridge.bak: original content contains syntax errors\n")
    except Exception as e:
        sys.stderr.write(f"[journal] failed to create .bridge.bak: {e}\n")

    # Compute discrete diff hunks across all changed lines (no break on first line!)
    import difflib
    old_lines = original_content.splitlines()
    new_lines = new_content.splitlines()
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    changed_hunks = []
    for tag, alo, ahi, blo, bhi in matcher.get_opcodes():
        if tag == "equal":
            continue
        old_slice = old_lines[alo:ahi]
        new_slice = new_lines[blo:bhi]
        line_num = blo + 1 if blo < len(new_lines) else max(1, len(new_lines))
        changed_hunks.append({
            "line": line_num,
            "old_line": "\n".join(old_slice),
            "new_line": "\n".join(new_slice),
        })

    if not changed_hunks:
        changed_hunks.append({
            "line": 1,
            "old_line": "",
            "new_line": "",
        })

    first_hunk = changed_hunks[0]
    changed_line = first_hunk["line"]
    old_line_text = first_hunk["old_line"]
    new_line_text = first_hunk["new_line"]

    # 1. Record all hunks in PatternJournal for IDE
    try:
        from core.project_root import get_project_root
        proj_root = get_project_root()
    except Exception:
        proj_root = PROJECT_ROOT

    rel_path = str(file_path)
    try:
        rel_path = str(Path(file_path).relative_to(proj_root)).replace("\\", "/")
    except Exception:
        rel_path = str(file_path).replace("\\", "/")

    try:
        from core.pattern_journal import PatternJournal
        pj = PatternJournal(proj_root)
        for h in changed_hunks:
            pj.record_change(
                file=rel_path,
                line=h["line"],
                old_line=h["old_line"],
                new_line=h["new_line"],
                pattern_id=pattern_id,
            )
    except Exception as e:
        sys.stderr.write(f"[journal] failed to record in PatternJournal: {e}\n")

    # 2. Record in pending_edits.json
    try:
        pending_paths = [
            proj_root / ".composebridge-state" / "pending_edits.json",
            proj_root / "pending_edits.json",
        ]
        for ppath in pending_paths:
            ppath.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if ppath.exists():
                try:
                    with open(ppath, "r", encoding="utf-8") as pf:
                        existing = json.load(pf)
                except Exception:
                    existing = []
            if not isinstance(existing, list):
                existing = []

            # Preserve earliest original old value across multiple edits
            orig_old = old_line_text
            for item in existing:
                if item.get("file") == rel_path or Path(item.get("file", "")).name == Path(file_path).name:
                    if item.get("old"):
                        orig_old = item["old"]
                    break

            filtered = [item for item in existing if item.get("file") != rel_path and Path(item.get("file", "")).name != Path(file_path).name]
            filtered.append({
                "file": rel_path,
                "backup": str(file_path) + ".bridge.bak",
                "timestamp": time.time(),
                "line": changed_line,
                "old": orig_old,
                "new": new_line_text,
            })
            with open(ppath, "w", encoding="utf-8") as pf:
                json.dump(filtered, pf, indent=2, ensure_ascii=False)
    except Exception as e:
        sys.stderr.write(f"[journal] failed to save pending_edits: {e}\n")

    # 3. Live notification: broadcast changes to connected IDE & devices
    try:
        from network.ws_server import trigger_broadcast_refresh
        trigger_broadcast_refresh()
    except Exception:
        pass


def _validate_after_splice(file_path):
    from core.ast_finder import validate_file_parses
    if not validate_file_parses(file_path):
        if SPLICE_JOURNAL:
            last = SPLICE_JOURNAL[-1]
            Path(last["file"]).write_text(last["original"], encoding="utf-8")
        return False
    return True


def rollback_last():
    # إذا الذاكرة فارغة — اقرأ من القرص
    if not SPLICE_JOURNAL:
        if not JOURNAL_FILE.exists():
            return False

        try:
            with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if not lines:
                return False

            # آخر entry
            last = json.loads(lines[-1])
            SPLICE_JOURNAL.append(last)
        except Exception as e:
            sys.stderr.write(f"[journal] failed to read: {e}\n")
            return False

    # تراجع
    last = SPLICE_JOURNAL.pop()
    Path(last["file"]).write_text(last["original"], encoding="utf-8")

    # احذف آخر سطر من الملف
    try:
        if JOURNAL_FILE.exists():
            with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[:-1])
    except Exception:
        pass

    return True

