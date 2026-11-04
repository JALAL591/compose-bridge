# -*- coding: utf-8 -*-
"""
Common file operations, atomic writing, and registry discovery utilities.
Consolidated during Phase 1 refactoring to eliminate cross-module code duplication.
"""

import os
import time
import json
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Union

# Re-export acquire_write_lock from write_lock
try:
    from core.write_lock import acquire_write_lock, get_lock_path, WRITE_LOCK
except Exception:
    try:
        from server.core.write_lock import acquire_write_lock, get_lock_path, WRITE_LOCK
    except Exception:
        from contextlib import contextmanager

        @contextmanager
        def acquire_write_lock(timeout: float = 30):
            yield

        get_lock_path = None
        WRITE_LOCK = None

DIRTY_BUFFER_WARNING_AR = "الملف مفتوح في IDE وفيه تعديلات غير محفوظة. احفظ أولاً."
EXTERNAL_MODIFICATION_WARNING_TEMPLATE_AR = (
    "⚠️ Warning: File '{file_path}' was modified externally (manually or by another agent).\n"
    "Restoring the backup will overwrite these changes.\n"
    "Are you sure?"
)


def assert_inside(root: Path, p: Path) -> Path:
    """
    Enforces path containment: verifies that path p is strictly inside root.
    Raises PermissionError if path resolves outside the root directory.
    """
    rp = Path(p).resolve()
    rr = Path(root).resolve()
    try:
        if not rp.is_relative_to(rr):
            raise PermissionError(f"Security Block: Path {p} is outside project root!")
    except AttributeError:
        try:
            rp.relative_to(rr)
        except ValueError:
            raise PermissionError(f"Security Block: Path {p} is outside project root!")
    return rp


def _atomic_write_text(file_path: Path, text: str) -> None:
    """Write text atomically preserving CRLF and line endings with retry on Windows lock contention."""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=file_path.parent) as tf:
        tf.write(text)
        temp_name = tf.name

    replaced = False
    last_err = None
    for attempt in range(10):
        try:
            os.replace(temp_name, file_path)
            replaced = True
            break
        except PermissionError as pe:
            last_err = pe
            time.sleep(0.05 * (attempt + 1))
    if not replaced and last_err:
        raise last_err
    try:
        from common.project_cache import PROJECT_CACHE
        PROJECT_CACHE.update_file(file_path, text)
    except Exception:
        pass


def _resolve_project_root(project_root: Optional[Path] = None) -> Path:
    if project_root is not None:
        return Path(project_root)
    try:
        from core.project_root import get_project_root
        return get_project_root()
    except Exception:
        try:
            from server.core.project_root import get_project_root
            return get_project_root()
        except Exception:
            return Path.cwd()


def is_ignored_path(path: Union[str, Path], project_root: Optional[Path] = None) -> bool:
    """
    Returns True if the path belongs to a backup, build, cache, or internal directory.
    Strictly prevents token migrators, editors, and analyzers from touching backup/temporary files.
    """
    if not path:
        return True
    try:
        p = Path(path)

        root = project_root
        if root is None:
            try:
                from core.project_root import get_project_root
                root = get_project_root()
            except Exception:
                pass

        if root is not None:
            try:
                rel = p.relative_to(root)
                parts = rel.parts
                s = str(rel).lower().replace("\\", "/")
            except Exception:
                parts = p.parts
                s = str(p).lower().replace("\\", "/")
        else:
            parts = p.parts
            s = str(p).lower().replace("\\", "/")

        # 1. Keywords check within relative project path
        ignored_keywords = [
            "backup",
            "build",
            ".composebridge",
            "_composebridge",
            "migration_backups",
            ".bridge.bak",
            ".bak",
            ".gradle",
            ".idea",
            ".git",
            ".kotlin",
            "__pycache__",
            "composebridge-agent",
            "composebridge-runtime",
        ]
        for kw in ignored_keywords:
            if kw in s:
                return True

        # 2. Path components check (any directory starting with _ or .)
        for part in parts:
            part_clean = part.strip()
            if part_clean in (".", "..", "/", "\\") or ":" in part_clean:
                continue
            if (part_clean.startswith("_") or part_clean.startswith(".")) and not part_clean.endswith(".kt"):
                return True
            if part_clean.lower() == "build":
                return True

        return False
    except Exception:
        return False


def _find_registry_file(file_name: str = "AppDimens.kt", project_root: Optional[Path] = None) -> Optional[Path]:
    """Find registry or token file dynamically across the project."""
    root = _resolve_project_root(project_root)
    try:
        from common.project_cache import PROJECT_CACHE
        cached = PROJECT_CACHE.find_file(file_name, root)
        if cached and cached.exists() and not is_ignored_path(cached, root):
            return cached
    except Exception:
        pass

    matches = []
    for f in root.rglob(file_name):
        if not is_ignored_path(f, root):
            matches.append(f)
    if not matches:
        return None

    def _rank_path(p: Path) -> int:
        norm = str(p).replace("\\", "/").lower()
        if "/commonmain/" in norm:
            return 0
        if "/main/" in norm:
            return 1
        if "/src/" in norm:
            return 2
        return 3

    matches.sort(key=lambda p: (_rank_path(p), len(str(p))))
    return matches[0]


