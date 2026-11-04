# -*- coding: utf-8 -*-
"""
MCP Tools for real-time IDE diagnostics and compiler error analysis.
Queries IntelliJ Platform's DaemonCodeAnalyzer directly over WebSocket in <50ms without Gradle.
"""

import sys
import json
import time
import uuid
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path
import websockets

from mcp.app import app, log, PROJECT_ROOT
from mcp.types import ToolAnnotations
from core.auth_manager import get_or_create_auth_token


async def _query_ide_diagnostics_ws(
    file_path: Optional[str] = None,
    include_warnings: bool = False,
    timeout_seconds: float = 5.0,
) -> Dict[str, Any]:
    """
    Connects to ComposeBridge WebSocket server (ws://127.0.0.1:8711) and requests IDE diagnostics.
    """
    token = get_or_create_auth_token(PROJECT_ROOT)
    req_id = f"diag_{uuid.uuid4().hex[:8]}"

    try:
        async with websockets.connect(
            "ws://127.0.0.1:8711",
            open_timeout=2.0,
            close_timeout=1.0,
        ) as ws:
            # 1. Auth handshake
            await ws.send(json.dumps({"type": "auth", "token": token}))
            raw_auth = await asyncio.wait_for(ws.recv(), timeout=2.0)
            auth_res = json.loads(raw_auth)
            if not auth_res.get("authenticated", False):
                return {
                    "success": False,
                    "connected": False,
                    "error": "Authentication failed with ComposeBridge server",
                    "diagnostics": [],
                }

            # 2. Send ide_diagnostics_request
            request_payload = {
                "type": "ide_diagnostics_request",
                "request_id": req_id,
                "file": file_path or "",
                "include_warnings": include_warnings,
            }
            await ws.send(json.dumps(request_payload, ensure_ascii=False))

            # 3. Wait for matching response
            deadline = time.time() + timeout_seconds
            while time.time() < deadline:
                remaining = max(0.1, deadline - time.time())
                try:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
                    msg = json.loads(raw_msg)
                    if msg.get("type") == "ide_diagnostics_response" and msg.get("request_id") == req_id:
                        return msg
                except asyncio.TimeoutError:
                    break

            return {
                "success": False,
                "connected": True,
                "timeout": True,
                "error": f"Timed out waiting for Android Studio response after {timeout_seconds}s",
                "diagnostics": [],
            }
    except Exception as e:
        return {
            "success": False,
            "connected": False,
            "error": f"Could not connect to ComposeBridge WebSocket (ws://127.0.0.1:8711): {e}",
            "diagnostics": [],
        }


def _read_cached_state_diagnostics() -> Optional[Dict[str, Any]]:
    """Reads fallback diagnostics cached by the plugin in .composebridge-state/ide_diagnostics.json."""
    try:
        state_file = PROJECT_ROOT / ".composebridge-state" / "ide_diagnostics.json"
        if state_file.exists():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            mtime = state_file.stat().st_mtime
            age = time.time() - mtime
            data["cached"] = True
            data["cache_age_seconds"] = round(age, 1)
            return data
    except Exception:
        pass
    return None


@app.tool(
    name="get_ide_diagnostics",
    description="Fetches real-time compilation, unresolved reference, and syntax errors directly from Android Studio / IntelliJ IDE without running Gradle.",
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
)
def get_ide_diagnostics(
    file_path: Optional[str] = None,
    include_warnings: bool = False,
    timeout_seconds: float = 5.0,
) -> str:
    """
    Fetches real-time compilation, unresolved reference, and syntax errors directly from Android Studio / IntelliJ IDE without running Gradle.

    When to use:
    - Call immediately after surgical source edits to verify that code builds cleanly without syntax errors or unresolved references.
    - 60x faster than run_gradle_build (<50ms vs ~30s).
    - Checks red squiggles (DaemonCodeAnalyzer) in the active editor file or specified file.

    When NOT to use:
    - Do not use for packaging release APKs or running full test suites (use run_gradle_build instead).
    - Do not use if Android Studio is not open.

    Side effects:
    - None (strictly read-only AST highlighting query).

    Args:
        file_path: Optional relative or absolute path to .kt file. If omitted, checks currently active editor file in Android Studio.
        include_warnings: If True, returns both warnings and errors. Default is False (errors only).
        timeout_seconds: Max seconds to wait for IDE response (default 5.0s).

    Returns:
        JSON string containing error count, file name, and list of errors with line numbers and messages.
    """
    from mcp.network_client import run_async

    # Step 1: Query live over WebSocket
    result = run_async(_query_ide_diagnostics_ws(file_path, include_warnings, timeout_seconds))

    # Step 2: If live WS was not connected, check state cache fallback
    if not result.get("success", False) and not result.get("connected", False):
        cached = _read_cached_state_diagnostics()
        if cached:
            cached["fallback_notice"] = "Live WebSocket disconnected; returned recent cached diagnostics from IDE."
            return json.dumps(cached, indent=2, ensure_ascii=False)

    return json.dumps(result, indent=2, ensure_ascii=False)



