# -*- coding: utf-8 -*-
"""
MCP Miscellaneous and communication tools.
Re-exports network client utilities and text tools for backwards compatibility.
"""

from mcp.network_client import (
    notify_bridge_server,
    notify_refresh_to_bridge,
    notify_agent_lifecycle,
    run_async,
    send_refresh_signal,
)
from mcp.tools.text import set_text

__all__ = [
    "notify_bridge_server",
    "notify_refresh_to_bridge",
    "notify_agent_lifecycle",
    "run_async",
    "send_refresh_signal",
    "set_text",
]
