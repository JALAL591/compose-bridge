# -*- coding: utf-8 -*-
"""
MCP Gradle task execution, security validation, and sync status tools.
Supports asynchronous job tracking to prevent MCP client timeouts.
"""

import re
import sys
import json
import time
import uuid
import threading
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Any

from mcp.app import app, log, PROJECT_ROOT, state_manager
from mcp.types import ToolAnnotations

ALLOWED_GRADLE_TASKS = {"assembleDebug", "assembleRelease", "test", "lint", "clean", "compileDebugKotlin", "compileReleaseKotlin"}

# In-memory storage for asynchronous gradle jobs
_GRADLE_JOBS: Dict[str, Dict[str, Any]] = {}
_GRADLE_JOBS_LOCK = threading.Lock()


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


def _execute_gradle_background(job_id: str, task: str, timeout_seconds: int):
    """Background worker executing the gradle build."""
    from core.gradle_runner import run_gradle_build as _run
    try:
        with _GRADLE_JOBS_LOCK:
            _GRADLE_JOBS[job_id]["status"] = "running"
            _GRADLE_JOBS[job_id]["started_at"] = time.time()

        res = _run(PROJECT_ROOT, task, timeout_seconds)

        with _GRADLE_JOBS_LOCK:
            _GRADLE_JOBS[job_id]["status"] = "completed" if res.get("success") else "failed"
            _GRADLE_JOBS[job_id]["completed_at"] = time.time()
            _GRADLE_JOBS[job_id]["result"] = res
    except Exception as e:
        with _GRADLE_JOBS_LOCK:
            _GRADLE_JOBS[job_id]["status"] = "failed"
            _GRADLE_JOBS[job_id]["completed_at"] = time.time()
            _GRADLE_JOBS[job_id]["error"] = str(e)


@app.tool(
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=False,
    )
)
def run_gradle_build(
    task: str = "assembleDebug",
    timeout_seconds: int = 300,
    async_mode: bool = True,
) -> str:
    """
    Run a Gradle task with async tracking support.

    When to use:
    - Call to verify that surgical edits or token refactorings compile without errors.
    - Call after batch changes before approving or completing a task.

    When NOT to use:
    - Do not use for arbitrary shell execution; tasks are strictly whitelist-restricted.
    - Do not use for simple file reading or AST validation (use check_syntax_cli or ast_finder instead).

    Side effects:
    - Executes a Gradle build process in background; may write build artifacts to build/ directories.

    
    This lets the agent verify that code changes compile successfully
    before continuing with more changes, without locking the MCP connection.
    
    Args:
        task: gradle task to run (whitelist enforced: assembleDebug, assembleRelease, test, lint, clean, etc.).
        timeout_seconds: max execution time (default 5 min).
        async_mode: if true (default), returns job_id immediately so agent can poll with get_gradle_status.
    
    Returns:
        JSON with job_id and status, or execution result if sync.
    """
    if not is_gradle_task_allowed(task):
        return json.dumps({
            "success": False,
            "error": f"Task '{task}' is not allowed. Allowed tasks: {sorted(ALLOWED_GRADLE_TASKS)}"
        }, indent=2, ensure_ascii=False)

    if not async_mode:
        from core.gradle_runner import run_gradle_build as _run
        try:
            result = _run(PROJECT_ROOT, task, timeout_seconds)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    job_id = f"job_gradle_{uuid.uuid4().hex[:8]}"
    with _GRADLE_JOBS_LOCK:
        _GRADLE_JOBS[job_id] = {
            "job_id": job_id,
            "task": task,
            "status": "queued",
            "created_at": time.time(),
            "timeout_seconds": timeout_seconds,
            "result": None,
            "error": None,
        }

    t = threading.Thread(
        target=_execute_gradle_background,
        args=(job_id, task, timeout_seconds),
        daemon=True,
    )
    t.start()

    return json.dumps({
        "success": True,
        "job_id": job_id,
        "task": task,
        "status": "queued",
        "message": f"Gradle build started in background. Call get_gradle_status('{job_id}') to poll results.",
    }, indent=2, ensure_ascii=False)


@app.tool(
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
)
def get_gradle_status(job_id: str) -> str:
    """
    Check the status and result of a Gradle build job.

    When to use:
    - Call to poll background Gradle build status returned by run_gradle_build.

    When NOT to use:
    - Do not use if no Gradle job was started.

    Side effects:
    - None (strictly read-only job status query).

    
    Args:
        job_id: ID returned by run_gradle_build.
        
    Returns:
        JSON with {job_id, status: 'queued'|'running'|'completed'|'failed', result: {...}}.
    """
    with _GRADLE_JOBS_LOCK:
        job = _GRADLE_JOBS.get(job_id)

    if not job:
        return json.dumps({
            "success": False,
            "error": f"Job ID '{job_id}' not found.",
        }, indent=2, ensure_ascii=False)

    elapsed = time.time() - job["created_at"]
    return json.dumps({
        "success": True,
        "job_id": job["job_id"],
        "task": job["task"],
        "status": job["status"],
        "elapsed_seconds": round(elapsed, 1),
        "result": job.get("result"),
        "error": job.get("error"),
    }, indent=2, ensure_ascii=False)


@app.tool(
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
)
def list_allowed_gradle_tasks() -> str:
    """
    List gradle tasks that can be run via run_gradle_build.

    When to use:
    - Call to check which Gradle tasks are whitelisted for safe execution.

    When NOT to use:
    - Do not use to run builds (use run_gradle_build instead).

    Side effects:
    - None (strictly read-only whitelist listing).
    """
    return json.dumps({
        "success": True,
        "tasks": sorted(ALLOWED_GRADLE_TASKS),
    }, indent=2, ensure_ascii=False)


@app.tool(
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=True,
        idempotent_hint=False,
        open_world_hint=False,
    )
)
def trigger_user_sync() -> str:
    """
    Trigger user_sync on the Bridge Server.

    When to use:
    - Call to flush and apply pending queued edits (dimensions and colors) from the Android device to source files.

    When NOT to use:
    - Do not use if the AI agent is actively modifying source files (agent_busy lock).

    Side effects:
    - Modifies source files on disk by applying pending changes from the queue.

    
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


@app.tool(
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
)
def get_sync_status() -> str:
    """
    Get the current sync status from the Bridge Server.

    When to use:
    - Call to inspect agent_busy, queue_count, and snapshot_version before running batch operations.

    When NOT to use:
    - Do not use to apply changes (use trigger_user_sync instead).

    Side effects:
    - None (strictly read-only state inspection).
    """
    from core.sync_client import get_state_info
    try:
        result = get_state_info()
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
