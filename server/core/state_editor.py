"""
State Editor — Edits default values in BridgeState.kt
When user changes a value, we save it to file to persist across rebuilds.
"""

import sys
from pathlib import Path
from typing import Optional

# ast_finder
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ast_finder import parse_file, find_all_call_expressions
from core.utils import read_file_as_utf8


# ============================================================
# BridgeState.kt
# ============================================================

PROJECT_ROOT = Path(r"C:\Users\thinkpad\StudioProjects\StudentApp")
BRIDGE_STATE_FILE = (
 PROJECT_ROOT
 / "composebridge-agent"
 / "src"
 / "androidMain"
 / "kotlin"
 / "com"
 / "composebridge"
 / "agent"
 / "BridgeState.kt"
)

APP_COLORS_FILE = (
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
 / "AppColors.kt"
)

APP_TYPOGRAPHY_FILE = (
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
 / "AppTypography.kt"
)


# ============================================================
# : → Search File
# ============================================================

PROPERTY_PATTERNS = {
 # : (mutableStateOf\() ( )) ) (\))

 "cardPadding": r'(var\s+cardPadding[^\n]*?mutableStateOf\()(.+?)(\)\s*$)',
 "cardCornerRadius": r'(var\s+cardCornerRadius[^\n]*?mutableStateOf\()(.+?)(\)\s*$)',
 "cardBackgroundColor": r'(var\s+cardBackgroundColor[^\n]*?mutableStateOf\()(.+?)(\)\s*$)',
 "userNameFontSize": r'(var\s+userNameFontSize[^\n]*?mutableStateOf\()(.+?)(\)\s*$)',
 "userNameColor": r'(var\s+userNameColor[^\n]*?mutableStateOf\()(.+?)(\)\s*$)',
 "titleText": r'(var\s+titleText[^\n]*?mutableStateOf\()(.+?)(\)\s*$)',
 "titleFontSize": r'(var\s+titleFontSize[^\n]*?mutableStateOf\()(.+?)(\)\s*$)',
 "titleColor": r'(var\s+titleColor[^\n]*?mutableStateOf\()(.+?)(\)\s*$)',
 "columnPadding": r'(var\s+columnPadding[^\n]*?mutableStateOf\()(.+?)(\)\s*$)',
 "spacerHeight": r'(var\s+spacerHeight[^\n]*?mutableStateOf\()(.+?)(\)\s*$)',
}


# ============================================================
# Convert 
# ============================================================

def normalize_value(property_name: str, value: str) -> str:
 """
 Normalizes WebSocket value for mutableStateOf.

 : .
 : "80" → "80.dp" ( )
 """
 # 
 if property_name == "titleText":
 escaped = value.replace("\\", "\\\\").replace('"', '\\"')
 return f'"{escaped}"'

 # 
 if property_name in ("cardBackgroundColor", "userNameColor", "titleColor"):
 cleaned = value.removeprefix("#").removeprefix("0x").removeprefix("0X").strip()
 if len(cleaned) == 6:
 cleaned = "FF" + cleaned
 # ⚠️ — Color()
 return f"Color(0x{cleaned})"

 # (Dp)
 if property_name in ("cardPadding", "cardCornerRadius", "columnPadding", "spacerHeight"):
 # ".dp" → 
 if ".dp" in value:
 return value
 return f"{value}.dp"

 # 
 if property_name in ("userNameFontSize", "titleFontSize"):
 if ".sp" in value:
 return value
 return f"{value}.sp"

 return value


# ============================================================
# File
# ============================================================

