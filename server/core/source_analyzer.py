import os
# -*- coding: utf-8 -*-
"""
Source Analyzer — يحلل نطاق الكود المصدري للعنصر.
- يستخدم utf16Offset و utf16Length للعزل الدقيق
- يستخرج ألوان، خطوط، أبعاد، padding، ونسب مئوية وتوكنات BridgeSpacing
- يدعم Focus Mode: استخراج دقيق للألوان المستخدمة في العنصر مع usage_global و usage_in_element
- يدعم Split Token الذكي للعناصر
"""

import re
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple

try:
    from .project_root import get_project_root
    PROJECT_ROOT = get_project_root()
except Exception:
    PROJECT_ROOT = Path(os.environ.get("COMPOSEBRIDGE_ROOT", "."))


NAMED_COLORS_HEX = {
    "White": "#FFFFFF",
    "Black": "#000000",
    "LightGray": "#D3D3D3",
    "Gray": "#888888",
    "DarkGray": "#444444",
    "Red": "#EF4444",
    "Green": "#10B981",
    "Blue": "#3B82F6",
    "Yellow": "#F59E0B",
    "Cyan": "#06B6D4",
    "Magenta": "#D946EF",
    "Transparent": "#00000000",
    "Unspecified": "#00000000",
}

NAMED_COLOR_VARIANTS = {
    "FFFFFFFF": "Color.White",
    "FF000000": "Color.Black",
    "FF808080": "Color.Gray",
    "FFA9A9A9": "Color.DarkGray",
    "FFD3D3D3": "Color.LightGray",
    "FFFF0000": "Color.Red",
    "FF00FF00": "Color.Green",
    "FF0000FF": "Color.Blue",
    "FFFFFF00": "Color.Yellow",
    "FFFF00FF": "Color.Magenta",
    "FF00FFFF": "Color.Cyan",
    "00000000": "Color.Transparent",
}


def _normalize_color_literals(val: str, token_name: str = "") -> List[str]:
    """
    Generate all possible code representations of a color (hex or named).
    Returns list of exact search patterns ordered by specificity (longest first).
    """
    if not val:
        return []
    val_clean = val.strip().replace('"', '').replace("'", "")
    named_candidate = None
    if val_clean.startswith("Color."):
        named_candidate = val_clean.split(".")[1]
    elif val_clean in NAMED_COLORS_HEX:
        named_candidate = val_clean

    if named_candidate and named_candidate in NAMED_COLORS_HEX:
        hex_val = NAMED_COLORS_HEX[named_candidate].lstrip("#")
    elif val_clean.startswith("Color(0x") or val_clean.startswith("Color(0X"):
        m = re.search(r'0x([0-9A-Fa-f]+)', val_clean, re.IGNORECASE)
        hex_val = m.group(1) if m else val_clean.lstrip("#")
    elif val_clean.startswith("0x") or val_clean.startswith("0X"):
        hex_val = val_clean[2:]
    else:
        hex_val = val_clean.lstrip("#")

    hex_clean = hex_val.upper()
    if len(hex_clean) == 6:
        hex_argb = f"FF{hex_clean}"
    elif len(hex_clean) == 8:
        hex_argb = hex_clean
        hex_clean = hex_clean[2:]
    else:
        hex_argb = hex_clean

    variants = []
    if hex_argb:
        variants.append(f"Color(0x{hex_argb})")
        variants.append(f"Color(0x{hex_argb.lower()})")
        variants.append(f"Color(0xFF{hex_clean.lower()})")
    if hex_clean:
        variants.append(f"Color(0x{hex_clean})")
        variants.append(f"Color(0x{hex_clean.lower()})")
    if hex_argb in NAMED_COLOR_VARIANTS:
        variants.append(NAMED_COLOR_VARIANTS[hex_argb])
    if val_clean.startswith("Color."):
        variants.append(val_clean)
    if token_name:
        variants.append(f"AppColors.{token_name}")
    if re.match(r'^[A-Za-z]\w*$', val_clean) and not val_clean.startswith("0x") and not val_clean.startswith("Color"):
        variants.append(f"AppColors.{val_clean}")

    seen = set()
    unique_variants = []
    for v in sorted(variants, key=len, reverse=True):
        if v and v not in seen:
            seen.add(v)
            unique_variants.append(v)
    return unique_variants


_USAGE_GLOBAL_CACHE = {
    "project_path": None,
    "timestamp": 0,
    "counts": {},
}


def _clean_hex(val: str) -> str:
    """Converts 0xFF818CF8 or #818CF8 to clean #RRGGBB."""
    val = val.strip().replace('"', '').replace("'", "")
    if val.startswith("0x") or val.startswith("0X"):
        h = val[2:]
        if len(h) == 8:
            return f"#{h[2:].upper()}"
        elif len(h) == 6:
            return f"#{h.upper()}"
        return f"#{h.upper()}"
    if val.startswith("#"):
        return val.upper()
    return f"#{val.upper()}"


def get_token_value_map(project_root: Path) -> Dict[str, str]:
    """Reads DesignSystem.kt / AppColors.kt and returns token_name -> hex_value."""
    token_map = {}
    candidates = list(project_root.rglob("DesignSystem.kt")) + list(project_root.rglob("AppColors.kt"))
    candidates = [c for c in candidates if "build" not in str(c) and ".composebridge" not in str(c)]
    
    pattern = re.compile(
        r'val\s+(\w+)\s*:\s*Color[\s\r\n]*get\(\)\s*=\s*'
        r'BridgeThemeRegistry\.getColor\('
        r'"[^"]+"\s*,\s*([^)]+)\)'
    )
    
    for c in candidates:
        try:
            txt = c.read_text(encoding="utf-8")
            for line in txt.splitlines():
                if "BridgeThemeRegistry.getColor" not in line:
                    continue
                name_m = re.search(r'val\s+(\w+)\s*:\s*Color', line)
                if not name_m:
                    continue
                tname = name_m.group(1)
                
                # Check Color(0xFF...)
                hex_m = re.search(r'Color\s*\(\s*(0x[0-9A-Fa-f]+)', line)
                if hex_m:
                    token_map[tname] = _clean_hex(hex_m.group(1))
                    continue
                # Check Color.White / Color.LightGray
                named_m = re.search(r'Color\.(\w+)', line)
                if named_m and named_m.group(1) in NAMED_COLORS_HEX:
                    token_map[tname] = NAMED_COLORS_HEX[named_m.group(1)]
                    continue
                token_map[tname] = "#818CF8"
        except Exception:
            pass
            
    return token_map


def get_global_usage_counts(project_root: Path) -> Dict[str, int]:
    """
    Counts occurrences of tokens and colors project-wide with a 60-second in-memory cache.
    """
    global _USAGE_GLOBAL_CACHE
    now = time.time()
    if (
        _USAGE_GLOBAL_CACHE["project_path"] == str(project_root)
        and (now - _USAGE_GLOBAL_CACHE["timestamp"]) < 60
        and _USAGE_GLOBAL_CACHE["counts"]
    ):
        return _USAGE_GLOBAL_CACHE["counts"]

    counts: Dict[str, int] = {}
    for kt_file in project_root.rglob("*.kt"):
        s = str(kt_file)
        if "build" in s or ".composebridge" in s or ".gradle" in s or "DesignSystem.kt" in s or "AppColors.kt" in s:
            continue
        try:
            txt = kt_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Count tokens: AppColors.(\w+)
        for m in re.finditer(r'\bAppColors\.(\w+)\b', txt):
            tok = m.group(1)
            counts[f"AppColors.{tok}"] = counts.get(f"AppColors.{tok}", 0) + 1
            counts[tok] = counts.get(tok, 0) + 1

        # Count named colors
        for m in re.finditer(r'\bColor\.(White|Black|LightGray|Gray|DarkGray|Red|Green|Blue|Yellow|Cyan|Magenta|Transparent)\b', txt):
            col = m.group(0)
            counts[col] = counts.get(col, 0) + 1
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1

        # Count literals
        for m in re.finditer(r'Color\s*\(\s*(0x[0-9A-Fa-f]+)\s*\)', txt):
            raw_hex = _clean_hex(m.group(1))
            counts[raw_hex] = counts.get(raw_hex, 0) + 1
            counts[f"Color({m.group(1)})"] = counts.get(f"Color({m.group(1)})", 0) + 1

    _USAGE_GLOBAL_CACHE["project_path"] = str(project_root)
    _USAGE_GLOBAL_CACHE["timestamp"] = now
    _USAGE_GLOBAL_CACHE["counts"] = counts
    return counts


def _detect_property(line: str) -> str:
    """Detects Compose color property name from code line."""
    prop_patterns = [
        (r'\bc1\s*[=:]', "c1"),
        (r'\bc2\s*[=:]', "c2"),
        (r'\bcontainerColor\s*[=:]', "containerColor"),
        (r'\bcontentColor\s*[=:]', "contentColor"),
        (r'\bdisabledContainerColor\s*[=:]', "disabledContainerColor"),
        (r'\bdisabledContentColor\s*[=:]', "disabledContentColor"),
        (r'\.background\s*\(|\bbackground\s*[=:]', "background"),
        (r'\.tint\s*\(|\btint\s*[=:]|\biconColor\s*[=:]', "tint"),
        (r'BorderStroke\s*\(|\bborder\s*[=:]|\.border\s*\(', "border"),
        (r'\btextColor\s*[=:]', "textColor"),
        (r'\.color\s*\(|\bcolor\s*[=:]', "color"),
    ]
    for pattern, name in prop_patterns:
        if re.search(pattern, line):
            return name
    return "color"


