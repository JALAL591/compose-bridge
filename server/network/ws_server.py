# -*- coding: utf-8 -*-
"""
WebSocket Server connection management, client sessions, and broadcasting.
"""

import asyncio
import json
import secrets
import hmac
from pathlib import Path
from typing import Set, Tuple, Optional, Dict
import websockets
from websockets.server import WebSocketServerProtocol

from core.project_root import get_project_root
from core.state_manager import StateManager
from core.auth_manager import get_or_create_auth_token

HOST = "0.0.0.0"
PORT = 8711

PROJECT_ROOT = get_project_root()
STATE_MANAGER = StateManager(PROJECT_ROOT)
AUTH_TOKEN = get_or_create_auth_token(PROJECT_ROOT)

CONNECTED_CLIENTS: Set[WebSocketServerProtocol] = set()
AUTHENTICATED_CLIENTS: Set[WebSocketServerProtocol] = set()

class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    END = "\033[0m"


def _safe_print(prefix: str, msg: str):
    text = f"{prefix} {msg}"
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        try:
            import sys
            sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
            sys.stdout.buffer.flush()
        except Exception:
            pass


def log_info(msg): _safe_print(f"{Color.CYAN}[INFO]{Color.END}", msg)


def log_success(msg): _safe_print(f"{Color.GREEN}[OK]{Color.END}", msg)


def log_error(msg): _safe_print(f"{Color.RED}[ERR]{Color.END}", msg)


def log_recv(msg): _safe_print(f"{Color.BLUE}[<-]{Color.END}", msg)


def log_send(msg): _safe_print(f"{Color.YELLOW}[->]{Color.END}", msg)


def log_forward(msg): _safe_print(f"{Color.MAGENTA}[>>]{Color.END}", msg)


async def broadcast(message: str, exclude: WebSocketServerProtocol = None) -> int:
    """
    يرسل رسالة لجميع العملاء المتصلين عدا المُرسِل.
    يعيد عدد العملاء الذين استقبلوا الرسالة.
    """
    count = 0
    dead_clients = []

    for client in list(AUTHENTICATED_CLIENTS):
        if client == exclude:
            continue
        try:
            # ⭐ تحقق أن الاتصال مفتوح
            if client.state.name == "OPEN":
                await client.send(message)
                count += 1
        except Exception as e:
            log_error(f"Failed to send to client: {e}")
            dead_clients.append(client)

    # نظّف العملاء الميتين
    for client in dead_clients:
        CONNECTED_CLIENTS.discard(client)
        AUTHENTICATED_CLIENTS.discard(client)

    return count


async def safe_send(websocket: WebSocketServerProtocol, payload: dict) -> bool:
    """Send message only if WebSocket is open."""
    try:
        if websocket.state.name == "OPEN":
            await websocket.send(json.dumps(payload, ensure_ascii=False))
            return True
        else:
            log_error(f"Skip send — WS not open ({websocket.state.name})")
            return False
    except Exception as e:
        log_error(f"Send failed: {e}")
        return False


async def handle_client(websocket: WebSocketServerProtocol) -> None:
    """يتعامل مع عميل واحد."""
    from network.message_router import handle_message
    CONNECTED_CLIENTS.add(websocket)
    peer = websocket.remote_address
    log_success(f"Client connected: {peer} (total: {len(CONNECTED_CLIENTS)})")

    try:
        async for raw in websocket:
            try:
                await handle_message(websocket, raw)
            except Exception as e:
                log_error(f"Handler error: {e}")
                import traceback
                traceback.print_exc()
    except websockets.ConnectionClosed:
        log_info(f"Client disconnected: {peer}")
    except Exception as e:
        log_error(f"Connection error: {e}")
    finally:
        CONNECTED_CLIENTS.discard(websocket)
        AUTHENTICATED_CLIENTS.discard(websocket)
        log_info(f"Client removed. Total: {len(CONNECTED_CLIENTS)}")

