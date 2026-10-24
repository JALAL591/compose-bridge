# -*- coding: utf-8 -*-
"""
Core bridge state editor, MutableState property finder, and typography mutator.
"""

import os
import re
import json
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

def get_config_paths() -> dict:
    """Load path mappings from composebridge.json if available."""
    root = get_project_root()
    for candidate in [
        root / "composebridge.json",
        Path.cwd() / "composebridge.json",
        Path(__file__).resolve().parent.parent.parent / "composebridge.json",
    ]:
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return data.get("paths", {})
            except Exception:
                pass
    return {}


def get_bridge_state_file() -> Path:
    """Resolve BridgeState.kt dynamically from config or project structure."""
    cfg_paths = get_config_paths()
    if "bridge_state" in cfg_paths:
        p = PROJECT_ROOT / cfg_paths["bridge_state"]
        if p.exists():
            return p
    for candidate in [
        PROJECT_ROOT / "agent" / "src" / "androidMain" / "kotlin" / "com" / "composebridge" / "agent" / "BridgeState.kt",
        PROJECT_ROOT / "composebridge-agent" / "src" / "androidMain" / "kotlin" / "com" / "composebridge" / "agent" / "BridgeState.kt",
        PROJECT_ROOT / "composebridge-agent" / "src" / "commonMain" / "kotlin" / "com" / "composebridge" / "agent" / "BridgeState.kt",
    ]:
        if candidate.exists():
            return candidate
    for f in PROJECT_ROOT.rglob("BridgeState.kt"):
        s = str(f)
        if ".bak" not in s and "build" not in s:
            return f
    return PROJECT_ROOT / "agent" / "src" / "androidMain" / "kotlin" / "com" / "composebridge" / "agent" / "BridgeState.kt"


def get_app_typography_file() -> Path:
    """Resolve AppTypography.kt dynamically."""
    cfg_paths = get_config_paths()
    if "app_typography" in cfg_paths:
        p = PROJECT_ROOT / cfg_paths["app_typography"]
        if p.exists():
            return p
    for f in PROJECT_ROOT.rglob("AppTypography.kt"):
        s = str(f)
        if ".bak" not in s and "build" not in s:
            return f
    return _find_registry_file("AppTypography.kt") or (PROJECT_ROOT / "AppTypography.kt")


BRIDGE_STATE_FILE = get_bridge_state_file()


APP_TYPOGRAPHY_FILE = get_app_typography_file()


def find_mutable_state_property(tree, source_bytes: bytes, target_prop: str):
    """
    Dynamically locate 'var <target_prop> by mutableStateOf(...)' using Tree-sitter.
    Returns: (val_byte_start, val_byte_end, old_value_str) or None
    """
    def _search(node):
        if node.type == "property_declaration":
            var_decl = next((c for c in node.children if c.type == "variable_declaration"), None)
            prop_del = next((c for c in node.children if c.type == "property_delegate"), None)
            if var_decl and prop_del:
                var_id = next((c for c in var_decl.children if c.type in ("identifier", "simple_identifier")), None)
                if var_id:
                    name = source_bytes[var_id.start_byte:var_id.end_byte].decode("utf-8")
                    if name == target_prop:
                        call = next((c for c in prop_del.children if c.type == "call_expression"), None)
                        if call:
                            args = next((c for c in call.children if c.type == "value_arguments"), None)
                            if args:
                                val_node = next((c for c in args.children if c.type not in ("(", ")", ",")), None)
                                if val_node:
                                    old_val = source_bytes[val_node.start_byte:val_node.end_byte].decode("utf-8")
                                    return val_node.start_byte, val_node.end_byte, old_val
        for child in node.children:
            res = _search(child)
            if res:
                return res
        return None

    return _search(tree.root_node)