def _detect_composable_name(search_scope: str, fallback_line_content: str = "") -> str:
    """Detects Composable name of the current scope."""
    # 1. Composable function signature: fun QuickAccessCard(...)
    fun_m = re.search(r'\bfun\s+([A-Z]\w+)\s*\(', search_scope)
    if fun_m:
        return fun_m.group(1)
        
    # 2. Main Composable calls: Card(, Button(, Surface(, Box(, etc.
    call_m = re.search(r'\b([A-Z]\w+Card|[A-Z]\w+Widget|[A-Z]\w+Item|[A-Z]\w+Button|[A-Z]\w+Bar|[A-Z]\w+Header|Card|Surface|Button)\s*\(', search_scope)
    if call_m:
        return call_m.group(1)
        
    # 3. Fallback from any Composable call
    any_m = re.search(r'\b([A-Z]\w+)\s*\(', fallback_line_content or search_scope)
    if any_m and any_m.group(1) not in {'Color', 'Modifier', 'Dp', 'TextStyle', 'Alignment', 'Arrangement'}:
        return any_m.group(1)
        
    return "Element"


def _find_color_locations(
    project_root: Path,
    hex_value: str,
    token_name: str = None,
) -> List[Dict]:
    """
    Find all locations where this color appears in the project.
    Returns: [{"file": "...", "line": N, "property": "..."}]
    """
    try:
        from core.project_scanner import ProjectScanner
        scanner = ProjectScanner(project_root)
        
        locations = []
        variants = _normalize_color_literals(hex_value, token_name or "")
        
        for kt_file in scanner.find_kt_files():
            if "backup" in str(kt_file).lower() or "build" in str(kt_file).lower():
                continue
            try:
                content = kt_file.read_text(encoding="utf-8")
                for i, line in enumerate(content.splitlines(), 1):
                    # تجاهل comments
                    if line.strip().startswith("//"):
                        continue
                    
                    for variant in variants:
                        if variant in line:
                            # استخرج property
                            property_match = re.search(
                                r'(\w+)\s*[=:]\s*' + re.escape(variant),
                                line,
                            )
                            prop = property_match.group(1) if property_match else _detect_property(line)
                            
                            locations.append({
                                "file": str(kt_file.relative_to(project_root)),
                                "line": i,
                                "property": prop,
                            })
                            break
            except Exception:
                continue
        
        return locations
    except Exception:
        return []


def _is_theme_dependent(color_name: str, value: str = "", is_token: bool = False, usage_global: int = 0) -> bool:
    """
    Detect if a color follows the theme (not editable directly).
    
    Cases:
    - MaterialTheme.colorScheme.X
    - AppColors.Background (or similar theme tokens)
    - Color.Transparent
    - Color.Unspecified
    - Color.copy(alpha=...) بدون token
    """
    name_lower = color_name.lower()
    val_lower = str(value).lower()
    
    # Material theme
    if "materialtheme" in name_lower or "colorscheme" in name_lower or "materialtheme" in val_lower or "colorscheme" in val_lower:
        return True
    
    # Transparent / Unspecified
    if color_name in ["Color.Transparent", "Color.Unspecified", "Transparent", "Unspecified"]:
        return True
    if name_lower in ["color.transparent", "color.unspecified", "transparent", "unspecified"]:
        return True
        
    # Color.copy without a standalone token or copy with alpha
    if ".copy(" in name_lower or ".copy(" in val_lower:
        return True
        
    # Theme tokens (Background, Surface, etc.) — لكن فقط إذا is_token=True
    # ⚠️ إذا is_token=True AND usage_global > 20 → theme-dependent
    clean_token = color_name.replace("AppColors.", "")
    if is_token and (clean_token in ["Background", "Surface", "Primary", "PrimaryLight", "PrimaryDark", "TextPrimary", "TextSecondary"] or usage_global > 20):
        return True
    
    return False


def _extract_composable_scope(
    content: str,
    composable_name: str,
    project_root: Optional[Path] = None,
    current_file: str = "",
) -> Tuple[str, int, int, str]:
    """
    Extract full Composable function body.
    Returns (scope_text, start_line, end_line, found_file).
    """
    lines = content.splitlines()
    
    # ابحث عن تعريف الدالة في نفس الملف
    start_idx = -1
    target_lines = lines
    found_file = current_file
    for i, line in enumerate(lines):
        if re.search(rf'\b(fun|private\s+fun|public\s+fun|internal\s+fun)\s+{re.escape(composable_name)}\s*\(', line):
            start_idx = i
            break
    
    # إذا لم نجدها في نفس الملف، ابحث في ملفات المشروع
    if start_idx < 0 and project_root:
        from core.project_scanner import ProjectScanner
        scanner = ProjectScanner(project_root)
        kt_finder = getattr(scanner, "find_kt_files", None) or getattr(scanner, "_find_kt_files")
        for kt_file in kt_finder():
            if "backup" in str(kt_file).lower() or "build" in str(kt_file).lower():
                continue
            try:
                c = kt_file.read_text(encoding="utf-8")
                c_lines = c.splitlines()
                for i, line in enumerate(c_lines):
                    if re.search(rf'\b(fun|private\s+fun|public\s+fun|internal\s+fun)\s+{re.escape(composable_name)}\s*\(', line):
                        start_idx = i
                        target_lines = c_lines
                        found_file = str(kt_file.relative_to(project_root)).replace("\\", "/")
                        break
                if start_idx >= 0:
                    break
            except Exception:
                continue

    if start_idx < 0:
        return "", 0, 0, ""
    
    # ابحث عن نهاية الدالة (accolades balancing)
    depth = 0
    end_idx = start_idx
    found_open = False
    
    for i in range(start_idx, len(target_lines)):
        line = target_lines[i]
        for ch in line:
            if ch == '{':
                depth += 1
                found_open = True
            elif ch == '}':
                depth -= 1
        
        if found_open and depth == 0:
            end_idx = i
            break
    
    scope_text = "\n".join(target_lines[start_idx:end_idx + 1])
    return scope_text, start_idx + 1, end_idx + 1, found_file


def _normalize_dim_value(val: str) -> List[str]:
    """
    Generate all possible representations of a dimension value.
    "24.0" -> ["24", "24.0", "24f", "24.0f"]
    "24.5" -> ["24.5", "24.5f"]
    """
    clean = str(val).replace(".dp", "").replace(".sp", "").strip()
    try:
        f = float(clean)
    except (ValueError, TypeError):
        return [clean]
    
    variants = []
    if f == int(f):
        int_val = int(f)
        variants.append(str(int_val))
        variants.append(f"{int_val}.0")
        variants.append(f"{int_val}f")
        variants.append(f"{int_val}.0f")
    else:
        variants.append(str(f))
        variants.append(f"{f}f")
    
    return variants


def _find_dimension_usage(project_root: Path, value: float, kind: str, kt_cache: Optional[List[Tuple[str, str]]] = None) -> Tuple[int, List[Dict]]:
    """ابحث عن كل استخدامات value.dp أو value.sp في المشروع مع مواقعها."""
    variants = _normalize_dim_value(str(value))
    count = 0
    locations = []
    
    if kt_cache is None:
        kt_cache = []
        for kt_file in project_root.rglob("*.kt"):
            if any(x in str(kt_file).lower() for x in ["build", "backup", ".composebridge", ".bak"]):
                continue
            try:
                kt_cache.append((str(kt_file.relative_to(project_root)).replace("\\", "/"), kt_file.read_text(encoding="utf-8")))
            except Exception:
                pass
                
    for rel_file, content in kt_cache:
        lines = content.splitlines()
        for line_idx, line in enumerate(lines, 1):
            found_in_line = False
            for variant in variants:
                pattern = rf'\b{re.escape(variant)}\.{kind}\b'
                matches = list(re.finditer(pattern, line))
                if matches:
                    count += len(matches)
                    if not found_in_line:
                        locations.append({
                            "file": rel_file,
                            "line": line_idx,
                            "property": "",
                        })
                        found_in_line = True
                        
    return count, locations


