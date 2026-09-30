"""
Theme Indexer — يفهرس AppColors.kt و AppStrings.kt
يبني خريطة عكسية: color value → token key
"""

import re
import sys
from pathlib import Path
from typing import Optional


# ============================================================
# المسارات
# ============================================================

PROJECT_ROOT = Path(r"C:\Users\thinkpad\StudioProjects\StudentApp")
THEME_DIR = (
    PROJECT_ROOT / "app" / "src" / "main"
    / "java" / "com" / "student" / "app" / "ui" / "theme"
)
APP_COLORS_FILE = THEME_DIR / "AppColors.kt"


# ============================================================
# الأنماط
# ============================================================

# مثال:
#   val SurfaceDark: Color get() = BridgeThemeRegistry.getColor("SurfaceDark", Color(0xFF02173B).copy(alpha = 0.8f))
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
    """خريطة Theme Tokens في الذاكرة."""

    def __init__(self):
        # token_key → {"name": "PrimaryDark", "hex": "0xFF010D2A", "kind": "color"}
        self.tokens = {}
        # reverse: hex → token_key
        self.reverse_color = {}

    def reload(self) -> bool:
        """يعيد قراءة AppColors.kt ويحدّث الفهرس."""
        self.tokens.clear()
        self.reverse_color.clear()

        if not APP_COLORS_FILE.exists():
            sys.stderr.write(f"[ThemeIndexer] File not found: {APP_COLORS_FILE}\n")
            return False

        content = APP_COLORS_FILE.read_text(encoding="utf-8")

        matches = COLOR_PATTERN.findall(content)

        for var_name, token_name, hex_value in matches:
            full_key = f"AppColors.{token_name}"

            # تحقق من .copy() بعد القيمة
            after_match_pos = content.find(f'Color({hex_value})', 0) + len(f'Color({hex_value})')
            has_copy = content[after_match_pos:after_match_pos + 10].startswith('.copy')

            self.tokens[full_key] = {
                "var_name": var_name,
                "token_name": token_name,
                "hex": hex_value,
                "kind": "color",
                "has_copy": has_copy,
            }

            # Reverse: نستخدم uppercase للمقارنة
            self.reverse_color[hex_value.upper()] = full_key

        sys.stderr.write(f"[ThemeIndexer] Indexed {len(self.tokens)} tokens\n")
        return True

    def find_token_by_color(self, hex_value: str) -> Optional[str]:
        """يبحث عن token من قيمة لون."""
        if not self.tokens:
            self.reload()

        cleaned = hex_value.strip().removeprefix("#").removeprefix("0x").removeprefix("0X").upper()
        if len(cleaned) == 6:
            cleaned = "FF" + cleaned
        key = "0X" + cleaned
        return self.reverse_color.get(key)

    def get_all_tokens(self) -> dict:
        """يعيد كل التوكنات."""
        return dict(self.tokens)

    def get_tokens_by_category(self) -> dict:
        """
        يعيد التوكنات مصنفة:
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

        # أزل الفئات الفارغة
        return {k: v for k, v in categories.items() if v}


# ============================================================
# Singleton
# ============================================================

_INDEX = ThemeIndex()


def get_index() -> ThemeIndex:
    """يعيد الفهرس الحالي."""
    if not _INDEX.tokens:
        _INDEX.reload()
    return _INDEX


def reload_index() -> bool:
    """يعيد بناء الفهرس."""
    return _INDEX.reload()


# ============================================================
# Init
# ============================================================

def init():
    """يُستدعى عند بدء السيرفر."""
    _INDEX.reload()


if __name__ == "__main__":
    # اختبار
    init()
    print()
    print("=" * 60)
    print("Theme Index")
    print("=" * 60)
    for key, info in _INDEX.get_all_tokens().items():
        print(f"  {key:40} → {info['hex']} (copy={info['has_copy']})")
    print()
    print(f"Total: {len(_INDEX.tokens)} tokens")
    print()
    print("Categories:")
    for cat, tokens in _INDEX.get_tokens_by_category().items():
        print(f"  {cat}: {len(tokens)}")
