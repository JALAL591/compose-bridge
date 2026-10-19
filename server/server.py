"""
ComposeBridge — Python Bridge Server (Phase 3: Message Hub)

- يستقبل اتصالات من الهاتف (Agent) ومن أدوات الاختبار
- يمرّر الرسائل من أي عميل إلى جميع العملاء الآخرين
- يمكّن Python من التحكم في UI الهاتف فوراً
"""

import asyncio
import json
import sys

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import re
import secrets
import hmac
from pathlib import Path
from typing import Set, Tuple, Optional, Dict

import websockets
from websockets.server import WebSocketServerProtocol

sys.path.insert(0, str(Path(__file__).parent))

from core.models import EditRequest, EditResponse, ErrorCode
from core import theme_indexer
from core.state_manager import StateManager


# ============================================================
# الإعدادات
# ============================================================

HOST = "0.0.0.0"
PORT = 8711

from core.project_root import get_project_root

PROJECT_ROOT = get_project_root()
print(f"[ROOT] Project root: {PROJECT_ROOT}")
STATE_MANAGER = StateManager(PROJECT_ROOT)
STATE_MANAGER.init()

# ⚠️ TEMPORARY — fixed token for local testing
# TODO: replace with QR code or env var before release
AUTH_TOKEN = "test-token-local-dev"
print(f"[AUTH] Token: {AUTH_TOKEN} (FIXED for testing)")


# ============================================================
# عملاء متصلون
# ============================================================

CONNECTED_CLIENTS: Set[WebSocketServerProtocol] = set()
AUTHENTICATED_CLIENTS: Set[WebSocketServerProtocol] = set()


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


# ============================================================
# Safe Send
# ============================================================

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


def _validate_kotlin_line(line: str) -> Tuple[bool, str]:
    """فحص أساسي — لا تحقق كامل."""
    # توازن الأقواس
    if line.count("(") != line.count(")"):
        return False, "Unbalanced parens"
    # لا تكرار modifier
    if line.count("modifier =") > 1:
        return False, "Duplicate modifier="
    # لا تكرار BridgeDimensionRegistry.get
    if line.count("BridgeDimensionRegistry.get") > 1:
        return False, "Duplicate BridgeDimensionRegistry.get"
    return True, ""


def _clean_duplicate_modifier(line: str) -> str:
    """إزالة السطر الأول المكرر."""
    # إذا السطر يحتوي على "modifier = X modifier = Y" في سطر واحد
    # احذف الجزء الأول
    pattern = r'(modifier\s*=\s*[^\n]+?)\s+modifier\s*=\s*([^\n]+)'
    match = re.search(pattern, line)
    if match:
        return re.sub(pattern, f'modifier = {match.group(2)}', line)
    return line


def _ensure_bridge_dimension_registry_import(
    file_path: Path,
    project_root: Path,
) -> Tuple[bool, int]:
    """
    تأكد من وجود import BridgeDimensionRegistry.
    Returns (was_added, line_number).
    """
    content = file_path.read_text(encoding="utf-8")
    
    import_stmt = "import com.composebridge.agent.BridgeDimensionRegistry"
    
    # ⭐ افحص إذا موجود
    if import_stmt in content:
        return False, -1
    
    # ⭐ لا يوجد — أضف
    lines = content.splitlines()
    
    # ابحث عن آخر import أو package
    last_import_idx = -1
    package_idx = -1
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('package '):
            package_idx = i
        elif stripped.startswith('import '):
            last_import_idx = i
    
    # ⭐ الموقع الصحيح للإدراج
    if last_import_idx >= 0:
        insert_idx = last_import_idx + 1
        lines.insert(insert_idx, import_stmt)
        inserted_line = insert_idx + 1
    elif package_idx >= 0:
        insert_idx = package_idx + 1
        lines.insert(insert_idx, "")
        lines.insert(insert_idx + 1, import_stmt)
        inserted_line = insert_idx + 2
    else:
        insert_idx = 0
        lines.insert(insert_idx, import_stmt)
        inserted_line = insert_idx + 1
    
    new_content = "\n".join(lines)
    if not new_content.endswith("\n"):
        new_content += "\n"
    
    file_path.write_text(new_content, encoding="utf-8")
    
    return True, inserted_line