def update_bridge_state(property_name: str, value: str) -> tuple:
 """
 Updates value in BridgeState.kt.

 Returns:
 (success, message, byte_range)
 """
 import re

 if property_name not in PROPERTY_PATTERNS:
 return (False, f"Unknown property: {property_name}", None)

 file_path = BRIDGE_STATE_FILE
 if not file_path.exists():
 return (False, f"File not found: {file_path}", None)

 # bytes ( )
 with open(file_path, "rb") as f:
 source_bytes = f.read()

 source_text = source_bytes.decode("utf-8")
 pattern = PROPERTY_PATTERNS[property_name]
 new_value = normalize_value(property_name, value)

 # ( re.MULTILINE $)
 match = re.search(pattern, source_text, flags=re.MULTILINE)
 if not match:
 return (False, f"Pattern not found for {property_name}", None)

 # : = Start = = End
 old_value = match.group(2)
 full_match_start = match.start()

 # bytes 
 prefix = match.group(1)
 value_start_in_match = len(prefix)
 value_end_in_match = value_start_in_match + len(old_value)

 byte_start = len(source_text[:full_match_start + value_start_in_match].encode("utf-8"))
 byte_end = len(source_text[:full_match_start + value_end_in_match].encode("utf-8"))

 return (True, new_value, {
 "file_path": str(file_path),
 "old_value": old_value,
 "new_value": new_value,
 "byte_start": byte_start,
 "byte_end": byte_end,
 })


def apply_state_update(property_name: str, value: str) -> tuple:
 """
 Applies update to file.

 Returns:
 (success, message, byte_range)
 """
 import shutil
 import tempfile
 import os

 # 1. Location
 result = update_bridge_state(property_name, value)
 if not result[0]:
 return result

 success, new_value_text, info = result
 file_path = Path(info["file_path"])
 byte_start = info["byte_start"]
 byte_end = info["byte_end"]
 old_value = info["old_value"]

 # 2. File
 with open(file_path, "rb") as f:
 source = f.read()

 # 3. 
 current = source[byte_start:byte_end].decode("utf-8")
 if current != old_value:
 return (False, f"Value mismatch: expected '{old_value}', found '{current}'", None)

 # 4. 
 backup_path = str(file_path) + ".bridge.bak"
 shutil.copy2(file_path, backup_path)

 # 5. 
 new_source = (
 source[:byte_start]
 + new_value_text.encode("utf-8")
 + source[byte_end:]
 )

 # 6. 
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
# AppColors.kt
# ============================================================

def _build_color_pattern(key: str) -> str:
 """
 regex pattern Extract AppColors.kt
 """
 import re
 return (
 rf'(BridgeThemeRegistry\.getColor\("{re.escape(key)}",\s*Color\()'
 rf'(0x[0-9A-Fa-f]+)'
 rf'(\))'
 )


def update_theme_color(key: str, new_hex: str) -> tuple:
 """
 AppColors.kt.

 Args:
 key: ( "GoldPrimary")
 new_hex: ( "#FF0000" "0xFFFF0000")

 Returns:
 (success, message, info)
 """
 import shutil
 import tempfile
 import os
 import re

 file_path = APP_COLORS_FILE
 if not file_path.exists():
 return (False, f"AppColors.kt not found: {file_path}", None)

 # 1. 
 cleaned = new_hex.removeprefix("#").removeprefix("0x").removeprefix("0X").strip()
 if len(cleaned) == 6:
 cleaned = "FF" + cleaned
 elif len(cleaned) != 8:
 return (False, f"Invalid hex: {new_hex}", None)

 normalized_hex = f"0x{cleaned.upper()}"

 # 2. File
 with open(file_path, "r", encoding="utf-8") as f:
 content = f.read()

 # 3. 
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

 # 4. 
 new_content = content[:match.start(2)] + normalized_hex + content[match.end(2):]

 # 5. 
 backup_path = str(file_path) + ".bridge.bak"
 shutil.copy2(file_path, backup_path)

 # 6. 
 try:
 with tempfile.NamedTemporaryFile(
 mode="w",
 encoding="utf-8",
 dir=file_path.parent,
 delete=False,
 prefix=file_path.name + ".tmp_",
 ) as tmp:
 tmp.write(new_content)
 tmp_path = tmp.name

 os.replace(tmp_path, file_path)
 except Exception as e:
 return (False, f"Write failed: {e}", None)

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
 """Checks if property is a theme color."""
 return property_name.startswith("AppColors.") or property_name in (
 "PrimaryDark", "SecondaryDark", "SurfaceDark",
 "GoldLight", "GoldPrimary", "GoldDeep",
 "PrimaryLight", "SecondaryLight", "SurfaceLight",
 "BlueVibrant", "OrangeVibrant", "RedVibrant", "GreenVibrant",
 "TextDark", "TextLight", "TextSecondary", "Error", "Success"
 )


