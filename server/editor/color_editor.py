# -*- coding: utf-8 -*-
"""
Theme color editor module.
Handles surgical AST updates for AppColors.kt and MaterialTheme color tokens.
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

from .journal_helpers import (
    with_write_lock,
    _journal_save,
    _validate_after_splice,
)

from .state_editor_core import get_config_paths

def get_app_colors_file() -> Path:
    """Resolve AppColors.kt dynamically."""
    cfg_paths = get_config_paths()
    if "app_colors" in cfg_paths:
        p = PROJECT_ROOT / cfg_paths["app_colors"]
        if p.exists():
            return p
    for f in PROJECT_ROOT.rglob("AppColors.kt"):
        s = str(f)
        if ".bak" not in s and "build" not in s:
            return f
    return _find_registry_file("AppColors.kt") or (PROJECT_ROOT / "AppColors.kt")


APP_COLORS_FILE = get_app_colors_file()


def _build_color_pattern(key: str) -> str:
    """
    يبني regex pattern لاستخراج قيمة لون من DesignSystem.kt أو AppColors.kt
    """
    import re
    return (
        rf'((?:BridgeThemeRegistry\.getColor\("{re.escape(key)}",\s*Color\(|val\s+{re.escape(key)}\s*(?::\s*Color)?\s*=\s*Color\())'
        rf'(0x[0-9A-Fa-f]+)'
        rf'(\))'
    )


def _find_color_file_for_key(key: str, project_root: Optional[Path] = None) -> Optional[Path]:
    import re
    from core.project_root import get_project_root
    root = project_root or get_project_root()
    pattern = _build_color_pattern(key)

    candidates = ["DesignSystem.kt", "AppColors.kt", "Theme.kt", "Color.kt", "Colors.kt"]
    for name in candidates:
        for f in root.rglob(name):
            s = str(f)
            if "build" in s or ".composebridge-state" in s or "composebridge-agent" in s:
                continue
            try:
                content = f.read_text(encoding="utf-8")
                if re.search(pattern, content):
                    return f
            except Exception:
                pass

    for f in root.rglob("*.kt"):
        s = str(f)
        if "build" in s or ".composebridge-state" in s or "composebridge-agent" in s:
            continue
        try:
            content = f.read_text(encoding="utf-8")
            if re.search(pattern, content):
                return f
        except Exception:
            pass

    return None


def update_theme_color(key: str, new_hex: str) -> tuple:
    """
    يعدّل قيمة لون في AppColors.kt أو DesignSystem.kt.

    Args:
        key: اسم اللون (مثل "GoldPrimary" أو "Primary")
        new_hex: القيمة الجديدة (مثل "#FF0000" أو "0xFFFF0000")

    Returns:
        (success, message, info)
    """
    import shutil
    import tempfile
    import os
    import re

    file_path = _find_color_file_for_key(key)
    if not file_path or not file_path.exists():
        if APP_COLORS_FILE.exists():
            file_path = APP_COLORS_FILE
        else:
            return (False, f"Color file not found for key: {key}", None)

    # 1. طبّع القيمة
    cleaned = new_hex.removeprefix("#").removeprefix("0x").removeprefix("0X").strip()
    if len(cleaned) == 6:
        cleaned = "FF" + cleaned
    elif len(cleaned) != 8:
        return (False, f"Invalid hex: {new_hex}", None)

    normalized_hex = f"0x{cleaned.upper()}"

    # 2. اقرأ الملف
    with open(file_path, "r", encoding="utf-8", newline="") as f:
        content = f.read()

    # 3. ابحث عن النمط
    pattern = _build_color_pattern(key)
    match = re.search(pattern, content)

    if not match:
        return (False, f"Pattern not found for key: {key}", None)

    old_hex = match.group(2)

    if old_hex.upper() == normalized_hex.upper():
        return (True, f"No change needed for {key}", {
            "key": key,
            "old_hex": old_hex,
            "new_hex": normalized_hex,
        })

    # 4. استبدل
    new_content = content[:match.start(2)] + normalized_hex + content[match.end(2):]

    # 5. نسخة احتياطية
    backup_path = str(file_path) + ".bridge.bak"
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
        f"Updated {key}: {old_hex} → {normalized_hex}",
        {
            "key": key,
            "old_hex": old_hex,
            "new_hex": normalized_hex,
            "backup": backup_path,
        }
    )


def is_theme_color_property(property_name: str) -> bool:
    """يتحقق إذا كانت الخاصية لون ثيم."""
    return property_name.startswith("AppColors.") or property_name in (
        "PrimaryDark", "SecondaryDark", "SurfaceDark",
        "GoldLight", "GoldPrimary", "GoldDeep",
        "PrimaryLight", "SecondaryLight", "SurfaceLight",
        "BlueVibrant", "OrangeVibrant", "RedVibrant", "GreenVibrant",
        "TextDark", "TextLight", "TextSecondary", "Error", "Success"
    )


def extract_theme_key(property_name: str) -> str:
    """يستخرج اسم اللون من 'AppColors.GoldPrimary'."""
    return property_name.removeprefix("AppColors.")


def update_color(token_name: str, value: str) -> tuple:
    """
    Update color token in source file and return (success, message).
    """
    res = update_theme_color(token_name, value)
    return res[0], res[1]

