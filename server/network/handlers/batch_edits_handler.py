# -*- coding: utf-8 -*-
"""
معالج رسائل التعديلات الجماعية وتعديل الألوان والأبعاد والنصوص.
Handles batch edits, global color replacements, token splits, and dimension/text modifications.
"""

import json
from pathlib import Path
from websockets.server import WebSocketServerProtocol

from core.pattern_journal import PatternJournal
from core.token_migrator import TokenMigrator
from common.file_ops import acquire_write_lock

from analysis.color_analyzer import global_color_edit, split_token_for_element
from analysis.dimension_analyzer import global_dimension_edit
from analysis.text_ref_analyzer import _find_ref_in_app_strings

from editor.color_editor import update_color
from editor.dimension_editor import edit_dimension_in_source, update_token_default
from editor.text_editor import update_text_in_source
from handlers.dimension_handler import _apply_dimension_edit

from network.ws_server import (
    safe_send,
    broadcast,
    broadcast_refresh,
    broadcast_changes_updated,
    log_info,
    log_error,
    log_send,
    log_success,
    PROJECT_ROOT,
    STATE_MANAGER,
)

async def handle_batch_update(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تحديث مجموعة من خصائص الحالة دفعة واحدة."""
    log_forward("Forwarding batch_update")
    forwarded = await broadcast(raw, exclude=websocket)

    await safe_send(websocket, {
        "type": "batch_update_ack",
        "status": "ok",
        "forwarded_to": forwarded,
    })
    log_send(f"batch_update_ack (forwarded={forwarded})")
    return

# ---------------------------------------------------------
# ⭐ reset_state — يُمرَّر للعملاء الآخرين
# ---------------------------------------------------------


async def handle_global_color_edit(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تعديل لون عام على مستوى المشروع أو إنشاء توكن جديد له."""
    from core.source_analyzer import global_color_edit
    from core.project_root import get_project_root
    
    result = global_color_edit(
        file=message.get("file"),
        line=message.get("line"),
        property_name=message.get("property", "all"),
        old_value=message.get("old_value"),
        new_value=message.get("new_value"),
        token_name=message.get("token_name"),
        project_root=get_project_root(),
    )
    
    await safe_send(websocket, {
        "type": "global_color_edit_ack",
        "status": "ok" if result.get("success") else "error",
        "result": result,
    })
    
    if result.get("success"):
        new_val = result.get("new_value") or result.get("value")
        token_name = result.get("token_name")
        await broadcast(json.dumps({
            "type": "state_update",
            "kind": "color",
            "token": token_name,
            "property": f"AppColors.{token_name}",
            "value": new_val,
        }, ensure_ascii=False))
        await broadcast(json.dumps({
            "type": "refresh_element_request",
        }, ensure_ascii=False))
        log_info(f"[BROADCAST] state_update: {token_name} = {new_val}")
        log_info(f"[BROADCAST] refresh_element_request")
        if result.get("updated"):
            log_success(f"[UPDATE] Token {token_name}: updated to {new_val}")
        else:
            skipped_cnt = len(result.get("skipped", []))
            log_success(f"[GLOBAL] Created {token_name}")
            if skipped_cnt > 0:
                log_success(f"[GLOBAL] Skipped {skipped_cnt} files (not compose)")
            log_success(f"[GLOBAL] Replaced {result.get('replaced_count', 0)} occurrences in {result.get('files_affected', 0)} files")
    else:
        log_error(f"[GLOBAL] Failed: {result.get('error')}")
    return

# ---------------------------------------------------------
# ⭐ split_token — Focus Mode: إنشاء token خاص لعنصر محدد
# ---------------------------------------------------------


async def handle_split_token(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """فصل توكن مشترك إلى توكن مخصص لعنصر معين."""
    from core.source_analyzer import split_token_for_element
    from core.project_root import get_project_root
    import json as json_lib
    
    occ_raw = message.get("occurrences_in_element", "[]")
    if isinstance(occ_raw, str):
        try:
            occurrences = json_lib.loads(occ_raw)
        except Exception:
            occurrences = []
    elif isinstance(occ_raw, list):
        occurrences = occ_raw
    else:
        occurrences = []
    
    result = split_token_for_element(
        original_token=message.get("original_token"),
        original_value=message.get("original_value", ""),
        new_token_name=message.get("new_token_name"),
        new_value=message.get("new_value"),
        element_file=message.get("element_file"),
        element_line=message.get("element_line", 1),
        occurrences=occurrences,
        project_root=get_project_root(),
    )
    
    orig_val = str(message.get("original_value", "") or message.get("old_value", ""))
    orig_tok = str(message.get("original_token", ""))
    is_hardcoded = (
        orig_val.startswith("#")
        or orig_val.startswith("Color(")
        or orig_tok.startswith("Color(")
        or "0x" in orig_val.lower()
    ) and not orig_tok.startswith("AppColors.") and not orig_val.startswith("AppColors.")
    if isinstance(result, dict):
        result["converted_hardcoded"] = is_hardcoded

    await safe_send(websocket, {
        "type": "split_token_ack",
        "status": "ok" if result.get("success") else "error",
        "result": result,
    })
    
    if result.get("success"):
        from core.pattern_journal import PatternJournal
        journal = PatternJournal(get_project_root())
        modified = journal.list_modified_files()
        log_info(f"[SPLIT] Journal now has {len(modified)} modified files")
        for f in modified:
            log_info(f"  - {f.get('file')} ({f.get('change_count')} changes)")
        
        new_val = message.get("new_value")
        await broadcast(json.dumps({
            "type": "state_update",
            "kind": "color",
            "token": result.get("new_token"),
            "property": f"AppColors.{result.get('new_token')}",
            "value": new_val,
        }, ensure_ascii=False))
        await broadcast(json.dumps({
            "type": "refresh_element_request",
        }, ensure_ascii=False))
        log_success(f"[SPLIT] Created {result['new_token']}, replaced {result['replaced_count']} in {result['file']}")
    else:
        log_error(f"[SPLIT] Failed: {result.get('error')}")
    return

# ---------------------------------------------------------
# ⭐ batch_edits — تطبيق دفعة من التعديلات المعلقة
# ---------------------------------------------------------


async def handle_batch_edits(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تطبيق مجموعة تعديلات مجمعة على ملفات المشروع مع التحقق من التعارض."""
    edits = message.get("edits", [])
    total = len(edits)

    log_info(f"[BATCH] Processing {total} edits")

    await safe_send(websocket, {
        "type": "batch_progress",
        "status": "started",
        "total": total,
    })

    results = []
    success_count = 0
    fail_count = 0

    from core.source_analyzer import global_color_edit, split_token_for_element
    from core.project_root import get_project_root
    import json as json_lib

    for i, edit in enumerate(edits):
        try:
            edit_type = edit.get("type")
            # ⭐ متغيرات محلية لكل edit لتفادي Value Bleeding
            local_new_value = edit.get("new_value", "")
            local_old_value = edit.get("old_value", "")
            local_token = edit.get("token_name", "")
            local_property = edit.get("property", "")
            local_kind = edit.get("dimension_kind", "dp")
            local_registry_key = edit.get("registry_key", "")

            if edit_type == "global_color":
                result = global_color_edit(
                    file=edit.get("file"),
                    line=edit.get("line"),
                    property_name=local_property or "all",
                    old_value=local_old_value,
                    new_value=local_new_value,
                    token_name=local_token,
                    project_root=get_project_root(),
                )
            elif edit_type == "split_token":
                occ_raw = edit.get("occurrences", [])
                if isinstance(occ_raw, str):
                    try:
                        occurrences = json_lib.loads(occ_raw)
                    except Exception:
                        occurrences = []
                elif isinstance(occ_raw, list):
                    occurrences = occ_raw
                else:
                    occurrences = []

                result = split_token_for_element(
                    original_token=edit.get("original_token", local_old_value),
                    original_value=local_old_value,
                    new_token_name=local_token,
                    new_value=local_new_value,
                    element_file=edit.get("file"),
                    element_line=edit.get("line", 1),
                    occurrences=occurrences,
                    project_root=get_project_root(),
                )
                if result.get("success"):
                    from core.pattern_journal import PatternJournal
                    journal = PatternJournal(get_project_root())
                    modified = journal.list_modified_files()
                    log_info(f"[SPLIT] Journal now has {len(modified)} modified files")
                    for f in modified:
                        log_info(f"  - {f.get('file')} ({f.get('change_count')} changes)")
            elif edit_type == "dimension":
                edit_mode = edit.get("edit_mode", "split")
                clean_new = str(local_new_value).replace(".dp", "").replace(".sp", "").strip()
                try:
                    new_value_float = float(clean_new)
                    new_val_str = str(int(new_value_float)) if new_value_float.is_integer() else str(new_value_float)
                except Exception:
                    new_val_str = clean_new
                    new_value_float = 0.0

                clean_old = str(local_old_value).replace(".dp", "").replace(".sp", "").strip()

                if edit_mode == "global":
                    from core.source_analyzer import global_dimension_edit
                    result = global_dimension_edit(
                        value=float(clean_old) if clean_old else 0.0,
                        kind=local_kind,
                        new_value=new_value_float,
                        project_root=get_project_root(),
                        property_name=local_property,
                    )
                    if result.get("success"):
                        dim_token = local_registry_key or result.get("registry_key") or f"global_{local_property}_{clean_old}"
                        await broadcast(json.dumps({
                            "type": "state_update",
                            "kind": "dimension",
                            "token": dim_token,
                            "value": f"{new_val_str}.dp",
                        }, ensure_ascii=False))
                        log_info(f"[BATCH-BROADCAST] (dimension-global) {dim_token} = {new_val_str}.dp")
                else:
                    result = _apply_dimension_edit(edit, get_project_root())
                    if result.get("success"):
                        dim_token = local_registry_key or result.get("registry_key") or edit.get("dimension_token") or local_property
                        await broadcast(json.dumps({
                            "type": "state_update",
                            "kind": "dimension",
                            "token": dim_token,
                            "value": f"{new_val_str}.dp",
                        }, ensure_ascii=False))
                        log_info(f"[BATCH-BROADCAST] (dimension-split) {dim_token} = {new_val_str}.dp")
                    
                if result.get("success"):
                    from core.pattern_journal import PatternJournal
                    journal = PatternJournal(get_project_root())
                    modified = journal.list_modified_files()
                    log_info(f"[DIMENSION] Journal now has {len(modified)} modified files")
                    log_info(f"[DIMENSION] {local_property}: {local_old_value} -> {new_val_str} (mode={edit_mode})")
            elif edit_type == "text_edit":
                from core.state_editor import update_text_in_source
                file_p = edit.get("file", "")
                line_num = edit.get("line", 1)
                old_t = str(edit.get("old_value") or edit.get("old_text", ""))
                new_t = str(edit.get("new_value") or edit.get("new_text", ""))
                ref_k = edit.get("ref_key") or edit.get("text_reference") or edit.get("target") or edit.get("token_name") or edit.get("property")
                if ref_k in ("text", "title", "subtitle", "label", "null", "all"):
                    ref_k = None
                ok, msg, info = update_text_in_source(
                    file_path=file_p,
                    line=line_num,
                    old_text=old_t,
                    new_text=new_t,
                    ref_key=ref_k,
                    project_root=get_project_root(),
                )
                result = {
                    "success": ok,
                    "error": msg if not ok else None,
                    "message": msg,
                    "info": info
                }
                if ok:
                    await broadcast(json.dumps({
                        "type": "state_update",
                        "kind": "text",
                        "token": ref_k or f"text_{line_num}",
                        "value": new_t,
                    }, ensure_ascii=False))
                    log_info(f"[BATCH-BROADCAST] (text) {ref_k or file_p} = '{new_t}'")
            else:
                result = {"success": False, "error": f"Unknown type: {edit_type}"}

            orig_val = str(local_old_value or edit.get("original_value", ""))
            orig_tok = str(edit.get("original_token", ""))
            is_hardcoded = (
                orig_val.startswith("#")
                or orig_val.startswith("Color(")
                or orig_tok.startswith("Color(")
                or "0x" in orig_val.lower()
            ) and not orig_tok.startswith("AppColors.") and not orig_val.startswith("AppColors.")
            if isinstance(result, dict):
                result["converted_hardcoded"] = is_hardcoded

            is_success = result.get("success", False)
            results.append({
                "id": edit.get("id"),
                "success": is_success,
                "result": result,
            })

            if is_success:
                success_count += 1
                if edit_type == "dimension":
                    log_success(f"[DIMENSION] {local_property}: {local_old_value} -> {new_val_str}")
                elif edit_type in ("global_color", "split_token"):
                    token_name = result.get("token_name") or local_token
                    val = result.get("new_value") or result.get("new") or result.get("value") or local_new_value
                    kind = "color" if edit_type == "global_color" else "split"
                    
                    await broadcast(json.dumps({
                        "type": "state_update",
                        "kind": kind,
                        "token": token_name or local_property,
                        "property": f"AppColors.{token_name}" if token_name and kind != "dimension" else "",
                        "value": str(val),
                    }, ensure_ascii=False))
                    log_info(f"[BATCH-BROADCAST] ({kind}) {token_name or local_property} = {val}")

                    if edit_type == "global_color" and result.get("replaced_count", 0) > 0:
                        log_success(f"[GLOBAL] Token {token_name}: replaced {result.get('replaced_count', 0)} occurrences")
                    elif result.get("updated"):
                        log_success(f"[UPDATE] Token {token_name}: {local_old_value} -> {val}")
                    elif edit_type == "global_color":
                        log_success(f"[GLOBAL] Token {token_name}: replaced {result.get('replaced_count', 0)} occurrences")
                    elif edit_type == "split_token":
                        log_success(f"[SPLIT] Token {result.get('new_token')}: created")
            else:
                fail_count += 1
                log_error(f"[BATCH] Edit failed: {result.get('error', 'unknown error')}")

            await safe_send(websocket, {
                "type": "batch_progress",
                "status": "in_progress",
                "current": i + 1,
                "total": total,
                "current_token": edit.get("token_name"),
                "success_so_far": success_count,
                "failed_so_far": fail_count,
            })

        except Exception as e:
            fail_count += 1
            results.append({
                "id": edit.get("id", ""),
                "success": False,
                "error": str(e),
            })

    await safe_send(websocket, {
        "type": "batch_edits_ack",
        "status": "ok" if fail_count == 0 else "partial",
        "total": total,
        "success_count": success_count,
        "failed_count": fail_count,
        "results": results,
    })

    if success_count > 0:
        await broadcast_changes_updated(exclude=None)

    log_info(f"[BATCH] Done: {success_count}/{total} successful")
    return

# ---------------------------------------------------------
# ⭐ reject_all_files — إلغاء كافة التغييرات وتنظيف الـ Journal
# ---------------------------------------------------------


async def handle_edit_dimension(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تعديل بعد في الكود المصدري."""
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
        await broadcast_changes_updated(exclude=None)
    else:
        log_error(f"⚠️ {file_msg}")

    # مرّر للهاتف لتطبيق override في runtime
    forwarded = await broadcast(raw, exclude=websocket)

    await safe_send(websocket, {
        "type": "edit_dimension_ack",
        "status": "ok",
        "file_updated": file_success,
        "file_message": file_msg,
        "forwarded_to": forwarded,
    })
    log_send(f"edit_dimension_ack (file={file_success}, forwarded={forwarded})")
    return

# ---------------------------------------------------------
# ⭐ dimension_override — يمرّر للأجهزة (الهاتف)
# ---------------------------------------------------------
# ---------------------------------------------------------
# ⭐ text_edit — تعديل نص مباشرة
# ---------------------------------------------------------


async def handle_text_edit(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تعديل نص في الكود المصدري أو ملف الموارد."""
    file_path = message.get("file", "")
    line_num = message.get("line", 1)
    old_text = message.get("old_text") or message.get("old_value", "")
    new_text = message.get("new_text") or message.get("new_value", "")
    ref_key = message.get("ref_key") or message.get("text_reference") or message.get("target") or message.get("token_name") or message.get("property")
    if ref_key in ("text", "title", "subtitle", "label", "null", "all"):
        ref_key = None

    from core.state_editor import update_text_in_source
    from core.project_root import get_project_root

    ok, msg, info = update_text_in_source(
        file_path=file_path,
        line=line_num,
        old_text=str(old_text),
        new_text=str(new_text),
        ref_key=ref_key,
        project_root=get_project_root(),
    )

    await safe_send(websocket, {
        "type": "text_edit_ack",
        "success": ok,
        "message": msg,
        "info": info,
    })

    if ok:
        await broadcast(json.dumps({
            "type": "state_update",
            "kind": "text",
            "token": ref_key or f"text_{line_num}",
            "value": new_text,
        }, ensure_ascii=False))
        await broadcast_changes_updated(exclude=None)
    return



async def handle_dimension_override(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تجاوز قيمة بعد مؤقتاً في الذاكرة الحية."""
    log_forward("Forwarding dimension_override")
    forwarded = await broadcast(raw, exclude=websocket)

    await safe_send(websocket, {
        "type": "dimension_override_ack",
        "status": "ok",
        "forwarded_to": forwarded,
    })
    log_send(f"dimension_override_ack (forwarded={forwarded})")
    return

# ---------------------------------------------------------
# ⭐ dimension_reset — يمرّر للأجهزة (الهاتف)
# ---------------------------------------------------------


async def handle_dimension_reset(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """إعادة تعيين أبعاد العنصر للقيم الافتراضية."""
    log_forward("Forwarding dimension_reset")
    forwarded = await broadcast(raw, exclude=websocket)

    await safe_send(websocket, {
        "type": "dimension_reset_ack",
        "status": "ok",
        "forwarded_to": forwarded,
    })
    log_send(f"dimension_reset_ack (forwarded={forwarded})")
    return

# ---------------------------------------------------------
# ⭐ update_token_default — يُحفظ في BridgeSpacing.kt
# ---------------------------------------------------------


async def handle_update_token_default(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تحديث القيمة الافتراضية للتوكن في ملف DesignSystem."""
    from core.state_editor import update_token_default

    token_name = message.get("token", "")
    value = message.get("value", "")

    from core.write_lock import acquire_write_lock
    with acquire_write_lock():
        # ⭐ Check if Agent is busy
        if STATE_MANAGER.agent_busy:
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
                kind="dimension",
            )
            STATE_MANAGER.events.log(
                "user_edit_queued",
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
                    "type": "update_token_default_ack",
                    "status": "queued",
                    "token": token_name,
                    "value": value,
                    "queue_position": STATE_MANAGER.queue.count(),
                    "agent_busy": True,
                })
                log_send(f"update_token_default_ack (queued, pos={STATE_MANAGER.queue.count()})")
                return

        # ⭐ NEW: Remove queued edits for the SAME token
        # (User's new direct edit supersedes old queued intent)
        removed = STATE_MANAGER.queue.remove_by_token(token_name)
        if removed > 0:
            log_forward(f"🗑️ Removed {removed} queued edit(s) for {token_name}")
            STATE_MANAGER.events.log(
                "queue_superseded",
                {"token": token_name, "removed": removed, "reason": "direct_edit"},
                source="user",
            )

        # ⭐ Agent not busy — apply directly
        file_success, file_msg, file_info = update_token_default(token_name, value)

        if file_success:
            log_success(f"📁 Saved: {file_msg}")

            # ⭐ Record in State Manager
            STATE_MANAGER.history.record_value(
                token=token_name,
                old_value="",
                new_value=value,
                source="user",
            )
            STATE_MANAGER.events.log(
                "user_edit_applied",
                {"token": token_name, "value": value},
                source="user",
            )
            STATE_MANAGER.save_all()
            await broadcast_changes_updated(exclude=None)
        else:
            log_error(f"⚠️ {file_msg}")
            STATE_MANAGER.failures.record(
                operation="update_token_default",
                token=token_name,
                location="unknown",
                error=file_msg,
                severity="error",
            )
            STATE_MANAGER.save_all()

        await safe_send(websocket, {
            "type": "update_token_default_ack",
            "status": "ok" if file_success else "error",
            "file_updated": file_success,
            "file_message": file_msg,
            "queued": False,
            "agent_busy": False,
        })
        log_send(f"update_token_default_ack (direct, file={file_success})")
        return

# ---------------------------------------------------------
# ⭐ agent_start — MCP يُخبر Bridge أن Agent بدأ
# ---------------------------------------------------------


HANDLERS = {
    "batch_update": handle_batch_update,
    "global_color_edit": handle_global_color_edit,
    "split_token": handle_split_token,
    "batch_edits": handle_batch_edits,
    "edit_dimension": handle_edit_dimension,
    "text_edit": handle_text_edit,
    "dimension_override": handle_dimension_override,
    "dimension_reset": handle_dimension_reset,
    "update_token_default": handle_update_token_default,
}
