import secrets
import hmac

AUTH_TOKEN = secrets.token_hex(32)
print(f"[AUTH] Token: {AUTH_TOKEN}")

"""
ComposeBridge — Python Bridge Server (Phase 3: Message Hub)

- Receives connections from device (Agent) and test tools
- Forwards messages from any client to all other clients
- Enables Python to control device UI in real-time
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Set

import websockets
from websockets.server import WebSocketServerProtocol

sys.path.insert(0, str(Path(__file__).parent))

from core.models import EditRequest, EditResponse, ErrorCode
from core import theme_indexer


# ============================================================
# Settings
# ============================================================

HOST = "0.0.0.0"
PORT = 8711

PROJECT_ROOT = Path(r"C:\Users\thinkpad\StudioProjects\StudentApp")


# ============================================================
# 
# ============================================================

CONNECTED_CLIENTS: Set[WebSocketServerProtocol] = set()


# ============================================================
# Color logging
# ============================================================

class Color:
 GREEN = "\033[92m"
 RED = "\033[91m"
 YELLOW = "\033[93m"
 BLUE = "\033[94m"
 CYAN = "\033[96m"
 MAGENTA = "\033[95m"
 BOLD = "\033[1m"
 END = "\033[0m"


def log_info(msg): print(f"{Color.CYAN}[INFO]{Color.END} {msg}", flush=True)
def log_success(msg): print(f"{Color.GREEN}[OK]{Color.END} {msg}", flush=True)
def log_error(msg): print(f"{Color.RED}[ERR]{Color.END} {msg}", flush=True)
def log_recv(msg): print(f"{Color.BLUE}[<-]{Color.END} {msg}", flush=True)
def log_send(msg): print(f"{Color.YELLOW}[->]{Color.END} {msg}", flush=True)
def log_forward(msg): print(f"{Color.MAGENTA}[>>]{Color.END} {msg}", flush=True)


# ============================================================
# Broadcast
# ============================================================

async def broadcast(message: str, exclude: WebSocketServerProtocol = None) -> int:
 """
 Sends message to all connected clients except sender.
 Returns count of clients receiving message.
 """
 count = 0
 dead_clients = []

 for client in list(CONNECTED_CLIENTS):
 if client == exclude:
 continue
 try:
 await client.send(message)
 count += 1
 except Exception as e:
 log_error(f"Failed to send to client: {e}")
 dead_clients.append(client)

 # Clean dead clients
 for client in dead_clients:
 CONNECTED_CLIENTS.discard(client)

 return count


# ============================================================
# Message handling
# ============================================================

async def handle_message(websocket: WebSocketServerProtocol, raw: str) -> None:
    # ---------------------------------------------------------
    # Auth
    # ---------------------------------------------------------
    if msg_type == "auth":
        client_token = message.get("token", "")
        if not hmac.compare_digest(client_token, AUTH_TOKEN):
            await websocket.close(4001, "Unauthorized")
            return
        await websocket.send(json.dumps({"type": "auth_ok"}))
        return


 """Handles a single message."""
 log_recv(raw[:200])

 try:
 message = json.loads(raw)
 except json.JSONDecodeError as e:
 log_error(f"Invalid JSON: {e}")
 await websocket.send(json.dumps({
 "type": "error",
 "message": f"Invalid JSON: {e}"
 }))
 return

 msg_type = message.get("type")
 log_info(f"Message type: {msg_type}")

 # ---------------------------------------------------------
 # Hello / Handshake
 # ---------------------------------------------------------
     # ---------------------------------------------------------
    # rollback_last
    # ---------------------------------------------------------
    if msg_type == "rollback_last":
        from core.state_editor import rollback_last
        ok = rollback_last()
        await websocket.send(json.dumps({
            "type": "rollback_ack",
            "status": "ok" if ok else "empty",
        }))
        log_send(f"rollback_ack (success={ok})")
        return

if msg_type == "hello":
 await websocket.send(json.dumps({
 "type": "hello_ack",
 "server": "composebridge",
 "protocol": 1,
 "clients": len(CONNECTED_CLIENTS),
 }))
 log_send("hello_ack")
 return

 # ---------------------------------------------------------
 # Ping
 # ---------------------------------------------------------
 if msg_type == "ping":
 await websocket.send(json.dumps({"type": "pong"}))
 return

 # ---------------------------------------------------------
 # ⭐ state_update — Forwarded to other clients (device)
 # ---------------------------------------------------------
 if msg_type == "state_update":
 property_name = message.get("property")
 value = message.get("value")
 log_forward(f"Handling state_update: {property_name} = {value}")

 # 1. Update file on disk
 from core.state_editor import (
 apply_state_update,
 update_theme_color,
 is_theme_color_property,
 extract_theme_key,
 update_typography_property,
 is_typography_property,
 parse_typography_property,
 )

 if is_typography_property(property_name):
 # Typography
 style_key, prop_name = parse_typography_property(property_name)
 if style_key and prop_name:
 file_success, file_msg, file_info = update_typography_property(
 style_key, prop_name, value
 )
 else:
 file_success, file_msg, file_info = (False, f"Invalid typography property: {property_name}", None)
 elif is_theme_color_property(property_name):
 # 
 theme_key = extract_theme_key(property_name)
 file_success, file_msg, file_info = update_theme_color(theme_key, value)
 else:
 # Path (BridgeState)
 file_success, file_msg, file_info = apply_state_update(property_name, value)

 if file_success:
 log_success(f"📁 File updated: {file_msg}")
 # ⚠️ installDebug — Commit
 else:
 log_error(f"⚠️ File update failed: {file_msg}")

 # 2. Forward to device
 forwarded = await broadcast(raw, exclude=websocket)
 log_forward(f"📱 Forwarded to {forwarded} client(s)")

 # 3. Acknowledge sender
 await websocket.send(json.dumps({
 "type": "state_update_ack",
 "status": "ok",
 "forwarded_to": forwarded,
 "file_updated": file_success,
 "file_message": file_msg,
 "property": property_name,
 "value": value,
 }))
 log_send(f"state_update_ack (file={file_success}, phone={forwarded})")
 return

 # ---------------------------------------------------------
 # ⭐ batch_update — Forwarded to other clients
 # ---------------------------------------------------------
 if msg_type == "batch_update":
 log_forward("Forwarding batch_update")
 forwarded = await broadcast(raw, exclude=websocket)

 await websocket.send(json.dumps({
 "type": "batch_update_ack",
 "status": "ok",
 "forwarded_to": forwarded,
 }))
 log_send(f"batch_update_ack (forwarded={forwarded})")
 return

 # ---------------------------------------------------------
 # ⭐ reset_state — Forwarded to other clients
 # ---------------------------------------------------------
 if msg_type == "reset_state":
 log_forward("Forwarding reset_state")
 forwarded = await broadcast(raw, exclude=websocket)

 await websocket.send(json.dumps({
 "type": "reset_ack",
 "status": "ok",
 "forwarded_to": forwarded,
 }))
 log_send(f"reset_ack (forwarded={forwarded})")
 return

 # ---------------------------------------------------------
 # ⭐ theme_tokens — Returns list of all tokens
 # ---------------------------------------------------------
 if msg_type == "theme_tokens":
 idx = theme_indexer.get_index()
 await websocket.send(json.dumps({
 "type": "theme_tokens_response",
 "tokens": idx.get_all_tokens(),
 "categories": idx.get_tokens_by_category(),
 }, ensure_ascii=False))
 log_send(f"theme_tokens_response ({len(idx.tokens)} tokens)")
 return

 # ---------------------------------------------------------
 # ⭐ identify_token — Finds token by color value
 # ---------------------------------------------------------
 if msg_type == "identify_token":
 hex_value = message.get("hex", "")
 idx = theme_indexer.get_index()
 token = idx.find_token_by_color(hex_value)
 await websocket.send(json.dumps({
 "type": "identify_token_response",
 "hex": hex_value,
 "token": token,
 }, ensure_ascii=False))
 log_send(f"identify_token_response: {hex_value} → {token}")
 return

 # ---------------------------------------------------------
 # ⭐ analyze_element_with_tree — children
 # ---------------------------------------------------------
 if msg_type == "analyze_element_with_tree":
 from core.source_analyzer import analyze_element_range
 import json as json_lib

 source_file = message.get("file", "")
 line_number = message.get("line", 0)
 utf16_offset = message.get("offset", 0)
 utf16_length = message.get("length", 0)
 tree_raw = message.get("tree", "[]")

 # Extract analysis
 result = analyze_element_range(
 source_file, line_number, utf16_offset, utf16_length
 )

 # Try parsing tree (can be string or list)
 try:
 if isinstance(tree_raw, str):
 tree = json_lib.loads(tree_raw)
 else:
 tree = tree_raw
 except Exception as e:
 log_error(f"Tree parse failed: {e}")
 tree = []

 # ⭐ Add suggested tokens based on file
 if "WelcomeHeader.kt" in source_file or source_file.endswith("WelcomeHeader.kt"):
 result["suggested_tokens"] = [
 {"name": "cardHeight", "default": 100.0},
 {"name": "cardCorner", "default": 20.0},
 {"name": "cardBorder", "default": 2.0},
 {"name": "cardIcon", "default": 60.0},
 ]

 # Send response
 await websocket.send(json_lib.dumps({
 "type": "analyze_element_response",
 "result": result,
 "root": {
 "name": "root",
 "sourceFile": source_file,
 "line": line_number,
 "utf16Offset": utf16_offset,
 "utf16Length": utf16_length,
 "children": tree,
 },
 }, ensure_ascii=False))

 log_send(f"analyze_element_with_tree_response: {source_file}:{line_number} → {len(tree)} children")
 return

 # ---------------------------------------------------------
 # ⭐ analyze_element — Analyzes element based on source
 # ---------------------------------------------------------
 if msg_type == "analyze_element":
 from core.source_analyzer import analyze_element_range
 import json as json_lib

 source_file = message.get("file", "")
 line_number = message.get("line", 0)
 utf16_offset = message.get("offset", 0)
 utf16_length = message.get("length", 0)

 result = analyze_element_range(
 source_file,
 line_number,
 utf16_offset,
 utf16_length,
 )

 # ⭐ Add suggested tokens based on file
 if "WelcomeHeader.kt" in source_file or source_file.endswith("WelcomeHeader.kt"):
 result["suggested_tokens"] = [
 {"name": "cardHeight", "default": 100.0},
 {"name": "cardCorner", "default": 20.0},
 {"name": "cardBorder", "default": 2.0},
 {"name": "cardIcon", "default": 60.0},
 ]

 await websocket.send(json_lib.dumps({
 "type": "analyze_element_response",
 "result": result,
 "root": {
 "name": "root",
 "sourceFile": source_file,
 "line": line_number,
 "utf16Offset": utf16_offset,
 "utf16Length": utf16_length,
 "children": [],
 },
 }, ensure_ascii=False))

 log_send(f"analyze_element_response: {source_file}:{line_number} → "
 f"{len(result.get('tokens_used', []))} tokens, "
 f"{len(result.get('dimensions', []))} dims, "
 f"{len(result.get('font_sizes', []))} sizes "
 f"(exact={result.get('used_exact_range', False)})")
 return

 # ---------------------------------------------------------
 # ⭐ edit_dimension — Edits .dp value directly
 # ---------------------------------------------------------
 if msg_type == "edit_dimension":
 from core.state_editor import edit_dimension_in_source

 source_file = message.get("file", "")
 line_number = message.get("line", 0)
 utf16_offset = message.get("offset", 0)
 utf16_length = message.get("length", 0)
 old_value = message.get("oldValue", "")
 new_value = message.get("newValue", "")

 file_success, file_msg, file_info = edit_dimension_in_source(
 source_file, line_number, utf16_offset, utf16_length,
 old_value, new_value
 )

 if file_success:
 log_success(f"📁 {file_msg}")
 else:
 log_error(f"⚠️ {file_msg}")

 # Forward to device Apply override runtime
 forwarded = await broadcast(raw, exclude=websocket)

 await websocket.send(json.dumps({
 "type": "edit_dimension_ack",
 "status": "ok",
 "file_updated": file_success,
 "file_message": file_msg,
 "forwarded_to": forwarded,
 }))
 log_send(f"edit_dimension_ack (file={file_success}, forwarded={forwarded})")
 return

 # ---------------------------------------------------------
 # ⭐ dimension_override — Forwarded to devices
 # ---------------------------------------------------------
 if msg_type == "dimension_override":
 log_forward("Forwarding dimension_override")
 forwarded = await broadcast(raw, exclude=websocket)

 await websocket.send(json.dumps({
 "type": "dimension_override_ack",
 "status": "ok",
 "forwarded_to": forwarded,
 }))
 log_send(f"dimension_override_ack (forwarded={forwarded})")
 return

 # ---------------------------------------------------------
 # ⭐ dimension_reset — Forwarded to devices
 # ---------------------------------------------------------
 if msg_type == "dimension_reset":
 log_forward("Forwarding dimension_reset")
 forwarded = await broadcast(raw, exclude=websocket)

 await websocket.send(json.dumps({
 "type": "dimension_reset_ack",
 "status": "ok",
 "forwarded_to": forwarded,
 }))
 log_send(f"dimension_reset_ack (forwarded={forwarded})")
 return

 # ---------------------------------------------------------
 # ⭐ update_token_default — BridgeSpacing.kt
 # ---------------------------------------------------------
 if msg_type == "update_token_default":
 from core.state_editor import update_token_default

 token_name = message.get("token", "")
 value = message.get("value", "")

 file_success, file_msg, file_info = update_token_default(token_name, value)

 if file_success:
 log_success(f"📁 Saved: {file_msg}")
 else:
 log_error(f"⚠️ {file_msg}")

 await websocket.send(json.dumps({
 "type": "update_token_default_ack",
 "status": "ok",
 "file_updated": file_success,
 "file_message": file_msg,
 }))
 log_send(f"update_token_default_ack (file={file_success})")
 return

 # ---------------------------------------------------------
 # ⭐ toggle_design_mode — /Disable 
 # ---------------------------------------------------------
 if msg_type == "toggle_design_mode":
 # Forward to device
 forwarded = await broadcast(raw, exclude=websocket)

 await websocket.send(json.dumps({
 "type": "toggle_design_mode_ack",
 "status": "ok",
 "forwarded_to": forwarded,
 }))
 log_send(f"toggle_design_mode_ack (forwarded={forwarded})")
 return

 # ---------------------------------------------------------
 # ⭐ reload_theme_index — Rebuild index
 # ---------------------------------------------------------
 if msg_type == "reload_theme_index":
 success = theme_indexer.reload_index()
 await websocket.send(json.dumps({
 "type": "reload_theme_index_response",
 "status": "ok" if success else "error",
 "count": len(theme_indexer.get_index().tokens),
 }, ensure_ascii=False))
 log_send(f"reload_theme_index_response (success={success})")
 return

 # ---------------------------------------------------------
 # edit_request — From device
 # ---------------------------------------------------------
 if msg_type == "edit_request":
 await handle_edit_request(websocket, message)
 return

 # ---------------------------------------------------------
 # Unknown
 # ---------------------------------------------------------
 # ⚠️ error messages ( )
 if msg_type == "error":
 log_error(f"Received error from client: {message.get('message')}")
 return

 # Unknown - 
 log_error(f"Unknown message type (no reply): {msg_type}")


async def handle_edit_request(websocket: WebSocketServerProtocol, message: dict) -> None:
 """ ."""
 payload = message.get("payload", {})
 log_info("=" * 50)
 log_info("📥 EDIT REQUEST")
 log_info("=" * 50)
 for k, v in payload.items():
 log_info(f" {k}: {v}")
 log_info("=" * 50)

 await websocket.send(json.dumps({
 "type": "edit_response",
 "payload": {
 "requestId": payload.get("requestId", "unknown"),
 "status": "success",
 "note": "Phase 3: receive only",
 }
 }))


# ============================================================
# Connection lifecycle
# ============================================================

async def handle_client(websocket: WebSocketServerProtocol) -> None:
 """Handles a single client."""
 CONNECTED_CLIENTS.add(websocket)
    from core.registry_sync import get_sync_manager
    get_sync_manager(PROJECT_ROOT).register_client(websocket)
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
        get_sync_manager(PROJECT_ROOT).unregister_client(websocket)
 log_info(f"Client removed. Total: {len(CONNECTED_CLIENTS)}")


# ============================================================
# Entry point
# ============================================================

async def main():
 print()
 print(f"{Color.BOLD}{Color.GREEN}{'=' * 55}{Color.END}")
 print(f"{Color.BOLD}{Color.GREEN} ComposeBridge — Message Hub{Color.END}")
 print(f"{Color.BOLD}{Color.GREEN}{'=' * 55}{Color.END}")
 print(f" Host: {HOST}")
 print(f" Port: {PORT}")
 print(f" Project root: {PROJECT_ROOT}")
 print(f" Mode: Message Hub (broadcast)")
 print(f"{Color.BOLD}{Color.GREEN}{'=' * 55}{Color.END}")
 print()

 # Theme Tokens index
 theme_indexer.init()

 log_info("Waiting for clients (phone + test tools)...")
 print()

 async with websockets.serve(handle_client, HOST, PORT):
 await asyncio.Future()


if __name__ == "__main__":
 try:
 asyncio.run(main())
 except KeyboardInterrupt:
 print()
 log_info("Shutting down...")