# -*- coding: utf-8 -*-
"""
MCP Miscellaneous and communication tools.
"""

import sys
import asyncio
import json
import traceback
import websockets
from pathlib import Path
from typing import Optional, List, Dict, Any

from mcp.app import app, log, PROJECT_ROOT, state_manager
from core.auth_manager import get_or_create_auth_token
from core.state_editor import update_text_in_source
from core.project_root import get_project_root
from common.file_ops import acquire_write_lock

async def notify_bridge_server(token: str, value: str) -> bool:
    """
    After editing a file, notify the Bridge Server.
    Bridge will broadcast to connected phones.
    """
    try:
        async with websockets.connect(
            "ws://127.0.0.1:8711",
            open_timeout=2,
        ) as ws:
            # Auth
            await ws.send(json.dumps({
                "type": "auth",
                "token": get_or_create_auth_token(PROJECT_ROOT),
            }))
            await asyncio.wait_for(ws.recv(), timeout=2)

            # Send mcp_state_update
            await ws.send(json.dumps({
                "type": "mcp_state_update",
                "property": f"AppColors.{token}",
                "value": value,
                "source": "mcp",
            }))
            ack = await asyncio.wait_for(ws.recv(), timeout=2)
            return True
    except Exception as e:
        print(f"[MCP] Bridge notify failed: {e}", file=sys.stderr)
        return False


async def notify_agent_lifecycle(event: str) -> bool:
    """
    Notify Bridge Server about agent session start/end.
    
    Args:
        event: "agent_start" or "agent_end"
    """
    try:
        async with websockets.connect(
            "ws://127.0.0.1:8711",
            open_timeout=2,
        ) as ws:
            # Auth
            await ws.send(json.dumps({
                "type": "auth",
                "token": get_or_create_auth_token(PROJECT_ROOT),
            }))
            await asyncio.wait_for(ws.recv(), timeout=2)
            
            # Send lifecycle event
            await ws.send(json.dumps({"type": event}))
            ack = await asyncio.wait_for(ws.recv(), timeout=2)
            return True
    except Exception as e:
        print(f"[MCP] Lifecycle notify failed: {e}", file=sys.stderr)
        return False


def run_async(coro):
    """Run async coroutine safely from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.create_task(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@app.tool()
def set_text(token_name: str, new_value: str, file_path: str = None, line: int = None) -> str:
    """
    DESTRUCTIVE: Modifies .kt files. Surgically edit text content with automatic BridgeTextRegistry wrapping.
    
    What it does: Modifies .kt files. Auto-migrates hardcoded text to BridgeTextRegistry for live preview.
    When to use: When editing UI text strings, whether defined in AppStrings or hardcoded in Composable Text("...") elements.
    When NOT to use: Do not use for colors or dimensions (use set_token or add_token).
    Side effects: DESTRUCTIVE: Modifies source code on disk. Requires approve_file_changes before changes take effect in git. Can be reverted via reject_file_changes.
    Parameters:
      - token_name: reference key (e.g., 'AppStrings.Dashboard.title') OR exact old text content to replace.
      - new_value: The new text string to set.
      - file_path: relative path to source file (e.g., 'QuickActionsWidget.kt' or 'ui/theme/AppStrings.kt').
      - line: optional line number for disambiguation if text appears multiple times.
    Returns:
      JSON string with success status, old_text, new_text, and modified file location.
    """
    from core.write_lock import acquire_write_lock
    with acquire_write_lock():
        try:
            from core.state_editor import update_text_in_source
            from core.project_root import get_project_root
            
            p_root = get_project_root()
            
            ref_key = None
            old_text = token_name
            if token_name.startswith("AppStrings.") or (file_path and "AppStrings" in file_path):
                ref_key = token_name if token_name.startswith("AppStrings.") else f"AppStrings.{token_name}"
                old_text = ""
                file_path = file_path or "AppStrings.kt"
            elif not file_path:
                # Search for old_text across .kt files in project
                found_file = None
                found_line = 1
                for f in p_root.rglob("*.kt"):
                    if "build" in str(f) or ".composebridge" in str(f):
                        continue
                    try:
                        f_text = f.read_text(encoding="utf-8", errors="ignore")
                        if token_name in f_text:
                            for idx, l_str in enumerate(f_text.splitlines(), 1):
                                if token_name in l_str:
                                    found_file = str(f)
                                    found_line = idx
                                    break
                            if found_file:
                                break
                    except Exception:
                        pass
                if found_file:
                    file_path = found_file
                    line = found_line
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Could not locate text or token '{token_name}' in project",
                    })

            ok, msg, info = update_text_in_source(
                file_path=file_path or "AppStrings.kt",
                line=line or 1,
                old_text=old_text,
                new_text=new_value,
                ref_key=ref_key,
                project_root=p_root,
            )
            
            if not ok:
                return json.dumps({"success": False, "error": msg})
                
            # Notify Bridge server for live update
            try:
                run_async(notify_bridge_server(ref_key or f"text_{file_path}_{line}", new_value))
            except Exception:
                pass
                
            return json.dumps({
                "success": True,
                "message": msg,
                "info": info
            }, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

