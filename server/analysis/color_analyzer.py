from common.color_constants import NAMED_COLORS_HEX, NAMED_COLOR_VARIANTS
# -*- coding: utf-8 -*-
"""
Color analysis and refactoring module.
Handles Compose color literals, Hex values, AppColors imports, and global/local color splits.
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

from .ast_scope_resolver import (
    _is_safe_compose_file,
    _is_safe_line,
    _find_all_occurrences,
    _update_existing_token,
    _find_token_by_value,
    _find_file,
    _detect_property,
    _validate_modified_file,
)

try:
    from common.file_ops import _atomic_write_text, _find_registry_file
except ImportError:
    try:
        from server.common.file_ops import _atomic_write_text, _find_registry_file
    except ImportError:
        from ..common.file_ops import _atomic_write_text, _find_registry_file



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


def _detect_app_colors_pkg(file_path: Path) -> str:
    """Detect package of AppColors by searching for AppColors.kt or inspecting build.gradle.kts."""
    try:
        cur = file_path.parent
        project_root = None
        for _ in range(8):
            if any((cur / f).exists() for f in ["settings.gradle.kts", "settings.gradle", ".git"]):
                project_root = cur
                break
            if cur.parent == cur:
                break
            cur = cur.parent

        if project_root:
            # 1. Search for AppColors.kt in project
            for candidate in project_root.rglob("AppColors.kt"):
                if candidate.is_file() and "build" not in candidate.parts:
                    c = candidate.read_text(encoding="utf-8", errors="ignore")
                    m = re.search(r'^\s*package\s+([\w.]+)', c, re.MULTILINE)
                    if m:
                        return m.group(1)

            # 2. Check build.gradle.kts for namespace
            for candidate in project_root.rglob("build.gradle.kts"):
                if candidate.is_file() and "build" not in candidate.parts:
                    c = candidate.read_text(encoding="utf-8", errors="ignore")
                    m = re.search(r'namespace\s*=\s*["\']([\w.]+)["\']', c)
                    if m:
                        return f"{m.group(1)}.ui.theme"
    except Exception:
        pass
    return ""


def _ensure_app_colors_import(file_path: Path, content: str, app_colors_pkg: str = "") -> Tuple[str, bool, int, str]:
    """
    Ensure the file has an AppColors import.
    Returns (new_content, was_added, line_num, target_import).
    """
    pkg_match = re.search(r'^\s*package\s+([\w.]+)', content, re.MULTILINE)
    file_pkg = pkg_match.group(1) if pkg_match else ""

    if not app_colors_pkg:
        app_colors_pkg = _detect_app_colors_pkg(file_path)

    if not app_colors_pkg and file_pkg:
        parts = file_pkg.split('.')
        base = ".".join(parts[:3]) if len(parts) >= 3 else file_pkg
        app_colors_pkg = f"{base}.ui.theme"

    if app_colors_pkg and file_pkg == app_colors_pkg:
        return content, False, 0, ""

    target_import = f"import {app_colors_pkg}.AppColors" if app_colors_pkg else ""
    wildcard_import = f"import {app_colors_pkg}.*" if app_colors_pkg else ""

    if not target_import:
        return content, False, 0, ""

    import_patterns = [
        target_import,
        wildcard_import,
    ]
    for pattern in import_patterns:
        if pattern and pattern in content:
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

