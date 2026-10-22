# -*- coding: utf-8 -*-
"""
Text source editor module.
Handles escaping Kotlin string literals, wrapping raw strings, and live text editing in Compose.
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

try:
    from common.file_ops import acquire_write_lock, _atomic_write_text, _find_registry_file
except ImportError:
    try:
        from server.common.file_ops import acquire_write_lock, _atomic_write_text, _find_registry_file
    except ImportError:
        from ..common.file_ops import acquire_write_lock, _atomic_write_text, _find_registry_file

from core.ast_finder import parse_file, find_all_call_expressions, surgical_edit
from core.pattern_journal import PatternJournal

from .journal_helpers import (
    with_write_lock,
    _journal_save,
    _validate_after_splice,
)

def escape_kotlin_string(text: str) -> str:
    r"""
    يقوم بتحويل المحارف الخاصة إلى صيغة آمنة لسلاسل كوتلن النصية (Double-quoted strings).
    - تحويل \ إلى \\
    - تحويل " إلى \"
    - تحويل \n إلى \n
    - تحويل \r إلى \r
    - تحويل \t إلى \t
    - تحويل $ إلى \$ لتجنب الـ String Template غير المقصود
    """
    if not text:
        return ""
    # تأكد من استبدال الـ backslash أولاً لتفادي مضاعفة الـ escapes اللاحقة
    escaped = text.replace("\\", "\\\\")
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace("\n", "\\n")
    escaped = escaped.replace("\r", "\\r")
    escaped = escaped.replace("\t", "\\t")
    escaped = escaped.replace("$", "\\$")
    return escaped


def update_text_in_source(
    file_path: str,
    line: int,
    old_text: str,
    new_text: str,
    ref_key: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> tuple:
    r"""
    يقوم بالتعديل الجراحي للنصوص في الكود المصدري عبر حالتين:
    أ. نص مباشر (Hardcoded): استبدال النص بين علامتي التنصيص Text("old") إلى Text("new") في الملف المحدد.
    ب. نص مرجعي (Reference): إذا كان النص يشير لـ AppStrings.xyz، يتم تعديل قيمة المتغير في ملف AppStrings.kt نفسه بدلاً من تخريب استدعاء الـ Composable.
    
    معالجة الـ String Escaping:
    يتم تحويل " إلى \" و \ إلى \\ و \n إلى \n لضمان سلامة كود كوتلن من أخطاء الترجمة.
    
    الضمانات:
    - يستخدم FileLock (قفل الملفات).
    - ينشئ نسخة احتياطية .bridge.bak.
    - يسجل العملية في PatternJournal ليظهر التعديل في تبويب Changes في الـ IDE.
    
    Returns:
        (success: bool, message: str, info: dict)
    """
    from core.project_root import get_project_root
    from common.file_ops import acquire_write_lock, _atomic_write_text
    from core.ast_finder import surgical_edit
    from core.pattern_journal import PatternJournal
    import re
    import os

    if not project_root:
        project_root = get_project_root()
    else:
        project_root = Path(project_root)

    with acquire_write_lock():
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
        if not target_ref and old_text:
            try:
                candidates = list(project_root.rglob("AppStrings.kt"))
                candidates = [c for c in candidates if "build" not in str(c) and ".composebridge" not in str(c)]
                if candidates:
                    s_content = candidates[0].read_text(encoding="utf-8", errors="ignore")
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
        # الحالة ب: نص مرجعي (Reference في AppStrings.kt)
        # ----------------------------------------------------
        if is_ref:
            candidates = list(project_root.rglob("AppStrings.kt"))
            candidates = [c for c in candidates if "build" not in str(c) and ".composebridge" not in str(c)]
            if not candidates:
                return (False, f"AppStrings.kt not found in project {project_root}", None)

            strings_file = candidates[0]
            with open(strings_file, "r", encoding="utf-8", newline="") as f:
                content = f.read()

            parts = target_ref.split(".")
            var_name = parts[-1]
            object_name = parts[-2] if len(parts) >= 2 and parts[-2] != "AppStrings" else None

            lines_with_ends = content.splitlines(keepends=True)
            target_idx = -1
            old_literal = None
            chosen_m = None

            in_target_object = object_name is None

            for idx, line_str in enumerate(lines_with_ends):
                if object_name and re.search(rf'\bobject\s+{re.escape(object_name)}\b', line_str):
                    in_target_object = True
                elif in_target_object and object_name and re.search(r'\bobject\s+\w+', line_str) and not re.search(rf'\bobject\s+{re.escape(object_name)}\b', line_str):
                    in_target_object = False

                if in_target_object and re.search(rf'\bval\s+{re.escape(var_name)}\b', line_str):
                    all_matches = list(re.finditer(r'"([^"\\]*(?:\\.[^"\\]*)*)"', line_str))
                    # Exclude BridgeTextRegistry key string (e.g. "AppStrings.xxx")
                    matches = [m for m in all_matches if not m.group(1).startswith("AppStrings.")] or all_matches
                    if matches:
                        # 1. النمط الفردي (Single Pattern): مثل val unit @Composable get() = "أنشطة"
                        # نص واحد فقط في السطر - يتم اختياره فوراً وبدقة
                        if len(matches) == 1:
                            chosen_m = matches[0]
                        else:
                            # 2. النمط الشرطي (If/Else Pattern): مثل val selectClass = if (...) "..." else "..."
                            if old_text:
                                # تطابق تام
                                for m in matches:
                                    if m.group(1) == old_text:
                                        chosen_m = m
                                        break
                                # تطابق جزئي
                                if not chosen_m:
                                    for m in matches:
                                        if old_text in m.group(1) or m.group(1) in old_text:
                                            chosen_m = m
                                            break
                                # تطابق بدون templates ($...)
                                if not chosen_m:
                                    clean_old = re.sub(r'\$\{?[a-zA-Z0-9_.]+\}?', '', old_text).strip()
                                    for m in matches:
                                        clean_m = re.sub(r'\$\{?[a-zA-Z0-9_.]+\}?', '', m.group(1)).strip()
                                        if clean_m and (clean_m in old_text or clean_old in m.group(1)):
                                            chosen_m = m
                                            break
                            # الافتراضي: فرع else أو آخر نص في السطر
                            if not chosen_m:
                                m_else = None
                                for m in matches:
                                    prefix = line_str[:m.start()]
                                    if re.search(r'\belse\s*$', prefix):
                                        m_else = m
                                        break
                                chosen_m = m_else or matches[-1]

                        target_idx = idx
                        old_literal = chosen_m.group(1)
                        break

            # Fallback 1: بحث في كامل الملف عن val <var_name>
            if target_idx == -1 or old_literal is None:
                for idx, line_str in enumerate(lines_with_ends):
                    if re.search(rf'\bval\s+{re.escape(var_name)}\b', line_str):
                        all_matches = list(re.finditer(r'"([^"\\]*(?:\\.[^"\\]*)*)"', line_str))
                        matches = [m for m in all_matches if not m.group(1).startswith("AppStrings.")] or all_matches
                        if matches:
                            target_idx = idx
                            chosen_m = matches[0] if len(matches) == 1 else matches[-1]
                            old_literal = chosen_m.group(1)
                            break

            # Fallback 2: بحث عن النص القديم في كامل AppStrings.kt
            if target_idx == -1 or old_literal is None:
                if old_text:
                    for idx, line_str in enumerate(lines_with_ends):
                        if old_text in line_str:
                            matches = list(re.finditer(r'"([^"\\]*(?:\\.[^"\\]*)*)"', line_str))
                            for m in matches:
                                if m.group(1) == old_text or old_text in m.group(1):
                                    target_idx = idx
                                    chosen_m = m
                                    old_literal = m.group(1)
                                    break
                            if chosen_m:
                                break

            if target_idx == -1 or old_literal is None:
                return (False, f"Could not find declaration for '{target_ref}' in {strings_file.name}", None)

            target_line_str = lines_with_ends[target_idx]
            already_wrapped = "BridgeTextRegistry." in target_line_str

            if already_wrapped:
                # Property already wrapped with BridgeTextRegistry: update default value surgically
                if chosen_m is not None:
                    val_start_col = chosen_m.start(1)
                else:
                    col_in_line = target_line_str.find(f'"{old_literal}"')
                    val_start_col = col_in_line + 1 if col_in_line != -1 else target_line_str.find(old_literal)

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
                # ⭐ On-the-Fly Auto-Migration: Wrap property with BridgeTextRegistry on first edit!
                eq_idx = target_line_str.find("=")
                line_ending = "\r\n" if target_line_str.endswith("\r\n") else "\n" if target_line_str.endswith("\n") else ""
                stripped_line = target_line_str.rstrip("\r\n")

                if eq_idx != -1:
                    prefix = stripped_line[:eq_idx + 1]
                    rhs = stripped_line[eq_idx + 1:].strip()
                    if chosen_m is not None:
                        start_c = chosen_m.start(1)
                        end_c = chosen_m.end(1)
                        new_line_content = stripped_line[:start_c] + escaped_new + stripped_line[end_c:]
                        new_rhs = new_line_content[eq_idx + 1:].strip()
                    else:
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
                byte_start = line_byte_start
                byte_end = line_byte_start + len(target_line_str.encode("utf-8"))

                ok, msg, bak = surgical_edit(
                    file_path=str(strings_file),
                    byte_start=byte_start,
                    byte_end=byte_end,
                    expected_old_value=target_line_str,
                    new_value=new_line_str,
                )

                # Ensure import com.composebridge.agent.BridgeTextRegistry is present
                if ok:
                    try:
                        updated_file_content = strings_file.read_text(encoding="utf-8")
                        if "import com.composebridge.agent.BridgeTextRegistry" not in updated_file_content:
                            pkg_match = re.search(r'(package\s+[^\n]+)', updated_file_content)
                            if pkg_match:
                                ins_pos = pkg_match.end()
                                imp_line = "\n\nimport com.composebridge.agent.BridgeTextRegistry"
                                updated_file_content = updated_file_content[:ins_pos] + imp_line + updated_file_content[ins_pos:]
                                _atomic_write_text(strings_file, updated_file_content)
                    except Exception as e:
                        print(f"[update_text_in_source] Warning adding import: {e}")
            if not ok:
                return (False, f"Surgical edit failed on {strings_file.name}: {msg}", None)

            # تسجيل التعديل في Journal
            try:
                journal = PatternJournal(project_root)
                journal.record(
                    pattern_id=f"text_ref_{var_name}",
                    file=str(strings_file.relative_to(project_root)),
                    line=target_idx + 1,
                    old_content=target_line_str.strip(),
                    new_content=target_line_str.replace(old_literal, escaped_new).strip(),
                )
            except Exception as e:
                print(f"[update_text_in_source] Warning recording journal: {e}")

            return (
                True,
                f"Successfully updated reference '{target_ref}' in {strings_file.name}:{target_idx + 1}",
                {
                    "type": "reference",
                    "ref_key": target_ref,
                    "file": str(strings_file.relative_to(project_root)),
                    "line": target_idx + 1,
                    "old_text": old_literal,
                    "new_text": new_text,
                }
            )

        # ----------------------------------------------------
        # الحالة أ: نص مباشر (Hardcoded في ملف المصدر)
        # ----------------------------------------------------
        full_path = None
        if os.path.isabs(file_path) and os.path.exists(file_path):
            full_path = Path(file_path)
        else:
            fname = Path(file_path).name
            candidates = list(project_root.rglob(fname))
            candidates = [c for c in candidates if "build" not in str(c) and ".composebridge" not in str(c)]
            if candidates:
                full_path = candidates[0]

        if not full_path or not full_path.exists():
            return (False, f"Source file not found: {file_path}", None)

        with open(full_path, "r", encoding="utf-8", newline="") as f:
            content = f.read()

        lines_with_ends = content.splitlines(keepends=True)
        if not lines_with_ends:
            return (False, f"File {full_path.name} is empty", None)

        target_idx = -1
        target_literal = None

        # البحث حول السطر المطلوب (نطاق ±20 سطر)
        check_idx = max(0, min(len(lines_with_ends) - 1, line - 1))
        search_indices = [check_idx]
        for offset in range(1, 21):
            if check_idx - offset >= 0:
                search_indices.append(check_idx - offset)
            if check_idx + offset < len(lines_with_ends):
                search_indices.append(check_idx + offset)

        # 1. البحث عن تطابق مباشر مع old_text
        if old_text:
            for s_idx in search_indices:
                line_str = lines_with_ends[s_idx]
                if old_text in line_str:
                    target_idx = s_idx
                    target_literal = old_text
                    break

        # 2. البحث عن Text("...") في الأسطر المحيطة
        if target_idx == -1:
            for s_idx in search_indices:
                line_str = lines_with_ends[s_idx]
                m_txt = re.search(r'Text\s*\(\s*(?:text\s*=\s*)?"([^"\\]*(?:\\.[^"\\]*)*)"', line_str)
                if m_txt:
                    target_idx = s_idx
                    target_literal = m_txt.group(1)
                    break

        # 3. بحث أوسع في كامل الملف إذا لم يتم العثور عليه قرب السطر
        if target_idx == -1 and old_text:
            for s_idx, line_str in enumerate(lines_with_ends):
                if old_text in line_str:
                    target_idx = s_idx
                    target_literal = old_text
                    break

        if target_idx == -1 or not target_literal:
            return (False, f"Text '{old_text}' not found near line {line} in {full_path.name}", None)

        target_line_str = lines_with_ends[target_idx]
        col_in_line = target_line_str.find(f'"{target_literal}"')
        if col_in_line != -1:
            val_start_col = col_in_line + 1
        else:
            val_start_col = target_line_str.find(target_literal)

        if val_start_col == -1:
            return (False, f"Literal '{target_literal}' offset not found in {full_path.name}:{target_idx + 1}", None)

        # Check if line or file already has BridgeTextRegistry
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
                        updated_file_content = full_path.read_text(encoding="utf-8")
                        if "import com.composebridge.agent.BridgeTextRegistry" not in updated_file_content:
                            imp_str = "import com.composebridge.agent.BridgeTextRegistry"
                            lines = updated_file_content.splitlines()
                            last_imp = max([i for i, l in enumerate(lines) if l.strip().startswith("import ")] or [-1])
                            if last_imp >= 0:
                                lines.insert(last_imp + 1, imp_str)
                            else:
                                pkg_idx = max([i for i, l in enumerate(lines) if l.strip().startswith("package ")] or [-1])
                                lines.insert(pkg_idx + 1 if pkg_idx >= 0 else 0, imp_str)
                            _atomic_write_text(full_path, "\n".join(lines))
                    except Exception as imp_err:
                        print(f"[update_text_in_source] Import insertion warning: {imp_err}")
                return (
                    True,
                    f"Successfully transformed text to live BridgeTextRegistry in {full_path.name}:{target_idx + 1}",
                    {
                        "type": "bridge_registry_migrated",
                        "file": str(full_path.relative_to(project_root)),
                        "line": target_idx + 1,
                        "old_text": target_literal,
                        "new_text": new_text,
                        "token_name": auto_key,
                        "ref_key": auto_key,
                    }
                )

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

        # تسجيل التعديل في Journal
        try:
            journal = PatternJournal(project_root)
            journal.record(
                pattern_id=f"text_hardcoded_{full_path.stem}_{target_idx + 1}",
                file=str(full_path.relative_to(project_root)),
                line=target_idx + 1,
                old_content=target_line_str.strip(),
                new_content=target_line_str.replace(target_literal, escaped_new).strip(),
            )
        except Exception as e:
            print(f"[update_text_in_source] Warning recording journal: {e}")

        return (
            True,
            f"Successfully updated text in {full_path.name}:{target_idx + 1}",
            {
                "type": "hardcoded",
                "file": str(full_path.relative_to(project_root)),
                "line": target_idx + 1,
                "old_text": target_literal,
                "new_text": new_text,
            }
        )

