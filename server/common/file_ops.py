# -*- coding: utf-8 -*-
"""
Common file operations, atomic writing, and registry discovery utilities.
Consolidated during Phase 1 refactoring to eliminate cross-module code duplication.
"""

import os
import time
import tempfile
from pathlib import Path
from typing import Optional

# Re-export acquire_write_lock from write_lock
try:
    from core.write_lock import acquire_write_lock, get_lock_path, WRITE_LOCK
except ImportError:
    try:
        from server.core.write_lock import acquire_write_lock, get_lock_path, WRITE_LOCK
    except ImportError:
        acquire_write_lock = None
        get_lock_path = None
        WRITE_LOCK = None


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


def _find_registry_file(file_name: str = "AppDimens.kt", project_root: Optional[Path] = None) -> Optional[Path]:
    """Find registry or token file dynamically across the project."""
    if project_root is None:
        try:
            from core.project_root import get_project_root
            project_root = get_project_root()
        except ImportError:
            try:
                from server.core.project_root import get_project_root
                project_root = get_project_root()
            except ImportError:
                project_root = Path.cwd()

    for f in project_root.rglob(file_name):
        s = str(f)
        if ".bak" not in s and "build" not in s and ".composebridge" not in s:
            return f
    return None
