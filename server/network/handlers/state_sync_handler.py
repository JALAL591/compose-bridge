# -*- coding: utf-8 -*-
"""
معالج رسائل المصادقة، والمزامنة، والحالة، وتحديثات المعاينة الحية.
Handles auth, handshake, live state updates, sync queues, and agent lifecycle.
"""

import hmac
import json
import time
from pathlib import Path
from websockets.server import WebSocketServerProtocol

from core.project_root import get_project_root
from network.ws_server import (
    safe_send,
    broadcast,
    broadcast_refresh,
    broadcast_changes_updated,
    log_info,
    log_error,
    log_send,
    log_forward,
    log_success,
    CONNECTED_CLIENTS,
    AUTHENTICATED_CLIENTS,
    AUTH_TOKEN,
    STATE_MANAGER,
    PROJECT_ROOT,
)

async def handle_auth(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """التحقق من توكن المصادقة واعتماد الاتصال."""
    client_token = message.get("token", "")
    from core.auth_manager import verify_token
    if not verify_token(client_token, PROJECT_ROOT):
        log_error(f"[SECURITY] Auth failed for peer: {websocket.remote_address}")
        CONNECTED_CLIENTS.discard(websocket)
        AUTHENTICATED_CLIENTS.discard(websocket)
        await safe_send(websocket, {
            "type": "error",
            "error_code": "UNAUTHORIZED",
            "message": "Invalid authentication token",
        })
        await websocket.close(4001, "Unauthorized")
        return
    AUTHENTICATED_CLIENTS.add(websocket)
    await safe_send(websocket, {"type": "auth_ok", "authenticated": True})
    log_success(f"Client authenticated successfully: {websocket.remote_address}")
    try:
        from network.ws_server import update_device_status_file
        update_device_status_file()
    except Exception:
        pass
    return


async def handle_hello(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """المصافحة الأولية لبروتوكول ComposeBridge."""
    await safe_send(websocket, {
        "type": "hello_ack",
        "server": "composebridge",
        "protocol": 1,
        "clients": len(AUTHENTICATED_CLIENTS),
    })
    log_send("hello_ack")
    return

# ---------------------------------------------------------
# Ping
# ---------------------------------------------------------


async def handle_ping(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """الرد على نبضات التحقق من الاتصال."""
    await safe_send(websocket, {"type": "pong"})
    return

# ---------------------------------------------------------
# ⭐ state_update — يُمرَّر للعملاء الآخرين (الهاتف)
# ---------------------------------------------------------


async def handle_state_update(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تحديث قيمة خاصية في الحالة وإرسالها لباقي العملاء."""
    property_name = message.get("property")
    value = message.get("value")
    log_forward(f"Handling state_update: {property_name} = {value}")

    from core.write_lock import acquire_write_lock
    with acquire_write_lock():
        # ⭐ افحص agent_busy — نفس منطق update_token_default
        if STATE_MANAGER.agent_busy:
            # استخرج اسم الـ token من "AppColors.Primary"
            token_name = property_name.replace("AppColors.", "").strip()

            removed = STATE_MANAGER.queue.remove_by_token(token_name)
            if removed > 0:
                log_forward(f"🗑️ Removed {removed} queued edit(s) for {token_name} (superseded)")
                STATE_MANAGER.events.log(
                    "queue_superseded",
                    {"token": token_name, "removed": removed, "reason": "queued_new_edit"},
                    source="user",
                )

            edit = STATE_MANAGER.queue.add(
                token=token_name,
                value=value,
                source="user",
                kind="color",
            )
            STATE_MANAGER.events.log(
                "user_color_queued",
                {"token": token_name, "value": value, "edit_id": edit["id"]},
                source="user",
            )
            STATE_MANAGER.save_all()
            log_forward(f"📥 Queued in state_queue: {token_name} = {value}")

            # Reactive wait for agent session to finish
            wait_t0 = time.time()
            while STATE_MANAGER.agent_busy and (time.time() - wait_t0) < 2.5:
                await asyncio.sleep(0.05)

            if STATE_MANAGER.agent_busy:
                await safe_send(websocket, {
                    "type": "state_update_ack",
                    "status": "queued",
                    "property": property_name,
                    "value": value,
                    "queue_position": STATE_MANAGER.queue.count(),
                    "agent_busy": True,
                })
                return

        else:
            # ⭐ حفظ في الملف المصدر
            from core.state_editor import update_color
            token_name = property_name.replace("AppColors.", "").strip()
            
            # حذف أي queue قديم
            STATE_MANAGER.queue.remove_by_token(token_name)
            
            # ⭐ الحفظ الفعلي
            ok, msg = update_color(token_name, value)
            
            if ok:
                log_success(f"📁 Saved: Updated {token_name}: -> {value}")
                STATE_MANAGER.history.record_value(
                    token=token_name,
                    old_value="",
                    new_value=value,
                    source="user",
                )
                STATE_MANAGER.events.log(
                    "user_color_applied",
                    {"token": token_name, "value": value},
                    source="user",
                )
                STATE_MANAGER.save_all()
                await broadcast_changes_updated(exclude=None)
            else:
                log_error(f"⚠️ Failed to save: {msg}")
            
            # ثم forward للهواتف الأخرى
            forwarded = await broadcast(raw, exclude=websocket)
            log_forward(f"📱 Forwarded to {forwarded} phone(s)")
            
            await safe_send(websocket, {
                "type": "state_update_ack",
                "status": "ok" if ok else "error",
                "file_updated": ok,
                "file_message": msg,
                "property": property_name,
                "value": value,
                "forwarded_to": forwarded,
            })
            return

# ---------------------------------------------------------
# ⭐ refresh_element_request — بث تحديث للإضافة والهاتف
# ---------------------------------------------------------


async def handle_refresh_element_request(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """طلب تحديث عنصر واجهة معين."""
    forwarded = await broadcast_refresh(exclude=websocket)
    from core.pattern_journal import PatternJournal
    journal = PatternJournal(PROJECT_ROOT)
    updated_files = journal.list_modified_files()
    remaining = [{"file": (f.get("file","") if isinstance(f, dict) else str(f)), "name": Path(f.get("file","") if isinstance(f, dict) else str(f)).name, "status": "modified"} for f in updated_files if (f.get("file","") if isinstance(f, dict) else str(f))]
    await broadcast(json.dumps({"type": "modified_files_list", "files": remaining}, ensure_ascii=False))
    log_info(f"[BROADCAST] refresh_element_request & modified_files_list (forwarded to {forwarded} client(s))")
    await safe_send(websocket, {
        "type": "refresh_element_ack",
        "status": "ok",
        "forwarded_to": forwarded,
    })
    return

# ---------------------------------------------------------
# MCP State Update — من mcp_server.py
# ---------------------------------------------------------


async def handle_mcp_state_update(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تحديث حالة قادم من خادم MCP."""
    property_name = message.get("property")
    value = message.get("value")
    log_forward(f"MCP update: {property_name} = {value}")

    # ⚠️ لا نعدّل الملف — mcp_server.py عدّله بالفعل
    # فقط: نمرّر للهواتف

    # Forward to all connected phones
    forwarded = await broadcast(raw, exclude=websocket)
    log_forward(f"📱 Forwarded to {forwarded} phone(s)")

    await safe_send(websocket, {
        "type": "mcp_state_update_ack",
        "status": "ok",
        "forwarded_to": forwarded,
        "property": property_name,
        "value": value,
    })
    return

# ---------------------------------------------------------
# ⭐ batch_update — يُمرَّر للعملاء الآخرين
# ---------------------------------------------------------


async def handle_reset_state(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """إعادة تعيين الحالة وإخطار العملاء."""
    log_forward("Forwarding reset_state")
    forwarded = await broadcast(raw, exclude=websocket)

    await safe_send(websocket, {
        "type": "reset_ack",
        "status": "ok",
        "forwarded_to": forwarded,
    })
    log_send(f"reset_ack (forwarded={forwarded})")
    return

# ---------------------------------------------------------
# ⭐ theme_tokens — يعيد قائمة كل الـ tokens
# ---------------------------------------------------------


async def handle_agent_start(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """إشعار بدء جلسة وكيل الذكاء الاصطناعي وإيقاف مزامنة المستخدم مؤقتاً."""
    STATE_MANAGER.set_agent_busy(True)
    STATE_MANAGER.save_all()
    log_success("🤖 Agent session started")

    # Broadcast to all phones
    forwarded = await broadcast(json.dumps({
        "type": "agent_status",
        "agent_busy": True,
    }), exclude=websocket)

    await safe_send(websocket, {
        "type": "agent_start_ack",
        "status": "ok",
        "forwarded_to": forwarded,
    })
    return

# ---------------------------------------------------------
# ⭐ agent_end — MCP يُخبر Bridge أن Agent انتهى
# ---------------------------------------------------------


async def handle_agent_end(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """إشعار انتهاء جلسة الوكيل واستئناف المزامنة."""
    STATE_MANAGER.set_agent_busy(False)
    STATE_MANAGER.save_all()
    log_success("🤖 Agent session ended")

    # Broadcast to all phones
    forwarded = await broadcast(json.dumps({
        "type": "agent_status",
        "agent_busy": False,
        "queue_pending": STATE_MANAGER.queue.count(),
    }), exclude=websocket)

    await safe_send(websocket, {
        "type": "agent_end_ack",
        "status": "ok",
        "forwarded_to": forwarded,
    })
    return

# ---------------------------------------------------------
# ⭐ queue_status — Phone يسأل عن حالة الطابور
# ---------------------------------------------------------


async def handle_queue_status(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """الاستعلام عن حالة طابور التعديلات المعلقة."""
    queue_edits = STATE_MANAGER.queue.get_all()
    await safe_send(websocket, {
        "type": "queue_status_response",
        "count": STATE_MANAGER.queue.count(),
        "agent_busy": STATE_MANAGER.agent_busy,
        "edits": queue_edits,
    })
    return

# ---------------------------------------------------------
# ⭐ queue_clear — Phone يطلب إفراغ الطابور
# ---------------------------------------------------------


async def handle_queue_clear(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """مسح طابور التعديلات المعلقة."""
    count = STATE_MANAGER.queue.count()
    STATE_MANAGER.queue.clear()
    STATE_MANAGER.save_all()
    STATE_MANAGER.events.log(
        "queue_cleared",
        {"count": count},
        source="user",
    )
    log_forward(f"🗑️ Queue cleared ({count} edits)")

    await safe_send(websocket, {
        "type": "queue_clear_ack",
        "status": "ok",
        "cleared": count,
    })
    return

# ---------------------------------------------------------
# ⭐ user_sync — Phone يطلب تطبيق الطابور
# ---------------------------------------------------------


async def handle_user_sync(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تطبيق التعديلات المتراكمة في الطابور على ملفات المشروع."""
    if STATE_MANAGER.agent_busy:
        log_error("⚠️ Sync refused — agent busy")
        await safe_send(websocket, {
            "type": "user_sync_ack",
            "status": "refused",
            "reason": "agent_busy",
            "queue_count": STATE_MANAGER.queue.count(),
        })
        return

    # Apply queue
    log_forward(f"🔄 Sync: applying {STATE_MANAGER.queue.count()} edits")

    # Phase 4D: Real apply (not dry run)
    preview = STATE_MANAGER.apply_user_sync(dry_run=False)

    log_forward(f"   Applied: {len(preview['applied'])}")
    log_forward(f"   Skipped: {len(preview['skipped'])}")
    log_forward(f"   Errors: {len(preview['errors'])}")

    skipped_count = len(preview["skipped"])
    errors_count = len(preview["errors"])
    applied_count = len(preview["applied"])
    
    # ⭐ حدد الرسالة
    if skipped_count > 0 and applied_count > 0:
        status = "partial"
        message_text = f"تم تطبيق {applied_count} — فشل {skipped_count}"
    elif skipped_count > 0 and applied_count == 0:
        status = "failed"
        message_text = f"فشل التطبيق — {skipped_count} token غير موجود"
    elif errors_count > 0:
        status = "error"
        message_text = f"{errors_count} خطأ"
    else:
        status = "ok"
        message_text = None
    
    if applied_count > 0:
        await broadcast_changes_updated(exclude=None)

    await safe_send(websocket, {
        "type": "user_sync_ack",
        "status": status,
        "dry_run": False,
        "applied": applied_count,
        "skipped": skipped_count,
        "errors": errors_count,
        "message": message_text,
        "details": preview,
    })
    return

# ---------------------------------------------------------
# ⭐ state_info — Phone يسأل عن الحالة الكاملة
# ---------------------------------------------------------


async def handle_state_info(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """استرجاع معلومات مفصلة عن كائن الحالة الحالي."""
    await safe_send(websocket, {
        "type": "state_info_response",
        "agent_busy": STATE_MANAGER.agent_busy,
        "queue_count": STATE_MANAGER.queue.count(),
        "snapshot_version": STATE_MANAGER.snapshot.version,
        "token_count": len(STATE_MANAGER.snapshot.tokens),
        "unresolved_failures": len(STATE_MANAGER.failures.get_unresolved()),
    })
    return

# ---------------------------------------------------------
# ⭐ scan_project — فحص شامل للمشروع والـ Tokens
# ---------------------------------------------------------


async def handle_toggle_design_mode(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تبديل وضع التصميم (Design Mode) في الهاتف."""
    # مرّر للهاتف
    forwarded = await broadcast(raw, exclude=websocket)

    await safe_send(websocket, {
        "type": "toggle_design_mode_ack",
        "status": "ok",
        "forwarded_to": forwarded,
    })
    log_send(f"toggle_design_mode_ack (forwarded={forwarded})")
    return

# ---------------------------------------------------------
# ⭐ reload_theme_index — إعادة بناء الفهرس
# ---------------------------------------------------------


async def handle_reload_theme_index(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """إعادة فهرسة توكنز الثيم ونظام التصميم."""
    success = theme_indexer.reload_index()
    await safe_send(websocket, {
        "type": "reload_theme_index_response",
        "status": "ok" if success else "error",
        "count": len(theme_indexer.get_index().tokens),
    })
    log_send(f"reload_theme_index_response (success={success})")
    return

# ---------------------------------------------------------
# ---------------------------------------------------------
# ⭐ reject_file_force — استعادة ملف بالقوة عند تأكيد المستخدم
# ---------------------------------------------------------
# ---------------------------------------------------------
# ⭐ get_modified_files — استرجاع قائمة الملفات المعدلة
# ---------------------------------------------------------
# ---------------------------------------------------------
# ⭐ build_and_send_apk — بناء الـ APK وإرساله للهاتف عبر WebSocket
# ---------------------------------------------------------


async def handle_clean_cache(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تنظيف الكاش والملفات المؤقتة بأمان."""
    from core.project_root import clean_temp_files, get_project_root
    res = clean_temp_files(get_project_root())
    await websocket.send(json.dumps({
        "type": "clean_cache_ack",
        **res
    }))
    return



async def handle_warning_dialog(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """توجيه حوار تحذيري إلى الهاتف."""
    forwarded = await broadcast(raw, exclude=websocket)
    await safe_send(websocket, {
        "type": "warning_dialog_ack",
        "status": "ok",
        "forwarded_to": forwarded,
    })
    log_send(f"warning_dialog broadcasted (forwarded={forwarded})")
    return

# edit_request — من الهاتف
# ---------------------------------------------------------


async def handle_edit_request(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """معالجة طلب تعديل عام."""
    await handle_edit_request(websocket, message)
    return

# ---------------------------------------------------------
# غير معروف
# ---------------------------------------------------------
# ⚠️ لا نرد على error messages (لتجنب الحلقات)


async def handle_error(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تسجيل رسائل الخطأ الواردة من العميل."""
    log_error(f"Received error from client: {message.get('message')}")
    return



async def handle_ide_diagnostics_request(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """Forward diagnostics query to IDE plugin, or respond immediately if no IDE client is connected."""
    log_info("Forwarding ide_diagnostics_request to connected clients")
    forwarded = await broadcast(raw, exclude=websocket)
    if forwarded == 0:
        await safe_send(websocket, {
            "type": "ide_diagnostics_response",
            "request_id": message.get("request_id"),
            "success": False,
            "connected": False,
            "error": "No IDE plugin connected to ComposeBridge server",
            "errors_count": 0,
            "diagnostics": []
        })


async def handle_ide_diagnostics_response(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """Forward diagnostics response back to MCP client."""
    log_info(f"Forwarding ide_diagnostics_response (req_id={message.get('request_id')})")
    await broadcast(raw, exclude=websocket)


async def handle_project_diagnostics_scan_request(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """Forward project diagnostics scan query to IDE plugin."""
    log_info("Forwarding project_diagnostics_scan_request to connected clients")
    forwarded = await broadcast(raw, exclude=websocket)
    if forwarded == 0:
        await safe_send(websocket, {
            "type": "project_diagnostics_scan_response",
            "request_id": message.get("request_id"),
            "success": False,
            "connected": False,
            "error": "No IDE plugin connected to ComposeBridge server",
            "scanned_files_count": 0,
            "total_errors": 0,
            "total_warnings": 0,
            "files": []
        })


async def handle_project_diagnostics_scan_response(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """Forward project diagnostics scan response back to MCP client."""
    log_info(f"Forwarding project_diagnostics_scan_response (req_id={message.get('request_id')})")
    await broadcast(raw, exclude=websocket)


HANDLERS = {
    "ide_diagnostics_request": handle_ide_diagnostics_request,
    "ide_diagnostics_response": handle_ide_diagnostics_response,
    "project_diagnostics_scan_request": handle_project_diagnostics_scan_request,
    "project_diagnostics_scan_response": handle_project_diagnostics_scan_response,
    "auth": handle_auth,
    "hello": handle_hello,
    "ping": handle_ping,
    "state_update": handle_state_update,
    "refresh_element_request": handle_refresh_element_request,
    "mcp_state_update": handle_mcp_state_update,
    "reset_state": handle_reset_state,
    "agent_start": handle_agent_start,
    "agent_end": handle_agent_end,
    "queue_status": handle_queue_status,
    "queue_clear": handle_queue_clear,
    "user_sync": handle_user_sync,
    "state_info": handle_state_info,
    "toggle_design_mode": handle_toggle_design_mode,
    "reload_theme_index": handle_reload_theme_index,
    "clean_cache": handle_clean_cache,
    "warning_dialog": handle_warning_dialog,
    "edit_request": handle_edit_request,
    "error": handle_error,
}
