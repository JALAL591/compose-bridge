# -*- coding: utf-8 -*-
"""
Universal Discovery & Design Scatter Scanner.
Analyzes scattered design tokens (colors, dimensions, strings) across any Kotlin/Compose codebase.
Provides configuration mapping and graceful degradation guards.
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    from common.file_ops import is_ignored_path
except ImportError:
    try:
        from server.common.file_ops import is_ignored_path
    except ImportError:
        def is_ignored_path(p, root=None): return any(k in str(p).lower() for k in ["build", "backup", ".composebridge", ".bak", ".git"])

try:
    from core.project_root import get_project_root
except ImportError:
    try:
        from server.core.project_root import get_project_root
    except ImportError:
        def get_project_root(): return Path.cwd()


# ═══════════════════════════════════════════════════════════════
# Regex Patterns for Design Token Identification
# ═══════════════════════════════════════════════════════════════
COLOR_BRIDGE_PATTERN = re.compile(r'BridgeThemeRegistry\.getColor\(\s*"([^"]+)"(?:\s*,\s*([^)]+))?\)')
COLOR_DEF_PATTERN = re.compile(r'\bval\s+([A-Za-z0-9_]+)\s*(?::\s*Color)?\s*(?:get\(\)\s*=\s*|=\s*)(?:BridgeThemeRegistry\.getColor\([^,]+,\s*([^)]+)\)|Color\s*\(\s*(0x[0-9A-Fa-f]+|[^)]+)\s*\)|Color\.([A-Za-z]+))')
COLOR_LITERAL_PATTERN = re.compile(r'\bColor\s*\(\s*(0x[0-9A-Fa-f]{6,8})\s*\)|\bColor\.([A-Za-z]+)\b')
DIMEN_BRIDGE_PATTERN = re.compile(r'BridgeDimensionRegistry\.get\(\s*"([^"]+)"(?:\s*,\s*([^)]+))?\)')
DIMEN_DEF_PATTERN = re.compile(r'\bval\s+([A-Za-z0-9_]+)\s*(?::\s*(?:Dp|TextUnit))?\s*(?:get\(\)\s*=\s*|=\s*)(?:BridgeDimensionRegistry\.get\([^,]+,\s*([^)]+)\)|([0-9]+(?:\.[0-9]+)?)\.(dp|sp))')
DIMEN_LITERAL_PATTERN = re.compile(r'\b([0-9]+(?:\.[0-9]+)?)\.(dp|sp)\b')
STRING_BRIDGE_PATTERN = re.compile(r'BridgeTextRegistry\.get\(\s*"([^"]+)"(?:\s*,\s*"([^"]*)")?\)')
STRING_DEF_PATTERN = re.compile(r'\bval\s+([A-Za-z0-9_]+)\s*(?::\s*String)?\s*(?:get\(\)\s*=\s*|=\s*)(?:BridgeTextRegistry\.get\([^,]+,\s*"([^"]*)"\)|"([^"]*)")')
UI_TEXT_PATTERN = re.compile(r'\bText\s*\(\s*(?:text\s*=\s*)?"([^"\\]*(?:\\.[^"\\]*)*)"')
STRING_RES_PATTERN = re.compile(r'\bstringResource\s*\(\s*([^)]+)\s*\)')

# Mandatory Registry Candidates
MANDATORY_REGISTRY_NAMES = ("DesignSystem", "AppColors", "Color", "Colors", "Theme", "Dimens", "AppDimens", "Dimensions", "Strings", "AppStrings", "StringResources")
MANDATORY_REGISTRY_OBJS = ("object AppColors", "object DesignSystem", "object AppDimens", "object AppStrings", "BridgeThemeRegistry", "BridgeDimensionRegistry", "BridgeTextRegistry")


def is_mandatory_registry(filename: str, content: str) -> bool:
    """Returns True if the file is designed to be a central token registry."""
    name_no_ext = Path(filename).stem
    if any(r.lower() == name_no_ext.lower() or name_no_ext.lower().endswith(r.lower()) for r in MANDATORY_REGISTRY_NAMES):
        return True
    if any(obj in content for obj in MANDATORY_REGISTRY_OBJS):
        return True
    return False


def should_skip_file(filename: str, content: str) -> bool:
    """Excludes ONLY explicit pure data/serialization files that have NO design tokens."""
    if is_mandatory_registry(filename, content):
        return False
    is_data = ("@Serializable" in content or "data class" in content)
    has_tokens = any(k in content for k in ("Color(", ".dp", ".sp", "Text(", "stringResource(", "BridgeThemeRegistry", "BridgeDimensionRegistry", "BridgeTextRegistry"))
    return is_data and not has_tokens


def strip_comments_and_annotations(content: str) -> str:
    """
    Strips comments and annotations while preserving exact line count and numbering.
    """
    def _preserve_lines(m):
        return '\n' * m.group(0).count('\n')

    # Multi-line comments: /* ... */
    content = re.sub(r'/\*.*?\*/', _preserve_lines, content, flags=re.DOTALL)
    # Single-line comments: // ...
    content = re.sub(r'//.*', '', content)
    # Strip annotations with parameters: @SerialName("..."), @JsonClass(...), @Inject(...), @file:Suppress(...)
    content = re.sub(r'@(?:\w+:)?\w+\s*\([^)]*\)', '', content)
    return content


# ═══════════════════════════════════════════════════════════════
# Configuration & Manual Mapping Functions
# ═══════════════════════════════════════════════════════════════

def get_config_path(project_root: Optional[Path] = None) -> Path:
    """Returns path to .composebridge/config.json."""
    root = Path(project_root) if project_root else get_project_root()
    return root / ".composebridge" / "config.json"


def get_design_file_mappings(project_root: Optional[Path] = None) -> Dict[str, str]:
    """Reads configured design file mappings from .composebridge/config.json."""
    cfg_file = get_config_path(project_root)
    if not cfg_file.exists():
        return {}
    try:
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        return data.get("design_files", {})
    except Exception:
        return {}


def save_design_file_mapping(
    token_type: str,
    file_path: str,
    project_root: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Saves a designated design/registry file mapping to .composebridge/config.json.
    Supported token_types: 'color', 'dimension', 'string', 'all'.
    """
    root = Path(project_root) if project_root else get_project_root()
    token_type_norm = token_type.strip().lower()
    if token_type_norm not in ("color", "dimension", "string", "all"):
        return {
            "success": False,
            "error": f"Invalid token_type '{token_type}'. Supported: 'color', 'dimension', 'string', 'all'."
        }

    # Normalize relative path
    target_p = Path(file_path)
    if target_p.is_absolute():
        try:
            rel_str = str(target_p.relative_to(root)).replace("\\", "/")
        except Exception:
            rel_str = str(file_path).replace("\\", "/")
    else:
        rel_str = str(file_path).replace("\\", "/")

    # Verify target file exists or parent exists
    full_target = root / rel_str
    if not full_target.exists():
        # Check if match exists anywhere in project
        matches = [m for m in root.rglob(Path(rel_str).name) if not is_ignored_path(m, root)]
        if matches:
            rel_str = str(matches[0].relative_to(root)).replace("\\", "/")
            full_target = matches[0]

    cfg_file = get_config_path(root)
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    current_data = {}
    if cfg_file.exists():
        try:
            current_data = json.loads(cfg_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    if "design_files" not in current_data or not isinstance(current_data.get("design_files"), dict):
        current_data["design_files"] = {}

    if token_type_norm == "all":
        for t in ("color", "dimension", "string"):
            current_data["design_files"][t] = rel_str
    else:
        current_data["design_files"][token_type_norm] = rel_str

    cfg_file.write_text(json.dumps(current_data, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "success": True,
        "token_type": token_type_norm,
        "mapped_file": rel_str,
        "file_exists": full_target.exists(),
        "all_mappings": current_data["design_files"],
    }


def resolve_target_design_file(
    token_type: str,
    project_root: Optional[Path] = None
) -> Tuple[Optional[Path], str]:
    """
    Resolves the target file for a given token type with clear priority:
    1. Explicit user mapping from .composebridge/config.json
    2. Standard design system candidates (DesignSystem.kt, AppColors.kt, etc.)
    3. Heuristic content discovery (first file defining tokens of this type)
    Returns: (Path or None, resolution_source: "config_mapping" | "standard_candidate" | "heuristic" | "NOT_FOUND")
    """
    root = Path(project_root) if project_root else get_project_root()
    token_type_norm = token_type.strip().lower()

    # 1. Config mapping check
    mappings = get_design_file_mappings(root)
    if token_type_norm in mappings:
        mapped_path = root / mappings[token_type_norm]
        if mapped_path.exists() and not is_ignored_path(mapped_path, root):
            return (mapped_path, "config_mapping")
        # Try finding by filename if relative path moved
        matches = [m for m in root.rglob(Path(mappings[token_type_norm]).name) if not is_ignored_path(m, root)]
        if matches:
            return (matches[0], "config_mapping")

    # 2. Standard Candidates
    candidates_map = {
        "color": ["DesignSystem.kt", "AppColors.kt", "Color.kt", "Colors.kt", "Theme.kt"],
        "dimension": ["DesignSystem.kt", "AppDimens.kt", "Dimens.kt", "Dimensions.kt", "Theme.kt"],
        "string": ["AppStrings.kt", "Strings.kt", "StringResources.kt", "DesignSystem.kt"],
    }
    candidates = candidates_map.get(token_type_norm, ["DesignSystem.kt", "Theme.kt"])

    def _rank(p: Path) -> int:
        norm = str(p).replace("\\", "/").lower()
        if "/commonmain/" in norm: return 0
        if "/main/" in norm: return 1
        return 2 if "/src/" in norm else 3

    for name in candidates:
        matches = [f for f in root.rglob(name) if not is_ignored_path(f, root)]
        if matches:
            matches.sort(key=lambda p: (_rank(p), len(str(p))))
            return (matches[0], "standard_candidate")

    # 3. Heuristic discovery
    pattern_map = {"color": COLOR_DEF_PATTERN, "dimension": DIMEN_DEF_PATTERN, "string": STRING_DEF_PATTERN}
    target_pat = pattern_map.get(token_type_norm)
    if target_pat:
        for kt in root.rglob("*.kt"):
            if not is_ignored_path(kt, root):
                try:
                    if target_pat.search(kt.read_text(encoding="utf-8", errors="ignore")):
                        return (kt, "heuristic")
                except Exception:
                    pass

    return (None, "NOT_FOUND")


# ═══════════════════════════════════════════════════════════════
# Universal Scanner Implementation
# ═══════════════════════════════════════════════════════════════

def scan_design_scatter(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Scans the entire project for design tokens (colors, dimensions, strings),
    identifies scattered tokens, locates candidate registries, and returns
    a comprehensive structured report. Excludes non-UI data models and noise.
    """
    root = Path(project_root) if project_root else get_project_root()
    scatter_files = []
    total_colors = 0
    total_dimensions = 0
    total_strings = 0
    excluded_data_models = 0

    candidate_registries = {
        "color": set(),
        "dimension": set(),
        "string": set(),
    }

    all_kt_files = []
    for kt in root.rglob("*.kt"):
        if not is_ignored_path(kt, root):
            all_kt_files.append(kt)

    for kt_file in all_kt_files:
        try:
            rel_file = str(kt_file.relative_to(root)).replace("\\", "/")
        except Exception:
            rel_file = str(kt_file).replace("\\", "/")

        try:
            content = kt_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Step 1: Skip explicit pure data model files that have no design elements
        if should_skip_file(kt_file.name, content):
            excluded_data_models += 1
            continue

        clean_content = strip_comments_and_annotations(content)
        lines = clean_content.splitlines()

        is_registry_file = is_mandatory_registry(kt_file.name, content)
        name_lower = kt_file.name.lower()
        is_string_registry = (
            is_registry_file and ("string" in name_lower or "designsystem" in name_lower)
        ) or any(k in content.lower() for k in ["object appstrings", "class appstrings", "bridgetextregistry"])

        file_tokens = []
        c_count = 0
        d_count = 0
        s_count = 0

        for idx, line in enumerate(lines):
            l_num = idx + 1
            trimmed_line = line.strip()
            if not trimmed_line:
                continue

            # -------------------------------------------------------------
            # 1. Colors
            # -------------------------------------------------------------
            # A) BridgeThemeRegistry.getColor(...)
            m_c_bridge = COLOR_BRIDGE_PATTERN.search(line)
            if m_c_bridge:
                token_val = (m_c_bridge.group(2) or "Color").strip()
                file_tokens.append({
                    "type": "color_bridge",
                    "name": m_c_bridge.group(1),
                    "value": token_val,
                    "line": l_num,
                    "raw": trimmed_line
                })
                c_count += 1
            else:
                # B) val Color definitions (with = or get() =)
                m_c_def = COLOR_DEF_PATTERN.search(line)
                if m_c_def:
                    t_name = m_c_def.group(1)
                    t_val = (m_c_def.group(2) or m_c_def.group(3) or m_c_def.group(4) or "Color").strip()
                    if t_val.lower() not in ("transparent", "unspecified", "color.transparent", "color.unspecified"):
                        file_tokens.append({
                            "type": "color_def",
                            "name": t_name,
                            "value": t_val,
                            "line": l_num,
                            "raw": trimmed_line
                        })
                        c_count += 1
                else:
                    # C) Inline color literals: Color(0x...) or Color.Red
                    m_c_lit = COLOR_LITERAL_PATTERN.search(line)
                    if m_c_lit:
                        t_val = (m_c_lit.group(1) or m_c_lit.group(2) or "").strip()
                        if t_val.lower() not in ("transparent", "unspecified", "color.transparent", "color.unspecified"):
                            file_tokens.append({
                                "type": "color_literal",
                                "name": f"Color_L{l_num}",
                                "value": t_val,
                                "line": l_num,
                                "raw": trimmed_line
                            })
                            c_count += 1

            # -------------------------------------------------------------
            # 2. Dimensions
            # -------------------------------------------------------------
            # A) BridgeDimensionRegistry.get(...)
            m_d_bridge = DIMEN_BRIDGE_PATTERN.search(line)
            if m_d_bridge:
                token_val = (m_d_bridge.group(2) or "Dp").strip()
                file_tokens.append({
                    "type": "dimension_bridge",
                    "name": m_d_bridge.group(1),
                    "value": token_val,
                    "line": l_num,
                    "raw": trimmed_line
                })
                d_count += 1
            else:
                # B) Dimension definitions or inline literals: \d+.dp or \d+.sp
                m_d_lit = DIMEN_LITERAL_PATTERN.search(line)
                if m_d_lit:
                    m_d_def = DIMEN_DEF_PATTERN.search(line)
                    if m_d_def:
                        t_name = m_d_def.group(1)
                        t_val = m_d_def.group(2) or f"{m_d_def.group(3)}.{m_d_def.group(4)}"
                        t_type = "dimension_def"
                    else:
                        t_name = f"Dimen_L{l_num}"
                        t_val = f"{m_d_lit.group(1)}.{m_d_lit.group(2)}"
                        t_type = "dimension_literal"

                    file_tokens.append({
                        "type": t_type,
                        "name": t_name,
                        "value": t_val.strip(),
                        "line": l_num,
                        "raw": trimmed_line
                    })
                    d_count += 1

            # -------------------------------------------------------------
            # 3. Strings
            # -------------------------------------------------------------
            is_const = bool(re.search(r'\bconst\s+val\b', line))
            if not is_const:
                # A) BridgeTextRegistry.get(...)
                m_s_bridge = STRING_BRIDGE_PATTERN.search(line)
                if m_s_bridge:
                    file_tokens.append({
                        "type": "string_bridge",
                        "name": m_s_bridge.group(1),
                        "value": m_s_bridge.group(2) or "",
                        "line": l_num,
                        "raw": trimmed_line
                    })
                    s_count += 1
                elif is_string_registry:
                    # In designated string registries (e.g. AppStrings.kt, Strings.kt),
                    # capture all val string definitions accurately
                    m_s_def = STRING_DEF_PATTERN.search(line)
                    if m_s_def:
                        t_name = m_s_def.group(1)
                        t_val = m_s_def.group(2) or m_s_def.group(3) or ""
                        if len(t_val) > 0 and not t_name.startswith("_"):
                            file_tokens.append({
                                "type": "string_def",
                                "name": t_name,
                                "value": t_val,
                                "line": l_num,
                                "raw": trimmed_line
                            })
                            s_count += 1
                elif "@Composable" in content:
                    # In Composable UI files, capture all UI string resources and literals
                    # (including multi-line text = "...", custom composable parameters, and conditionals)
                    for m_sr in STRING_RES_PATTERN.finditer(line):
                        res_val = m_sr.group(1).strip()
                        file_tokens.append({
                            "type": "string_res",
                            "name": f"Res_L{l_num}",
                            "value": res_val,
                            "line": l_num,
                            "raw": trimmed_line
                        })
                        s_count += 1

                    # Extract UI string literals on this line (skip logging, tags, etc.)
                    if not re.search(r'\b(?:TAG|Log\.[diewv]|println|print)\b', line):
                        for m_lit in re.finditer(r'"([^"\\]*(?:\\.[^"\\]*)*)"', line):
                            lit_val = m_lit.group(1).strip()
                            if not lit_val:
                                continue
                            if len(lit_val) == 1 and not lit_val.isalnum():
                                continue
                            file_tokens.append({
                                "type": "ui_string",
                                "name": f"String_L{l_num}",
                                "value": lit_val,
                                "line": l_num,
                                "raw": trimmed_line
                            })
                            s_count += 1

        total_file_tokens = c_count + d_count + s_count
        if total_file_tokens > 0:
            total_colors += c_count
            total_dimensions += d_count
            total_strings += s_count
            is_candidate = is_registry_file

            if is_candidate:
                if c_count > 0 or any(k in name_lower for k in ["color", "theme", "designsystem"]) or "appcolors" in content.lower() or "bridgethemeregistry" in content:
                    candidate_registries["color"].add(rel_file)
                if d_count > 0 or any(k in name_lower for k in ["dimen", "theme", "designsystem"]) or "appdimens" in content.lower() or "bridgedimensionregistry" in content:
                    candidate_registries["dimension"].add(rel_file)
                if s_count > 0 or any(k in name_lower for k in ["string", "designsystem"]) or "appstrings" in content.lower() or "bridgetextregistry" in content:
                    candidate_registries["string"].add(rel_file)

            scatter_files.append({
                "file": rel_file,
                "name": kt_file.name,
                "counts": {
                    "color": c_count,
                    "dimension": d_count,
                    "string": s_count,
                    "total": total_file_tokens,
                },
                "is_candidate_registry": is_candidate,
                "tokens": file_tokens[:40],
            })

    scatter_files.sort(key=lambda x: (1 if x["is_candidate_registry"] else 0, x["counts"]["total"]), reverse=True)
    mappings = get_design_file_mappings(root)
    from analysis.scatter_formatter import build_category_reports
    summary_data, colors_rep, dimens_rep, strings_rep = build_category_reports(scatter_files)

    return {
        "success": True,
        "project_root": str(root),
        "summary": {
            "total_files_needing_fix": summary_data["total_files_needing_fix"],
            "total_colors": total_colors,
            "total_dimensions": total_dimensions,
            "total_strings": total_strings,
            "total_scanned_files": len(all_kt_files),
            "excluded_data_models": excluded_data_models,
            "files_with_tokens": len(scatter_files),
        },
        "colors_report": colors_rep,
        "dimensions_report": dimens_rep,
        "strings_report": strings_rep,
        "recommended_registries": {
            "color": sorted(list(candidate_registries["color"])),
            "dimension": sorted(list(candidate_registries["dimension"])),
            "string": sorted(list(candidate_registries["string"])),
        },
        "mapped_design_files": mappings,
        "scatter_files": scatter_files,
    }

