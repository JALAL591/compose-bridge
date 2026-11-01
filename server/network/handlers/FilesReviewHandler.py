# -*- coding: utf-8 -*-
"""
معالج رسائل مراجعة الملفات المعدلة، وفحص المشروع، وقبول/رفض التغييرات.
Handles modified files listing, hunk diff reviews, approve/reject operations, and project scanning.
"""

import json
from pathlib import Path
from websockets.server import WebSocketServerProtocol

from core.pattern_journal import PatternJournal
from core.token_migrator import TokenMigrator
from core.project_scanner import ProjectScanner
from network.ws_server import (
    safe_send,
    broadcast,
    broadcast_changes_updated,
    log_info,
    log_error,
    log_send,
    PROJECT_ROOT,
)

async def handle_reject_all_files(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """رفض والتراجع عن جميع الملفات المعدلة."""
    from core.pattern_journal import PatternJournal
    from core.project_root import get_project_root
    
    force = message.get("force", False)
    journal = PatternJournal(get_project_root())
    result = journal.reject_all_files(force=force)
    
    await safe_send(websocket, {
        "type": "reject_all_files_ack",
        "result": result,
    })
    await broadcast(json.dumps({
        "type": "reject_all_files_ack",
        "result": result,
    }, ensure_ascii=False))
    log_info(f"[REJECT_ALL] Reverted: {result.get('reverted_count', 0)} files (forced={result.get('forced', False)})")
    return

# ---------------------------------------------------------
# ⭐ edit_dimension — تعديل قيمة .dp مباشرة
# ---------------------------------------------------------


async def handle_scan_project(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """مسح المشروع الشامل للبحث عن التوكنز والقيم الثابتة."""
    from core.project_scanner import ProjectScanner
    
    try:
        scanner = ProjectScanner(PROJECT_ROOT)
        report = scanner.scan()
        report_dict = report.to_dict()
        broken_files = report_dict.get("broken_files", [])
        
        await safe_send(websocket, {
            "type": "scan_project_response",
            "status": "ok",
            "report": report_dict,
            "broken_files": broken_files,
            "broken_count": len(broken_files),
            "scan_result": report_dict,
        })
    except Exception as e:
        await safe_send(websocket, {
            "type": "scan_project_response",
            "status": "error",
            "error": str(e),
        })
    return

# ---------------------------------------------------------
# ⭐ add_token — تحويل Hardcoded إلى Token
# ---------------------------------------------------------


async def handle_add_token(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """إضافة توكن جديد إلى نظام التصميم وترحيل استخداماته."""
    from core.token_migrator import TokenMigrator
    
    try:
        migrator = TokenMigrator(PROJECT_ROOT)
        success, mig_msg, info = migrator.migrate(
            file_name=message.get("file", ""),
            line=message.get("line", 0),
            value=message.get("value", ""),
            token_name=message.get("token_name", ""),
            token_type=message.get("token_type", ""),
            force_create=message.get("force_create", False),
        )
        
        if success:
            STATE_MANAGER.events.log(
                "token_added",
                {
                    "token_name": message.get("token_name"),
                    "value": message.get("value"),
                    "file": message.get("file"),
                    "line": message.get("line"),
                },
                source="user",
            )
            STATE_MANAGER.save_all()
            
            # Broadcast to phones
            forwarded = await broadcast(json.dumps({
                "type": "token_added",
                "token_name": message.get("token_name"),
                "value": message.get("value"),
                "file": message.get("file"),
                "line": message.get("line"),
            }), exclude=websocket)
            await broadcast_changes_updated(exclude=None)
            
            await safe_send(websocket, {
                "type": "add_token_ack",
                "status": "ok",
                "message": mig_msg,
                "info": info,
                "forwarded_to": forwarded,
            })
        else:
            await safe_send(websocket, {
                "type": "add_token_ack",
                "status": "error",
                "error": mig_msg,
                "info": info,
            })
    except Exception as e:
        await safe_send(websocket, {
            "type": "add_token_ack",
            "status": "error",
            "error": str(e),
        })
    return

# ---------------------------------------------------------
# ⭐ toggle_design_mode — تفعيل/إيقاف وضع التصميم
# ---------------------------------------------------------


async def handle_get_modified_files(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """استرجاع قائمة الملفات المعدلة في الذاكرة أو القرص."""
    log_info(f"📂 [Server] Received get_modified_files from {websocket.remote_address}")
    from core.pattern_journal import PatternJournal
    journal = PatternJournal(PROJECT_ROOT)
    files = journal.list_modified_files()
    # using top-level Path
    file_entries = []
    for item in files:
        fp = item.get("file", "") if isinstance(item, dict) else str(item)
        if not fp:
            continue
        file_entries.append({
            "file": fp,
            "name": Path(fp).name,
            "status": "modified",
            "change_count": item.get("change_count", 1) if isinstance(item, dict) else 1
        })
    
    # Send both modified_files_response and modified_files_list for full compatibility
    resp_payload = {
        "type": "modified_files_response",
        "count": len(file_entries),
        "files": file_entries,
    }
    await safe_send(websocket, resp_payload)
    resp_payload_list = dict(resp_payload)
    resp_payload_list["type"] = "modified_files_list"
    await safe_send(websocket, resp_payload_list)
    log_success(f"📂 [Server] Sent modified_files ({len(file_entries)} files) to {websocket.remote_address}")
    return

# ---------------------------------------------------------
# ⭐ reject_change — التراجع عن تعديل جزئي واحد داخل الملف
# ---------------------------------------------------------


async def handle_reject_change(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """رفض تغيير محدد داخل ملف (Hunk Revert)."""
    file_to_reject = message.get("file", "")
    change_id = message.get("change_id", "")
    from core.diff_engine import reject_change
    result = reject_change(file_to_reject, change_id, PROJECT_ROOT)
    if result.get("success"):
        await broadcast_refresh(exclude=None)
    from core.pattern_journal import PatternJournal
    journal = PatternJournal(PROJECT_ROOT)
    updated_files = journal.list_modified_files()
    remaining = [{"file": (f.get("file","") if isinstance(f, dict) else str(f)), "name": Path(f.get("file","") if isinstance(f, dict) else str(f)).name, "status": "modified", "changes": f.get("changes", []), "change_count": f.get("change_count", 0)} for f in updated_files if (f.get("file","") if isinstance(f, dict) else str(f))]
    ack_payload = {
        "type": "reject_change_ack",
        "file": file_to_reject,
        "change_id": change_id,
        "result": result,
        "success": result.get("success", False),
        "remaining_files": remaining
    }
    await safe_send(websocket, ack_payload)
    await broadcast(json.dumps(ack_payload, ensure_ascii=False), exclude=websocket)
    await broadcast(json.dumps({"type": "modified_files_list", "files": remaining}, ensure_ascii=False))
    log_send(f"reject_change_ack sent for: {file_to_reject} (change={change_id})")
    return

# ---------------------------------------------------------
# ⭐ approve_change — قبول تعديل جزئي واحد داخل الملف
# ---------------------------------------------------------


async def handle_approve_change(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """قبول تغيير محدد داخل ملف."""
    file_to_approve = message.get("file", "")
    change_id = message.get("change_id", "")
    from core.diff_engine import approve_change
    result = approve_change(file_to_approve, change_id, PROJECT_ROOT)
    if result.get("success"):
        await broadcast_refresh(exclude=None)
    from core.pattern_journal import PatternJournal
    journal = PatternJournal(PROJECT_ROOT)
    updated_files = journal.list_modified_files()
    remaining = [{"file": (f.get("file","") if isinstance(f, dict) else str(f)), "name": Path(f.get("file","") if isinstance(f, dict) else str(f)).name, "status": "modified", "changes": f.get("changes", []), "change_count": f.get("change_count", 0)} for f in updated_files if (f.get("file","") if isinstance(f, dict) else str(f))]
    ack_payload = {
        "type": "approve_change_ack",
        "file": file_to_approve,
        "change_id": change_id,
        "result": result,
        "success": result.get("success", False),
        "remaining_files": remaining
    }
    await safe_send(websocket, ack_payload)
    await broadcast(json.dumps(ack_payload, ensure_ascii=False), exclude=websocket)
    await broadcast(json.dumps({"type": "modified_files_list", "files": remaining}, ensure_ascii=False))
    log_send(f"approve_change_ack sent for: {file_to_approve} (change={change_id})")
    return

# ---------------------------------------------------------
# ⭐ reject_file — التراجع عن تعديلات ملف واحد
# ---------------------------------------------------------


async def handle_reject_file(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """رفض جميع التعديلات في ملف واحد والتراجع عنها بأمان."""
    file_to_reject = message.get("file", "")
    force = message.get("force", False)
    from core.pattern_journal import PatternJournal
    journal = PatternJournal(PROJECT_ROOT)
    result = journal.reject_file_changes(file_to_reject, force=force)
    if result.get("success"):
        await broadcast_refresh(exclude=None)
    updated_files = journal.list_modified_files()
    remaining = [{"file": (f.get("file","") if isinstance(f, dict) else str(f)), "name": Path(f.get("file","") if isinstance(f, dict) else str(f)).name, "status": "modified"} for f in updated_files if (f.get("file","") if isinstance(f, dict) else str(f))]
    ack_payload = {
        "type": "reject_file_ack",
        "file": file_to_reject,
        "result": result,
        "success": result.get("success", False),
        "error_code": result.get("error_code"),
        "message": result.get("message"),
        "remaining_files": remaining
    }
    await safe_send(websocket, ack_payload)
    await broadcast(json.dumps(ack_payload, ensure_ascii=False), exclude=websocket)
    await broadcast(json.dumps({"type": "modified_files_list", "files": remaining}, ensure_ascii=False))
    log_send(f"reject_file_ack broadcasted for: {file_to_reject} (success={result.get('success')})")
    return

# ---------------------------------------------------------
# ⭐ approve_all_files — قبول جميع الملفات المعدلة
# ---------------------------------------------------------


async def handle_approve_all_files(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """قبول واعتماد كافة التعديلات في كافة الملفات وتنظيف السجل."""
    from core.pattern_journal import PatternJournal
    journal = PatternJournal(PROJECT_ROOT)
    result = journal.approve_all_files()
    await safe_send(websocket, {
        "type": "approve_all_ack",
        "result": result,
        "success": result.get("success", False),
        "remaining_files": []
    })
    log_send("approve_all_ack sent")
    return



async def handle_reject_file_force(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """فرض التراجع عن تعديلات ملف حتى لو تم تعديله خارجياً في الـ IDE."""
    file_to_reject = message.get("file", "")
    from core.pattern_journal import PatternJournal
    journal = PatternJournal(PROJECT_ROOT)
    result = journal.reject_file_changes(file_to_reject, force=True)
    await safe_send(websocket, {
        "type": "reject_file_ack",
        "file": file_to_reject,
        "result": result,
    })
    return

# ---------------------------------------------------------
# ⭐ approve_file — الاحتفاظ بالتعديلات الحالية للملف
# ---------------------------------------------------------


async def handle_approve_file(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """قبول تعديلات ملف واحد."""
    file_to_approve = message.get("file", "")
    from core.pattern_journal import PatternJournal
    journal = PatternJournal(PROJECT_ROOT)
    result = journal.approve_file_changes(file_to_approve)
    await broadcast_refresh(exclude=None)
    updated_files = journal.list_modified_files()
    remaining = [{"file": (f.get("file","") if isinstance(f, dict) else str(f)), "name": Path(f.get("file","") if isinstance(f, dict) else str(f)).name, "status": "modified"} for f in updated_files if (f.get("file","") if isinstance(f, dict) else str(f))]
    ack_payload = {
        "type": "approve_file_ack",
        "file": file_to_approve,
        "result": result,
        "success": result.get("success", False),
        "remaining_files": remaining
    }
    await safe_send(websocket, ack_payload)
    await broadcast(json.dumps(ack_payload, ensure_ascii=False), exclude=websocket)
    await broadcast(json.dumps({"type": "modified_files_list", "files": remaining}, ensure_ascii=False))
    log_send(f"approve_file_ack broadcasted for: {file_to_approve}")
    return

# ---------------------------------------------------------
# ⭐ warning_dialog — بث تحذير تعديل خارجي أو dirty buffer للعملاء
# ---------------------------------------------------------


HANDLERS = {
    "reject_all_files": handle_reject_all_files,
    "scan_project": handle_scan_project,
    "add_token": handle_add_token,
    "get_modified_files": handle_get_modified_files,
    "reject_change": handle_reject_change,
    "approve_change": handle_approve_change,
    "reject_file": handle_reject_file,
    "approve_all_files": handle_approve_all_files,
    "reject_file_force": handle_reject_file_force,
    "approve_file": handle_approve_file,
}
