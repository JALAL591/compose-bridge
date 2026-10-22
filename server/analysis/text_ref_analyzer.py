# -*- coding: utf-8 -*-
"""
Text reference and AppStrings analysis module.
Resolves UI string literals, refKey mappings, and parent Composable identifiers.
"""

import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Set, Any

try:
    from core.project_root import get_project_root
    PROJECT_ROOT = get_project_root()
except Exception:
    PROJECT_ROOT = Path(os.environ.get("COMPOSEBRIDGE_ROOT", "."))

from .ast_scope_resolver import (
    _find_enclosing_function_or_class,
    _find_file,
)

def _resolve_app_strings_value(project_root: Optional[Path], ref_key: str, runtime_hint: Optional[str] = None) -> Optional[str]:
    """
    Resolves AppStrings reference (e.g. AppStrings.Dashboard.syncTitle or AppStrings.Actions.scheduleTitle)
    to its actual string value.
    Supports:
    - Single pattern: val syncTitle @Composable get() = "المزامنة مع الإدارة"
    - If/else pattern: val selectClass @Composable get() = if (Terminology.isUni) "..." else "..."
    - BridgeTextRegistry wrappers: BridgeTextRegistry.getText("...", "...")
    - Dynamic fallbacks and runtime_hint fallback
    """
    try:
        from core.project_root import get_project_root
        effective_root = project_root or get_project_root()

        candidates = []
        if effective_root and effective_root.exists():
            candidates = list(effective_root.rglob("AppStrings.kt"))
            candidates = [c for c in candidates if "build" not in str(c) and ".composebridge" not in str(c) and ".bak" not in str(c)]

        if not candidates:
            # Check common directories
            for base in [Path.cwd(), Path.cwd().parent]:
                if base.exists():
                    c_list = [c for c in base.rglob("AppStrings.kt") if "build" not in str(c) and ".composebridge" not in str(c) and ".bak" not in str(c)]
                    if c_list:
                        candidates = c_list
                        break

        if not candidates:
            if runtime_hint and runtime_hint.strip() and not runtime_hint.startswith("AppStrings."):
                return runtime_hint.strip()
            return None

        # Search across candidates
        for target_file in candidates:
            text = target_file.read_text(encoding="utf-8", errors="ignore")
            parts = ref_key.split(".")
            var_name = parts[-1]
            object_name = parts[-2] if len(parts) >= 2 and parts[-2] != "AppStrings" else None

            lines = text.splitlines()
            in_target_obj = object_name is None
            matched_line = None

            for line in lines:
                if object_name and re.search(rf'\bobject\s+{re.escape(object_name)}\b', line):
                    in_target_obj = True
                    continue
                elif in_target_obj and object_name and re.search(r'\bobject\s+[a-zA-Z0-9_]+', line) and not re.search(rf'\bobject\s+{re.escape(object_name)}\b', line):
                    # nested object or sibling object: check if it's the right line anyway
                    pass

                if in_target_obj and re.search(rf'\bval\s+{re.escape(var_name)}\b', line):
                    matched_line = line
                    break

            # Fallback 1: search anywhere in file for val <var_name>
            if not matched_line:
                for line in lines:
                    if re.search(rf'\bval\s+{re.escape(var_name)}\b', line):
                        matched_line = line
                        break

            # Fallback 2: search by runtime_hint if provided
            if not matched_line and runtime_hint and runtime_hint.strip() and not runtime_hint.startswith("AppStrings."):
                for line in lines:
                    if f'"{runtime_hint.strip()}"' in line:
                        matched_line = line
                        break

            if matched_line:
                m_bridge = re.search(r'BridgeTextRegistry\.getText\s*\(\s*"[^"]+"\s*,\s*"([^"\\]*(?:\\.[^"\\]*)*)"\s*\)', matched_line)
                if m_bridge:
                    return m_bridge.group(1).replace('\\"', '"').replace('\\\\', '\\')

                quotes = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', matched_line)
                if quotes:
                    filtered_quotes = [q for q in quotes if not q.startswith("AppStrings.")] or quotes

                    # 1. If/else pattern: prefer the else branch if present
                    m_else = re.search(r'else\s+"([^"\\]*(?:\\.[^"\\]*)*)"', matched_line)
                    if m_else:
                        return m_else.group(1).replace('\\"', '"').replace('\\\\', '\\')

                    # 2. Single pattern or default: extract the value between the last quotes in the line
                    return filtered_quotes[-1].replace('\\"', '"').replace('\\\\', '\\')

    except Exception as e:
        pass

    if runtime_hint and runtime_hint.strip() and not runtime_hint.startswith("AppStrings."):
        return runtime_hint.strip()

    return None

