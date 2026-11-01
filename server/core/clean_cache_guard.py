# -*- coding: utf-8 -*-
"""
Clean Cache Guard.
Prevents accidental deletion of journal, migration backups, and state files
when there are pending, unapproved edits in the project.
"""

import json
from pathlib import Path
from typing import Tuple, Optional

try:
    from core.project_root import get_project_root
except ImportError:
    try:
        from server.core.project_root import get_project_root
    except ImportError:
        def get_project_root():
            return Path.cwd()


def should_allow_clean_cache(project_root: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Checks if it is safe to clean temporary cache and state files.
    Returns (True, "Safe to clean.") if no pending edits exist.
    Returns (False, warning_message) if unapproved edits are detected.
    """
    root = Path(project_root) if project_root else get_project_root()
    journal_file = root / ".composebridge-state" / "pattern_journal.jsonl"
    legacy_journal = root / ".composebridge-journal.json"

    pending_count = 0

    # 1. Inspect primary pattern_journal.jsonl
    if journal_file.exists():
        try:
            with open(journal_file, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        entry = json.loads(line_str)
                        if isinstance(entry, dict) and entry.get("file"):
                            pending_count += 1
                    except Exception:
                        pending_count += 1
        except Exception:
            pass

    # 2. Inspect legacy journal
    if legacy_journal.exists() and pending_count == 0:
        try:
            data = json.loads(legacy_journal.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 0:
                pending_count += len(data)
            elif isinstance(data, dict) and data.get("changes"):
                pending_count += len(data["changes"])
        except Exception:
            pass

    # 3. Inspect pending_edits.json
    pending_edits = root / ".composebridge-state" / "pending_edits.json"
    if pending_edits.exists() and pending_count == 0:
        try:
            p_data = json.loads(pending_edits.read_text(encoding="utf-8"))
            if isinstance(p_data, list) and len(p_data) > 0:
                pending_count += len(p_data)
        except Exception:
            pass

    if pending_count > 0:
        return (
            False,
            f"There are {pending_count} pending edit(s). Please Approve or Reject them before cleaning cache."
        )

    return (True, "Safe to clean.")

