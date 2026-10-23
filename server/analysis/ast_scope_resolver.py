# -*- coding: utf-8 -*-
"""
AST scope resolver and element analyzer core.
Provides Composable scope extraction, usage counting, token discovery,
and element range inspection.
"""

import os
import re
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Set, Any

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

try:
    from common.color_constants import NAMED_COLORS_HEX, NAMED_COLOR_VARIANTS
except ImportError:
    try:
        from ..common.color_constants import NAMED_COLORS_HEX, NAMED_COLOR_VARIANTS
    except ImportError:
        from server.common.color_constants import NAMED_COLORS_HEX, NAMED_COLOR_VARIANTS


RISKY_FILE_PATTERNS = [
    "ViewModel", "Repository", "DataSource", "Dao", "Database", 
    "Model", "Worker", "Service", "Entity", "Dto", "Test", "Preview"
]


_USAGE_GLOBAL_CACHE = {
    "project_path": None,
    "timestamp": 0,
    "counts": {},
}


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


def _find_enclosing_function_or_class(content: str, line_number: int) -> str:
    """Finds enclosing @Composable function, standard function, or class around line_number."""
    if not content or line_number <= 0:
        return "Element"
    lines = content.splitlines()
    target_idx = min(len(lines) - 1, max(0, line_number - 1))

    # 1. Search backwards for @Composable fun or standard fun
    for idx in range(target_idx, -1, -1):
        line = lines[idx]
        m_fun = re.search(r'\b(?:(?:private|public|internal)\s+)*fun\s+([A-Za-z0-9_]+)\s*\(', line)
        if m_fun:
            name = m_fun.group(1)
            is_comp = False
            for prev_idx in range(idx, max(-1, idx - 4), -1):
                if '@Composable' in lines[prev_idx]:
                    is_comp = True
                    break
            if is_comp or name[0].isupper():
                return name

    # 2. Search backwards for class or object
    for idx in range(target_idx, -1, -1):
        line = lines[idx]
        m_cls = re.search(r'\b(?:class|object)\s+([A-Za-z0-9_]+)', line)
        if m_cls:
            return m_cls.group(1)

    return "Element"


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
    
    # إذا لم نجدها في نفس الملف، ابحث في ملفات المشروع عبر الكاش
    if start_idx < 0 and project_root:
        try:
            from common.project_cache import PROJECT_CACHE
            kt_cache = PROJECT_CACHE.get_kt_cache(project_root)
        except Exception:
            kt_cache = None

        if kt_cache is not None:
            fn_regex = re.compile(rf'\b(fun|private\s+fun|public\s+fun|internal\s+fun)\s+{re.escape(composable_name)}\s*\(')
            for rel_file, c in kt_cache:
                if "backup" in rel_file.lower() or "build" in rel_file.lower():
                    continue
                if composable_name not in c:
                    continue
                c_lines = c.splitlines()
                for i, line in enumerate(c_lines):
                    if fn_regex.search(line):
                        start_idx = i
                        target_lines = c_lines
                        found_file = rel_file
                        break
                if start_idx >= 0:
                    break
        else:
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


def _count_function_calls(
    project_root: Path,
    composable_name: str,
    kt_cache: Optional[List[Tuple[str, str]]] = None,
) -> int:
    """احسب عدد مرات استدعاء الدالة في المشروع."""
    count = 0
    pattern = rf'\b{re.escape(composable_name)}\s*\('
    
    if kt_cache is None:
        try:
            from common.project_cache import PROJECT_CACHE
            kt_cache = PROJECT_CACHE.get_kt_cache(project_root)
        except Exception:
            kt_cache = None

    if kt_cache is not None:
        for rel_path, content in kt_cache:
            if any(x in rel_path.lower() for x in ["build", "backup", ".bak", ".composebridge"]):
                continue
            try:
                content_no_def = re.sub(
                    rf'\bfun\s+{re.escape(composable_name)}\s*\(',
                    f'_DEF_{composable_name}_',
                    content,
                )
                count += len(re.findall(pattern, content_no_def))
            except Exception:
                continue
        return count

    for kt_file in project_root.rglob("*.kt"):
        if any(x in str(kt_file).lower() for x in ["build", "backup", ".bak", ".composebridge"]):
            continue
        try:
            content = kt_file.read_text(encoding="utf-8")
            content_no_def = re.sub(
                rf'\bfun\s+{re.escape(composable_name)}\s*\(',
                f'_DEF_{composable_name}_',
                content,
            )
            count += len(re.findall(pattern, content_no_def))
        except Exception:
            continue
    
    return count


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
    from .color_analyzer import _hex_to_color_expr
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