def _find_ref_in_app_strings(project_root: Path, text_value: str) -> Optional[str]:
    """Finds matching AppStrings reference for a given text value by searching AppStrings.kt."""
    if not text_value or len(text_value.strip()) < 2:
        return None
    val_clean = text_value.strip()
    try:
        candidates = list(project_root.rglob("AppStrings.kt"))
        candidates = [c for c in candidates if "build" not in str(c) and ".composebridge" not in str(c)]
        if not candidates:
            return None
        content = candidates[0].read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()

        stack = []
        best_sub = None
        best_sub_len = 0

        for line in lines:
            obj_m = re.search(r'\bobject\s+([a-zA-Z0-9_]+)\b', line)
            if obj_m:
                stack.append((obj_m.group(1), line.count('{') - line.count('}')))
            else:
                brace_delta = line.count('{') - line.count('}')
                if brace_delta != 0 and stack:
                    name, b_count = stack[-1]
                    b_count += brace_delta
                    if b_count <= 0:
                        stack.pop()
                    else:
                        stack[-1] = (name, b_count)

            val_m = re.search(r'\bval\s+([a-zA-Z0-9_]+)\b', line)
            if val_m and '"' in line:
                prop_name = val_m.group(1)
                quotes = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', line)
                filtered = [q for q in quotes if not q.startswith("AppStrings.")] or quotes
                obj_path = [s[0] for s in stack if s[0] != "AppStrings"]
                full_key = f"AppStrings.{'.'.join(obj_path + [prop_name])}"

                for q in filtered:
                    if q == val_clean:
                        return full_key
                    if q and (q in val_clean or val_clean in q) and len(q) >= 3:
                        if len(q) > best_sub_len:
                            best_sub_len = len(q)
                            best_sub = full_key
        return best_sub
    except Exception:
        return None


def _detect_composable_name(search_scope: str, fallback_line_content: str = "", full_content: str = "", line_number: int = 0) -> str:
    """Detects Composable name of the current scope or enclosing function/class."""
    # 1. Composable function signature: fun QuickAccessCard(...)
    fun_m = re.search(r'\bfun\s+([A-Z]\w+)\s*\(', search_scope)
    if fun_m:
        return fun_m.group(1)

    # 2. Main Composable calls: Card(, Button(, Surface(, Box(, etc.
    call_m = re.search(r'\b([A-Z]\w+Card|[A-Z]\w+Widget|[A-Z]\w+Item|[A-Z]\w+Button|[A-Z]\w+Bar|[A-Z]\w+Header|Card|Surface|Button)\s*\(', search_scope)
    if call_m:
        return call_m.group(1)

    # 3. Fallback from any Composable call
    any_m = re.search(r'\b([A-Z]\w+)\s*\(', fallback_line_content or search_scope)
    if any_m and any_m.group(1) not in {'Color', 'Modifier', 'Dp', 'TextStyle', 'Alignment', 'Arrangement'}:
        candidate = any_m.group(1)
        if candidate not in {'Text', 'BasicText', 'Column', 'Row', 'Spacer', 'Box'} or not full_content:
            return candidate

    # 4. Enclosing @Composable function or class in full_content
    if full_content and line_number > 0:
        enclosing = _find_enclosing_function_or_class(full_content, line_number)
        if enclosing != "Element":
            return enclosing

    return any_m.group(1) if (any_m and any_m.group(1) not in {'Color', 'Modifier', 'Dp', 'TextStyle', 'Alignment', 'Arrangement'}) else "Element"