def _extract_dimensions_with_property(scope_text: str) -> List[Dict]:
    """
    Extract dimensions with their property (width, height, padding, etc.).
    Supports:
      1. Ternary + Registry: if (isDesktop) X.dp else BridgeDimensionRegistry.get("Key", Y.dp)
      2. Ternary normal: if (isDesktop) X.dp else Y.dp
      3. Direct Registry: BridgeDimensionRegistry.get("Key", X.dp)
      4. Simple: X.dp
    """
    dimensions = []
    processed_offsets = set()
    
    property_patterns = [
        ('height', r'\.height\('),
        ('width', r'\.width\('),
        ('size', r'\.size\('),
        ('cornerRadius', r'RoundedCornerShape\('),
        ('cornerRadius', r'cornerRadius\('),
        ('padding_horizontal', r'horizontal\s*=\s*'),
        ('padding_vertical', r'vertical\s*=\s*'),
        ('padding', r'\.padding\(\s*(?!horizontal|vertical)'),
        ('minHeight', r'\.heightIn\('),
        ('minWidth', r'\.widthIn\('),
        ('borderWidth', r'\.border\([^,]+,\s*'),
        ('fontSize', r'fontSize\s*=\s*'),
        ('letterSpacing', r'letterSpacing\s*=\s*'),
    ]
    
    for prop, prefix_pattern in property_patterns:
        for prefix_match in re.finditer(prefix_pattern, scope_text):
            prefix_end = prefix_match.end()
            rel_off = prefix_match.start()
            
            if rel_off in processed_offsets:
                continue
                
            snippet = scope_text[prefix_end:prefix_end + 200]
            depth = scope_text[:rel_off].count('{') - scope_text[:rel_off].count('}')
            
            # 1. Ternary + Registry
            reg_ternary_match = re.match(
                r'\s*if\s*\([^)]+\)\s*(\d+(?:\.\d+)?)\.(dp|sp)\s*else\s*BridgeDimensionRegistry\.get\(\s*"([^"]+)"\s*,\s*(\d+(?:\.\d+)?)\.(dp|sp)',
                snippet,
            )
            if reg_ternary_match:
                desktop_val = float(reg_ternary_match.group(1))
                registry_key = reg_ternary_match.group(3)
                mobile_val = float(reg_ternary_match.group(4))
                kind = reg_ternary_match.group(5)
                mob_str = str(int(mobile_val)) if mobile_val.is_integer() else str(mobile_val)
                dimensions.append({
                    "property": prop,
                    "value": f"{mob_str}.{kind}",
                    "number": mobile_val,
                    "kind": kind,
                    "relative_offset": rel_off,
                    "depth": depth,
                    "is_ternary": True,
                    "desktop_value": desktop_val,
                    "mobile_value": mobile_val,
                    "platform_target": "mobile",
                    "registry_key": registry_key,
                    "is_registry_wrapped": True,
                })
                processed_offsets.add(rel_off)
                continue
                
            # 2. Ternary normal
            ternary_match = re.match(
                r'\s*if\s*\([^)]+\)\s*(\d+(?:\.\d+)?)\.(dp|sp)\s*else\s*(\d+(?:\.\d+)?)\.(dp|sp)',
                snippet,
            )
            if ternary_match:
                desktop_val = float(ternary_match.group(1))
                mobile_val = float(ternary_match.group(3))
                kind = ternary_match.group(4)
                mob_str = str(int(mobile_val)) if mobile_val.is_integer() else str(mobile_val)
                dimensions.append({
                    "property": prop,
                    "value": f"{mob_str}.{kind}",
                    "number": mobile_val,
                    "kind": kind,
                    "relative_offset": rel_off,
                    "depth": depth,
                    "is_ternary": True,
                    "desktop_value": desktop_val,
                    "mobile_value": mobile_val,
                    "platform_target": "mobile",
                    "registry_key": "",
                    "is_registry_wrapped": False,
                })
                processed_offsets.add(rel_off)
                continue
                
            # 3. Direct Registry
            reg_match = re.match(
                r'\s*BridgeDimensionRegistry\.get\(\s*"([^"]+)"\s*,\s*(\d+(?:\.\d+)?)\.(dp|sp)',
                snippet,
            )
            if reg_match:
                registry_key = reg_match.group(1)
                mobile_val = float(reg_match.group(2))
                kind = reg_match.group(3)
                mob_str = str(int(mobile_val)) if mobile_val.is_integer() else str(mobile_val)
                dimensions.append({
                    "property": prop,
                    "value": f"{mob_str}.{kind}",
                    "number": mobile_val,
                    "kind": kind,
                    "relative_offset": rel_off,
                    "depth": depth,
                    "is_ternary": False,
                    "mobile_value": mobile_val,
                    "registry_key": registry_key,
                    "is_registry_wrapped": True,
                })
                processed_offsets.add(rel_off)
                continue
                
            # 4. Simple literal
            simple_match = re.match(
                r'\s*(\d+(?:\.\d+)?)\.(dp|sp)',
                snippet,
            )
            if simple_match:
                val = float(simple_match.group(1))
                kind = simple_match.group(2)
                val_str = str(int(val)) if val.is_integer() else str(val)
                dimensions.append({
                    "property": prop,
                    "value": f"{val_str}.{kind}",
                    "number": val,
                    "kind": kind,
                    "relative_offset": rel_off,
                    "depth": depth,
                    "is_ternary": False,
                    "mobile_value": val,
                    "registry_key": "",
                    "is_registry_wrapped": False,
                })
                processed_offsets.add(rel_off)
                continue
                
    dimensions.sort(key=lambda x: x.get("relative_offset", 0))
    seen = set()
    unique = []
    for d in dimensions:
        key = (d["property"], d["value"], d.get("relative_offset", 0))
        if key not in seen:
            seen.add(key)
            unique.append(d)
    
    return unique


def _count_function_calls(
    project_root: Path,
    composable_name: str,
) -> int:
    """احسب عدد مرات استدعاء الدالة في المشروع."""
    count = 0
    pattern = rf'\b{re.escape(composable_name)}\s*\('
    
    for kt_file in project_root.rglob("*.kt"):
        if any(x in str(kt_file).lower() for x in ["build", "backup", ".bak", ".composebridge"]):
            continue
        try:
            content = kt_file.read_text(encoding="utf-8")
            # تجاهل تعريف الدالة نفسه
            content_no_def = re.sub(
                rf'\bfun\s+{re.escape(composable_name)}\s*\(',
                f'_DEF_{composable_name}_',
                content,
            )
            count += len(re.findall(pattern, content_no_def))
        except Exception:
            continue
    
    return count