def _find_all_occurrences(project_root: Path, literal: str, token_name: str = "") -> List[Dict]:
    """ابحث عن كل occurrences الآمنة للـ literal في المشروع."""
    from .color_analyzer import _normalize_color_literals
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
    """Finds file in project root using ProjectCache."""
    full_path = root / source_file
    if full_path.exists():
        return full_path

    try:
        from common.project_cache import PROJECT_CACHE
        cached = PROJECT_CACHE.find_file(source_file, root)
        if cached and cached.exists():
            return cached
    except Exception:
        pass

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
        l = lines[cand]
        if re.search(r'^\s*[a-zA-Z0-9_]+\s*=', l):
            continue
        if re.search(r'\b[A-Z]\w*\s*\(', l):
            call_start = cand
            break

    # If not found looking ahead/at target, check backwards up to 15 lines, ensuring call doesn't close before target_idx
    if call_start is None:
        for b in range(1, min(15, idx + 1)):
            cand = idx - b
            l = lines[cand]
            if re.search(r'^\s*[a-zA-Z0-9_]+\s*=', l):
                continue
            if re.search(r'\b[A-Z]\w*\s*\(', l):
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


def get_token_value_map(project_root: Path) -> Dict[str, str]:
    """Reads DesignSystem.kt / AppColors.kt and returns token_name -> hex_value using cache."""
    from .color_analyzer import _clean_hex
    try:
        from common.project_cache import PROJECT_CACHE
        if PROJECT_CACHE._is_valid(project_root) and PROJECT_CACHE._token_map is not None:
            return PROJECT_CACHE._token_map
    except Exception:
        pass

    token_map = {}
    candidates = []
    try:
        from common.project_cache import PROJECT_CACHE
        for name in ["DesignSystem.kt", "AppColors.kt"]:
            found = PROJECT_CACHE.find_file(name, project_root)
            if found and found.exists():
                candidates.append(found)
    except Exception:
        pass

    if not candidates:
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
            
    try:
        from common.project_cache import PROJECT_CACHE
        PROJECT_CACHE._token_map = token_map
    except Exception:
        pass
    return token_map


def get_global_usage_counts(project_root: Path) -> Dict[str, int]:
    """
    Counts occurrences of tokens and colors project-wide with a 60-second in-memory cache.
    """
    from .color_analyzer import _clean_hex
    global _USAGE_GLOBAL_CACHE
    now = time.time()
    if (
        _USAGE_GLOBAL_CACHE["project_path"] == str(project_root)
        and (now - _USAGE_GLOBAL_CACHE["timestamp"]) < 60
        and _USAGE_GLOBAL_CACHE["counts"]
    ):
        return _USAGE_GLOBAL_CACHE["counts"]

    counts: Dict[str, int] = {}
    try:
        from common.project_cache import PROJECT_CACHE
        kt_cache = PROJECT_CACHE.get_kt_cache(project_root)
    except Exception:
        kt_cache = None

    if kt_cache is not None:
        file_entries = [(path, txt) for path, txt in kt_cache]
    else:
        file_entries = []
        for kt_file in project_root.rglob("*.kt"):
            try:
                file_entries.append((str(kt_file.relative_to(project_root)), kt_file.read_text(encoding="utf-8")))
            except Exception:
                continue

    for s, txt in file_entries:
        if "build" in s.lower() or ".composebridge" in s.lower() or ".gradle" in s.lower() or "designsystem.kt" in s.lower() or "appcolors.kt" in s.lower():
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