def normalize_value(property_name: str, value: str) -> str:
    """
    يحوّل قيمة WebSocket إلى القيمة الكاملة لـ mutableStateOf.

    المهم: القيمة الناتجة هنا هي القيمة الكاملة داخل الأقواس.
    مثال: "80" → "80.dp" (بدون قوسين)
    """
    # النصوص
    if property_name == "titleText":
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    # الألوان
    if property_name in ("cardBackgroundColor", "userNameColor", "titleColor"):
        cleaned = value.removeprefix("#").removeprefix("0x").removeprefix("0X").strip()
        if len(cleaned) == 6:
            cleaned = "FF" + cleaned
        # ⚠️ القيمة الكاملة — تشمل Color()
        return f"Color(0x{cleaned})"

    # الأبعاد (Dp)
    if property_name in ("cardPadding", "cardCornerRadius", "columnPadding", "spacerHeight"):
        # إذا القيمة تحتوي بالفعل على ".dp" → اتركها
        if ".dp" in value:
            return value
        return f"{value}.dp"

    # أحجام الخط
    if property_name in ("userNameFontSize", "titleFontSize"):
        if ".sp" in value:
            return value
        return f"{value}.sp"

    return value


def update_bridge_state(property_name: str, value: str) -> tuple:
    """
    Dynamically locate and update property in BridgeState.kt using Tree-sitter.

    Returns:
        (success, message, byte_range_dict)
    """
    file_path = get_bridge_state_file()
    if not file_path.exists():
        return (False, f"File not found: {file_path}", None)

    try:
        tree, source_bytes = parse_file(str(file_path))
    except Exception as e:
        return (False, f"Failed to parse {file_path}: {e}", None)

    prop_info = find_mutable_state_property(tree, source_bytes, property_name)
    if not prop_info:
        return (False, f"Property '{property_name}' with mutableStateOf not found in {file_path.name}", None)

    byte_start, byte_end, old_value = prop_info
    new_value = normalize_value(property_name, value)

    return (True, new_value, {
        "file_path": str(file_path),
        "old_value": old_value,
        "new_value": new_value,
        "byte_start": byte_start,
        "byte_end": byte_end,
    })


def apply_state_update(property_name: str, value: str) -> tuple:
    """
    يطبّق التعديل على الملف.

    Returns:
        (success, message, byte_range)
    """
    import shutil
    import tempfile
    import os

    # 1. ابحث عن الموقع
    result = update_bridge_state(property_name, value)
    if not result[0]:
        return result

    success, new_value_text, info = result
    file_path = Path(info["file_path"])
    byte_start = info["byte_start"]
    byte_end = info["byte_end"]
    old_value = info["old_value"]

    # 2. اقرأ الملف
    with open(file_path, "rb") as f:
        source = f.read()

    # 3. تحقق
    current = source[byte_start:byte_end].decode("utf-8")
    if current != old_value:
        return (False, f"Value mismatch: expected '{old_value}', found '{current}'", None)

    # 4. أنشئ نسخة احتياطية (فقط إذا لم تكن موجودة للحفاظ على النسخة الأصلية النقية)
    backup_path = str(file_path) + ".bridge.bak"
    if not os.path.exists(backup_path):
        shutil.copy2(file_path, backup_path)

    # 5. ابنِ المحتوى الجديد
    new_source = (
        source[:byte_start]
        + new_value_text.encode("utf-8")
        + source[byte_end:]
    )

    # 6. كتابة ذرية
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=file_path.parent,
            delete=False,
            prefix=file_path.name + ".tmp_",
        ) as tmp:
            tmp.write(new_source)
            tmp_path = tmp.name

        os.replace(tmp_path, file_path)
    except Exception as e:
        return (False, f"Write failed: {e}", None)

    try:
        _journal_save(file_path, source.decode("utf-8", errors="replace"), new_source.decode("utf-8", errors="replace"))
    except Exception:
        pass

    return (
        True,
        f"Updated {property_name}: '{old_value}' → '{new_value_text}'",
        {
            "byte_start": byte_start,
            "byte_end": byte_end,
            "old": old_value,
            "new": new_value_text,
            "backup": backup_path,
        }
    )


