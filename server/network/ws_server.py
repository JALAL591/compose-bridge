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
from network.rate_limiter import RateLimiter

HOST = "0.0.0.0"
PORT = 8711

PROJECT_ROOT = get_project_root()
STATE_MANAGER = StateManager(PROJECT_ROOT)
AUTH_TOKEN = get_or_create_auth_token(PROJECT_ROOT)

CONNECTED_CLIENTS: Set[WebSocketServerProtocol] = set()
AUTHENTICATED_CLIENTS: Set[WebSocketServerProtocol] = set()
RATE_LIMITER = RateLimiter(max_requests=60, window_seconds=60.0)

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


MAIN_EVENT_LOOP: Optional[asyncio.AbstractEventLoop] = None


async def broadcast_refresh(exclude: WebSocketServerProtocol = None) -> int:
    """
    يرسل refresh_element_request لجميع العملاء المتصلين (الهاتف وإضافة IDE).
    """
    return await broadcast(json.dumps({
        "type": "refresh_element_request",
    }, ensure_ascii=False), exclude=exclude)


async def broadcast_changes_updated(exclude: WebSocketServerProtocol = None) -> int:
    """
    يبث إشارة refresh_element_request وقائمة modified_files_list المحدثة
    لجميع العملاء المتصلين (إضافة IDE والهاتف) لمنع التعديلات الصامتة (Zero Silent Modifications).
    """
    from core.pattern_journal import PatternJournal
    count = await broadcast_refresh(exclude=exclude)
    try:
        journal = PatternJournal(PROJECT_ROOT)
        updated_files = journal.list_modified_files()
        remaining = [
            {
                "file": (f.get("file", "") if isinstance(f, dict) else str(f)),
                "name": Path(f.get("file", "") if isinstance(f, dict) else str(f)).name,
                "status": "modified",
            }
            for f in updated_files
            if (f.get("file", "") if isinstance(f, dict) else str(f))
        ]
        await broadcast(json.dumps({
            "type": "modified_files_list",
            "files": remaining,
        }, ensure_ascii=False), exclude=exclude)
        log_info(f"[BROADCAST-SYNC] broadcast_changes_updated: {len(remaining)} modified file(s) sent to {count} client(s)")
    except Exception as e:
        log_error(f"Failed to broadcast modified_files_list: {e}")
    return count


def trigger_broadcast_refresh():
    """Trigger broadcast_changes_updated synchronously from any thread or function if server is running."""
    global MAIN_EVENT_LOOP
    try:
        loop = MAIN_EVENT_LOOP
        if not loop or loop.is_closed():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_changes_updated(), loop)
    except Exception:
        pass


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
            else:
                dead_clients.append(client)
        except Exception as e:
            log_error(f"Failed to send to client: {e}")
            dead_clients.append(client)

    # نظّف العملاء الميتين
    for client in dead_clients:
        CONNECTED_CLIENTS.discard(client)
        AUTHENTICATED_CLIENTS.discard(client)

    return count


async def safe_send(websocket: WebSocketServerProtocol, payload: dict) -> bool:
    """Send message only if WebSocket is open. Clean up dead sockets immediately."""
    try:
        if websocket.state.name == "OPEN":
            await websocket.send(json.dumps(payload, ensure_ascii=False))
            return True
        else:
            log_error(f"Skip send — WS not open ({websocket.state.name})")
            CONNECTED_CLIENTS.discard(websocket)
            AUTHENTICATED_CLIENTS.discard(websocket)
            return False
    except Exception as e:
        log_error(f"Send failed: {e}")
        CONNECTED_CLIENTS.discard(websocket)
        AUTHENTICATED_CLIENTS.discard(websocket)
        return False



def update_apk_build_status_file(
    building: bool,
    stage: str = "",
    progress: float = 0.0,
    message: str = "",
    success: bool = False,
    file_name: str = "",
    file_path: str = ""
):
    try:
        import time
        state_dir = PROJECT_ROOT / ".composebridge-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        status_file = state_dir / "apk_build_status.json"
        data = {
            "building": building,
            "stage": stage,
            "progress": progress,
            "message": message,
            "success": success,
            "file_name": file_name,
            "file_path": file_path,
            "updated_at": time.time(),
        }
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def update_device_status_file():
    try:
        import time
        state_dir = PROJECT_ROOT / ".composebridge-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        status_file = state_dir / "device_status.json"
        auth_count = len(AUTHENTICATED_CLIENTS)
        devices = []
        for ws in list(AUTHENTICATED_CLIENTS):
            addr = getattr(ws, "remote_address", None)
            if addr:
                devices.append(f"{addr[0]}:{addr[1]}")
        data = {
            "connected": auth_count > 0,
            "count": auth_count,
            "devices": devices,
            "total_clients": len(CONNECTED_CLIENTS),
            "updated_at": time.time(),
        }
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


async def handle_client(websocket: WebSocketServerProtocol) -> None:
    """Handles a single WebSocket client connection with rate limiting."""
    from network.message_router import handle_message
    CONNECTED_CLIENTS.add(websocket)
    peer = websocket.remote_address
    client_ip = peer[0] if peer else "unknown"
    log_success(f"Client connected: {peer} (total: {len(CONNECTED_CLIENTS)})")
    update_device_status_file()

    try:
        async for raw in websocket:
            # 1. Fast-path: Ping/Heartbeat handled IMMEDIATELY in microseconds!
            if isinstance(raw, str) and ('"type":"ping"' in raw or '"type": "ping"' in raw):
                await safe_send(websocket, {"type": "pong"})
                continue

            # 2. Rate Limiting Protection:
            # Authenticated clients and local loopback have generous limit (1200 req/min) for real-time sliders
            is_auth = (websocket in AUTHENTICATED_CLIENTS) or (client_ip in ("127.0.0.1", "::1", "localhost"))
            effective_limit = 1200 if is_auth else 60
            allowed, remaining = RATE_LIMITER.is_allowed(client_ip, max_requests=effective_limit)
            if not allowed:
                log_error(f"[SECURITY] Rate limit exceeded for {client_ip} (limit: {effective_limit}/min). Terminating connection.")
                await safe_send(websocket, {
                    "type": "error",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Connection terminated.",
                })
                await websocket.close(4029, "Rate limit exceeded")
                break

            # 3. Dispatch to message router asynchronously as a Task so incoming pings/messages are NEVER blocked!
            async def _safe_dispatch(msg_raw):
                try:
                    await handle_message(websocket, msg_raw)
                except Exception as e:
                    log_error(f"Handler error: {e}")
                    import traceback
                    traceback.print_exc()

            asyncio.create_task(_safe_dispatch(raw))
    except websockets.ConnectionClosed:
        log_info(f"Client disconnected: {peer}")
    except Exception as e:
        log_error(f"Connection error: {e}")
    finally:
        CONNECTED_CLIENTS.discard(websocket)
        AUTHENTICATED_CLIENTS.discard(websocket)
        log_info(f"Client removed. Total: {len(CONNECTED_CLIENTS)}")
        update_device_status_file()

