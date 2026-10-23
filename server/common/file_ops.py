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
from typing import Optional, Union

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
    "⚠️ تحذير: الملف '{file_path}' تم تعديله خارج الأداة (يدوياً أو بواسطة وكيل آخر).\n"
    "استعادة النسخة الاحتياطية ستحذف هذه التعديلات.\n"
    "هل أنت متأكد؟"
)


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


def _find_registry_file(file_name: str = "AppDimens.kt", project_root: Optional[Path] = None) -> Optional[Path]:
    """Find registry or token file dynamically across the project."""
    root = _resolve_project_root(project_root)
    try:
        from common.project_cache import PROJECT_CACHE
        cached = PROJECT_CACHE.find_file(file_name, root)
        if cached and cached.exists():
            return cached
    except Exception:
        pass
    for f in root.rglob(file_name):
        s = str(f)
        if ".bak" not in s and "build" not in s and ".composebridge" not in s:
            return f
    return None


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
