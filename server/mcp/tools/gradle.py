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


@app.tool()
def run_gradle_build(
    task: str = "assembleDebug",
    timeout_seconds: int = 300,
    async_mode: bool = True,
) -> str:
    """
    Run a Gradle task with async tracking support.
    
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


@app.tool()
def get_gradle_status(job_id: str) -> str:
    """
    Check the status and result of a Gradle build job.
    
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


@app.tool()
def list_allowed_gradle_tasks() -> str:
    """List gradle tasks that can be run via run_gradle_build."""
    return json.dumps({
        "success": True,
        "tasks": sorted(ALLOWED_GRADLE_TASKS),
    }, indent=2, ensure_ascii=False)


@app.tool()
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


@app.tool()
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