def _clean_duplicate_imports(file_path: Path) -> int:
    """إزالة imports مكررة."""
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    
    seen_imports = set()
    new_lines = []
    removed = 0
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('import '):
            if stripped in seen_imports:
                removed += 1
                continue
            seen_imports.add(stripped)
        new_lines.append(line)
    
    if removed > 0:
        file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    
    return removed


def _validate_modified_file(
    file_path: Path,
    content: str,
) -> Tuple[bool, str]:
    """فحص Kotlin syntax بسيط."""
    
    # ⭐ 1. توازن الأقواس
    if content.count("{") != content.count("}"):
        return False, "Unbalanced braces"
    if content.count("(") != content.count(")"):
        return False, "Unbalanced parens"
    
    # ⭐ 2. إذا فيه BridgeDimensionRegistry.get → يجب import
    if "BridgeDimensionRegistry.get" in content:
        if "import com.composebridge.agent.BridgeDimensionRegistry" not in content:
            return False, "Missing BridgeDimensionRegistry import"
    
    return True, ""


def _apply_dimension_edit(edit: dict, project_root: Path) -> dict:
    """Apply dimension edit at specific line with PatternJournal recording."""
    from core.pattern_journal import PatternJournal
    import re
    
    file_rel = edit.get("file")
    line = edit.get("line", 0)
    property_name = edit.get("property", "")
    old_value = str(edit.get("old_value", "")).replace(".dp", "").replace(".sp", "").strip()
    new_value = str(edit.get("new_value", "")).replace(".dp", "").replace(".sp", "").strip()
    
    if not file_rel or line < 1:
        return {"success": False, "error": "Invalid file/line"}
    
    file_path = project_root / file_rel
    if not file_path.exists():
        matches = [m for m in project_root.rglob(Path(file_rel).name) 
                   if "build" not in str(m) and ".composebridge" not in str(m) 
                   and "backup" not in str(m).lower()]
        if not matches:
            return {"success": False, "error": f"File not found: {file_rel}"}
        file_path = matches[0]
    
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        if line > len(lines):
            return {"success": False, "error": f"Line {line} out of range"}
        
        target_idx = line - 1
        
        try:
            num = float(new_value)
            new_val_str = str(int(num)) if num.is_integer() else str(num)
        except Exception:
            new_val_str = new_value

        from core.source_analyzer import _normalize_dim_value
        old_val_variants = _normalize_dim_value(old_value)
        is_ternary = edit.get("is_ternary", False)
        registry_key = str(edit.get("registry_key", "")).strip()
        kind = edit.get("dimension_kind", "dp")

        # 0. Check if target_idx itself is a match
        found_idx = -1
        exact_line = lines[target_idx]
        has_val = any(re.search(rf'\b{re.escape(v)}\.(?:dp|sp)\b', exact_line) for v in old_val_variants)
        has_prop = (property_name in exact_line) if property_name else False

        if has_val:
            found_idx = target_idx
        elif has_prop and ("BridgeDimensionRegistry" in exact_line or re.search(r'\d+(?:\.\d+)?\.(?:dp|sp)\b', exact_line)):
            found_idx = target_idx

        # Search range ±5 lines if not directly at target_idx
        if found_idx < 0:
            search_range = range(
                max(0, target_idx - 5),
                min(len(lines), target_idx + 6),
            )
            # 1. First: line that matches property and old value
            for i in search_range:
                content_line = lines[i]
                prop_matches = False
                if property_name == "padding_horizontal" and "horizontal" in content_line:
                    prop_matches = True
                elif property_name == "padding_vertical" and "vertical" in content_line:
                    prop_matches = True
                elif property_name and property_name in content_line:
                    prop_matches = True
                
                if prop_matches:
                    for variant in old_val_variants:
                        if re.search(rf'\b{re.escape(variant)}\.(?:dp|sp)\b', content_line):
                            found_idx = i
                            break
                    if found_idx >= 0:
                        break

            # 2. Second: line that matches property and BridgeDimensionRegistry
            if found_idx < 0:
                for i in search_range:
                    content_line = lines[i]
                    if property_name and property_name in content_line and "BridgeDimensionRegistry" in content_line:
                        found_idx = i
                        break

            # 3. Third: line that matches old value with dp/sp
            if found_idx < 0:
                for i in search_range:
                    content_line = lines[i]
                    for variant in old_val_variants:
                        if re.search(rf'\b{re.escape(variant)}\.(?:dp|sp)\b', content_line):
                            found_idx = i
                            break
                    if found_idx >= 0:
                        break

        if found_idx < 0:
            return {
                "success": False,
                "error": f"Could not find line for {property_name}={old_value}",
                "search_range": f"{target_idx-5}..{target_idx+5}",
            }

        target_idx = found_idx
        actual_line = target_idx + 1
        old_line = lines[target_idx]
        new_line = old_line

        replaced = False

        # If already wrapped in registry with this key, update value inside
        if registry_key and f'BridgeDimensionRegistry.get("{registry_key}"' in old_line:
            new_line = re.sub(
                rf'BridgeDimensionRegistry\.get\(\s*"{re.escape(registry_key)}"\s*,\s*[^)]+\)',
                f'BridgeDimensionRegistry.get("{registry_key}", {new_val_str}.{kind})',
                old_line,
                count=1,
            )
            replaced = new_line != old_line

        # ⭐ 1. حاول استبدال X.dp
        if not replaced:
            for variant in old_val_variants:
                pattern = rf'(\b{re.escape(variant)})(\.(?:dp|sp)\b)'
                if re.search(pattern, old_line):
                    repl_str = (
                        f'BridgeDimensionRegistry.get("{registry_key}", {new_val_str}.{kind})'
                        if registry_key
                        else f'{new_val_str}.{kind}'
                    )
                    new_line = re.sub(pattern, repl_str, old_line, count=1)
                    replaced = True
                    break

        # ⭐ 2. إذا لم يُستبدل → ابحث عن النمط الكامل
        if not replaced:
            pattern = rf'(\.\w+\s*\(\s*|\b\w+\s*=\s*)(\d+(?:\.\d+)?\.(?:dp|sp))(\s*\)?)'
            def _repl(m):
                prefix = m.group(1)
                suffix = m.group(3)
                val = (
                    f'BridgeDimensionRegistry.get("{registry_key}", {new_val_str}.{kind})'
                    if registry_key
                    else f'{new_val_str}.{kind}'
                )
                return f'{prefix}{val}{suffix}'

            new_line = re.sub(pattern, _repl, old_line, count=1)
            replaced = new_line != old_line

        if not replaced:
            return {
                "success": False,
                "error": f"Could not replace in line {line}",
                "line_content": old_line.strip(),
            }

        # Clean duplicate modifier in line
        new_line = _clean_duplicate_modifier(new_line)

        # ⭐ 3. تحقق: لا يوجد تكرار
        count_get = new_line.count('BridgeDimensionRegistry.get')
        if count_get > 1:
            return {
                "success": False,
                "error": "Multiple BridgeDimensionRegistry.get in one line",
                "new_line": new_line,
            }

        # ⭐ 4. تحقق: السطر الجديد صالح (لا يحتوي على old_value بدون BridgeDimensionRegistry)
        is_ternary_line = "if" in new_line and "else" in new_line
        if not is_ternary_line:
            for variant in old_val_variants:
                if re.search(rf'\b{re.escape(variant)}\.(?:dp|sp)\b', new_line):
                    return {
                        "success": False,
                        "error": "Old value still present in new line",
                        "old_value": old_value,
                        "new_line": new_line,
                    }

        # ⭐ 5. Validate Kotlin line before writing
        is_valid, error = _validate_kotlin_line(new_line)
        if not is_valid:
            return {
                "success": False,
                "error": f"Invalid Kotlin: {error}",
                "new_line": new_line,
            }

        # Clean up any leftover duplicate modifier line if previous line is duplicated
        if target_idx > 0 and "modifier =" in lines[target_idx - 1] and "modifier =" in new_line:
            prev_line = lines[target_idx - 1].strip()
            if "BridgeDimensionRegistry" not in prev_line and "modifier = Modifier.size" in prev_line:
                lines.pop(target_idx - 1)
                target_idx -= 1
                actual_line = target_idx + 1

        lines[target_idx] = new_line
        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        journal = PatternJournal(project_root)
        try:
            rel_file = str(file_path.relative_to(project_root)).replace("\\", "/")
        except Exception:
            rel_file = file_rel

        journal.record_change(
            file=rel_file,
            line=actual_line,
            old_line=old_line,
            new_line=new_line,
            pattern_id=f"dimension_{property_name}_{actual_line}",
        )

        # ⭐ تأكد من import
        was_added, import_line = _ensure_bridge_dimension_registry_import(
            file_path=file_path,
            project_root=project_root,
        )

        if was_added:
            # ⭐ سجّل في Journal
            journal.record_change(
                file=rel_file,
                line=import_line,
                old_line="",
                new_line="import com.composebridge.agent.BridgeDimensionRegistry",
                pattern_id=f"import_bridge_dim_{registry_key}",
            )
            log_info(f"[DIMENSION] Added BridgeDimensionRegistry import to {file_path.name}")

        _clean_duplicate_imports(file_path)

        final_content = file_path.read_text(encoding="utf-8")
        is_file_valid, file_err = _validate_modified_file(file_path, final_content)
        if not is_file_valid:
            log_error(f"[DIMENSION] File validation warning: {file_err}")

        return {
            "success": True,
            "file": rel_file,
            "line": actual_line,
            "old": old_value,
            "new": new_val_str,
            "property": property_name,
            "registry_key": registry_key,
            "wrapped_in_registry": bool(registry_key),
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()[:500],
        }


