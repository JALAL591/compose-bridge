# -*- coding: utf-8 -*-
"""
Kotlin source code validation and import hygiene utilities.
"""

import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from core.ast_finder import parse_file

def _validate_kotlin_line(line: str) -> Tuple[bool, str]:
    """فحص أساسي — لا تحقق كامل."""
    # توازن الأقواس
    if line.count("(") != line.count(")"):
        return False, "Unbalanced parens"
    # لا تكرار modifier
    if line.count("modifier =") > 1:
        return False, "Duplicate modifier="
    # لا تداخل (nesting) داخل BridgeDimensionRegistry.get
    if re.search(r'BridgeDimensionRegistry\.get\([^)]*BridgeDimensionRegistry\.get', line):
        return False, "Nested BridgeDimensionRegistry.get"
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

