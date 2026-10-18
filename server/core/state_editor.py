import os
"""
State Editor — يعدّل القيم الافتراضية في BridgeState.kt
عندما يغيّر المستخدم قيمة، نحفظها في الملف لتبقى بعد إعادة البناء.
"""

import json
import time
import sys
from pathlib import Path
from typing import Optional

# استورد من ast_finder
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ast_finder import parse_file, find_all_call_expressions
from core.utils import read_file_as_utf8
from core.write_lock import acquire_write_lock


def with_write_lock(func):
    """Decorator to run function inside shared write lock."""
    def wrapper(*args, **kwargs):
        with acquire_write_lock():
            return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ============================================================
# مسار BridgeState.kt وثوابت Journal
# ============================================================

from core.project_root import get_project_root
PROJECT_ROOT = get_project_root()
JOURNAL_FILE = PROJECT_ROOT / ".composebridge-journal.json"
MAX_JOURNAL = 50
def get_config_paths() -> dict:
    """Load path mappings from composebridge.json if available."""
    root = get_project_root()
    for candidate in [
        root / "composebridge.json",
        Path.cwd() / "composebridge.json",
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
    return PROJECT_ROOT / "app" / "src" / "main" / "java" / "com" / "student" / "app" / "ui" / "theme" / "AppColors.kt"


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
    return PROJECT_ROOT / "app" / "src" / "main" / "java" / "com" / "student" / "app" / "ui" / "theme" / "AppTypography.kt"


BRIDGE_STATE_FILE = get_bridge_state_file()
APP_COLORS_FILE = get_app_colors_file()
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


# ============================================================
# تحويل القيم
# ============================================================

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


# ============================================================
# تعديل الملف
# ============================================================

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


@with_write_lock
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

    # 4. أنشئ نسخة احتياطية
    backup_path = str(file_path) + ".bridge.bak"
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

    return (False, f"Write failed: {e}", None)

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


# ============================================================
# تعديل ألوان AppColors.kt
# ============================================================

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


@with_write_lock
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


# ============================================================
# تعديل Typography
# ============================================================

@with_write_lock
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


# ============================================================
# تعديل الأبعاد مباشرة بـ .dp
# ============================================================

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


# ============================================================
# تعديل قيمة Token الافتراضية في BridgeSpacing.kt
# ============================================================

@with_write_lock
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

    file_path = (
        PROJECT_ROOT
        / "app"
        / "src"
        / "main"
        / "java"
        / "com"
        / "student"
        / "app"
        / "ui"
        / "theme"
        / "AppDimens.kt"
    )

    if not file_path.exists():
        return (False, f"AppDimens.kt not found: {file_path}", None)

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


SPLICE_JOURNAL = []


def _journal_save(file_path, original_content, new_content):
    entry = {
        "file": str(file_path),
        "original": original_content,
        "new": new_content,
        "timestamp": time.time(),
    }

    # In-memory
    SPLICE_JOURNAL.append(entry)
    if len(SPLICE_JOURNAL) > MAX_JOURNAL:
        SPLICE_JOURNAL.pop(0)

    # Disk (.composebridge-journal.json)
    try:
        with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        sys.stderr.write(f"[journal] failed to persist: {e}\n")

    # Line number & difference
    old_lines = original_content.splitlines()
    new_lines = new_content.splitlines()
    changed_line = 1
    old_line_text = ""
    new_line_text = ""
    for idx, (l1, l2) in enumerate(zip(old_lines, new_lines)):
        if l1 != l2:
            changed_line = idx + 1
            old_line_text = l1
            new_line_text = l2
            break

    rel_path = str(file_path)
    try:
        rel_path = str(Path(file_path).relative_to(PROJECT_ROOT)).replace("\\", "/")
    except Exception:
        rel_path = str(file_path).replace("\\", "/")

    # 1. Record in PatternJournal for IDE
    try:
        from core.pattern_journal import PatternJournal
        pj = PatternJournal(PROJECT_ROOT)
        pj.record_change(
            file=rel_path,
            line=changed_line,
            old_line=old_line_text,
            new_line=new_line_text,
            pattern_id="cli_edit",
        )
    except Exception as e:
        sys.stderr.write(f"[journal] failed to record in PatternJournal: {e}\n")

    # 2. Record in pending_edits.json
    try:
        pending_paths = [
            PROJECT_ROOT / ".composebridge-state" / "pending_edits.json",
            PROJECT_ROOT / "pending_edits.json",
        ]
        for ppath in pending_paths:
            ppath.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if ppath.exists():
                try:
                    with open(ppath, "r", encoding="utf-8") as pf:
                        existing = json.load(pf)
                except Exception:
                    existing = []
            if not isinstance(existing, list):
                existing = []

            filtered = [item for item in existing if item.get("file") != rel_path and Path(item.get("file", "")).name != Path(file_path).name]
            filtered.append({
                "file": rel_path,
                "backup": str(file_path) + ".bridge.bak",
                "timestamp": time.time(),
                "line": changed_line,
                "old": old_line_text,
                "new": new_line_text,
            })
            with open(ppath, "w", encoding="utf-8") as pf:
                json.dump(filtered, pf, indent=2, ensure_ascii=False)
    except Exception as e:
        sys.stderr.write(f"[journal] failed to save pending_edits: {e}\n")



def _validate_after_splice(file_path):
    from core.ast_finder import validate_file_parses
    if not validate_file_parses(file_path):
        if SPLICE_JOURNAL:
            last = SPLICE_JOURNAL[-1]
            Path(last["file"]).write_text(last["original"], encoding="utf-8")
        return False
    return True


@with_write_lock
def rollback_last():
    # إذا الذاكرة فارغة — اقرأ من القرص
    if not SPLICE_JOURNAL:
        if not JOURNAL_FILE.exists():
            return False

        try:
            with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if not lines:
                return False

            # آخر entry
            last = json.loads(lines[-1])
            SPLICE_JOURNAL.append(last)
        except Exception as e:
            sys.stderr.write(f"[journal] failed to read: {e}\n")
            return False

    # تراجع
    last = SPLICE_JOURNAL.pop()
    Path(last["file"]).write_text(last["original"], encoding="utf-8")

    # احذف آخر سطر من الملف
    try:
        if JOURNAL_FILE.exists():
            with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[:-1])
    except Exception:
        pass

    return True


