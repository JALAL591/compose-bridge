# -*- coding: utf-8 -*-
"""
Text source editor module.
Handles escaping Kotlin string literals, wrapping raw strings, and live text editing in Compose.
Guarded by NEEDS_MANUAL_MAPPING to ensure no edits occur without a centralized string file.
"""

import os
import re
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

try:
    from core.project_root import get_project_root
    PROJECT_ROOT = get_project_root()
except Exception:
    PROJECT_ROOT = Path(os.environ.get("COMPOSEBRIDGE_ROOT", "."))

from common.file_ops import is_ignored_path, acquire_write_lock, _atomic_write_text, _find_registry_file
from core.ast_finder import surgical_edit, validate_kotlin_syntax
from core.pattern_journal import PatternJournal
from .journal_helpers import with_write_lock, _journal_save


def escape_kotlin_string(text: str) -> str:
    """Escapes special characters for safe Kotlin double-quoted strings."""
    if not text:
        return ""
    escaped = text.replace("\\", "\\\\")
    for ch, rep in [('"', '\\"'), ("\n", "\\n"), ("\r", "\\r"), ("\t", "\\t"), ("$", "\\$")]:
        escaped = escaped.replace(ch, rep)
    return escaped


def update_text_in_source(
    file_path: str,
    line: int,
    old_text: str,
    new_text: str,
    ref_key: Optional[str] = None,
    project_root: Optional[Path] = None,
    expected_checksum: Optional[str] = None,
) -> tuple:
    """
    Surgically edits text in Kotlin source code.
    Guarded: Refuses to edit any file unless a centralized string file exists or is mapped.
    """
    from common.file_ops import is_file_dirty_in_ide
    from analysis.universal_scanner import resolve_target_design_file
    import hashlib

    p_root = Path(project_root) if project_root else get_project_root()

    with acquire_write_lock():
        # ⭐ P0 GUARD: Ensure a centralized string file exists (AppStrings.kt / mapped file)
        target_str_file, _ = resolve_target_design_file("string", p_root)
        if not target_str_file or not target_str_file.exists():
            return (
                False,
                "NEEDS_MANUAL_MAPPING: No centralized string file found. Please map a string file using the Discovery tab before editing text.",
                {
                    "error_code": "NEEDS_MANUAL_MAPPING",
                    "token_type": "string",
                }
            )

        target_ref = ref_key
        if not target_ref and old_text and old_text.strip().startswith("AppStrings."):
            target_ref = old_text.strip()

        # Check line in file_path for AppStrings reference if not passed
        if not target_ref and file_path and os.path.exists(file_path):
            try:
                src_lines = Path(file_path).read_text(encoding="utf-8", errors="ignore").splitlines()
                chk_idx = max(0, min(len(src_lines) - 1, line - 1))
                for delta in range(0, 6):
                    for cand_idx in (chk_idx + delta, chk_idx - delta):
                        if 0 <= cand_idx < len(src_lines):
                            m_cand = re.search(r'\b(AppStrings(?:\.[a-zA-Z0-9_]+)+)\b', src_lines[cand_idx])
                            if m_cand:
                                target_ref = m_cand.group(1)
                                break
                    if target_ref:
                        break
            except Exception:
                pass

        # Check if old_text belongs to an AppStrings declaration
        if not target_ref and old_text and target_str_file.exists():
            try:
                s_content = target_str_file.read_text(encoding="utf-8", errors="ignore")
                if f'"{old_text}"' in s_content:
                    for s_line in s_content.splitlines():
                        if f'"{old_text}"' in s_line and "val " in s_line:
                            m_prop = re.search(r'\bval\s+([a-zA-Z0-9_]+)\b', s_line)
                            if m_prop:
                                target_ref = f"AppStrings.{m_prop.group(1)}"
                                break
            except Exception:
                pass

        is_ref = bool(target_ref and target_ref.startswith("AppStrings."))
        escaped_new = escape_kotlin_string(new_text)

        # ----------------------------------------------------
        # الحالة ب: نص مرجعي (Reference في AppStrings.kt أو الملف المعين)
        # ----------------------------------------------------
        if is_ref:
            strings_file = target_str_file
            if is_file_dirty_in_ide(strings_file, p_root):
                return (False, f"الملف '{strings_file.name}' مفتوح في IDE وفيه تعديلات غير محفوظة. احفظ أولاً.", {"error_code": "DIRTY_BUFFER_DETECTED", "file": str(strings_file)})

            with open(strings_file, "r", encoding="utf-8", newline="") as f:
                content = f.read()

            curr_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if expected_checksum and curr_hash != expected_checksum:
                return (False, f"Warning: File '{strings_file.name}' was modified externally.", {"error_code": "EXTERNAL_MODIFICATION_DETECTED", "suggested_action": "confirm_restore", "file": str(strings_file)})

            parts = target_ref.split(".")
            var_name = parts[-1]
            object_name = parts[-2] if len(parts) >= 2 and parts[-2] != "AppStrings" else None

            lines_with_ends = content.splitlines(keepends=True)
            target_idx, old_literal, chosen_m = -1, None, None
            in_target_object = object_name is None

            for idx, line_str in enumerate(lines_with_ends):
                if object_name and re.search(rf'\bobject\s+{re.escape(object_name)}\b', line_str):
                    in_target_object = True
                elif in_target_object and object_name and re.search(r'\bobject\s+\w+', line_str) and not re.search(rf'\bobject\s+{re.escape(object_name)}\b', line_str):
                    in_target_object = False

                if in_target_object and re.search(rf'\bval\s+{re.escape(var_name)}\b', line_str):
                    all_matches = list(re.finditer(r'"([^"\\]*(?:\\.[^"\\]*)*)"', line_str))
                    matches = [m for m in all_matches if not m.group(1).startswith("AppStrings.")] or all_matches
                    if matches:
                        if len(matches) == 1:
                            chosen_m = matches[0]
                        else:
                            if old_text:
                                for m in matches:
                                    if m.group(1) == old_text or old_text in m.group(1):
                                        chosen_m = m
                                        break
                            if not chosen_m:
                                chosen_m = matches[-1]
                        target_idx = idx
                        old_literal = chosen_m.group(1)
                        break

            # Fallbacks
            if target_idx == -1 or old_literal is None:
                for idx, line_str in enumerate(lines_with_ends):
                    if re.search(rf'\bval\s+{re.escape(var_name)}\b', line_str) or (old_text and old_text in line_str):
                        all_matches = list(re.finditer(r'"([^"\\]*(?:\\.[^"\\]*)*)"', line_str))
                        matches = [m for m in all_matches if not m.group(1).startswith("AppStrings.")] or all_matches
                        if matches:
                            target_idx = idx
                            chosen_m = matches[0] if len(matches) == 1 else matches[-1]
                            old_literal = chosen_m.group(1)
                            break

            if target_idx == -1 or old_literal is None:
                return (False, f"Could not find declaration for '{target_ref}' in {strings_file.name}", None)

            target_line_str = lines_with_ends[target_idx]
            already_wrapped = "BridgeTextRegistry." in target_line_str

            if already_wrapped:
                val_start_col = chosen_m.start(1) if chosen_m is not None else target_line_str.find(old_literal)
                line_byte_start = len("".join(lines_with_ends[:target_idx]).encode("utf-8"))
                byte_start = line_byte_start + len(target_line_str[:val_start_col].encode("utf-8"))
                byte_end = byte_start + len(old_literal.encode("utf-8"))

                ok, msg, bak = surgical_edit(
                    file_path=str(strings_file),
                    byte_start=byte_start,
                    byte_end=byte_end,
                    expected_old_value=old_literal,
                    new_value=escaped_new,
                )
            else:
                eq_idx = target_line_str.find("=")
                line_ending = "\r\n" if target_line_str.endswith("\r\n") else "\n" if target_line_str.endswith("\n") else ""
                stripped_line = target_line_str.rstrip("\r\n")

                if eq_idx != -1:
                    prefix = stripped_line[:eq_idx + 1]
                    rhs = stripped_line[eq_idx + 1:].strip()
                    new_rhs = rhs.replace(f'"{old_literal}"', f'"{escaped_new}"', 1)
                    is_composable = "@Composable" in stripped_line
                    fn_name = "getText" if is_composable else "get"
                    if not is_composable and "get()" not in prefix:
                        indent_val = prefix.split("val")[0]
                        var_name_decl = prefix.split("val")[1].split("=")[0].strip()
                        prefix = f"{indent_val}val {var_name_decl} get() ="
                    new_line_str = f'{prefix} BridgeTextRegistry.{fn_name}("{target_ref}", {new_rhs}){line_ending}'
                else:
                    new_line_str = target_line_str.replace(f'"{old_literal}"', f'"{escaped_new}"', 1)

                line_byte_start = len("".join(lines_with_ends[:target_idx]).encode("utf-8"))
                ok, msg, bak = surgical_edit(
                    file_path=str(strings_file),
                    byte_start=line_byte_start,
                    byte_end=line_byte_start + len(target_line_str.encode("utf-8")),
                    expected_old_value=target_line_str,
                    new_value=new_line_str,
                )
                if ok:
                    try:
                        u_content = strings_file.read_text(encoding="utf-8")
                        if "import com.composebridge.agent.BridgeTextRegistry" not in u_content:
                            pkg_m = re.search(r'(package\s+[^\n]+)', u_content)
                            if pkg_m:
                                ins = pkg_m.end()
                                _atomic_write_text(strings_file, u_content[:ins] + "\n\nimport com.composebridge.agent.BridgeTextRegistry" + u_content[ins:])
                    except Exception:
                        pass

            if not ok:
                return (False, f"Surgical edit failed on {strings_file.name}: {msg}", None)

            try:
                journal = PatternJournal(p_root)
                journal.record(pattern_id=f"text_ref_{var_name}", file=str(strings_file.relative_to(p_root)), line=target_idx + 1, old_content=target_line_str.strip(), new_content=target_line_str.replace(old_literal, escaped_new).strip())
            except Exception:
                pass

            return (True, f"Successfully updated reference '{target_ref}' in {strings_file.name}:{target_idx + 1}", {"type": "reference", "ref_key": target_ref, "file": str(strings_file.relative_to(p_root)), "line": target_idx + 1, "old_text": old_literal, "new_text": new_text})

        # ----------------------------------------------------
        # الحالة أ: نص مباشر (Hardcoded في ملف المصدر مع وجود ملف نصوص مركزي)
        # ----------------------------------------------------
        full_path = None
        if os.path.isabs(file_path) and os.path.exists(file_path):
            full_path = Path(file_path)
        else:
            fname = Path(file_path).name
            candidates = [c for c in p_root.rglob(fname) if not is_ignored_path(c, p_root)]
            def _rank(p):
                norm = str(p).replace("\\", "/").lower()
                return 0 if "/commonmain/" in norm else 1 if "/main/" in norm else 2 if "/src/" in norm else 3
            candidates.sort(key=lambda p: (_rank(p), len(str(p))))
            if candidates:
                full_path = candidates[0]

        if not full_path or not full_path.exists():
            return (False, f"Source file not found: {file_path}", None)

        if is_file_dirty_in_ide(full_path, p_root):
            return (False, f"الملف '{full_path.name}' مفتوح في IDE وفيه تعديلات غير محفوظة. احفظ أولاً.", {"error_code": "DIRTY_BUFFER_DETECTED", "file": str(full_path)})

        is_valid, err_msg = validate_kotlin_syntax(full_path)
        if not is_valid:
            return (False, err_msg, None)

        with open(full_path, "r", encoding="utf-8", newline="") as f:
            content = f.read()

        lines_with_ends = content.splitlines(keepends=True)
        if not lines_with_ends:
            return (False, f"File {full_path.name} is empty", None)

        target_idx, target_literal = -1, None
        check_idx = max(0, min(len(lines_with_ends) - 1, line - 1))
        search_indices = [check_idx]
        for offset in range(1, 21):
            if check_idx - offset >= 0:
                search_indices.append(check_idx - offset)
            if check_idx + offset < len(lines_with_ends):
                search_indices.append(check_idx + offset)

        clean_target = (old_text or "").strip()
        for idx in search_indices:
            l_str = lines_with_ends[idx]
            if clean_target and clean_target in l_str:
                matches = list(re.finditer(r'"([^"\\]*(?:\\.[^"\\]*)*)"', l_str))
                for m in matches:
                    if m.group(1) == clean_target or clean_target in m.group(1):
                        target_idx, target_literal = idx, m.group(1)
                        break
            if target_idx != -1:
                break

        if target_idx == -1:
            for idx in search_indices:
                l_str = lines_with_ends[idx]
                if "Text(" in l_str or "text =" in l_str:
                    m = re.search(r'"([^"\\]*(?:\\.[^"\\]*)*)"', l_str)
                    if m:
                        target_idx, target_literal = idx, m.group(1)
                        break

        if target_idx == -1:
            for idx, l_str in enumerate(lines_with_ends):
                if clean_target and clean_target in l_str:
                    m = re.search(r'"([^"\\]*(?:\\.[^"\\]*)*)"', l_str)
                    if m:
                        target_idx, target_literal = idx, m.group(1)
                        break

        if target_idx == -1 or not target_literal:
            return (False, f"Text '{old_text}' not found near line {line} in {full_path.name}", None)

        target_line_str = lines_with_ends[target_idx]
        col_in_line = target_line_str.find(f'"{target_literal}"')
        val_start_col = col_in_line + 1 if col_in_line != -1 else target_line_str.find(target_literal)
        if val_start_col == -1:
            return (False, f"Literal '{target_literal}' offset not found in {full_path.name}:{target_idx + 1}", None)

        has_bridge_import = "import com.composebridge.agent.BridgeTextRegistry" in content
        already_wrapped = "BridgeTextRegistry.getText" in target_line_str
        auto_key = f"{full_path.stem}.line_{target_idx + 1}"

        if not already_wrapped and f'"{target_literal}"' in target_line_str:
            exact_target = f'"{target_literal}"'
            line_byte_start = len("".join(lines_with_ends[:target_idx]).encode("utf-8"))
            byte_start = line_byte_start + len(target_line_str[:col_in_line].encode("utf-8"))
            byte_end = byte_start + len(exact_target.encode("utf-8"))
            wrapped_replacement = f'BridgeTextRegistry.getText("{auto_key}", "{escaped_new}")'
            ok, msg, bak = surgical_edit(
                file_path=str(full_path),
                byte_start=byte_start,
                byte_end=byte_end,
                expected_old_value=exact_target,
                new_value=wrapped_replacement,
            )
            if ok:
                if not has_bridge_import:
                    try:
                        u_content = full_path.read_text(encoding="utf-8")
                        if "import com.composebridge.agent.BridgeTextRegistry" not in u_content:
                            imp = "import com.composebridge.agent.BridgeTextRegistry"
                            lines = u_content.splitlines()
                            last_imp = max([i for i, l in enumerate(lines) if l.strip().startswith("import ")] or [-1])
                            if last_imp >= 0:
                                lines.insert(last_imp + 1, imp)
                            else:
                                pkg_idx = max([i for i, l in enumerate(lines) if l.strip().startswith("package ")] or [-1])
                                lines.insert(pkg_idx + 1 if pkg_idx >= 0 else 0, imp)
                            _atomic_write_text(full_path, "\n".join(lines))
                    except Exception:
                        pass
                return (True, f"Successfully transformed text to live BridgeTextRegistry in {full_path.name}:{target_idx + 1}", {"type": "bridge_registry_migrated", "file": str(full_path.relative_to(p_root)), "line": target_idx + 1, "old_text": target_literal, "new_text": new_text, "token_name": auto_key, "ref_key": auto_key})

        line_byte_start = len("".join(lines_with_ends[:target_idx]).encode("utf-8"))
        byte_start = line_byte_start + len(target_line_str[:val_start_col].encode("utf-8"))
        byte_end = byte_start + len(target_literal.encode("utf-8"))

        ok, msg, bak = surgical_edit(
            file_path=str(full_path),
            byte_start=byte_start,
            byte_end=byte_end,
            expected_old_value=target_literal,
            new_value=escaped_new,
        )
        if not ok:
            return (False, f"Surgical edit failed on {full_path.name}: {msg}", None)

        try:
            journal = PatternJournal(p_root)
            journal.record(pattern_id=f"text_hardcoded_{full_path.stem}_{target_idx + 1}", file=str(full_path.relative_to(p_root)), line=target_idx + 1, old_content=target_line_str.strip(), new_content=target_line_str.replace(target_literal, escaped_new).strip())
        except Exception:
            pass

        return (True, f"Successfully updated text in {full_path.name}:{target_idx + 1}", {"type": "hardcoded", "file": str(full_path.relative_to(p_root)), "line": target_idx + 1, "old_text": target_literal, "new_text": new_text})
