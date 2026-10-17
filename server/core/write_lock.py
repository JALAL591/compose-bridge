# -*- coding: utf-8 -*-
"""
Shared file lock for all write operations.

CRITICAL: This lock is shared between:
- server.py (Bridge process)
- mcp_server.py (MCP process)

Both processes must import and use the same _WRITE_LOCK.
"""

from pathlib import Path
from filelock import FileLock


from core.project_root import get_project_root


# ⭐ مسار موحد للـ lock — يجب أن يكون نفسه في كل العمليات
def get_lock_path() -> Path:
    """Get the shared lock file path."""
    project_root = get_project_root()
    state_dir = project_root / ".composebridge-state"
    state_dir.mkdir(exist_ok=True)
    
    return state_dir / ".write.lock"


# ⭐ Instance واحد مشترك (مع is_singleton=True لمنع Deadlock داخل نفس الـ Thread)
LOCK_PATH = get_lock_path()
WRITE_LOCK = FileLock(str(LOCK_PATH), timeout=30, is_singleton=True)


def acquire_write_lock(timeout: float = 30):
    """
    Acquire the shared write lock.
    
    Usage:
        with acquire_write_lock():
            # do file writes
            pass
    """
    return FileLock(str(LOCK_PATH), timeout=timeout, is_singleton=True)
