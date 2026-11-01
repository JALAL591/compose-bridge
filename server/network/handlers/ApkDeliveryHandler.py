# -*- coding: utf-8 -*-
"""
معالج رسائل بناء وتدفق ملفات APK إلى العميل (الهاتف / الإضافة).
Handles building, finding, streaming, and tracking APK delivery to clients.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Optional
from websockets.server import WebSocketServerProtocol

from network.ws_server import (
    safe_send,
    log_info,
    log_error,
    log_send,
    log_success,
    PROJECT_ROOT,
)

def _find_latest_apk(p_root: Path) -> Optional[Path]:
    candidates = []
    apk_patterns = [
        "**/build/outputs/apk/debug/*.apk",
        "composeApp/build/outputs/apk/debug/*.apk",
        "app/build/outputs/apk/debug/*.apk",
        "**/build/intermediates/apk/debug/*.apk",
        "**/outputs/apk/debug/*.apk",
        "**/*-debug.apk",
        "**/*.apk",
    ]
    for pattern in apk_patterns:
        for p in p_root.glob(pattern):
            if p.is_file() and not p.name.endswith("-unaligned.apk"):
                candidates.append((p.stat().st_mtime, p))
    if not candidates:
        return None
    debug_candidates = [c for c in candidates if "debug" in c[1].name.lower()]
    best_candidates = debug_candidates if debug_candidates else candidates
    best_candidates.sort(key=lambda x: x[0], reverse=True)
    return best_candidates[0][1]


async def _stream_apk_to_client(websocket, apk_path: Path, start_chunk: int = 0):
    from network.ws_server import update_apk_build_status_file
    file_size = apk_path.stat().st_size
    file_name = apk_path.name
    import base64
    chunk_size = 64 * 1024  # 64 KB chunks
    total_chunks = (file_size + chunk_size - 1) // chunk_size

    if start_chunk >= total_chunks:
        await safe_send(websocket, {
            "type": "apk_complete",
            "file_name": file_name,
            "total_bytes": file_size,
            "message": "APK transfer complete! Ready to install."
        })
        return

    init_progress = (start_chunk / total_chunks) if total_chunks > 0 else 0.1
    update_apk_build_status_file(
        building=False,
        stage="sending",
        progress=init_progress,
        message=f"Sending APK ({round(file_size / (1024*1024), 1)} MB)...",
        success=True,
        file_name=file_name,
        file_path=str(apk_path)
    )

    await safe_send(websocket, {
        "type": "apk_build_progress",
        "stage": "sending",
        "progress": init_progress,
        "file_name": file_name,
        "total_bytes": file_size,
        "total_chunks": total_chunks,
        "resumed_from": start_chunk,
        "message": f"Sending APK ({round(file_size / (1024*1024), 1)} MB)..."
    })

    log_info(f"📦 [Server] Streaming chunks {start_chunk + 1}..{total_chunks} ({round(file_size / (1024*1024), 2)} MB) to {websocket.remote_address}...")
    with open(apk_path, "rb") as f:
        if start_chunk > 0:
            f.seek(start_chunk * chunk_size)
            chunk_index = start_chunk
        else:
            chunk_index = 0

        while True:
            data = f.read(chunk_size)
            if not data:
                break
            chunk_index += 1
            b64_data = base64.b64encode(data).decode("ascii")
            sent = await safe_send(websocket, {
                "type": "apk_chunk",
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "data": b64_data,
                "file_name": file_name,
                "total_bytes": file_size
            })
            if not sent:
                log_error(f"❌ [Server] Client disconnected while streaming APK chunk {chunk_index}")
                return

            if chunk_index % 25 == 0 or chunk_index == start_chunk + 1 or chunk_index == total_chunks:
                pct = int(chunk_index * 100 / total_chunks)
                progress_val = 0.1 + 0.85 * (chunk_index / total_chunks)
                await safe_send(websocket, {
                    "type": "apk_build_progress",
                    "stage": "sending",
                    "progress": progress_val,
                    "file_name": file_name,
                    "total_bytes": file_size,
                    "total_chunks": total_chunks,
                    "message": f"Sending APK ({pct}%)..."
                })

            if chunk_index % 10 == 0:
                await asyncio.sleep(0.01)

    await safe_send(websocket, {
        "type": "apk_complete",
        "file_name": file_name,
        "total_bytes": file_size,
        "message": "APK transfer complete! Ready to install."
    })
    update_apk_build_status_file(
        building=False,
        stage="done",
        progress=1.0,
        message=f"APK transfer complete: {file_name}",
        success=True,
        file_name=file_name,
        file_path=str(apk_path)
    )
    log_success(f"📦 [Server] APK transfer of {file_name} successfully delivered to {websocket.remote_address}")


async def handle_get_apk_build_status(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """إرجاع حالة بناء الـ APK الحالية."""
    p_root = Path(PROJECT_ROOT).resolve()
    state_file = p_root / ".composebridge-state" / "apk_build_status.json"
    if state_file.exists():
        try:
            status_data = json.loads(state_file.read_text(encoding="utf-8"))
            if status_data.get("building") and (time.time() - status_data.get("updated_at", 0) > 600):
                status_data["building"] = False
                status_data["stage"] = "idle"
            await safe_send(websocket, {
                "type": "apk_build_status_response",
                "building": status_data.get("building", False),
                "stage": status_data.get("stage", "idle"),
                "progress": status_data.get("progress", 0.0),
                "message": status_data.get("message", ""),
                "file_name": status_data.get("file_name", "")
            })
            return
        except Exception:
            pass
    await safe_send(websocket, {
        "type": "apk_build_status_response",
        "building": False,
        "stage": "idle",
        "progress": 0.0,
        "message": ""
    })
    return



async def handle_fetch_existing_apk(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """البحث عن ملف APK موجود وبثه إلى العميل."""
    p_root = Path(PROJECT_ROOT).resolve()
    latest_apk = _find_latest_apk(p_root)
    if not latest_apk:
        await safe_send(websocket, {
            "type": "apk_build_error",
            "message": "لم يتم العثور على ملف APK جاهز على السيرفر. يرجى اختيار إعادة البناء."
        })
        return
    log_info(f"📦 [Server] User requested to fetch existing APK: {latest_apk.name}")
    await _stream_apk_to_client(websocket, latest_apk)
    return



async def handle_resume_apk(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """استئناف بث ملف APK من نقطة توقف معينة."""
    last_chunk = message.get("last_chunk", 0)
    file_name = message.get("file_name", "")
    log_info(f"📦 [Server] Received resume_apk request from {websocket.remote_address} (last_chunk={last_chunk}, file={file_name})")
    p_root = Path(PROJECT_ROOT).resolve()
    latest_apk = _find_latest_apk(p_root)
    if not latest_apk:
        await safe_send(websocket, {
            "type": "apk_build_error",
            "message": "لم يتم العثور على ملف APK على السيرفر لاستئناف التحميل."
        })
        return
    await _stream_apk_to_client(websocket, latest_apk, start_chunk=last_chunk)
    return




async def handle_build_and_send_apk(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تشغيل بناء APK عبر Gradle وبث الناتج فور اكتماله."""
    log_info(f"📦 [Server] Received build_and_send_apk request from {websocket.remote_address}")
    p_root = Path(PROJECT_ROOT).resolve()
    force_rebuild = message.get("force_rebuild", False)

    # Check if recent APK (< 60 min) exists and user did not specify force_rebuild
    latest_apk = _find_latest_apk(p_root)
    if latest_apk and not force_rebuild:
        age_seconds = time.time() - latest_apk.stat().st_mtime
        if age_seconds < 3600:
            file_size = latest_apk.stat().st_size
            size_mb = round(file_size / (1024 * 1024), 1)
            mins_ago = int(age_seconds // 60)
            time_ago_str = f"منذ {mins_ago} دقيقة" if mins_ago > 0 else "الآن تقريباً"
            log_info(f"📦 [Server] Recent APK found ({latest_apk.name}, {size_mb} MB, {time_ago_str}). Prompting user: Fetch or Rebuild?")
            await safe_send(websocket, {
                "type": "apk_available",
                "file_name": latest_apk.name,
                "file_size": file_size,
                "file_size_str": f"{size_mb} MB",
                "time_ago": time_ago_str,
                "message": f"يوجد ملف APK جاهز ({latest_apk.name} - {size_mb} MB) تم بناؤه {time_ago_str}. هل تريد جلبه فوراً أم إعادة البناء؟"
            })
            return

    from network.ws_server import update_apk_build_status_file
    update_apk_build_status_file(
        building=True,
        stage="building",
        progress=0.05,
        message="Building APK via gradlew assembleDebug..."
    )

    await safe_send(websocket, {
        "type": "apk_build_progress",
        "stage": "building",
        "progress": 0.05,
        "message": "Starting Gradle assembleDebug on server..."
    })

    loop = asyncio.get_running_loop()

    def _on_progress(progress_val, line_text):
        if websocket in CONNECTED_CLIENTS:
            update_apk_build_status_file(
                building=True,
                stage="building",
                progress=progress_val,
                message=line_text[:120]
            )
            asyncio.run_coroutine_threadsafe(
                safe_send(websocket, {
                    "type": "apk_build_progress",
                    "stage": "building",
                    "progress": progress_val,
                    "message": line_text[:120]
                }),
                loop
            )

    def _build_task():
        from core.gradle_runner import run_gradle_build
        return run_gradle_build(p_root, task="assembleDebug", timeout_seconds=360, on_progress=_on_progress)

    build_res = await loop.run_in_executor(None, _build_task)

    if not build_res.get("success"):
        err_msg = "\\n".join(build_res.get("errors", [])) or build_res.get("error", "Build failed")
        log_error(f"❌ [Server] APK Build failed: {err_msg}")
        update_apk_build_status_file(
            building=False,
            stage="error",
            progress=0.0,
            message=err_msg[:300],
            success=False
        )
        await safe_send(websocket, {
            "type": "apk_build_error",
            "message": f"Gradle build failed: {err_msg[:300]}"
        })
        return

    log_success("✅ [Server] Gradle assembleDebug succeeded! Searching for generated APK...")
    apk_path = _find_latest_apk(p_root)
    if not apk_path:
        log_error(f"❌ [Server] No APK file found in {p_root} after successful build")
        await safe_send(websocket, {
            "type": "apk_build_error",
            "message": "Build succeeded but no APK file was found on disk."
        })
        return

    file_size = apk_path.stat().st_size
    file_name = apk_path.name
    log_success(f"📦 [Server] Selected APK: {apk_path} ({file_size} bytes, {round(file_size/(1024*1024), 2)} MB)")
    update_apk_build_status_file(
        building=False,
        stage="done",
        progress=1.0,
        message=f"APK built successfully: {file_name}",
        success=True,
        file_name=file_name,
        file_path=str(apk_path)
    )

    await _stream_apk_to_client(websocket, apk_path)
    return



HANDLERS = {
    "get_apk_build_status": handle_get_apk_build_status,
    "fetch_existing_apk": handle_fetch_existing_apk,
    "resume_apk": handle_resume_apk,
    "build_and_send_apk": handle_build_and_send_apk,
}