# ⭐ Update color token in source file and return (success, message)
@with_write_lock
def update_color(token_name: str, value: str) -> tuple:
    """
    Update color token in source file and return (success, message).
    """
    res = update_theme_color(token_name, value)
    return res[0], res[1]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ComposeBridge State Editor CLI")
    parser.add_argument("action", nargs="?", default="update_theme_color",
                        choices=["update_theme_color", "update_color", "update_dimension", "rollback", "apply_state"],
                        help="Action to perform")
    parser.add_argument("--key", type=str, help="Color or Token key (e.g. GoldPrimary or Primary)")
    parser.add_argument("--value", type=str, help="New value (e.g. #FFD700 or 150)")
    parser.add_argument("--file", type=str, help="Source file relative path")
    parser.add_argument("--line", type=int, default=1, help="Line number")
    parser.add_argument("--old", type=str, help="Old value")
    parser.add_argument("--new", type=str, help="New value")

    args = parser.parse_args()

    if args.action in ("update_theme_color", "update_color"):
        if not args.key or not args.value:
            print("Error: --key and --value required for " + args.action)
            sys.exit(1)
        res = update_theme_color(args.key, args.value)
        print(json.dumps({"success": res[0], "message": res[1], "info": res[2]}, indent=2, ensure_ascii=False))
        sys.exit(0 if res[0] else 1)
    elif args.action == "rollback":
        res = rollback_last()
        print(json.dumps({"success": res, "message": "Rollback completed" if res else "Rollback failed"}))
        sys.exit(0 if res else 1)
    elif args.action == "apply_state":
        if not args.key or not args.value:
            print("Error: --key and --value required for apply_state")
            sys.exit(1)
        res = apply_state_update(args.key, args.value)
        print(json.dumps({"success": res[0], "message": res[1], "info": res[2]}, indent=2, ensure_ascii=False))
        sys.exit(0 if res[0] else 1)
    elif args.action == "update_dimension":
        if not args.file or not args.old or not args.new:
            print("Error: --file, --old, and --new required for update_dimension")
            sys.exit(1)
        res = edit_dimension_in_source(args.file, args.line, 0, 0, args.old, args.new)
        print(json.dumps({"success": res[0], "message": res[1], "info": res[2]}, indent=2, ensure_ascii=False))
        sys.exit(0 if res[0] else 1)