def _resolve_app_strings_value(project_root: Path, ref_key: str) -> Optional[str]:
    """يبحث في AppStrings.kt عن قيمة المتغير المرجعي ويستخرج النص المبدئي."""
    try:
        candidates = list(project_root.rglob("AppStrings.kt"))
        candidates = [c for c in candidates if "build" not in str(c) and ".composebridge" not in str(c)]
        if not candidates:
            return None
        text = candidates[0].read_text(encoding="utf-8", errors="ignore")
        var_name = ref_key.split(".")[-1]
        for line in text.splitlines():
            if var_name in line and "val " in line:
                m = re.search(r'"([^"\\]*(?:\\.[^"\\]*)*)"', line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


def analyze_element_range(
    source_file: str,
    line_number: int,
    utf16_offset: int = 0,
    utf16_length: int = 0,
    project_root: Optional[Path] = None,
    tree: Optional[list] = None,
) -> dict:
    """
    Analyzes literal source code range of an element.
    Returns dimensions, tokens, literals, and structured Focus Mode color objects.
    """
    root = project_root or PROJECT_ROOT

    # ⭐ فحص tree لتحديد الملف الحقيقي للعنصر (إذا كان مضمناً من ملف آخر)
    actual_source_file = source_file
    actual_line_number = line_number
    if tree and isinstance(tree, list):
        for node in tree:
            if isinstance(node, dict):
                sf = node.get("sourceFile")
                if sf and sf != source_file and not sf.endswith(source_file):
                    sf_path = _find_file(sf, root)
                    if sf_path and sf_path.exists():
                        actual_source_file = sf
                        actual_line_number = node.get("line", line_number)
                        break

    full_path = _find_file(actual_source_file, root)
    if full_path is None:
        full_path = _find_file(source_file, root)
        actual_source_file = source_file

    if full_path is None:
        return _empty_result(error=f"File not found: {source_file}")

    try:
        content = full_path.read_text(encoding="utf-8")
    except Exception as e:
        return _empty_result(error=f"Read failed: {e}")

    # Extract literal range or line context
    start_line_in_file = 1
    if utf16_offset > 0 and utf16_length > 0 and actual_source_file == source_file:
        element_code = _extract_utf16_range(content, utf16_offset, utf16_length)
        if element_code:
            search_scope = element_code
            # Calculate line number where offset begins
            prefix = content.encode('utf-16-le')[:utf16_offset * 2].decode('utf-16-le', errors='ignore')
            start_line_in_file = prefix.count('\n') + 1
        else:
            search_scope, start_line_in_file = _line_context_with_start(content, actual_line_number)
    else:
        search_scope, start_line_in_file = _line_context_with_start(content, actual_line_number)

    if not search_scope:
        return _empty_result(error="Empty scope")

    scope_lines = search_scope.splitlines()

    # 1. Colors & Tokens
    token_pattern = re.compile(r'\bAppColors\.(\w+)\b')
    literal_pattern = re.compile(r'Color\s*\(\s*(0x[0-9A-Fa-f]+)\s*\)')
    named_pattern = re.compile(r'\bColor\.(White|Black|LightGray|Gray|DarkGray|Red|Green|Blue|Yellow|Cyan|Magenta|Transparent|Unspecified)\b')
    material_pattern = re.compile(r'\b(?:MaterialTheme\.)?colorScheme\.(\w+)\b')

    tokens = list(set(token_pattern.findall(search_scope)))
    literals = list(set(literal_pattern.findall(search_scope)))

    # Look up token hex values & global counts
    token_value_map = get_token_value_map(root)
    global_counts = get_global_usage_counts(root)

    # Line-by-line detailed color extraction
    element_color_occurrences: Dict[str, List[Dict]] = {}

    for idx, l_str in enumerate(scope_lines):
        line_no = start_line_in_file + idx
        prop = _detect_property(l_str)

        # AppColors tokens
        for m in token_pattern.finditer(l_str):
            t_name = m.group(1)
            t_hex = token_value_map.get(t_name, "#818CF8")
            occ_key = f"{t_name}::{prop}::{line_no}"
            if occ_key not in element_color_occurrences:
                element_color_occurrences[occ_key] = []
            element_color_occurrences[occ_key].append({
                "name": t_name,
                "value": t_hex,
                "is_token": True,
                "property": prop,
                "line": line_no,
            })

        # MaterialTheme colors (MaterialTheme.colorScheme.surface, etc.)
        for m in material_pattern.finditer(l_str):
            mat_name = m.group(0)
            rest_of_line = l_str[m.end():]
            copy_m = re.match(r'^\s*\.copy\s*\([^)]*\)', rest_of_line)
            if copy_m:
                mat_name = f"{mat_name}{copy_m.group(0)}"
            occ_key = f"{mat_name}::{prop}::{line_no}"
            if occ_key not in element_color_occurrences:
                element_color_occurrences[occ_key] = []
            element_color_occurrences[occ_key].append({
                "name": mat_name,
                "value": mat_name,
                "is_token": False,
                "property": prop,
                "line": line_no,
            })

        # Named colors (Color.White, Color.LightGray, etc.)
        for m in named_pattern.finditer(l_str):
            col_name = m.group(0)  # e.g. "Color.White"
            simple_name = m.group(1)
            col_hex = NAMED_COLORS_HEX.get(simple_name, "#FFFFFF")
            rest_of_line = l_str[m.end():]
            copy_m = re.match(r'^\s*\.copy\s*\([^)]*\)', rest_of_line)
            if copy_m:
                col_name = f"{col_name}{copy_m.group(0)}"
                col_hex = col_name
            occ_key = f"{col_name}::{prop}::{line_no}"
            if occ_key not in element_color_occurrences:
                element_color_occurrences[occ_key] = []
            element_color_occurrences[occ_key].append({
                "name": col_name,
                "value": col_hex,
                "is_token": False,
                "property": prop,
                "line": line_no,
            })

        # Literal colors Color(0xFF...)
        for m in literal_pattern.finditer(l_str):
            raw_hex = m.group(1)
            clean_val = _clean_hex(raw_hex)
            lit_name = f"Color({raw_hex})"
            rest_of_line = l_str[m.end():]
            copy_m = re.match(r'^\s*\.copy\s*\([^)]*\)', rest_of_line)
            if copy_m:
                lit_name = f"{lit_name}{copy_m.group(0)}"
                clean_val = lit_name
            occ_key = f"{lit_name}::{prop}::{line_no}"
            if occ_key not in element_color_occurrences:
                element_color_occurrences[occ_key] = []
            element_color_occurrences[occ_key].append({
                "name": lit_name,
                "value": clean_val,
                "is_token": False,
                "property": prop,
                "line": line_no,
            })

    # Build final structured color list for Focus Mode BottomSheet
    structured_colors = []
    for c_name, occs in element_color_occurrences.items():
        primary_occ = occs[0]
        usage_in_element = len(occs)
        
        # Determine global usage count
        if primary_occ["is_token"]:
            usage_global = global_counts.get(c_name, usage_in_element)
        else:
            clean_val = primary_occ["value"].upper()
            usage_global = global_counts.get(c_name, global_counts.get(clean_val, usage_in_element))

        usage_global = max(usage_global, usage_in_element)
        is_shared = usage_global > usage_in_element

        locations = _find_color_locations(
            root,
            primary_occ["value"],
            primary_occ["name"] if primary_occ["is_token"] else None,
        )

        is_theme_dep = _is_theme_dependent(
            color_name=primary_occ["name"],
            value=primary_occ["value"],
            is_token=primary_occ["is_token"],
            usage_global=usage_global,
        )

        structured_colors.append({
            "name": primary_occ["name"],
            "value": primary_occ["value"],
            "usage_global": usage_global,
            "usage_in_element": usage_in_element,
            "is_shared": is_shared,
            "is_token": primary_occ["is_token"],
            "property": primary_occ["property"],
            "line_in_element": primary_occ["line"],
            "occurrences_in_element": [{"line": o["line"], "property": o["property"]} for o in occs],
            "locations": locations[:50],
            "is_theme_dependent": is_theme_dep,
        })

    # Composable Name
    composable_name = _detect_composable_name(
        search_scope,
        fallback_line_content=content.splitlines()[line_number - 1] if 0 < line_number <= len(content.splitlines()) else ""
    )

    # ⭐ 1. ابحث عن Composable scope أولاً
    dim_scope_text = search_scope
    dim_scope_start_line = start_line_in_file
    effective_file = actual_source_file

    if composable_name and composable_name not in ["Box", "Column", "Row", "Text", "Icon", "Spacer", "_"]:
        comp_scope, comp_start, comp_end, comp_file = _extract_composable_scope(
            content, composable_name, root, current_file=actual_source_file
        )
        if comp_scope:
            dim_scope_text = comp_scope
            dim_scope_start_line = comp_start
            if comp_file:
                effective_file = comp_file

    # ⭐ 2. استخرج الأبعاد مع property
    dimensions_with_props = _extract_dimensions_with_property(dim_scope_text)

    # ⭐ 3. احسب line number لكل بُعد
    for d in dimensions_with_props:
        rel = d.get("relative_offset", 0)
        lines_before = dim_scope_text[:rel].count("\n")
        d["line"] = dim_scope_start_line + lines_before
        d["file"] = effective_file
        d["default_value"] = d["number"]
        d["current_value"] = d["number"]

    # ⭐ 4. تصفية الأبعاد حسب الـ depth: اعرض فقط depth <= 2 (البطاقة الخارجية)
    filtered_dims = [d for d in dimensions_with_props if d.get("depth", 1) <= 2]
    if not filtered_dims:
        filtered_dims = dimensions_with_props

    # ⭐ 5. حساب عدد مرات الاستخدام في المشروع (usage_global & is_shared & locations)
    kt_cache = []
    for kt_file in root.rglob("*.kt"):
        if any(x in str(kt_file).lower() for x in ["build", "backup", ".composebridge", ".bak"]):
            continue
        try:
            kt_cache.append((str(kt_file.relative_to(root)).replace("\\", "/"), kt_file.read_text(encoding="utf-8")))
        except Exception:
            pass

    # ⭐ احسب عدد الاستدعاءات للدالة
    call_count = 0
    if composable_name and composable_name not in ["Box", "Column", "Row", "Text", "Icon", "Surface", "Spacer", "_"]:
        call_count = _count_function_calls(root, composable_name)

    for d in filtered_dims:
        num = d.get("number", 0.0)
        kind = d.get("kind", "dp")
        u_count, u_locs = _find_dimension_usage(root, num, kind, kt_cache=kt_cache)
        d["usage_global"] = u_count
        d["is_shared"] = u_count > 1
        d["locations"] = u_locs
        d["in_shared_function"] = call_count > 1
        d["function_name"] = composable_name
        d["function_call_count"] = call_count

    # Bridge spacing tokens & typography
    bridge_token_pattern = re.compile(r'BridgeSpacing\.(\w+)')
    bridge_tokens = list(set(bridge_token_pattern.findall(dim_scope_text)))

    sps = [d["value"] for d in filtered_dims if d["kind"] == "sp"]
    weight_pattern = re.compile(r'FontWeight\.(\w+)')
    weights = list(set(weight_pattern.findall(dim_scope_text)))

    prop_pattern = re.compile(
        r'\.(background|padding|width|height|size|fillMaxWidth|fontSize|'
        r'lineHeight|letterSpacing|fontWeight|color|tint|containerColor|'
        r'cornerRadius|shape|border)\s*[=(]'
    )
    properties = list(set(prop_pattern.findall(dim_scope_text)))

    # ═══ Text Extraction ═══
    structured_texts = []
    seen_texts = set()

    # 1. Hardcoded text: Text("...") or Text(text = "...")
    hardcoded_text_pattern = re.compile(r'Text\s*\(\s*(?:text\s*=\s*)?"([^"\\]*(?:\\.[^"\\]*)*)"')
    for m in hardcoded_text_pattern.finditer(dim_scope_text):
        val = m.group(1).replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n')
        key = ("hardcoded", val)
        if key not in seen_texts and val.strip():
            seen_texts.add(key)
            offset_in_scope = m.start()
            line_in_scope = dim_scope_text[:offset_in_scope].count("\n")
            detected_line = (scope_start_line or line_number) + line_in_scope
            structured_texts.append({
                "text": val,
                "file": effective_file,
                "line": detected_line,
                "is_resource_or_ref": False,
                "ref_key": None,
            })

    # 2. Reference text: Text(AppStrings.xyz) or Text(text = AppStrings.xyz)
    ref_text_pattern = re.compile(r'Text\s*\(\s*(?:text\s*=\s*)?(AppStrings(?:\.[a-zA-Z0-9_]+)+)')
    for m in ref_text_pattern.finditer(dim_scope_text):
        ref_k = m.group(1)
        key = ("ref", ref_k)
        if key not in seen_texts:
            seen_texts.add(key)
            offset_in_scope = m.start()
            line_in_scope = dim_scope_text[:offset_in_scope].count("\n")
            detected_line = (scope_start_line or line_number) + line_in_scope
            resolved_val = _resolve_app_strings_value(project_root, ref_k)
            structured_texts.append({
                "text": resolved_val or ref_k,
                "file": effective_file,
                "line": detected_line,
                "is_resource_or_ref": True,
                "ref_key": ref_k,
            })

    # 3. Parameter/Variable text: Text(title) or Text(subtitle)
    var_text_pattern = re.compile(r'Text\s*\(\s*(?:text\s*=\s*)?([a-zA-Z0-9_]+)')
    for m in var_text_pattern.finditer(dim_scope_text):
        var_name = m.group(1)
        if var_name in ("modifier", "color", "style", "null", "true", "false", "it", "fontSize", "fontWeight"):
            continue
        # Find enclosing function
        abs_pos = content.find(dim_scope_text) + m.start() if dim_scope_text in content else m.start()
        before_code = content[:abs_pos]
        func_matches = list(re.finditer(r'fun\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)', before_code))
        if func_matches:
            last_func = func_matches[-1]
            func_name = last_func.group(1)
            params = last_func.group(2)
            if re.search(rf'\b{var_name}\b', params):
                # Search for calls to func_name in this file
                call_pattern = re.compile(rf'{func_name}\s*\((.*?)\)', re.DOTALL)
                for call_m in call_pattern.finditer(content):
                    call_body = call_m.group(1)
                    param_m = re.search(rf'{var_name}\s*=\s*([^\n,]+)', call_body)
                    if param_m:
                        arg_val = param_m.group(1).strip()
                        call_line = content[:call_m.start()].count("\n") + 1
                        if arg_val.startswith("AppStrings."):
                            ref_k = arg_val
                            resolved_val = _resolve_app_strings_value(project_root, ref_k)
                            key = ("ref", ref_k)
                            if key not in seen_texts:
                                seen_texts.add(key)
                                structured_texts.append({
                                    "text": resolved_val or ref_k,
                                    "file": effective_file,
                                    "line": call_line,
                                    "is_resource_or_ref": True,
                                    "ref_key": ref_k,
                                })
                        elif arg_val.startswith('"') and arg_val.endswith('"'):
                            raw_val = arg_val[1:-1].replace('\\"', '"').replace('\\\\', '\\')
                            key = ("hardcoded", raw_val)
                            if key not in seen_texts:
                                seen_texts.add(key)
                                structured_texts.append({
                                    "text": raw_val,
                                    "file": effective_file,
                                    "line": call_line,
                                    "is_resource_or_ref": False,
                                    "ref_key": None,
                                })

    return {
        "composable_name": composable_name,
        "texts": structured_texts,
        "source_file": effective_file,
        "colors": structured_colors,
        "tokens_used": [f"AppColors.{t}" for t in tokens],
        "literals": literals,
        "dimensions": [d["value"] for d in filtered_dims],
        "dimension_details": filtered_dims,
        "bridge_spacing_tokens": bridge_tokens,
        "font_sizes": list(set(sps))[:10],
        "font_weights": weights,
        "properties": properties,
        "composables": [composable_name],
        "scope_size": len(search_scope),
        "used_exact_range": utf16_offset > 0 and utf16_length > 0,
    }
RISKY_FILE_PATTERNS = [
    "ViewModel", "Repository", "DataSource", "Dao", "Database", 
    "Model", "Worker", "Service", "Entity", "Dto", "Test", "Preview"
]


def _ensure_app_colors_import(file_path: Path, content: str, app_colors_pkg: str = "") -> Tuple[str, bool, int, str]:
    """
    Ensure the file has an AppColors import.
    Returns (new_content, was_added, line_num, target_import).
    """
    pkg_match = re.search(r'^\s*package\s+([\w.]+)', content, re.MULTILINE)
    file_pkg = pkg_match.group(1) if pkg_match else ""

    if app_colors_pkg and file_pkg == app_colors_pkg:
        return content, False, 0, ""

    target_import = f"import {app_colors_pkg}.AppColors" if app_colors_pkg else "import com.edu.teacher.ui.theme.AppColors"
    wildcard_import = f"import {app_colors_pkg}.*" if app_colors_pkg else "import com.edu.teacher.ui.theme.*"

    import_patterns = [
        target_import,
        wildcard_import,
        "import com.edu.teacher.ui.theme.AppColors",
        "import com.edu.teacher.ui.theme.*",
        "import com.student.app.ui.theme.AppColors",
        "import com.student.app.ui.theme.*",
    ]
    for pattern in import_patterns:
        if pattern in content:
            return content, False, 0, ""

    lines = content.splitlines()
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("import "):
            last_import_idx = i

    if last_import_idx >= 0:
        lines.insert(last_import_idx + 1, target_import)
        return "\n".join(lines), True, last_import_idx + 2, target_import

    for i, line in enumerate(lines):
        if line.strip().startswith("package "):
            lines.insert(i + 1, "")
            lines.insert(i + 2, target_import)
            return "\n".join(lines), True, i + 3, target_import

    lines.insert(0, target_import)
    return "\n".join(lines), True, 1, target_import


def _is_safe_compose_file(file_rel_path: str, content: str) -> Tuple[bool, str]:
    """Check if the file is safe to replace Compose color tokens."""
    fname = Path(file_rel_path).name

    for p in RISKY_FILE_PATTERNS:
        if p in fname:
            return False, f"Risky pattern in filename ({p})"

    is_compose = (
        "androidx.compose" in content
        and ("@Composable" in content or "import androidx.compose.ui.graphics.Color" in content or "androidx.compose.ui" in content)
    )
    if not is_compose:
        return False, "Not a Compose UI file"

    return True, "Safe"


def _is_safe_line(line: str) -> bool:
    """Check if a line is safe for replacement."""
    stripped = line.strip()
    if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
        return False
    if "@ColorInt" in line or "toArgb()" in line or "android.graphics.Color" in line:
        return False
    return True


def preview_global_color_edit(
    old_value: str,
    project_root: Path,
) -> Dict:
    """Preview what will change before committing."""
    from core.project_scanner import ProjectScanner
    scanner = ProjectScanner(project_root)

    safe_occs = _find_all_occurrences(project_root, old_value)
    preview = {
        "total": len(safe_occs),
        "safe": safe_occs,
        "risky": [],
        "skipped": [],
    }

    clean_variations = _normalize_color_literals(old_value)
    kt_finder = getattr(scanner, "find_kt_files", None) or getattr(scanner, "_find_kt_files")
    for kt_file in kt_finder():
        if kt_file.name in ("DesignSystem.kt", "AppColors.kt", "Theme.kt"):
            continue
        rel_file = str(kt_file.relative_to(project_root))
        try:
            content = kt_file.read_text(encoding="utf-8")
            is_safe, reason = _is_safe_compose_file(rel_file, content)
            if not is_safe:
                for i, line in enumerate(content.splitlines(), 1):
                    if any(v in line for v in clean_variations):
                        preview["skipped"].append({
                            "file": rel_file,
                            "line": i,
                            "reason": reason,
                        })
        except Exception as e:
            preview["risky"].append({
                "file": rel_file,
                "error": str(e),
            })

    return {"success": True, "preview": preview}


def _hex_to_color_expr(hex_val: str) -> str:
    """Convert '#10B981' or 'Color(...)' to 'Color(0xFF...)'."""
    if not hex_val:
        return "Color.Transparent"
    if hex_val.startswith("Color("):
        return hex_val
    if hex_val.startswith("Color."):
        return hex_val
    
    hex_clean = hex_val.lstrip("#").upper()
    if hex_clean.startswith("0X"):
        hex_clean = hex_clean[2:]
    if len(hex_clean) == 6:
        hex_clean = "FF" + hex_clean
    elif len(hex_clean) == 3:
        hex_clean = "FF" + "".join(c * 2 for c in hex_clean)
    elif len(hex_clean) != 8:
        return "Color.Transparent"
    return f"Color(0x{hex_clean})"


def _is_valid_kotlin_identifier(name: str) -> bool:
    if not name:
        return False
    if not name[0].isalpha() and name[0] != '_':
        return False
    return all(c.isalnum() or c == '_' for c in name)


def _find_token_by_value(project_root: Path, hex_argb: str) -> Optional[str]:
    """Find a token with this color value in DesignSystem.kt. Returns token name ONLY if exactly 1 match, else None."""
    from core.token_migrator import TokenMigrator
    migrator = TokenMigrator(project_root)
    ds = migrator._find_design_system()
    if not ds or not ds.exists():
        return None
    
    content = ds.read_text(encoding="utf-8")
    hex_clean = hex_argb.lstrip("#").upper()
    if hex_clean.startswith("0X"):
        hex_clean = hex_clean[2:]
    if len(hex_clean) == 6:
        target_argb = "FF" + hex_clean
    else:
        target_argb = hex_clean

    matches = []
    for match in re.finditer(
        r'val\s+(\w+):\s*Color[\s\S]*?getColor\(\s*"(\w+)"\s*,\s*Color\(0x([0-9A-Fa-f]+)\)',
        content,
    ):
        token_val = match.group(3).upper()
        if len(token_val) == 6:
            token_val = "FF" + token_val
        if token_val == target_argb:
            matches.append(match.group(1))
    
    if len(matches) != 1:
        return None
    
    return matches[0]


def _update_existing_token(
    token_name: str,
    new_value: str,
    project_root: Path,
) -> Dict:
    """
    Update an existing token's default value in DesignSystem.kt.
    No source code changes needed — only the default value in DesignSystem.kt changes.
    """
    from core.token_migrator import TokenMigrator
    migrator = TokenMigrator(project_root)
    ds = migrator._find_design_system()
    
    if not ds or not ds.exists():
        return {"success": False, "error": "DesignSystem.kt not found"}
    
    content = ds.read_text(encoding="utf-8")
    new_color_expr = _hex_to_color_expr(new_value)
    
    # Match both BridgeThemeRegistry.getColor("token", ...) and getColor("token", ...)
    pattern = rf'((?:BridgeThemeRegistry\.)?getColor\(\s*"{re.escape(token_name)}"\s*,\s*)(?:Color\([^)]*\)|Color\.\w+|0x[0-9A-Fa-f]+|[^)]+?)\)'
    replacement = rf'\g<1>{new_color_expr})'
    
    new_content, count = re.subn(pattern, replacement, content)
    
    if count == 0:
        return {
            "success": False,
            "error": f"Could not update token '{token_name}' — pattern not found in DesignSystem.kt",
        }
    
    # PatternJournal recording
    old_line = ""
    new_line = ""
    target_line_no = 0
    for idx, line in enumerate(content.splitlines(), 1):
        if f'"{token_name}"' in line and 'getColor' in line:
            old_line = line.strip()
            target_line_no = idx
            break
    for line in new_content.splitlines():
        if f'"{token_name}"' in line and 'getColor' in line:
            new_line = line.strip()
            break
    
    ds.write_text(new_content, encoding="utf-8")
    
    try:
        from core.pattern_journal import PatternJournal
        journal = PatternJournal(project_root)
        journal.record_change(
            file=str(ds.relative_to(project_root)),
            line=target_line_no,
            old_line=old_line or "",
            new_line=new_line or f"{token_name} -> {new_color_expr}",
            pattern_id=f"update_token_{token_name}",
        )
    except Exception:
        pass
    
    return {
        "success": True,
        "token_name": token_name,
        "new_value": new_value.lstrip("#"),
        "value": new_value,
        "value_expr": new_color_expr,
        "updated": True,
        "message": f"تم تحديث قيمة {token_name} إلى {new_value}",
    }


def global_color_edit(
    file: str,
    line: int,
    old_value: str,
    new_value: str,
    token_name: str,
    project_root: Path,
    property_name: str = "all",
) -> Dict:
    """
    Global Color Edit:
    - If old_value is literal (#... or Color(...)): search literal occurrences only,
      replace literals with AppColors.<token>, and do NOT modify existing tokens.
    - If old_value is token (or matches token name): update only that single token in DesignSystem.kt.
    """
    try:
        from core.token_migrator import TokenMigrator
        from core.pattern_journal import PatternJournal
        
        migrator = TokenMigrator(project_root)
        journal = PatternJournal(project_root)
        
        ds_file = migrator._find_design_system()
        ds_content = ds_file.read_text(encoding="utf-8") if ds_file and ds_file.exists() else ""

        old_val_str = (old_value or "").strip()
        clean_token = (token_name or "").replace("AppColors.", "").strip()

        # Check if old_value is a literal color
        is_literal = (
            old_val_str.startswith("#")
            or old_val_str.startswith("Color(")
            or old_val_str.startswith("0x")
            or old_val_str.startswith("0X")
            or (len(old_val_str) in (6, 8) and all(c in "0123456789abcdefABCDEF" for c in old_val_str))
        )

        # Check if old_value or token_name matches an existing token in DesignSystem.kt
        is_token = False
        target_token_name = ""
        if not is_literal:
            clean_old = old_val_str.replace("AppColors.", "").strip()
            if _is_valid_kotlin_identifier(clean_old) and re.search(rf'\bval\s+{re.escape(clean_old)}\b', ds_content):
                is_token = True
                target_token_name = clean_old
            elif clean_token and _is_valid_kotlin_identifier(clean_token) and re.search(rf'\bval\s+{re.escape(clean_token)}\b', ds_content):
                is_token = True
                target_token_name = clean_token

        # ─── CASE 1: TOKEN EDIT (عدّل token واحد فقط — لا تبحث عن literals) ───
        if is_token:
            print(f"[OK] [UPDATE] Token {target_token_name}: {old_val_str} -> {new_value}")
            return _update_existing_token(
                token_name=target_token_name,
                new_value=new_value,
                project_root=project_root,
            )

        # ─── CASE 2: LITERAL EDIT (ابحث عن literal فقط واستبدله بـ token — لا تُعدِّل tokens موجودة) ───
        if clean_token and _is_valid_kotlin_identifier(clean_token):
            final_token_name = clean_token
        else:
            from core.name_suggester import NameSuggester
            final_token_name = NameSuggester().suggest_name(new_value, "color") or f"SuccessColor{int(time.time()) % 1000}"

        token_exists_in_ds = bool(re.search(rf'\bval\s+{re.escape(final_token_name)}\b', ds_content))

        # If token does NOT exist in DesignSystem.kt, create it
        if not token_exists_in_ds:
            new_expr = _hex_to_color_expr(new_value)
            create_result = migrator.create_color_token(
                token_name=final_token_name,
                value_expr=new_expr,
                original_value=new_expr,
            )
            if not create_result.get("success"):
                return create_result

        # AppColors package for imports
        app_colors_pkg = ""
        if ds_file and ds_file.exists():
            pkg_m = re.search(r'^\s*package\s+([\w.]+)', ds_content, re.MULTILINE)
            if pkg_m:
                app_colors_pkg = pkg_m.group(1)

        # Find literal occurrences only
        if property_name and property_name != "all":
            file_path = project_root / file
            if not file_path.exists():
                matches = [m for m in project_root.rglob(Path(file).name) if "build" not in str(m) and ".composebridge" not in str(m)]
                if matches:
                    file_path = matches[0]
            
            matched_var = old_value
            if file_path.exists():
                f_lines = file_path.read_text(encoding="utf-8").splitlines()
                if 1 <= line <= len(f_lines):
                    target_l = f_lines[line - 1]
                    for v in [f"Color(0xFF{old_value.lstrip('#')})", f"Color(0xff{old_value.lstrip('#').lower()})", old_value]:
                        if v in target_l:
                            matched_var = v
                            break
                    if matched_var not in target_l:
                        lit_m = re.search(r'Color\s*\(\s*0x[0-9A-Fa-f]+\s*\)|Color\.\w+', target_l)
                        if lit_m:
                            matched_var = lit_m.group(0)

            all_occurrences = [{
                "file": str(file_path.relative_to(project_root)) if file_path.exists() else file,
                "line": line,
                "property": property_name,
                "matched_variant": matched_var,
            }]
        else:
            all_occurrences = _find_all_occurrences(project_root, old_value, final_token_name)

        # Replace literal occurrences in source files
        replaced = 0
        errors = []
        skipped_files = []
        
        by_file: Dict[str, List[Dict]] = {}
        for occ in all_occurrences:
            f = occ["file"]
            if f not in by_file:
                by_file[f] = []
            by_file[f].append(occ)
        
        for f, occs in by_file.items():
            file_path = project_root / f
            if not file_path.exists():
                matches = list(project_root.rglob(Path(f).name))
                if not matches:
                    errors.append({"file": f, "error": "not found"})
                    continue
                file_path = matches[0]
            
            try:
                content = file_path.read_text(encoding="utf-8")
                is_safe, reason = _is_safe_compose_file(f, content)
                if not is_safe:
                    skipped_files.append({"file": f, "reason": reason})
                    continue

                lines = content.splitlines()
                file_replaced_in_this_file = False
                
                sorted_occs = sorted(occs, key=lambda x: x["line"], reverse=True)
                for occ in sorted_occs:
                    occ_line = occ["line"]
                    target_match = occ.get("matched_variant") or occ.get("target_match", old_value)
                    if occ_line < 1 or occ_line > len(lines):
                        continue
                    
                    cur_line = lines[occ_line - 1]
                    if not _is_safe_line(cur_line):
                        continue

                    if f"AppColors.{final_token_name}" in cur_line:
                        continue
                    
                    if target_match in cur_line:
                        new_line = cur_line.replace(target_match, f"AppColors.{final_token_name}")
                    else:
                        matched_in_line = None
                        for v in _normalize_color_literals(old_value, final_token_name):
                            if v and v in cur_line:
                                matched_in_line = v
                                break
                        if matched_in_line:
                            new_line = cur_line.replace(matched_in_line, f"AppColors.{final_token_name}")
                        else:
                            continue
                    
                    if new_line != cur_line:
                        lines[occ_line - 1] = new_line
                        journal.record_change(
                            file=f,
                            line=occ_line,
                            old_line=cur_line,
                            new_line=new_line,
                            pattern_id=f"global_color_{final_token_name}",
                        )
                        replaced += 1
                        file_replaced_in_this_file = True
                
                if file_replaced_in_this_file:
                    updated_content = "\n".join(lines)
                    updated_content, was_added, import_line, target_import = _ensure_app_colors_import(file_path, updated_content, app_colors_pkg)
                    if was_added:
                        journal.record_change(
                            file=f,
                            line=import_line,
                            old_line="",
                            new_line=target_import,
                            pattern_id=f"global_color_{final_token_name}",
                        )
                    file_path.write_text(updated_content + "\n", encoding="utf-8")
            
            except Exception as e:
                errors.append({"file": f, "error": str(e)})

        # ⚠️ Do NOT modify existing tokens in DesignSystem.kt when old_value was a literal

        if replaced == 0 and not token_exists_in_ds:
            return {
                "success": False,
                "error": f"لا توجد occurrences لـ {old_value}. ربما تم استبدالها بالفعل بـ token آخر.",
                "token_name": final_token_name,
                "hint": "حاول Reject All ثم أعد المحاولة",
                "replaced_count": 0,
                "files_affected": 0,
                "skipped": skipped_files,
                "errors": errors,
            }

        return {
            "success": True,
            "token_name": final_token_name,
            "new_value": new_value.lstrip("#"),
            "value": new_value,
            "value_expr": _hex_to_color_expr(new_value),
            "replaced_count": replaced,
            "files_affected": len([f for f in by_file if f not in [s["file"] for s in skipped_files]]),
            "skipped": skipped_files,
            "errors": errors,
            "created": not token_exists_in_ds,
            "updated": False,
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


def split_token_for_element(
    original_token: str,
    original_value: str,
    new_token_name: str,
    new_value: str,
    element_file: str,
    element_line: int,
    occurrences: List[Dict],
    project_root: Path,
) -> Dict:
    """
    Split: create token ONLY for this element + replace occurrences in scope.
    Other occurrences in project: unchanged.
    - If token exists with same name + value: reuse existing token.
    - If token exists with same name but different value: add numeric suffix.
    - If token is new: create it.
    """
    try:
        from core.token_migrator import TokenMigrator
        from core.pattern_journal import PatternJournal
        
        migrator = TokenMigrator(project_root)
        journal = PatternJournal(project_root)
        
        app_colors_pkg = ""
        ds_file = migrator._find_design_system()
        ds_content = ds_file.read_text(encoding="utf-8") if ds_file and ds_file.exists() else ""
        if ds_content:
            pkg_m = re.search(r'^\s*package\s+([\w.]+)', ds_content, re.MULTILINE)
            if pkg_m:
                app_colors_pkg = pkg_m.group(1)

        def _get_token_color_hex(tname: str) -> Optional[str]:
            m = re.search(
                rf'val\s+{re.escape(tname)}:\s*Color[\s\S]*?getColor\(\s*"{re.escape(tname)}"\s*,\s*Color\(0x([0-9A-Fa-f]+)\)',
                ds_content,
            )
            if m:
                val = m.group(1).upper()
                return "FF" + val if len(val) == 6 else val
            return None

        new_hex_clean = (new_value or "").lstrip("#").upper()
        if new_hex_clean.startswith("0X"):
            new_hex_clean = new_hex_clean[2:]
        if len(new_hex_clean) == 6:
            target_argb = "FF" + new_hex_clean
        else:
            target_argb = new_hex_clean

        final_token_name = new_token_name
        token_already_exists = False

        # ⭐ تحقق: هل token موجود؟
        if re.search(rf'\bval\s+{re.escape(final_token_name)}\b', ds_content):
            existing_val = _get_token_color_hex(final_token_name)
            if existing_val == target_argb:
                # Same name and same value: reuse existing token
                token_already_exists = True
            else:
                # Same name but different value: add suffix
                suffix = 2
                while True:
                    cand_name = f"{new_token_name}{suffix}"
                    if not re.search(rf'\bval\s+{re.escape(cand_name)}\b', ds_content):
                        final_token_name = cand_name
                        break
                    cand_val = _get_token_color_hex(cand_name)
                    if cand_val == target_argb:
                        final_token_name = cand_name
                        token_already_exists = True
                        break
                    suffix += 1

        original_expr = _hex_to_color_expr(original_value)
        new_expr = _hex_to_color_expr(new_value)
        
        # Create token only if it doesn't already exist
        if not token_already_exists:
            result = migrator.create_color_token(
                token_name=final_token_name,
                value_expr=new_expr,
                original_value=new_expr,
            )
            if not result.get("success"):
                return result
            print(f"[OK] [SPLIT] Token {final_token_name}: created")
        else:
            print(f"[OK] [SPLIT] Token {final_token_name}: already exists with matching value, reusing")

        # Find element file
        file_path = project_root / element_file
        if not file_path.exists() or "backup" in str(file_path).lower():
            clean_matches = [
                m for m in project_root.rglob(Path(element_file).name)
                if "build" not in str(m)
                and ".composebridge" not in str(m)
                and "backup" not in str(m).lower()
            ]
            if not clean_matches:
                return {"success": False, "error": f"File not found: {element_file}"}
            src_matches = [m for m in clean_matches if "src" in str(m).replace("\\", "/").split("/")]
            file_path = src_matches[0] if src_matches else clean_matches[0]
        
        # Replace occurrences in element scope only
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        replaced = 0
        
        if not occurrences and element_line > 0:
            occurrences = []
            cand_search = _normalize_color_literals(original_value or original_token)
            clean_token = (original_token or "").replace("AppColors.", "").strip()
            clean_hex = (original_value or "").lstrip("#").upper()
            start_i = max(0, element_line - 20)
            end_i = min(len(lines), element_line + 25)
            for idx in range(start_i, end_i):
                l_txt = lines[idx]
                if (clean_token and f"AppColors.{clean_token}" in l_txt) or any(c in l_txt for c in cand_search) or (clean_hex and len(clean_hex) == 6 and clean_hex in l_txt):
                    occurrences.append({"line": idx + 1, "property": ""})
            if not occurrences and 0 < element_line <= len(lines):
                occurrences.append({"line": element_line, "property": ""})

        sorted_occs = sorted(occurrences, key=lambda x: x.get("line", 0), reverse=True)
        
        for occ in sorted_occs:
            occ_line = occ.get("line", 0)
            if occ_line < 1 or occ_line > len(lines):
                continue
            
            # If not in exact line, search nearby lines (+-5)
            target_idx = occ_line - 1
            cand_patterns = _normalize_color_literals(original_token or original_value)
            if original_token:
                cand_patterns.extend([original_token, f"AppColors.{original_token}"])
            if original_value:
                cand_patterns.extend(_normalize_color_literals(original_value))
            seen_c = set()
            clean_cands = []
            for c in sorted(cand_patterns, key=len, reverse=True):
                if c and c not in seen_c:
                    seen_c.add(c)
                    clean_cands.append(c)

            matched_cand = None
            for c in clean_cands:
                if c in lines[target_idx]:
                    matched_cand = c
                    break

            if not matched_cand:
                for off in [1, -1, 2, -2, 3, -3, 4, -4, 5, -5]:
                    c_idx = target_idx + off
                    if 0 <= c_idx < len(lines):
                        for c in clean_cands:
                            if c in lines[c_idx]:
                                matched_cand = c
                                target_idx = c_idx
                                occ_line = c_idx + 1
                                break
                    if matched_cand:
                        break

            old_line = lines[target_idx]
            new_line = old_line
            if matched_cand:
                new_line = old_line.replace(matched_cand, f"AppColors.{final_token_name}")
            
            if new_line != old_line:
                lines[target_idx] = new_line
                journal.record_change(
                    file=str(file_path.relative_to(project_root)),
                    line=occ_line,
                    old_line=old_line,
                    new_line=new_line,
                    pattern_id=f"split_token_{final_token_name}",
                )
                replaced += 1
        
        updated_content = "\n".join(lines)
        updated_content, was_added, import_line, target_import = _ensure_app_colors_import(file_path, updated_content, app_colors_pkg)
        if was_added:
            journal.record_change(
                file=str(file_path.relative_to(project_root)),
                line=import_line,
                old_line="",
                new_line=target_import,
                pattern_id=f"split_import_{final_token_name}",
            )
        file_path.write_text(updated_content + "\n", encoding="utf-8")
        
        modified = journal.list_modified_files()
        print(f"[SPLIT-JOURNAL] Modified files after split: {len(modified)}")
        for f in modified:
            print(f"  - {f.get('file')} ({f.get('change_count')} changes)")

        return {
            "success": True,
            "new_token": final_token_name,
            "new_token_name": final_token_name,
            "token_name": final_token_name,
            "new_value": new_value.lstrip("#"),
            "value": new_value,
            "value_expr": new_expr,
            "replaced_count": replaced,
            "file": str(file_path.relative_to(project_root)),
            "element_file": element_file,
            "already_exists": token_already_exists,
            "journal_files": [f["file"] for f in modified],
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


def _find_all_occurrences(project_root: Path, literal: str, token_name: str = "") -> List[Dict]:
    """ابحث عن كل occurrences الآمنة للـ literal في المشروع."""
    import logging
    from core.project_scanner import ProjectScanner
    scanner = ProjectScanner(project_root)

    clean_variations = _normalize_color_literals(literal, token_name)
    logging.info(f"[FIND] Searching for variants of {literal}: {clean_variations}")

    occurrences = []
    kt_finder = getattr(scanner, "find_kt_files", None) or getattr(scanner, "_find_kt_files")
    for kt_file in kt_finder():
        s = str(kt_file).lower()
        if "backup" in s or "build" in s:
            continue
        if kt_file.name in ("DesignSystem.kt", "AppColors.kt", "Theme.kt", "Color.kt"):
            continue
        try:
            content = kt_file.read_text(encoding="utf-8")
            rel_file = str(kt_file.relative_to(project_root))
            is_safe, _ = _is_safe_compose_file(rel_file, content)
            if not is_safe:
                continue

            for i, line in enumerate(content.splitlines(), 1):
                if not _is_safe_line(line):
                    continue
                for v in clean_variations:
                    if v and v in line:
                        occurrences.append({
                            "file": rel_file,
                            "line": i,
                            "line_content": line.strip(),
                            "matched_variant": v,
                            "target_match": v,
                        })
                        break
        except Exception:
            continue

    return occurrences


def _find_file(source_file: str, root: Path = PROJECT_ROOT) -> Optional[Path]:
    """Finds file in project root."""
    full_path = root / source_file
    if full_path.exists():
        return full_path

    filename = Path(source_file).name
    candidates = [
        c for c in root.rglob(filename)
        if 'build' not in str(c) and '.composebridge' not in str(c) and 'backup' not in str(c).lower()
    ]
    return candidates[0] if candidates else None


def _extract_utf16_range(content: str, offset: int, length: int) -> str:
    """Extracts range using UTF-16 offset."""
    try:
        encoded = content.encode('utf-16-le')
        start_byte = offset * 2
        end_byte = (offset + length) * 2
        if end_byte > len(encoded):
            end_byte = len(encoded)
        sub = encoded[start_byte:end_byte]
        return sub.decode('utf-16-le', errors='ignore')
    except Exception as e:
        print(f"[source_analyzer] UTF-16 extract failed: {e}")
        return ""


def _line_context_with_start(content: str, line_number: int, before: int = 3, after: int = 20) -> Tuple[str, int]:
    """Returns lines around line_number along with 1-based start line, isolating enclosing Composable call if possible."""
    lines = content.splitlines()
    idx = line_number - 1
    if idx < 0 or idx >= len(lines):
        return "", 1

    # Check if line_number is a comment or blank, look ahead a few lines for the Composable call
    target_idx = idx
    check_indices = [target_idx]
    if lines[idx].strip().startswith("//") or not lines[idx].strip():
        for fwd in range(1, 4):
            if idx + fwd < len(lines):
                check_indices.append(idx + fwd)

    call_start = None
    for cand in check_indices:
        if re.search(r'\b[A-Z]\w*\s*\(', lines[cand]):
            call_start = cand
            break

    # If not found looking ahead/at target, check backwards up to 10 lines, ensuring call doesn't close before target_idx
    if call_start is None:
        for b in range(1, min(10, idx + 1)):
            cand = idx - b
            if re.search(r'\b[A-Z]\w*\s*\(', lines[cand]):
                test_depth = 0
                test_open = False
                closed_before_idx = False
                for cur_idx in range(cand, min(cand + 50, len(lines))):
                    l = lines[cur_idx]
                    test_depth += l.count('(') - l.count(')')
                    if '(' in l:
                        test_open = True
                    if test_open and test_depth <= 0:
                        if cur_idx < target_idx:
                            closed_before_idx = True
                        break
                if not closed_before_idx:
                    call_start = cand
                    break

    if call_start is None:
        call_start = idx

    depth = 0
    collected = []
    found_open = False
    for l in lines[call_start:]:
        collected.append(l)
        depth += l.count('(') - l.count(')')
        if '(' in l:
            found_open = True
        if found_open and depth <= 0:
            break

    if collected and found_open and len(collected) <= 50:
        return "\n".join(collected), call_start + 1

    start = max(0, idx - before)
    end = min(len(lines), idx + after)
    return "\n".join(lines[start:end]), start + 1


def _empty_result(error: str = "") -> dict:
    return {
        "composable_name": "Element",
        "colors": [],
        "tokens_used": [],
        "literals": [],
        "dimensions": [],
        "dimension_details": [],
        "bridge_spacing_tokens": [],
        "font_sizes": [],
        "font_weights": [],
        "properties": [],
        "composables": [],
        "scope_size": 0,
        "error": error,
    }


def global_dimension_edit(
    value: float,
    kind: str,  # "dp" | "sp"
    new_value: float,
    project_root: Path,
    property_name: Optional[str] = None,
) -> Dict:
    """
    Global: wrap in BridgeDimensionRegistry.get + update all occurrences.
    """
    from core.pattern_journal import PatternJournal
    
    val_num = float(value)
    val_int = int(val_num) if val_num.is_integer() else val_num
    variants = _normalize_dim_value(str(value))
    journal = PatternJournal(project_root)
    
    count = 0
    files_affected = set()
    errors = []
    
    try:
        new_val_num = float(new_value)
        new_val_str = str(int(new_val_num)) if new_val_num.is_integer() else str(new_val_num)
    except Exception:
        new_val_str = str(new_value)
    
    for kt_file in project_root.rglob("*.kt"):
        if any(x in str(kt_file).lower() for x in ["build", "backup", ".composebridge", ".bak"]):
            continue
        
        try:
            content = kt_file.read_text(encoding="utf-8")
            lines = content.splitlines()
            new_lines = []
            file_changed = False
            file_changes_to_record = []
            
            for line_idx, line in enumerate(lines, 1):
                old_l = line
                new_l = old_l
                
                # First: if already wrapped in BridgeDimensionRegistry.get, update it
                if 'BridgeDimensionRegistry.get' in new_l:
                    p_reg = rf'(BridgeDimensionRegistry\.get\(\s*"(?:global_[^"]+_{re.escape(str(val_int))}|global_[^"]+_{re.escape(str(value))})"\s*,\s*)[^)]+(\))'
                    if re.search(p_reg, new_l):
                        new_l = re.sub(p_reg, rf'\g<1>{new_val_str}.{kind}\g<2>', new_l)
                
                if new_l == old_l:
                    # Target property determination
                    # 1. RoundedCornerShape / cornerRadius
                    if property_name in (None, "cornerRadius", "shape"):
                        for variant in variants:
                            p_rcs = rf'(\b(?:RoundedCornerShape|cornerRadius)\(\s*)((?:if\s*\([^)]+\)\s*\d+(?:\.\d+)?\.(?:dp|sp)\s*else\s+)?)({re.escape(variant)}\.(?:dp|sp))(\s*\))'
                            if re.search(p_rcs, new_l):
                                reg_key = f"global_cornerRadius_{val_int}"
                                new_l = re.sub(p_rcs, rf'\g<1>\g<2>BridgeDimensionRegistry.get("{reg_key}", {new_val_str}.{kind})\g<4>', new_l)
                                break
                    
                    # 2. Modifiers: height, width, size, padding
                    if new_l == old_l:
                        mod_props = [property_name] if property_name in ['height', 'width', 'size', 'padding'] else ['height', 'width', 'size', 'padding']
                        for prop in mod_props:
                            if prop and (property_name is None or property_name == prop):
                                for variant in variants:
                                    p_mod = rf'(\.{prop}\(\s*)((?:if\s*\([^)]+\)\s*\d+(?:\.\d+)?\.(?:dp|sp)\s*else\s+)?)({re.escape(variant)}\.(?:dp|sp))(\s*\))'
                                    if re.search(p_mod, new_l):
                                        reg_key = f"global_{prop}_{val_int}"
                                        new_l = re.sub(p_mod, rf'\g<1>\g<2>BridgeDimensionRegistry.get("{reg_key}", {new_val_str}.{kind})\g<4>', new_l)
                                        break
                                if new_l != old_l:
                                    break
                    
                    # 3. Named parameters: horizontal, vertical, start, end, top, bottom
                    if new_l == old_l:
                        named_props = ['horizontal', 'vertical', 'start', 'end', 'top', 'bottom']
                        for prop in named_props:
                            if property_name is None or prop in property_name:
                                for variant in variants:
                                    p_named = rf'(\b{prop}\s*=\s*)((?:if\s*\([^)]+\)\s*\d+(?:\.\d+)?\.(?:dp|sp)\s*else\s+)?)({re.escape(variant)}\.(?:dp|sp))'
                                    if re.search(p_named, new_l):
                                        reg_key = f"global_{prop}_{val_int}"
                                        new_l = re.sub(p_named, rf'\g<1>\g<2>BridgeDimensionRegistry.get("{reg_key}", {new_val_str}.{kind})', new_l)
                                        break
                                if new_l != old_l:
                                    break
                    
                    # 4. Fallback: if property_name is explicitly given or line contains variant.kind
                    if new_l == old_l and property_name is not None:
                        for variant in variants:
                            p_fallback = rf'((?:else\s+)?)({re.escape(variant)}\.{kind}\b)'
                            if re.search(p_fallback, new_l):
                                reg_key = f"global_{property_name}_{val_int}"
                                new_l = re.sub(p_fallback, rf'\g<1>BridgeDimensionRegistry.get("{reg_key}", {new_val_str}.{kind})', new_l, count=1)
                                break

                if new_l != old_l:
                    file_changed = True
                    file_changes_to_record.append((line_idx, old_l, new_l))
                    count += 1
                new_lines.append(new_l)
            
            if file_changed:
                kt_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                rel_file = str(kt_file.relative_to(project_root)).replace("\\", "/")
                
                for l_idx, old_line_str, new_line_str in file_changes_to_record:
                    journal.record_change(
                        file=rel_file,
                        line=l_idx,
                        old_line=old_line_str,
                        new_line=new_line_str,
                        pattern_id=f"global_dim_{val_int}{kind}",
                    )
                
                content = kt_file.read_text(encoding="utf-8")
                if "BridgeDimensionRegistry.get" in content:
                    was_added, import_line = _ensure_bridge_dimension_registry_import(
                        file_path=kt_file,
                        project_root=project_root,
                    )
                    if was_added:
                        journal.record_change(
                            file=rel_file,
                            line=import_line,
                            old_line="",
                            new_line="import com.composebridge.agent.BridgeDimensionRegistry",
                            pattern_id=f"import_bridge_dim_global_{val_int}",
                        )
                    _clean_duplicate_imports(kt_file)
                
                files_affected.add(rel_file)
        
        except Exception as e:
            errors.append({"file": str(kt_file), "error": str(e)})
    
    return {
        "success": True,
        "value": value,
        "kind": kind,
        "new_value": new_val_str,
        "property": property_name or "dimension",
        "registry_key": f"global_{property_name or 'dimension'}_{val_int}",
        "replaced_count": count,
        "files_affected": len(files_affected),
        "errors": errors,
    }


def split_dimension_edit(
    value: float,
    kind: str,
    new_value: float,
    element_file: str,
    element_line: int,
    project_root: Path,
) -> Dict:
    """
    Split: edit only in this element (single line).
    """
    from core.pattern_journal import PatternJournal
    
    file_path = project_root / element_file
    if not file_path.exists():
        matches = [m for m in project_root.rglob(Path(element_file).name)
                   if "build" not in str(m) and ".bak" not in str(m)]
        if not matches:
            return {"success": False, "error": f"File not found: {element_file}"}
        file_path = matches[0]
    
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    
    if element_line > len(lines):
        return {"success": False, "error": "Line out of range"}
    
    target_idx = element_line - 1
    old_line = lines[target_idx]
    variants = _normalize_dim_value(str(value))
    
    try:
        new_val_num = float(new_value)
        new_val_str = str(int(new_val_num)) if new_val_num.is_integer() else str(new_val_num)
    except Exception:
        new_val_str = str(new_value)
    
    new_line = old_line
    for variant in variants:
        pattern = rf'\b{re.escape(variant)}(?=\.{kind}\b)'
        if re.search(pattern, old_line):
            new_line = re.sub(pattern, new_val_str, old_line, count=1)
            break
            
    if new_line == old_line:
        for variant in variants:
            if variant in old_line:
                new_line = old_line.replace(variant, new_val_str, 1)
                break
    
    if new_line == old_line:
        return {
            "success": False,
            "error": f"Could not find {value}.{kind} in line {element_line}",
        }
    
    lines[target_idx] = new_line
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    
    journal = PatternJournal(project_root)
    rel_file = str(file_path.relative_to(project_root)).replace("\\", "/")
    journal.record_change(
        file=rel_file,
        line=element_line,
        old_line=old_line,
        new_line=new_line,
        pattern_id=f"split_dim_{value}{kind}",
    )

    if "BridgeDimensionRegistry.get" in new_line or "BridgeDimensionRegistry.get" in file_path.read_text(encoding="utf-8"):
        was_added, import_line = _ensure_bridge_dimension_registry_import(
            file_path=file_path,
            project_root=project_root,
        )
        if was_added:
            journal.record_change(
                file=rel_file,
                line=import_line,
                old_line="",
                new_line="import com.composebridge.agent.BridgeDimensionRegistry",
                pattern_id=f"import_bridge_dim_{value}{kind}",
            )
        _clean_duplicate_imports(file_path)
    
    return {
        "success": True,
        "file": str(file_path.relative_to(project_root)),
        "line": element_line,
        "replaced_count": 1,
    }


def _ensure_bridge_dimension_registry_import(
    file_path: Path,
    project_root: Optional[Path] = None,
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