def is_file_dirty_in_ide(file_path: Union[str, Path], project_root: Optional[Path] = None) -> bool:
    """
    Check if a file has unsaved modifications (dirty buffer) in the IDE.
    Checks .composebridge-state/dirty_files.json.
    """
    root = _resolve_project_root(project_root)
    dirty_json = root / ".composebridge-state" / "dirty_files.json"
    if not dirty_json.exists():
        return False

    try:
        data = json.loads(dirty_json.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return False

        target_name = Path(file_path).name.lower()
        target_norm = str(file_path).replace("\\", "/").lower()

        for item in data:
            item_norm = str(item).replace("\\", "/").lower()
            if item_norm == target_norm or Path(item).name.lower() == target_name or target_norm.endswith(item_norm):
                return True
        return False
    except Exception:
        return False


def mark_file_dirty_in_ide(file_path: Union[str, Path], is_dirty: bool = True, project_root: Optional[Path] = None) -> None:
    """
    Mark or unmark a file as dirty in IDE state (used by IDE plugin and tests).
    """
    root = _resolve_project_root(project_root)
    state_dir = root / ".composebridge-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    dirty_json = state_dir / "dirty_files.json"

    current_dirty = []
    if dirty_json.exists():
        try:
            loaded = json.loads(dirty_json.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                current_dirty = loaded
        except Exception:
            current_dirty = []

    try:
        rel_path = str(Path(file_path).relative_to(root)).replace("\\", "/")
    except Exception:
        rel_path = str(file_path).replace("\\", "/")

    norm_target = rel_path.lower()
    filtered = [f for f in current_dirty if f.replace("\\", "/").lower() != norm_target and Path(f).name.lower() != Path(file_path).name.lower()]

    if is_dirty:
        filtered.append(rel_path)

    dirty_json.write_text(json.dumps(filtered, indent=2, ensure_ascii=False), encoding="utf-8")


def apply_safe_edit(
    file_path: Union[str, Path],
    new_content: str,
    original_content: Optional[str] = None,
    pattern_id: str = "safe_edit",
    project_root: Optional[Path] = None,
) -> Tuple[bool, str, Optional[Path]]:
    """
    Unified safe edit pipeline for ALL file modifications across server, phone, MCP, and IDE:
    1. Dirty Buffer Guard: Refuses modification if file has unsaved edits in IDE.
    2. Syntax Validation: Ensures file remains syntactically valid Kotlin (if .kt).
    3. Safe Backup: Creates or validates .bridge.bak baseline before applying edits.
    4. Atomic Write: Writes atomically with retry logic to avoid Windows lock contention.
    5. Pattern Journal Recording: Records modification into PatternJournal and pending_edits.json.
    6. Live Notification: Triggers instant refresh broadcast to IDE and connected devices.
    """
    root = _resolve_project_root(project_root)
    full_path = Path(file_path)
    if not full_path.is_absolute():
        full_path = root / full_path

    if not full_path.exists():
        return (False, f"File not found: {full_path}", None)

    # 1. Dirty buffer guard
    if is_file_dirty_in_ide(full_path, project_root=root):
        return (
            False,
            f"الملف '{full_path.name}' مفتوح في IDE وفيه تعديلات غير محفوظة. احفظ أولاً.",
            None,
        )

    # Read original if not provided
    if original_content is None:
        try:
            original_content = full_path.read_text(encoding="utf-8")
        except Exception as e:
            return (False, f"Failed to read file: {e}", None)

    if original_content == new_content:
        return (True, "No changes needed", None)

    # 2. Syntax Validation
    if full_path.name.endswith(".kt"):
        try:
            from core.ast_finder import validate_kotlin_syntax
            is_valid, err_msg = validate_kotlin_syntax(new_content)
            if not is_valid:
                return (False, f"Kotlin syntax error: {err_msg}", None)
        except Exception:
            pass

    # 3. Safe Backup (.bridge.bak)
    try:
        from core.ast_finder import safe_create_backup
        ok_bak, bak_err, backup_path_obj = safe_create_backup(full_path, project_root=root)
        if not ok_bak:
            return (False, f"Backup failed: {bak_err}", None)
    except Exception as e:
        return (False, f"Backup exception: {e}", None)

    # 4. Atomic Write
    try:
        _atomic_write_text(full_path, new_content)
    except Exception as e:
        return (False, f"Write failed: {e}", None)

    # 5. Record in Journal
    try:
        from editor.journal_helpers import _journal_save
        _journal_save(full_path, original_content, new_content, pattern_id=pattern_id)
    except Exception as e:
        try:
            from core.pattern_journal import PatternJournal
            pj = PatternJournal(root)
            rel = str(full_path.relative_to(root)).replace("\\", "/")
            pj.record_change(file=rel, line=1, old_line="", new_line="", pattern_id=pattern_id)
        except Exception:
            pass

    # 6. Live Broadcast Notification
    try:
        from network.ws_server import trigger_broadcast_refresh
        trigger_broadcast_refresh()
    except Exception:
        pass

    return (True, f"Safely updated {full_path.name}", backup_path_obj)
