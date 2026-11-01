# -*- coding: utf-8 -*-
"""
موجه رسائل الـ WebSocket الرئيسي لخادم ComposeBridge.
Main WebSocket message router and dispatcher using the Command/Handler pattern.
"""

import json
from websockets.server import WebSocketServerProtocol

from network.handlers import ALL_HANDLERS
from network.ws_server import (
    safe_send,
    log_info,
    log_error,
    log_recv,
    AUTHENTICATED_CLIENTS,
)

async def handle_message(websocket: WebSocketServerProtocol, raw: str) -> None:
    """
    استقبال ومعالجة رسالة WebSocket الواردة وتوجيهها إلى المعالج المختص.
    Receives and processes incoming WebSocket messages, dispatching to the appropriate handler.
    """
    log_recv(raw[:200])

    try:
        message = json.loads(raw)
    except json.JSONDecodeError as e:
        log_error(f"Invalid JSON: {e}")
        await safe_send(websocket, {
            "type": "error",
            "message": f"Invalid JSON: {e}"
        })
        return

    msg_type = message.get("type")
    log_info(f"Message type: {msg_type}")

    # 1. التحقق من المصادقة (Auth Check FIRST)
    if msg_type != "auth" and websocket not in AUTHENTICATED_CLIENTS:
        await safe_send(websocket, {
            "type": "error",
            "error_code": "AUTH_REQUIRED",
            "message": "Authentication required. First message must be {'type': 'auth', 'token': '...'}",
        })
        await websocket.close(4001, "Auth required")
        return

    # 2. توجيه الرسالة إلى المعالج المسجل في القاموس (Dispatcher Registry)
    handler = ALL_HANDLERS.get(msg_type)
    if handler:
        await handler(websocket, message, raw)
    else:
        log_info(f"Unknown message type: {msg_type}")
        await safe_send(websocket, {
            "type": "error",
            "message": f"Unknown message type: {msg_type}"
        })

async def handle_edit_request(websocket: WebSocketServerProtocol, message: dict) -> None:
    """يعالج طلب تعديل ملف (Legacy compatibility)."""
    handler = ALL_HANDLERS.get("edit_request")
    if handler:
        await handler(websocket, message, json.dumps(message))