def analyze_element_range(
    source_file: str,
    line_number: int,
    utf16_offset: int = 0,
    utf16_length: int = 0,
    project_root: Optional[Path] = None,
    tree: Optional[list] = None,
    runtime_text_hint: Optional[str] = None,
    parent_line: Optional[int] = None,
) -> dict:
    """
    Analyzes literal source code range of an element.
    Returns dimensions, tokens, literals, and structured Focus Mode color objects.
    """
    from .color_analyzer import _clean_hex, _find_color_locations, NAMED_COLORS_HEX, NAMED_COLOR_VARIANTS
    from .dimension_analyzer import _find_dimension_usage, _extract_dimensions_with_property
    from .text_ref_analyzer import _resolve_app_strings_value, _find_ref_in_app_strings, _detect_composable_name
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

    # Pre-warm In-Memory Cache once for the entire analysis
    try:
        from common.project_cache import PROJECT_CACHE
        kt_cache = PROJECT_CACHE.get_kt_cache(root)
    except Exception:
        kt_cache = None

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
            kt_cache=kt_cache,
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
        fallback_line_content=content.splitlines()[line_number - 1] if 0 < line_number <= len(content.splitlines()) else "",
        full_content=content,
        line_number=actual_line_number
    )
    if composable_name in ["Element", "Text", "BasicText", "Column", "Row", "Box", "Spacer"] and content:
        enclosing_name = _find_enclosing_function_or_class(content, actual_line_number)
        if enclosing_name != "Element":
            composable_name = enclosing_name

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
    if kt_cache is None:
        try:
            from common.project_cache import PROJECT_CACHE
            kt_cache = PROJECT_CACHE.get_kt_cache(root)
        except Exception:
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
        call_count = _count_function_calls(root, composable_name, kt_cache=kt_cache)

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

    # ─── Text Extraction ───
    def _extract_from_text(scope_str: str, base_line: int, file_p: str, filter_call_line: Optional[int] = None) -> List[Dict]:
        results = []
        seen = set()

        # 1. Composable parameter references: e.g. title = AppStrings.Actions.scheduleTitle
        param_ref_pattern = re.compile(r'([a-zA-Z0-9_]+)\s*=\s*(AppStrings(?:\.[a-zA-Z0-9_]+)+)')
        for m in param_ref_pattern.finditer(scope_str):
            prop_name = m.group(1)
            ref_k = m.group(2)
            key = ("ref", ref_k)
            if key not in seen:
                seen.add(key)
                line_off = scope_str[:m.start()].count("\n")
                detected_line = base_line + line_off
                resolved_val = _resolve_app_strings_value(root, ref_k, runtime_text_hint)
                results.append({
                    "property": prop_name,
                    "text": resolved_val or ref_k,
                    "file": file_p,
                    "line": detected_line,
                    "is_resource_or_ref": True,
                    "ref_key": ref_k,
                })

        # 2. Direct Text(AppStrings.xyz) or Text(text = AppStrings.xyz)
        ref_text_pattern = re.compile(r'Text\s*\(\s*(?:text\s*=\s*)?(AppStrings(?:\.[a-zA-Z0-9_]+)+)')
        for m in ref_text_pattern.finditer(scope_str):
            ref_k = m.group(1)
            key = ("ref", ref_k)
            if key not in seen:
                seen.add(key)
                line_off = scope_str[:m.start()].count("\n")
                detected_line = base_line + line_off
                resolved_val = _resolve_app_strings_value(root, ref_k, runtime_text_hint)
                results.append({
                    "property": "text",
                    "text": resolved_val or ref_k,
                    "file": file_p,
                    "line": detected_line,
                    "is_resource_or_ref": True,
                    "ref_key": ref_k,
                })

        # 3. Composable parameter string literals: e.g. title = "..."
        param_str_pattern = re.compile(r'([a-zA-Z0-9_]+)\s*=\s*"([^"\\]*(?:\\.[^"\\]*)*)"')
        for m in param_str_pattern.finditer(scope_str):
            prop_name = m.group(1)
            if prop_name in ("modifier", "tag", "key", "route", "id"):
                continue
            raw_lit = m.group(2)
            has_template = "$" in raw_lit
            # Check for embedded AppStrings reference in template
            embedded_ref = None
            if has_template:
                m_emb = re.search(r'\$\{?(AppStrings(?:\.[a-zA-Z0-9_]+)+)\}?', raw_lit)
                if m_emb:
                    embedded_ref = m_emb.group(1)

            val = runtime_text_hint if (has_template and runtime_text_hint) else raw_lit.replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n')
            if has_template and not runtime_text_hint and embedded_ref:
                val = _resolve_app_strings_value(root, embedded_ref) or val

            key = ("hardcoded", val)
            if key not in seen and val.strip():
                seen.add(key)
                line_off = scope_str[:m.start()].count("\n")
                detected_line = base_line + line_off
                results.append({
                    "property": prop_name,
                    "text": val,
                    "file": file_p,
                    "line": detected_line,
                    "is_resource_or_ref": bool(embedded_ref),
                    "ref_key": embedded_ref,
                })

        # 4. Direct Text("...") or Text(text = "...")
        hardcoded_text_pattern = re.compile(r'Text\s*\(\s*(?:text\s*=\s*)?"([^"\\]*(?:\\.[^"\\]*)*)"')
        for m in hardcoded_text_pattern.finditer(scope_str):
            raw_lit = m.group(1)
            has_template = "$" in raw_lit
            embedded_ref = None
            if has_template:
                m_emb = re.search(r'\$\{?(AppStrings(?:\.[a-zA-Z0-9_]+)+)\}?', raw_lit)
                if m_emb:
                    embedded_ref = m_emb.group(1)

            val = runtime_text_hint if (has_template and runtime_text_hint) else raw_lit.replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n')
            if has_template and not runtime_text_hint and embedded_ref:
                val = _resolve_app_strings_value(root, embedded_ref) or val

            key = ("hardcoded", val)
            if key not in seen and val.strip():
                seen.add(key)
                line_off = scope_str[:m.start()].count("\n")
                detected_line = base_line + line_off
                results.append({
                    "property": "text",
                    "text": val,
                    "file": file_p,
                    "line": detected_line,
                    "is_resource_or_ref": bool(embedded_ref),
                    "ref_key": embedded_ref,
                })

        # 5. Parameter/Variable text: Text(title) or Text(subtitle)
        var_text_pattern = re.compile(r'Text\s*\(\s*(?:text\s*=\s*)?([a-zA-Z0-9_]+)')
        for m in var_text_pattern.finditer(scope_str):
            var_name = m.group(1)
            if var_name in ("modifier", "color", "style", "null", "true", "false", "it", "fontSize", "fontWeight"):
                continue
            abs_pos = content.find(scope_str) + m.start() if scope_str in content else m.start()
            before_code = content[:abs_pos]
            func_matches = list(re.finditer(r'fun\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)', before_code))
            if func_matches:
                last_func = func_matches[-1]
                func_name = last_func.group(1)
                params = last_func.group(2)
                if re.search(rf'\b{var_name}\b', params):
                    call_pattern = re.compile(rf'{func_name}\s*\((.*?)\)', re.DOTALL)
                    all_calls = list(call_pattern.finditer(content))
                    chosen_call = None

                    # If filter_call_line specified, match call near that line
                    target_line = filter_call_line or parent_line
                    if target_line:
                        for call_m in all_calls:
                            c_line = content[:call_m.start()].count("\n") + 1
                            if abs(c_line - target_line) <= 5:
                                chosen_call = call_m
                                break

                    # Match by runtime_text_hint
                    if not chosen_call and runtime_text_hint:
                        for call_m in all_calls:
                            call_body = call_m.group(1)
                            if runtime_text_hint in call_body:
                                chosen_call = call_m
                                break
                            for ref_m in re.finditer(r'AppStrings(?:\.[a-zA-Z0-9_]+)+', call_body):
                                res_val = _resolve_app_strings_value(root, ref_m.group(0), runtime_text_hint)
                                if res_val == runtime_text_hint:
                                    chosen_call = call_m
                                    break
                            if chosen_call:
                                break

                    calls_to_process = [chosen_call] if chosen_call else all_calls
                    for call_m in calls_to_process:
                        call_body = call_m.group(1)
                        param_m = re.search(rf'{var_name}\s*=\s*([^\n,]+)', call_body)
                        if param_m:
                            arg_val = param_m.group(1).strip()
                            call_line = content[:call_m.start()].count("\n") + 1
                            if arg_val.startswith("AppStrings."):
                                ref_k = arg_val
                                resolved_val = _resolve_app_strings_value(root, ref_k, runtime_text_hint)
                                key = ("ref", ref_k)
                                if key not in seen:
                                    seen.add(key)
                                    results.append({
                                        "property": var_name,
                                        "text": resolved_val or ref_k,
                                        "file": actual_source_file,
                                        "line": call_line,
                                        "is_resource_or_ref": True,
                                        "ref_key": ref_k,
                                    })
                            elif arg_val.startswith('"') and arg_val.endswith('"'):
                                raw_val = arg_val[1:-1].replace('\\"', '"').replace('\\\\', '\\')
                                key = ("hardcoded", raw_val)
                                if key not in seen:
                                    seen.add(key)
                                    results.append({
                                        "property": var_name,
                                        "text": raw_val,
                                        "file": actual_source_file,
                                        "line": call_line,
                                        "is_resource_or_ref": False,
                                        "ref_key": None,
                                    })
        return results

    # First, extract from the immediate call scope (search_scope)
    structured_texts = _extract_from_text(search_scope, start_line_in_file, actual_source_file)

    # If no texts found in call scope and we expanded to composable scope, extract there
    if not structured_texts and dim_scope_text != search_scope:
        structured_texts = _extract_from_text(dim_scope_text, dim_scope_start_line, effective_file, filter_call_line=start_line_in_file)

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

