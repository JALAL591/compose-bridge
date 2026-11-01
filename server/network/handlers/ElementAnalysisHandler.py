# -*- coding: utf-8 -*-
"""
معالج رسائل تحليل عناصر واجهة Compose وشجرة الـ AST والتوكنز المرتبطة بها.
Handles element range analysis, AST tree queries, and token identification.
"""

import json
from pathlib import Path
from websockets.server import WebSocketServerProtocol

from analysis.ast_scope_resolver import analyze_element_range
from network.ws_server import (
    safe_send,
    log_info,
    log_error,
    log_send,
    PROJECT_ROOT,
)

async def handle_theme_tokens(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """استرجاع قائمة توكنز الثيم المتاحة في المشروع."""
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


async def handle_identify_token(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تحديد التوكن المطابق لقيمة لون أو بعد محدد."""
    hex_value = message.get("hex", "")
    idx = theme_indexer.get_index()
    token = idx.find_token_by_color(hex_value)
    await safe_send(websocket, {
        "type": "identify_token_response",
        "hex": hex_value,
        "token": token,
    })
    log_send(f"identify_token_response: {hex_value} -> {token}")
    return

# ---------------------------------------------------------
# ⭐ analyze_element_with_tree — مع children
# ---------------------------------------------------------


async def handle_analyze_element_with_tree(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تحليل عنصر الواجهة واستخراج سياق الـ AST وشجرة العناصر المحيطة به."""
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
    parent_file = message.get("parent_file")
    parent_line = message.get("parent_line")

    def _is_internal_lib(f: str) -> bool:
        if not f:
            return True
        fl = f.lower()
        return (
            "androidx" in fl or
            f.endswith("Text.kt") or
            f.endswith("BasicText.kt") or
            "lazylist" in fl or
            "foundation" in fl or
            "compose.ui" in fl or
            "compose.material" in fl
        )

    if _is_internal_lib(actual_file):
        if parent_file and not _is_internal_lib(parent_file):
            actual_file = parent_file
            actual_line = parent_line or line_number
        elif tree and isinstance(tree, list):
            for node in tree:
                if isinstance(node, dict):
                    sf = node.get("sourceFile")
                    if sf and not _is_internal_lib(sf):
                        actual_file = sf
                        actual_line = node.get("line", line_number)
                        break

    # استخرج التحليل
    parent_file = message.get("parent_file")
    parent_line = message.get("parent_line")
    req_text_val = message.get("text_value")
    req_text_ref = message.get("text_reference")

    result = analyze_element_range(
        actual_file, actual_line, utf16_offset, utf16_length, tree=tree,
        project_root=Path(PROJECT_ROOT) if PROJECT_ROOT else None,
        runtime_text_hint=req_text_val,
        parent_line=parent_line,
    )

    if parent_file and parent_line:
        try:
            parent_result = analyze_element_range(
                parent_file, parent_line, 0, 0,
                project_root=Path(PROJECT_ROOT) if PROJECT_ROOT else None,
                runtime_text_hint=req_text_val,
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

            # 3. Merge parent texts (e.g. AdaptiveActionCard parameters)
            existing_texts = {t.get("ref_key") or t.get("text") for t in result.get("texts", []) if isinstance(t, dict)}
            for pt in parent_result.get("texts", []):
                t_key = pt.get("ref_key") or pt.get("text")
                if t_key and t_key not in existing_texts:
                    existing_texts.add(t_key)
                    result.setdefault("texts", []).append(pt)

            # 4. Adopt parent composable_name if result is Element or Text
            p_cname = parent_result.get("composable_name")
            if p_cname and p_cname not in ["Element", "Text", "BasicText", "Column", "Row"]:
                if result.get("composable_name") in ["Element", "Text", "BasicText", "Column", "Row", None]:
                    result["composable_name"] = p_cname
        except Exception as e:
            log_error(f"Failed to aggregate parent properties: {e}")

    # If evaluated runtime text was captured from device screen, prefer it over raw template code
    if req_text_val:
        if not result.get("texts"):
            result["texts"] = [{
                "text": req_text_val,
                "file": actual_file,
                "line": actual_line,
                "is_resource_or_ref": bool(req_text_ref and str(req_text_ref).startswith("AppStrings.")),
                "ref_key": req_text_ref,
            }]
        else:
            for t in result.get("texts", []):
                # If extracted text has $ or { (template code), replace with real evaluated screen text
                if "$" in t.get("text", "") or "{" in t.get("text", ""):
                    t["text"] = req_text_val
                if req_text_ref and not t.get("ref_key"):
                    t["ref_key"] = req_text_ref
                    t["is_resource_or_ref"] = True

    # ⭐ Auto-resolve ref_key from AppStrings.kt and guarantee real text string
    p_root = Path(PROJECT_ROOT) if PROJECT_ROOT else None
    if p_root:
        from core.source_analyzer import _find_ref_in_app_strings
        from analysis.text_ref_analyzer import _resolve_app_strings_value
        for t in result.get("texts", []):
            # 1. Resolve ref_key if missing
            if not t.get("ref_key"):
                search_str = t.get("text") or req_text_val
                found_ref = _find_ref_in_app_strings(p_root, search_str)
                if found_ref:
                    t["ref_key"] = found_ref
                    t["is_resource_or_ref"] = True
                    if not t.get("property") or t.get("property") == "text":
                        t["property"] = found_ref
                    log_info(f"[ANALYZE] Auto-resolved ref_key: '{search_str}' -> {found_ref}")

            # 2. Guarantee that t["text"] contains human-readable string, NEVER raw 'AppStrings.xxx'
            current_t = t.get("text", "")
            if not current_t or current_t.startswith("AppStrings."):
                ref_to_use = t.get("ref_key") or current_t
                resolved_human_text = _resolve_app_strings_value(p_root, ref_to_use, req_text_val)
                if resolved_human_text:
                    t["text"] = resolved_human_text
                elif req_text_val and not req_text_val.startswith("AppStrings."):
                    t["text"] = req_text_val

    target_file = result.get("source_file", actual_file)

    # ⭐ أضف tokens مقترحة حسب الملف
    if "WelcomeHeader.kt" in target_file or target_file.endswith("WelcomeHeader.kt"):
        result["suggested_tokens"] = [
            {"name": "cardHeight", "default": 100.0},
            {"name": "cardCorner", "default": 20.0},
            {"name": "cardBorder", "default": 2.0},
            {"name": "cardIcon", "default": 60.0},
        ]

    # Preserve all colors, dimensions, and texts across all modes for seamless multi-mode inspection

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

    log_send(f"analyze_element_with_tree_response: {target_file}:{actual_line} (host: {source_file}:{line_number}) -> {len(tree)} children (req_id={request_id})")
    return

# ---------------------------------------------------------
# ⭐ analyze_element — يحلل عنصراً بناءً على مصدره
# ---------------------------------------------------------


async def handle_analyze_element(websocket: WebSocketServerProtocol, message: dict, raw: str) -> None:
    """تحليل عنصر الواجهة ومطابقته مع توكنز التصميم."""
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

    log_send(f"analyze_element_response: {source_file}:{line_number} -> "
             f"{len(result.get('tokens_used', []))} tokens, "
             f"{len(result.get('dimensions', []))} dims, "
             f"{len(result.get('font_sizes', []))} sizes "
             f"(exact={result.get('used_exact_range', False)})")
    return

# ---------------------------------------------------------
# ⭐ global_color_edit — Focus Mode: تعديل الكل لجميع occurrences
# ---------------------------------------------------------


HANDLERS = {
    "theme_tokens": handle_theme_tokens,
    "identify_token": handle_identify_token,
    "analyze_element_with_tree": handle_analyze_element_with_tree,
    "analyze_element": handle_analyze_element,
}
