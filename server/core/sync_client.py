# -*- coding: utf-8 -*-
"""
Sync Client — يرسل أوامر user_sync إلى Bridge Server عبر WebSocket.
"""

import asyncio
import json
from typing import Dict, Optional

try:
    import websockets
except ImportError:
    websockets = None


BRIDGE_URL = "ws://127.0.0.1:8711"
AUTH_TOKEN = "test-token-local-dev"


async def _send_message_async(msg_type: str, extra: Optional[Dict] = None) -> Dict:
    """Send a single message to the Bridge Server and return the response."""
    if websockets is None:
        return {"success": False, "error": "websockets library not installed"}
    
    try:
        async with websockets.connect(BRIDGE_URL, open_timeout=3) as ws:
            # Auth
            await ws.send(json.dumps({"type": "auth", "token": AUTH_TOKEN}))
            auth_resp = await asyncio.wait_for(ws.recv(), timeout=3)
            
            # Send command
            payload = {"type": msg_type}
            if extra:
                payload.update(extra)
            
            await ws.send(json.dumps(payload))
            response = await asyncio.wait_for(ws.recv(), timeout=10)
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {"success": False, "error": f"Invalid JSON: {response[:200]}"}
    
    except asyncio.TimeoutError:
        return {"success": False, "error": "Timeout — server not responding"}
    except ConnectionRefusedError:
        return {"success": False, "error": "Bridge Server not running (port 8711)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def trigger_user_sync() -> Dict:
    """Send user_sync to Bridge Server."""
    return asyncio.run(_send_message_async("user_sync"))


def get_queue_status() -> Dict:
    """Get current queue status from Bridge Server."""
    return asyncio.run(_send_message_async("queue_status"))


def get_state_info() -> Dict:
    """Get general state info (agent_busy, queue_count)."""
    return asyncio.run(_send_message_async("state_info"))


def send_warning_to_bridge(
    warning_type: str,
    file_path: str,
    message: str,
    error_code: str = "EXTERNAL_MODIFICATION_DETECTED",
    suggested_action: str = "confirm_restore",
    options: Optional[list] = None,
) -> Dict:
    """Send a warning dialog event to the Bridge Server to be broadcasted to Phone and IDE plugin."""
    if options is None:
        options = [
            {"action": "restore_anyway", "label": "استعادة على أي حال"},
            {"action": "keep_current", "label": "الاحتفاظ بالتعديلات الحالية"},
            {"action": "show_diff", "label": "عرض الفروقات"},
        ]
    payload = {
        "warning_type": warning_type,
        "file": file_path,
        "message": message,
        "error_code": error_code,
        "suggested_action": suggested_action,
        "options": options,
    }
    return asyncio.run(_send_message_async("warning_dialog", payload))


def broadcast_refresh() -> Dict:
    """Send refresh_element_request to Bridge Server to notify IDE Plugin and Phone."""
    return asyncio.run(_send_message_async("refresh_element_request"))
