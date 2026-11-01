# -*- coding: utf-8 -*-
"""
MCP Network Client — Bridge Server WebSocket communication & lifecycle events.
عميل شبكة الاتصال الخاص بـ MCP للتواصل مع خادم ComposeBridge عبر WebSocket.
"""

import sys
import asyncio
import json
import websockets
from pathlib import Path
from typing import Optional, Dict, Any

from mcp.app import PROJECT_ROOT
from core.auth_manager import get_or_create_auth_token


async def notify_bridge_server(token: str, value: str) -> Dict[str, Any]:
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
            prop_name = token if token.startswith("AppColors.") else f"AppColors.{token}"
            await ws.send(json.dumps({
                "type": "mcp_state_update",
                "property": prop_name,
                "value": value,
                "source": "mcp",
            }))
            raw_ack = await asyncio.wait_for(ws.recv(), timeout=2)
            try:
                ack_data = json.loads(raw_ack)
                forwarded = ack_data.get("forwarded_to", 0)
                return {"bridge_connected": True, "device_connected": forwarded > 0, "forwarded_to": forwarded}
            except Exception:
                return {"bridge_connected": True, "device_connected": False, "forwarded_to": 0}
    except Exception as e:
        print(f"[MCP] Bridge notify failed: {e}", file=sys.stderr)
        return {"bridge_connected": False, "device_connected": False, "forwarded_to": 0}


async def notify_refresh_to_bridge() -> bool:
    """
    Notify Bridge Server to broadcast refresh_element_request to IDE Plugin and Phone.
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

            # Send refresh_element_request
            await ws.send(json.dumps({
                "type": "refresh_element_request",
            }))
            await asyncio.wait_for(ws.recv(), timeout=2)
            return True
    except Exception as e:
        print(f"[MCP] Bridge refresh notify failed: {e}", file=sys.stderr)
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
            await asyncio.wait_for(ws.recv(), timeout=2)
            return True
    except Exception as e:
        print(f"[MCP] Lifecycle notify failed: {e}", file=sys.stderr)
        return False


def run_async(coro):
    """Run async coroutine safely from sync or running event loop context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


def send_refresh_signal() -> bool:
    """Send refresh_element_request to Bridge Server safely from any context."""
    try:
        return run_async(notify_refresh_to_bridge())
    except Exception as e:
        print(f"[MCP] send_refresh_signal failed: {e}", file=sys.stderr)
        return False

