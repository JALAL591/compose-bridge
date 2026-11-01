# -*- coding: utf-8 -*-
"""
MCP Text modification tools.
أداة تعديل النصوص في ComposeBridge عبر MCP.
"""

import json
from pathlib import Path
from typing import Optional

from mcp.app import app
from mcp.network_client import notify_bridge_server, send_refresh_signal, run_async


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
                err_dict = {"success": False, "error": msg}
                if isinstance(info, dict) and "error_code" in info:
                    err_dict["error_code"] = info["error_code"]
                return json.dumps(err_dict, indent=2, ensure_ascii=False)
                
            # Notify Bridge server for live update and IDE plugin refresh
            try:
                run_async(notify_bridge_server(ref_key or f"text_{file_path}_{line}", new_value))
            except Exception:
                pass
            try:
                send_refresh_signal()
            except Exception:
                pass
                
            return json.dumps({
                "success": True,
                "message": msg,
                "info": info
            }, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

