"""
Theme Indexer — Indexes AppColors.kt and AppStrings.kt
 : color value → token key
"""

import re
from pathlib import Path
from typing import Optional


# ============================================================
# Path 
# ============================================================

PROJECT_ROOT = Path(r"C:\Users\thinkpad\StudioProjects\StudentApp")
THEME_DIR = (
 PROJECT_ROOT / "app" / "src" / "main"
 / "java" / "com" / "student" / "app" / "ui" / "theme"
)
APP_COLORS_FILE = THEME_DIR / "AppColors.kt"


# ============================================================
# 
# ============================================================

# :
# val SurfaceDark: Color get() = BridgeThemeRegistry.getColor("SurfaceDark", Color(0xFF02173B).copy(alpha = 0.8f))
COLOR_PATTERN = re.compile(
 r'val\s+(\w+)\s*:\s*Color\s+get\(\)\s*=\s*'
 r'BridgeThemeRegistry\.getColor\('
 r'"([^"]+)"\s*,\s*Color\((0x[0-9A-Fa-f]+)\)'
 r'(?:\.copy\([^)]+\))?'
)


# ============================================================
# Index structure
# ============================================================

class ThemeIndex:
 """ Theme Tokens ."""

 def __init__(self):
 # token_key → {"name": "PrimaryDark", "hex": "0xFF010D2A", "kind": "color"}
 self.tokens = {}
 # reverse: hex → token_key
 self.reverse_color = {}

 def reload(self) -> bool:
 """Reloads AppColors.kt and updates index."""
 self.tokens.clear()
 self.reverse_color.clear()

 if not APP_COLORS_FILE.exists():
 print(f"[ThemeIndexer] ❌ File not found: {APP_COLORS_FILE}")
 return False

 content = APP_COLORS_FILE.read_text(encoding="utf-8")

 matches = COLOR_PATTERN.findall(content)

 for var_name, token_name, hex_value in matches:
 full_key = f"AppColors.{token_name}"

 # Check .copy() 
 after_match_pos = content.find(f'Color({hex_value})', 0) + len(f'Color({hex_value})')
 has_copy = content[after_match_pos:after_match_pos + 10].startswith('.copy')

 self.tokens[full_key] = {
 "var_name": var_name,
 "token_name": token_name,
 "hex": hex_value,
 "kind": "color",
 "has_copy": has_copy,
 }

 # Reverse: uppercase 
 self.reverse_color[hex_value.upper()] = full_key

 print(f"[ThemeIndexer] ✅ Indexed {len(self.tokens)} tokens")
 return True

 def find_token_by_color(self, hex_value: str) -> Optional[str]:
 """Finds token from color value."""
 cleaned = hex_value.upper()
 if not cleaned.startswith("0X"):
 cleaned = "0X" + cleaned
 return self.reverse_color.get(cleaned)

 def get_all_tokens(self) -> dict:
 """Returns all tokens."""
 return dict(self.tokens)

 def get_tokens_by_category(self) -> dict:
 """
 Returns categorized tokens:
 {
 "Dark": [...],
 "Light": [...],
 "Gold": [...],
 ...
 }
 """
 categories = {
 "Dark": [],
 "Light": [],
 "Gold": [],
 "Vibrant": [],
 "Text": [],
 "Status": [],
 "Other": [],
 }

 for key, info in self.tokens.items():
 name = info["token_name"]

 if "Dark" in name:
 categories["Dark"].append(key)
 elif "Light" in name:
 categories["Light"].append(key)
 elif "Gold" in name:
 categories["Gold"].append(key)
 elif "Vibrant" in name:
 categories["Vibrant"].append(key)
 elif "Text" in name:
 categories["Text"].append(key)
 elif name in ("Error", "Success"):
 categories["Status"].append(key)
 else:
 categories["Other"].append(key)

 # Remove empty categories
 return {k: v for k, v in categories.items() if v}


# ============================================================
# Singleton
# ============================================================

_INDEX = ThemeIndex()


def get_index() -> ThemeIndex:
 """Returns current index."""
 return _INDEX


def reload_index() -> bool:
 """Rebuilds index."""
 return _INDEX.reload()


# ============================================================
# Init
# ============================================================

def init():
 """Called on server startup."""
 _INDEX.reload()


if __name__ == "__main__":
 # Test
 init()
 print()
 print("=" * 60)
 print("Theme Index")
 print("=" * 60)
 for key, info in _INDEX.get_all_tokens().items():
 print(f" {key:40} → {info['hex']} (copy={info['has_copy']})")
 print()
 print(f"Total: {len(_INDEX.tokens)} tokens")
 print()
 print("Categories:")
 for cat, tokens in _INDEX.get_tokens_by_category().items():
 print(f" {cat}: {len(tokens)}")