async def _query_project_diagnostics_scan_ws(
    include_warnings: bool = False,
    max_files: int = 100,
    timeout_seconds: float = 30.0,
) -> Dict[str, Any]:
    """Connects to ComposeBridge WebSocket server (ws://127.0.0.1:8711) and requests sequential project scan."""
    token = get_or_create_auth_token(PROJECT_ROOT)
    req_id = f"proj_scan_{uuid.uuid4().hex[:8]}"

    try:
        async with websockets.connect(
            "ws://127.0.0.1:8711",
            open_timeout=2.0,
            close_timeout=1.0,
        ) as ws:
            await ws.send(json.dumps({"type": "auth", "token": token}))
            raw_auth = await asyncio.wait_for(ws.recv(), timeout=2.0)
            auth_res = json.loads(raw_auth)
            if not auth_res.get("authenticated", False):
                return {
                    "success": False,
                    "connected": False,
                    "error": "Authentication failed with ComposeBridge server",
                    "files": [],
                }

            request_payload = {
                "type": "project_diagnostics_scan_request",
                "request_id": req_id,
                "include_warnings": include_warnings,
                "max_files": max_files,
            }
            await ws.send(json.dumps(request_payload, ensure_ascii=False))

            deadline = time.time() + timeout_seconds
            while time.time() < deadline:
                remaining = max(0.5, deadline - time.time())
                try:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
                    msg = json.loads(raw_msg)
                    if msg.get("type") == "project_diagnostics_scan_response" and msg.get("request_id") == req_id:
                        return msg
                except asyncio.TimeoutError:
                    break

            return {
                "success": False,
                "connected": True,
                "timeout": True,
                "error": f"Timed out waiting for project diagnostics scan response after {timeout_seconds}s",
                "files": [],
            }
    except Exception as e:
        return {
            "success": False,
            "connected": False,
            "error": f"Could not connect to ComposeBridge WebSocket (ws://127.0.0.1:8711): {e}",
            "files": [],
        }


@app.tool(
    name="scan_project_diagnostics",
    description="Sequentially scans all Kotlin files in the project workspace to collect compilation errors and technical debt warnings without running Gradle.",
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
)
def scan_project_diagnostics(
    include_warnings: bool = False,
    max_files: int = 100,
    timeout_seconds: float = 30.0,
) -> str:
    """
    Sequentially scans all Kotlin files in the project workspace to collect compilation errors and technical debt warnings without running Gradle.

    When to use:
    - Use to verify project-wide build health and find all compilation errors across the entire codebase.
    - Uses a sequential memory-safe scanner in Android Studio (opens file, reads DaemonCodeAnalyzer AST highlights, closes file).
    - Preserves user state: never closes files already opened by the developer.

    When NOT to use:
    - Do not use for inspecting a single file (use get_ide_diagnostics instead for <50ms speed).
    - Do not use if Android Studio is not open.

    Side effects:
    - None (strictly read-only AST highlighting inspection).

    Args:
        include_warnings: If True, returns both warnings and errors. Default is False (errors only).
        max_files: Maximum number of Kotlin files to inspect (default: 100).
        timeout_seconds: Max seconds to wait for IDE response (default: 30.0s).

    Returns:
        JSON string containing total scanned files, total errors, total warnings, and list of files with issues.
    """
    from mcp.network_client import run_async

    result = run_async(_query_project_diagnostics_scan_ws(include_warnings, max_files, timeout_seconds))
    return json.dumps(result, indent=2, ensure_ascii=False)
