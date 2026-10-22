# -*- coding: utf-8 -*-
"""
MCP Gradle task execution, security validation, and sync status tools.
"""

import re
import sys
import json
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Any

from mcp.app import app, log, PROJECT_ROOT, state_manager

ALLOWED_GRADLE_TASKS = {"assembleDebug", "assembleRelease", "test", "lint", "clean"}


def is_gradle_task_allowed(task: str) -> bool:
    """Strictly validate task to prevent arbitrary execution or injection."""
    if not task or not isinstance(task, str):
        return False
    # Reject shell metacharacters, spaces, options/flags
    if not re.match(r"^:?[a-zA-Z0-9_\-]+(?::[a-zA-Z0-9_\-]+)*$", task.strip()):
        return False
    if task in ALLOWED_GRADLE_TASKS:
        return True
    parts = task.strip(":").split(":")
    base_task = parts[-1] if parts else ""
    return base_task in ALLOWED_GRADLE_TASKS


def run_gradle_build(
    task: str = "assembleDebug",
    timeout_seconds: int = 300,
) -> str:
    """
    Run a Gradle task and return structured result.
    
    This lets the agent verify that code changes compile successfully
    before continuing with more changes.
    
    Args:
        task: gradle task to run (whitelist enforced: assembleDebug, assembleRelease, test, lint, clean).
        timeout_seconds: max execution time (default 5 min).
    
    Returns:
        JSON with {success, exit_code, duration_ms, errors, warnings}.
    """
    if not is_gradle_task_allowed(task):
        return json.dumps({
            "success": False,
            "error": f"Task '{task}' is not allowed. Allowed tasks: {sorted(ALLOWED_GRADLE_TASKS)}"
        }, indent=2, ensure_ascii=False)

    from core.gradle_runner import run_gradle_build as _run
    
    try:
        result = _run(PROJECT_ROOT, task, timeout_seconds)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def list_allowed_gradle_tasks() -> str:
    """List gradle tasks that can be run via run_gradle_build."""
    return json.dumps({
        "success": True,
        "tasks": sorted(ALLOWED_GRADLE_TASKS),
    }, indent=2, ensure_ascii=False)


def trigger_user_sync() -> str:
    """
    Trigger user_sync on the Bridge Server.
    
    Applies all queued edits (dimension + color) to the files.
    Only works when the AI agent is not busy.
    
    Returns:
        JSON with {success, applied, skipped, errors}.
    """
    from core.sync_client import trigger_user_sync as _sync
    try:
        result = _sync()
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def get_sync_status() -> str:
    """
    Get the current sync status from the Bridge Server:
    agent_busy, queue_count, snapshot_version.
    """
    from core.sync_client import get_state_info
    try:
        result = get_state_info()
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