def extract_theme_key(property_name: str) -> str:
 """Extracts color name from 'AppColors.GoldPrimary'."""
 return property_name.removeprefix("AppColors.")


# ============================================================
# Typography
# ============================================================

def update_typography_property(
 style_key: str,
 property_name: str,
 new_value: str,
) -> tuple:
 """
 Updates property inside TextStyle in AppTypography.kt.

 :
 style_key = "headlineLarge"
 property_name = "fontSize"
 new_value = "48"

 :
 headlineLarge = BridgeTypographyRegistry.getStyle(
 key = "headlineLarge",
 default = TextStyle(
 fontWeight = FontWeight.Bold,
 fontSize = 30.sp, ← 30 48
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

 with open(file_path, "r", encoding="utf-8") as f:
 content = f.read()

 # 1. block style
 # `key = "headlineLarge"` `)` 
 block_start_pattern = rf'key\s*=\s*"{re.escape(style_key)}"'
 block_match = re.search(block_start_pattern, content)

 if not block_match:
 return (False, f"Style '{style_key}' not found", None)

 # End : Location TextStyle(
 start_pos = block_match.start()
 textstyle_match = re.search(r'TextStyle\s*\(', content[start_pos:])

 if not textstyle_match:
 return (False, f"TextStyle not found for {style_key}", None)

 textstyle_start = start_pos + textstyle_match.start()

 # 
 textstyle_end_match = re.search(r'\n\s{8,12}\)', content[textstyle_start:])

 if not textstyle_end_match:
 return (False, f"TextStyle end not found for {style_key}", None)

 textstyle_end = textstyle_start + textstyle_end_match.start()
 block_content = content[textstyle_start:textstyle_end]

 # 2. 
 # fontSize = 30.sp → 30
 prop_pattern = rf'({re.escape(property_name)}\s*=\s*)(\d+(?:\.\d+)?)(\.sp)'
 prop_match = re.search(prop_pattern, block_content)

 if not prop_match:
 return (False, f"Property '{property_name}' not found in {style_key}", None)

 old_value = prop_match.group(2)

 # 3. 
 new_value_clean = new_value.replace(".sp", "").strip()
 if old_value == new_value_clean:
 return (True, f"No change needed for {style_key}.{property_name}", None)

 # 4. 
 new_block = (
 block_content[:prop_match.start(2)]
 + new_value_clean
 + block_content[prop_match.end(2):]
 )

 new_content = content[:textstyle_start] + new_block + content[textstyle_end:]

 # 5. 
 backup_path = str(file_path) + ".bridge.bak"
 shutil.copy2(file_path, backup_path)

 # 6. 
 try:
 with tempfile.NamedTemporaryFile(
 mode="w",
 encoding="utf-8",
 dir=file_path.parent,
 delete=False,
 prefix=file_path.name + ".tmp_",
 ) as tmp:
 tmp.write(new_content)
 tmp_path = tmp.name

 os.replace(tmp_path, file_path)
 except Exception as e:
 return (False, f"Write failed: {e}", None)

 return (
 True,
 f"Updated AppTypography.{style_key}.{property_name}: {old_value} → {new_value_clean}",
 {"backup": backup_path}
 )


def is_typography_property(property_name: str) -> bool:
 """Checks if property is Typography."""
 return property_name.startswith("AppTypography.")


def parse_typography_property(property_name: str) -> tuple:
 """
 "AppTypography.headlineLarge.fontSize"
 ("headlineLarge", "fontSize")
 """
 parts = property_name.removeprefix("AppTypography.").split(".")
 if len(parts) == 2:
 return (parts[0], parts[1])
 return (None, None)


# ============================================================
# .dp
# ============================================================

def edit_dimension_in_source(
 source_file: str,
 line_number: int,
 utf16_offset: int,
 utf16_length: int,
 old_value: str, # "24.dp"
 new_value: str, # "32.dp"
) -> tuple:
 """
 Edits specified .dp value in source file.
 """
 import re
 import shutil
 import tempfile
 import os

 full_path = PROJECT_ROOT / source_file
 if not full_path.exists():
 candidates = list(PROJECT_ROOT.rglob(Path(source_file).name))
 candidates = [c for c in candidates if 'build/' not in str(c)]
 if not candidates:
 return (False, f"File not found: {source_file}", None)
 full_path = candidates[0]

 with open(full_path, "r", encoding="utf-8") as f:
 content = f.read()

 # old_value new_value ( .dp)
 old_clean = old_value.replace(".dp", "").strip()
 new_clean = new_value.replace(".dp", "").strip()

 encoded = content.encode('utf-16-le')
 start_byte = utf16_offset * 2
 end_byte = (utf16_offset + utf16_length) * 2

 pattern = re.compile(rf'\b{re.escape(old_clean)}\.dp\b')

 # ⭐ offset (>0) sub-range 
 if utf16_offset > 0 and utf16_length > 0 and end_byte <= len(encoded) and start_byte < len(encoded):
 sub = encoded[start_byte:end_byte].decode('utf-16-le', errors='ignore')
 match = pattern.search(sub)
 if not match:
 # Fallback: File 
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
 # fallback: File ( )
 sub = content
 match = pattern.search(sub)
 if not match:
 return (False, f"Value {old_value} not found in file", None)
 new_text = sub[:match.start()] + f"{new_clean}.dp" + sub[match.end():]
 print(f"[state_editor] ⚠️ Used fallback (no offset) for {old_value}")

 # 
 backup_path = str(full_path) + ".bridge.bak"
 shutil.copy2(full_path, backup_path)

 # 
 try:
 with tempfile.NamedTemporaryFile(
 mode="w",
 encoding="utf-8",
 dir=full_path.parent,
 delete=False,
 prefix=full_path.name + ".tmp_",
 ) as tmp:
 tmp.write(new_text)
 tmp_path = tmp.name

 os.replace(tmp_path, full_path)
 except Exception as e:
 return (False, f"Write failed: {e}", None)

 return (
 True,
 f"Updated {source_file}:{line_number}: {old_value} → {new_value}",
 {"backup": backup_path}
 )


# ============================================================
# Token BridgeSpacing.kt
# ============================================================

def update_token_default(token_name: str, value: str) -> tuple:
 """
 Updates token default value in AppDimens.kt.

 :
 token_name = "cardHeight"
 value = "150"

 :
 get("cardHeight", 100.dp)
 :
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

 with open(file_path, "r", encoding="utf-8") as f:
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

 # : get("cardHeight", 100.dp) get("cardHeight", 100f)
 # ⭐ pattern : ( )
 pattern = re.compile(
 rf'(BridgeDimensionRegistry\.get\(\s*"{re.escape(token_name)}"\s*,\s*)(\d+)(\.dp|\.f)'
 )

 match = pattern.search(content)
 if not match:
 return (False, f"Token not found: {token_name}", None)

 old_value = match.group(2)

 # 
 new_text = (
 content[:match.start(2)]
 + clean_display
 + content[match.end(2):]
 )

 # 
 backup_path = str(file_path) + ".bridge.bak"
 shutil.copy2(file_path, backup_path)

 # 
 try:
 with tempfile.NamedTemporaryFile(
 mode="w",
 encoding="utf-8",
 dir=file_path.parent,
 delete=False,
 prefix=file_path.name + ".tmp_",
 ) as tmp:
 tmp.write(new_text)
 tmp_path = tmp.name

 os.replace(tmp_path, file_path)
 except Exception as e:
 return (False, f"Write failed: {e}", None)

 return (
 True,
 f"Updated {token_name}: {old_value} → {clean_display}",
 {"backup": backup_path}
 )