# -*- coding: utf-8 -*-
"""
ComposeBridge Server Facade & Main Entrypoint.
Re-exports network, routing, handlers, and launches the WebSocket server.
"""

import os
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse
import asyncio
from pathlib import Path

# Parse CLI arguments early before initializing components
parser = argparse.ArgumentParser(description="ComposeBridge Server")
parser.add_argument("--project", type=str, default=None, help="Project root directory")
parser.add_argument("--dev-token", type=str, default=None, help="Use a fixed token for local testing (bypass auth.json)")
args, _ = parser.parse_known_args()

if args.project:
    os.environ["COMPOSEBRIDGE_ROOT"] = str(Path(args.project).resolve())

if args.dev_token:
    from core.auth_manager import set_dev_token
    set_dev_token(args.dev_token)

import websockets

from core import theme_indexer

# Re-export from network
from network.ws_server import (
    Color,
    HOST,
    PORT,
    PROJECT_ROOT,
    STATE_MANAGER,
    AUTH_TOKEN,
    CONNECTED_CLIENTS,
    AUTHENTICATED_CLIENTS,
    log_info,
    log_success,
    log_error,
    log_recv,
    log_send,
    log_forward,
    broadcast,
    broadcast_refresh,
    broadcast_changes_updated,
    trigger_broadcast_refresh,
    safe_send,
    handle_client,
)

# Re-export from message router
from network.message_router import (
    handle_message,
    handle_edit_request,
)

# Re-export from handlers
from handlers.kotlin_validation import (
    _validate_kotlin_line,
    _clean_duplicate_modifier,
    _ensure_bridge_dimension_registry_import,
    _clean_duplicate_imports,
    _validate_modified_file,
)

from handlers.dimension_handler import (
    _apply_dimension_edit,
)


async def main():
    from core.auth_manager import get_auth_token_file_path, get_or_create_auth_token
    token_file = get_auth_token_file_path(PROJECT_ROOT)
    token_val = get_or_create_auth_token(PROJECT_ROOT)

    print()
    print(f"{Color.BOLD}{Color.GREEN}{'=' * 65}{Color.END}")
    print(f"{Color.BOLD}{Color.GREEN}  ComposeBridge - Secure WebSocket Hub (v1.2.0){Color.END}")
    print(f"{Color.BOLD}{Color.GREEN}{'=' * 65}{Color.END}")
    print(f"  Host:         {HOST}")
    print(f"  Port:         {PORT}")
    print(f"  Project root: {PROJECT_ROOT}")
    print(f"  Rate Limit:   60 requests/minute per IP")
    print(f"{Color.BOLD}{Color.YELLOW}  🔑 Auth Token: {token_val}{Color.END}")
    print(f"  📁 Saved to:   {token_file}")
    if args.dev_token:
        print(f"  Dev Token:    {args.dev_token} (override)")
    print(f"{Color.BOLD}{Color.GREEN}{'=' * 65}{Color.END}")
    print()

    # Init Theme Tokens
    theme_indexer.init()
    print(f"[STATE] Loaded: {len(STATE_MANAGER.snapshot.tokens)} tokens")
    print(f"[STATE] Queue: {STATE_MANAGER.queue.count()} edits")
    print(f"[STATE] Agent busy: {STATE_MANAGER.agent_busy}")

    log_info("Waiting for clients (phone + test tools)...")
    print()

    import network.ws_server as ws_module
    ws_module.MAIN_EVENT_LOOP = asyncio.get_running_loop()

    async with websockets.serve(handle_client, HOST, PORT, ping_interval=20, ping_timeout=20):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print()
        log_info("Shutting down...")