# ============================================================
# Message handling
# ============================================================

async def handle_message(websocket: WebSocketServerProtocol, raw: str) -> None:
    """يعالج رسالة واحدة."""
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

    # ---------------------------------------------------------
    # Auth check FIRST
    # ---------------------------------------------------------
    if msg_type == "auth":
        client_token = message.get("token", "")
        if not hmac.compare_digest(client_token, AUTH_TOKEN):
            log_error(f"Auth failed: {websocket.remote_address}")
            await websocket.close(4001, "Unauthorized")
            return
        AUTHENTICATED_CLIENTS.add(websocket)
        await safe_send(websocket, {"type": "auth_ok"})
        log_success(f"Client authenticated: {websocket.remote_address}")
        return

    if websocket not in AUTHENTICATED_CLIENTS:
        remote_ip = websocket.remote_address[0] if websocket.remote_address else ""
        is_local = remote_ip in ("127.0.0.1", "localhost", "::1")
        if is_local or AUTH_TOKEN == "test-token-local-dev":
            AUTHENTICATED_CLIENTS.add(websocket)
            log_info(f"Auto-authenticated local client ({remote_ip}) for {msg_type}")
        else:
            log_error(f"Unauthenticated request: {msg_type}")
            await websocket.close(4001, "Auth required")
            return

    # ---------------------------------------------------------
    # Hello / Handshake
    # ---------------------------------------------------------
    if msg_type == "hello":
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
    if msg_type == "ping":
        await safe_send(websocket, {"type": "pong"})
        return

    # ---------------------------------------------------------
    # ⭐ state_update — يُمرَّر للعملاء الآخرين (الهاتف)
    # ---------------------------------------------------------
    if msg_type == "state_update":
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
                    log_success(f"📁 Saved: Updated {token_name}: → {value}")
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
    # MCP State Update — من mcp_server.py
    # ---------------------------------------------------------
    if msg_type == "mcp_state_update":
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
    if msg_type == "batch_update":
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
    if msg_type == "reset_state":
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
    if msg_type == "theme_tokens":
        idx = theme_indexer.get_index()
        await safe_send(websocket, {
            "type": "theme_tokens_response",
            "tokens": idx.get_all_tokens(),
            "categories": idx.get_tokens_by_category(),
        })
        log_send(f"theme_tokens_response ({len(idx.tokens)} tokens)")
        return

    # ---------------------------------------------------------
    # ⭐ identify_token — يبحث عن token بقيمة لون
    # ---------------------------------------------------------
    if msg_type == "identify_token":
        hex_value = message.get("hex", "")
        idx = theme_indexer.get_index()
        token = idx.find_token_by_color(hex_value)
        await safe_send(websocket, {
            "type": "identify_token_response",
            "hex": hex_value,
            "token": token,
        })
        log_send(f"identify_token_response: {hex_value} → {token}")
        return

    # ---------------------------------------------------------
    # ⭐ analyze_element_with_tree — مع children
    # ---------------------------------------------------------
    if msg_type == "analyze_element_with_tree":
        from core.source_analyzer import analyze_element_range
        import json as json_lib

        source_file = message.get("file", "")
        line_number = message.get("line", 0)
        utf16_offset = message.get("offset", 0)
        utf16_length = message.get("length", 0)
        tree_raw = message.get("tree", "[]")
        request_id = message.get("request_id", 0)
        mode = str(message.get("mode", "")).upper()

        # حاول تحليل tree (قد يكون string أو list)
        try:
            if isinstance(tree_raw, str):
                tree = json_lib.loads(tree_raw)
            else:
                tree = tree_raw
        except Exception as e:
            log_error(f"Tree parse failed: {e}")
            tree = []

        # ⭐ فحص ما إذا كان العنصر الحقيقي موجوداً في ملف مختلف (مثل Widget في Screen)
        actual_file = source_file
        actual_line = line_number
        if tree and isinstance(tree, list):
            for node in tree:
                if isinstance(node, dict):
                    sf = node.get("sourceFile")
                    if sf and sf != source_file and not sf.endswith(source_file):
                        actual_file = sf
                        actual_line = node.get("line", line_number)
                        break

        # استخرج التحليل
        result = analyze_element_range(
            actual_file, actual_line, utf16_offset, utf16_length, tree=tree,
            project_root=Path(PROJECT_ROOT) if PROJECT_ROOT else None
        )

        parent_file = message.get("parent_file")
        parent_line = message.get("parent_line")
        if parent_file and parent_line:
            try:
                parent_result = analyze_element_range(
                    parent_file, parent_line, 0, 0,
                    project_root=Path(PROJECT_ROOT) if PROJECT_ROOT else None,
                )
                # 1. Merge parent colors (container, background, surface)
                existing_colors = {c.get("color") for c in result.get("colors", []) if isinstance(c, dict)}
                for pc in parent_result.get("colors", []):
                    if isinstance(pc, dict) and pc.get("color") not in existing_colors:
                        existing_colors.add(pc.get("color"))
                        result.setdefault("colors", []).append(pc)

                # 2. Merge parent dimensions (padding, size, corner, etc.)
                existing_dims = {str(d.get("name", "")) + str(d.get("line", "")) for d in result.get("dimension_details", []) if isinstance(d, dict)}
                for pd in parent_result.get("dimension_details", []):
                    key = str(pd.get("name", "")) + str(pd.get("line", ""))
                    if key not in existing_dims:
                        existing_dims.add(key)
                        result.setdefault("dimension_details", []).append(pd)
                        if pd.get("value") and pd.get("value") not in result.get("dimensions", []):
                            result.setdefault("dimensions", []).append(pd.get("value"))
            except Exception as e:
                log_error(f"Failed to aggregate parent properties: {e}")

        req_text_val = message.get("text_value")
        req_text_ref = message.get("text_reference")
        if req_text_val:
            if result.get("texts"):
                for entry in result["texts"]:
                    if entry.get("is_resource_or_ref") or entry.get("text", "").startswith("AppStrings."):
                        entry["text"] = req_text_val
            else:
                result.setdefault("texts", []).append({
                    "text": req_text_val,
                    "file": actual_file,
                    "line": actual_line,
                    "is_resource_or_ref": bool(req_text_ref),
                    "ref_key": req_text_ref,
                })

        target_file = result.get("source_file", actual_file)

        # ⭐ أضف tokens مقترحة حسب الملف
        if "WelcomeHeader.kt" in target_file or target_file.endswith("WelcomeHeader.kt"):
            result["suggested_tokens"] = [
                {"name": "cardHeight", "default": 100.0},
                {"name": "cardCorner", "default": 20.0},
                {"name": "cardBorder", "default": 2.0},
                {"name": "cardIcon", "default": 60.0},
            ]

        # Mode-based filtering for payload reduction and speed
        if mode == "COLOR":
            result["dimensions"] = []
            result["dimension_details"] = []
            result["texts"] = []
        elif mode == "DIMENSION":
            result["colors"] = []
            result["texts"] = []
            result["suggested_tokens"] = []
        elif mode == "TEXT":
            result["colors"] = []
            result["dimensions"] = []
            result["dimension_details"] = []
            result["suggested_tokens"] = []

        # أرسل الـ response
        await safe_send(websocket, {
            "type": "analyze_element_response",
            "request_id": request_id,
            "result": result,
            "root": {
                "name": "root",
                "sourceFile": target_file,
                "line": actual_line,
                "utf16Offset": utf16_offset,
                "utf16Length": utf16_length,
                "children": tree,
            },
        })

        log_send(f"analyze_element_with_tree_response: {target_file}:{actual_line} (host: {source_file}:{line_number}) → {len(tree)} children (req_id={request_id})")
        return

    # ---------------------------------------------------------
    # ⭐ analyze_element — يحلل عنصراً بناءً على مصدره
    # ---------------------------------------------------------
    if msg_type == "analyze_element":
        from core.source_analyzer import analyze_element_range
        import json as json_lib

        source_file = message.get("file", "")
        line_number = message.get("line", 0)
        utf16_offset = message.get("offset", 0)
        utf16_length = message.get("length", 0)
        request_id = message.get("request_id", 0)

        result = analyze_element_range(
            source_file,
            line_number,
            utf16_offset,
            utf16_length,
        )

        target_file = result.get("source_file", source_file)

        # ⭐ أضف tokens مقترحة حسب الملف
        if "WelcomeHeader.kt" in target_file or target_file.endswith("WelcomeHeader.kt"):
            result["suggested_tokens"] = [
                {"name": "cardHeight", "default": 100.0},
                {"name": "cardCorner", "default": 20.0},
                {"name": "cardBorder", "default": 2.0},
                {"name": "cardIcon", "default": 60.0},
            ]

        await safe_send(websocket, {
            "type": "analyze_element_response",
            "request_id": request_id,
            "result": result,
            "root": {
                "name": "root",
                "sourceFile": target_file,
                "line": line_number,
                "utf16Offset": utf16_offset,
                "utf16Length": utf16_length,
                "children": [],
            },
        })

        log_send(f"analyze_element_response: {source_file}:{line_number} → "
                 f"{len(result.get('tokens_used', []))} tokens, "
                 f"{len(result.get('dimensions', []))} dims, "
                 f"{len(result.get('font_sizes', []))} sizes "
                 f"(exact={result.get('used_exact_range', False)})")
        return

    # ---------------------------------------------------------
    # ⭐ global_color_edit — Focus Mode: تعديل الكل لجميع occurrences
    # ---------------------------------------------------------
    if msg_type == "global_color_edit":
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
    if msg_type == "split_token":
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
    if msg_type == "batch_edits":
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
                        log_info(f"[DIMENSION] {local_property}: {local_old_value} → {new_val_str} (mode={edit_mode})")
                elif edit_type == "text_edit":
                    from core.state_editor import update_text_in_source
                    file_p = edit.get("file", "")
                    line_num = edit.get("line", 1)
                    old_t = str(edit.get("old_value") or edit.get("old_text", ""))
                    new_t = str(edit.get("new_value") or edit.get("new_text", ""))
                    ref_k = edit.get("ref_key") or edit.get("property")
                    if ref_k == "text":
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
                        log_success(f"[DIMENSION] {local_property}: {local_old_value} → {new_val_str}")
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
                            log_success(f"[UPDATE] Token {token_name}: {local_old_value} → {val}")
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
            await broadcast(json.dumps({
                "type": "refresh_element_request",
            }, ensure_ascii=False))
            log_info(f"[BROADCAST] refresh_element_request")

        log_info(f"[BATCH] Done: {success_count}/{total} successful")
        return

    # ---------------------------------------------------------
    # ⭐ reject_all_files — إلغاء كافة التغييرات وتنظيف الـ Journal
    # ---------------------------------------------------------
    if msg_type == "reject_all_files":
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
    if msg_type == "text_edit":
        file_path = message.get("file", "")
        line_num = message.get("line", 1)
        old_text = message.get("old_text") or message.get("old_value", "")
        new_text = message.get("new_text") or message.get("new_value", "")
        ref_key = message.get("ref_key") or message.get("text_reference") or message.get("property")
        if ref_key == "text":
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
        return

    if msg_type == "dimension_override":
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
    if msg_type == "dimension_reset":
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
    if msg_type == "update_token_default":
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
    if msg_type == "agent_start":
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
    if msg_type == "agent_end":
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
    if msg_type == "queue_status":
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
    if msg_type == "queue_clear":
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
    if msg_type == "user_sync":
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
    if msg_type == "state_info":
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
    if msg_type == "scan_project":
        from core.project_scanner import ProjectScanner
        
        try:
            scanner = ProjectScanner(PROJECT_ROOT)
            report = scanner.scan()
            
            await safe_send(websocket, {
                "type": "scan_project_response",
                "status": "ok",
                "report": report.to_dict(),
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
    if msg_type == "add_token":
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
    if msg_type == "toggle_design_mode":
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
    if msg_type == "reload_theme_index":
        success = theme_indexer.reload_index()
        await safe_send(websocket, {
            "type": "reload_theme_index_response",
            "status": "ok" if success else "error",
            "count": len(theme_indexer.get_index().tokens),
        })
        log_send(f"reload_theme_index_response (success={success})")
        return

    # ---------------------------------------------------------
    # edit_request — من الهاتف
    # ---------------------------------------------------------
    if msg_type == "edit_request":
        await handle_edit_request(websocket, message)
        return

    # ---------------------------------------------------------
    # غير معروف
    # ---------------------------------------------------------
    # ⚠️ لا نرد على error messages (لتجنب الحلقات)
    if msg_type == "error":
        log_error(f"Received error from client: {message.get('message')}")
        return

    # غير معروف - نسجّل فقط بدون رَد
    log_error(f"Unknown message type (no reply): {msg_type}")


async def handle_edit_request(websocket: WebSocketServerProtocol, message: dict) -> None:
    """يعالج طلب تعديل ملف."""
    payload = message.get("payload", {})
    log_info("=" * 50)
    log_info("📥 EDIT REQUEST")
    log_info("=" * 50)
    for k, v in payload.items():
        log_info(f"  {k}: {v}")
    log_info("=" * 50)

    await safe_send(websocket, {
        "type": "edit_response",
        "payload": {
            "requestId": payload.get("requestId", "unknown"),
            "status": "success",
            "note": "Phase 3: receive only",
        }
    })


# ============================================================
# Connection lifecycle
# ============================================================

async def handle_client(websocket: WebSocketServerProtocol) -> None:
    """يتعامل مع عميل واحد."""
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


# ============================================================
# Entry point
# ============================================================

async def main():
    print()
    print(f"{Color.BOLD}{Color.GREEN}{'=' * 55}{Color.END}")
    print(f"{Color.BOLD}{Color.GREEN}  ComposeBridge — Message Hub{Color.END}")
    print(f"{Color.BOLD}{Color.GREEN}{'=' * 55}{Color.END}")
    print(f"  Host:         {HOST}")
    print(f"  Port:         {PORT}")
    print(f"  Project root: {PROJECT_ROOT}")
    print(f"  Mode:         Message Hub (broadcast)")
    print(f"{Color.BOLD}{Color.GREEN}{'=' * 55}{Color.END}")
    print()

    # فهرس Theme Tokens
    theme_indexer.init()
    print(f"[STATE] Loaded: {len(STATE_MANAGER.snapshot.tokens)} tokens")
    print(f"[STATE] Queue: {STATE_MANAGER.queue.count()} edits")
    print(f"[STATE] Agent busy: {STATE_MANAGER.agent_busy}")

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
