# -*- coding: utf-8 -*-
"""
Dimension source editor module.
Handles surgical AST updates for AppDimens.kt, Modifier.size/padding, and default token values.
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
    from common.file_ops import _atomic_write_text, _find_registry_file
except ImportError:
    try:
        from server.common.file_ops import _atomic_write_text, _find_registry_file
    except ImportError:
        from ..common.file_ops import _atomic_write_text, _find_registry_file

from core.ast_finder import parse_file, find_all_call_expressions
from core.utils import read_file_as_utf8

from .journal_helpers import (
    with_write_lock,
    _journal_save,
    _validate_after_splice,
)

def edit_dimension_in_source(
    source_file: str,
    line_number: int,
    utf16_offset: int,
    utf16_length: int,
    old_value: str,    # "24.dp"
    new_value: str,    # "32.dp"
) -> tuple:
    """
    يعدّل قيمة .dp محددة في ملف مصدري مع الحفاظ على .dp.
    """
    import re
    import shutil
    import tempfile
    import os

    full_path = PROJECT_ROOT / source_file

    from core.ignore_rules import get_ignore_rules
    rules = get_ignore_rules(PROJECT_ROOT)
    ignored, reason = rules.is_ignored(full_path)
    if ignored:
        return (False, f"Refused: {reason}", None)

    if not full_path.exists():
        candidates = list(PROJECT_ROOT.rglob(Path(source_file).name))
        candidates = [c for c in candidates if 'build/' not in str(c)]
        if not candidates:
            return (False, f"File not found: {source_file}", None)
        full_path = candidates[0]

    with open(full_path, "r", encoding="utf-8", newline="") as f:
        content = f.read()

    # استبدل old_value بـ new_value (مع الحفاظ على .dp)
    old_clean = old_value.replace(".dp", "").strip()
    new_clean = new_value.replace(".dp", "").strip()

    encoded = content.encode('utf-16-le')
    start_byte = utf16_offset * 2
    end_byte = (utf16_offset + utf16_length) * 2

    pattern = re.compile(rf'\b{re.escape(old_clean)}\.dp\b')

    # ⭐ إذا offset صالح (>0)، استخدم sub-range فقط
    if utf16_offset > 0 and utf16_length > 0 and end_byte <= len(encoded) and start_byte < len(encoded):
        sub = encoded[start_byte:end_byte].decode('utf-16-le', errors='ignore')
        match = pattern.search(sub)
        if not match:
            # Fallback: ابحث في الملف كامل
            sub_full = content
            match_full = pattern.search(sub_full)
            if not match_full:
                return (False, f"Value {old_value} not found at offset {utf16_offset}", None)
            new_text = sub_full[:match_full.start()] + f"{new_clean}.dp" + sub_full[match_full.end():]
        else:
            new_sub = sub[:match.start()] + f"{new_clean}.dp" + sub[match.end():]
            new_encoded = new_sub.encode('utf-16-le')
            new_content = encoded[:start_byte] + new_encoded + encoded[end_byte:]
            new_text = new_content.decode('utf-16-le', errors='ignore')
    else:
        # fallback: ابحث في الملف كامل (مع تحذير)
        sub = content
        match = pattern.search(sub)
        if not match:
            return (False, f"Value {old_value} not found in file", None)
        new_text = sub[:match.start()] + f"{new_clean}.dp" + sub[match.end():]
        print(f"[state_editor] ⚠️ Used fallback (no offset) for {old_value}")

    # نسخة احتياطية
    backup_path = str(full_path) + ".bridge.bak"
    shutil.copy2(full_path, backup_path)

    # كتابة ذرية
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=full_path.parent,
            delete=False,
            prefix=full_path.name + ".tmp_",
        ) as tmp:
            tmp.write(new_text)
            tmp_path = tmp.name

        os.replace(tmp_path, full_path)
    except Exception as e:
        return (False, f"Write failed: {e}", None)

    try:
        _journal_save(full_path, content, new_text)
    except Exception:
        pass

    return (
        True,
        f"Updated {source_file}:{line_number}: {old_value} → {new_value}",
        {"backup": backup_path}
    )


def update_token_default(token_name: str, value: str) -> tuple:
    """
    يعدّل قيمة default لـ BridgeSpacing token في BridgeSpacing.kt.

    مثال:
        token_name = "cardHeight"
        value = "150"

    يبحث عن:
        get("cardHeight", 100.dp)
    يستبدل بـ:
        get("cardHeight", 150.dp)
    """
    import re
    import shutil
    import tempfile
    import os

    file_path = None
    for candidate in ["AppDimens.kt", "DesignSystem.kt", "Dimens.kt", "Dimensions.kt", "Spacing.kt"]:
        candidate_path = _find_registry_file(candidate)
        if candidate_path and candidate_path.exists():
            try:
                txt = candidate_path.read_text(encoding="utf-8")
                if f'"{token_name}"' in txt:
                    file_path = candidate_path
                    break
            except Exception:
                pass

    if not file_path or not file_path.exists():
        file_path = _find_registry_file("AppDimens.kt")

    if not file_path or not file_path.exists():
        return (False, f"Registry file for token '{token_name}' not found in project: {PROJECT_ROOT}", None)

    with open(file_path, "r", encoding="utf-8", newline="") as f:
        content = f.read()

    clean = value.replace(".dp", "").strip()
    if not clean:
        return (False, "Empty value", None)

    try:
        num = float(clean)
        if num.is_integer():
            clean_display = str(int(num))
        else:
            clean_display = str(num)
    except Exception:
        return (False, f"Invalid number: {value}", None)

    # ابحث عن: get("cardHeight", 100.dp) أو get("cardHeight", 100f)
    # ⭐ pattern صحيح: يقبض على الرقم فقط (بدون النقطة)
    pattern = re.compile(
        rf'(BridgeDimensionRegistry\.get\(\s*"{re.escape(token_name)}"\s*,\s*)(\d+)(\.dp|\.f)'
    )

    match = pattern.search(content)
    if not match:
        return (False, f"Token not found: {token_name}", None)

    old_value = match.group(2)

    # استبدل
    new_text = (
        content[:match.start(2)]
        + clean_display
        + content[match.end(2):]
    )

    # نسخة احتياطية
    backup_path = str(file_path) + ".bridge.bak"
    shutil.copy2(file_path, backup_path)

    # كتابة
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=file_path.parent,
            delete=False,
            prefix=file_path.name + ".tmp_",
        ) as tmp:
            tmp.write(new_text)
            tmp_path = tmp.name

        os.replace(tmp_path, file_path)
    except Exception as e:
        return (False, f"Write failed: {e}", None)

    _journal_save(file_path, content, new_text)

    return (
        True,
        f"Updated {token_name}: {old_value} → {clean_display}",
        {"backup": backup_path}
    )