def update_typography_property(
    style_key: str,
    property_name: str,
    new_value: str,
) -> tuple:
    """
    يعدّل خاصية داخل TextStyle في AppTypography.kt.

    مثال:
        style_key = "headlineLarge"
        property_name = "fontSize"
        new_value = "48"

    يبحث عن:
        headlineLarge = BridgeTypographyRegistry.getStyle(
            key = "headlineLarge",
            default = TextStyle(
                fontWeight = FontWeight.Bold,
                fontSize = 30.sp,    ← يستبدل 30 بـ 48
                letterSpacing = 0.sp
            )
        )
    """
    import re
    import shutil
    import tempfile
    import os

    file_path = APP_TYPOGRAPHY_FILE
    if not file_path.exists():
        return (False, f"AppTypography.kt not found: {file_path}", None)

    with open(file_path, "r", encoding="utf-8", newline="") as f:
        content = f.read()

    # 1. ابحث عن block الخاص بالـ style
    # يبدأ من `key = "headlineLarge"` وينتهي عند `)` المناسب
    block_start_pattern = rf'key\s*=\s*"{re.escape(style_key)}"'
    block_match = re.search(block_start_pattern, content)

    if not block_match:
        return (False, f"Style '{style_key}' not found", None)

    # ابحث عن نهاية الكتلة: ابدأ من الموقع وابحث عن TextStyle(
    start_pos = block_match.start()
    textstyle_match = re.search(r'TextStyle\s*\(', content[start_pos:])

    if not textstyle_match:
        return (False, f"TextStyle not found for {style_key}", None)

    textstyle_start = start_pos + textstyle_match.start()

    # ابحث عن القوس المغلق المقابل
    textstyle_end_match = re.search(r'\n\s{8,12}\)', content[textstyle_start:])

    if not textstyle_end_match:
        return (False, f"TextStyle end not found for {style_key}", None)

    textstyle_end = textstyle_start + textstyle_end_match.start()
    block_content = content[textstyle_start:textstyle_end]

    # 2. ابحث عن الخاصية داخل الكتلة
    # fontSize = 30.sp → 30
    prop_pattern = rf'({re.escape(property_name)}\s*=\s*)(\d+(?:\.\d+)?)(\.sp)'
    prop_match = re.search(prop_pattern, block_content)

    if not prop_match:
        return (False, f"Property '{property_name}' not found in {style_key}", None)

    old_value = prop_match.group(2)

    # 3. تحقق أن القيمة جديدة
    new_value_clean = new_value.replace(".sp", "").strip()
    if old_value == new_value_clean:
        return (True, f"No change needed for {style_key}.{property_name}", None)

    # 4. استبدل
    new_block = (
        block_content[:prop_match.start(2)]
        + new_value_clean
        + block_content[prop_match.end(2):]
    )

    new_content = content[:textstyle_start] + new_block + content[textstyle_end:]

    # 5. نسخة احتياطية (فقط إذا لم تكن موجودة للحفاظ على النسخة الأصلية النقية)
    backup_path = str(file_path) + ".bridge.bak"
    if not os.path.exists(backup_path):
        shutil.copy2(file_path, backup_path)

    # 6. كتابة ذرية
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=file_path.parent,
            delete=False,
            prefix=file_path.name + ".tmp_",
        ) as tmp:
            tmp.write(new_content)
            tmp_path = tmp.name

        os.replace(tmp_path, file_path)
    except Exception as e:
        return (False, f"Write failed: {e}", None)

    _journal_save(file_path, content, new_content)

    return (
        True,
        f"Updated AppTypography.{style_key}.{property_name}: {old_value} → {new_value_clean}",
        {"backup": backup_path}
    )


def is_typography_property(property_name: str) -> bool:
    """يتحقق إذا كانت الخاصية Typography."""
    return property_name.startswith("AppTypography.")


def parse_typography_property(property_name: str) -> tuple:
    """
    يفكك "AppTypography.headlineLarge.fontSize"
    إلى ("headlineLarge", "fontSize")
    """
    parts = property_name.removeprefix("AppTypography.").split(".")
    if len(parts) == 2:
        return (parts[0], parts[1])
    return (None, None)

