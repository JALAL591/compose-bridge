# -*- coding: utf-8 -*-
"""
Kotlin Parser — Extract tokens and values from .kt files.

Uses regex patterns for:
- BridgeDimensionRegistry.get("name", 240.dp)
- BridgeThemeRegistry.getColor("name", Color(0xFF...))
- Hardcoded: 16.dp, 120.dp, Color(0xFF...), fontSize = 14.sp
"""

import re
from pathlib import Path
from typing import List, Tuple, Set, Dict, Optional


# ═══════════════════════════════════════════════════════════
# Registered tokens patterns
# ═══════════════════════════════════════════════════════════

DIMENSION_REGISTRY = re.compile(
    r'BridgeDimensionRegistry\.get\(\s*["\'](\w+)["\']\s*,\s*([\d.]+)\.(dp|sp|f)\b',
    re.MULTILINE
)

COLOR_REGISTRY = re.compile(
    r'BridgeThemeRegistry\.getColor\(\s*["\'](\w+)["\']\s*,\s*(Color\([^)]+\)|Color\.\w+|0x[0-9A-Fa-f]{8})',
    re.MULTILINE
)

STANDARD_DIMENSION = re.compile(
    r'(?<!private\s)\bval\s+(\w+)\s*(?::\s*(?:Dp|TextUnit|Float))?\s*(?:get\(\)\s*=\s*|=)\s*(\d+(?:\.\d+)?)\s*\.(dp|sp|f)\b(?!\s*\.\s*(?:toPx|value))',
    re.MULTILINE
)

STANDARD_COLOR = re.compile(
    r'(?<!private\s)\bval\s+(\w+)\s*(?::\s*Color)?\s*(?:get\(\)\s*=\s*|=)\s*(Color\([^)]+\)|Color\.\w+|0x[0-9A-Fa-f]{8})',
    re.MULTILINE
)


# ═══════════════════════════════════════════════════════════
# Hardcoded patterns (for suggestions)
# ═══════════════════════════════════════════════════════════

HARDCODED_DP = re.compile(
    r'(\d+(?:\.\d+)?)\.dp',
    re.MULTILINE
)

HARDCODED_COLOR_HEX = re.compile(
    r'Color\((0x[0-9A-Fa-f]{8})\)',
    re.MULTILINE
)

HARDCODED_COLOR_RGB = re.compile(
    r'Color\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)',
    re.MULTILINE
)

HARDCODED_SP = re.compile(
    r'(\d+(?:\.\d+)?)\.sp',
    re.MULTILINE
)


# ═══════════════════════════════════════════════════════════
# Context detection — categorize by surrounding code
# ═══════════════════════════════════════════════════════════

CONTEXT_KEYWORDS = {
    "padding":    ["padding", "PaddingValues"],
    "margin":     ["margin", "Arrangement.spacedBy"],
    "size":       ["size", "width", "height", ".fillMax"],
    "corner":     ["RoundedCornerShape", "CornerSize", "corner"],
    "elevation":  ["elevation", "shadow"],
    "background": ["background", "Container"],
    "text_color": ["contentColor", "TextColor", "color ="],
    "border":     ["border", "BorderStroke"],
    "font_size":  ["fontSize"],
    "spacing":    ["spacedBy", "Arrangement", "gap"],
}


def detect_category(line: str) -> str:
    """Detect category from surrounding line."""
    for category, keywords in CONTEXT_KEYWORDS.items():
        for kw in keywords:
            if kw in line:
                return category
    return "unknown"


def suggest_token_name(category: str, value: str, kind: str) -> str:
    """Suggest a token name based on category and value."""
    if kind == "dimension":
        # Remove .dp
        numeric = value.replace(".dp", "").replace(".", "_")
        return f"{category}_{numeric}"
    elif kind == "color":
        return f"{category}_color"
    elif kind == "font_size":
        numeric = value.replace(".sp", "").replace(".", "_")
        return f"font_size_{numeric}"
    return f"custom_{category}"



def get_file_line_scopes(content: str) -> List[dict]:
    """Precompute scope hierarchy per line to accurately distinguish local vs member declarations."""
    lines = content.splitlines()
    obj_re = re.compile(r'\bobject\s+(\w+)')
    cls_re = re.compile(r'\b(?:class|interface)\s+(\w+)')
    fun_re = re.compile(r'\bfun\s+(?:<[^>]+>\s+)?(\w+)')
    
    stack = []
    pending = None
    scopes = []
    
    for raw_line in lines:
        line = re.sub(r'//.*', '', raw_line)
        line = re.sub(r'"[^"]*"', '', line)
        
        obj_m = obj_re.search(line)
        cls_m = cls_re.search(line)
        fun_m = fun_re.search(line)
        
        if fun_m:
            pending = ('fun', fun_m.group(1))
        elif obj_m:
            pending = ('object', obj_m.group(1))
        elif cls_m:
            pending = ('class', cls_m.group(1))
            
        for ch in line:
            if ch == '{':
                if pending:
                    stack.append(pending)
                    pending = None
                else:
                    stack.append(('block', ''))
            elif ch == '}':
                if stack:
                    stack.pop()
                    
        is_in_fun = any(s[0] == 'fun' for s in stack)
        enc_obj = next((s[1] for s in reversed(stack) if s[0] == 'object'), None)
        enc_cls = next((s[1] for s in reversed(stack) if s[0] == 'class'), None)
        scopes.append({
            "is_inside_function": is_in_fun,
            "enclosing_object": enc_obj,
            "enclosing_class": enc_cls,
        })
    return scopes


def scan_file_dimensions(content: str) -> List[dict]:
    """Scan for registered dimensions."""
    scopes = get_file_line_scopes(content)
    results = []
    for match in DIMENSION_REGISTRY.finditer(content):
        name = match.group(1)
        value = match.group(2)
        suffix = match.group(3) if match.lastindex >= 3 else "dp"
        line_num = content[:match.start()].count("\n") + 1
        line_start = content.rfind("\n", 0, match.start()) + 1
        column = match.start() - line_start + 1
        scope_obj = scopes[line_num - 1]["enclosing_object"] if line_num <= len(scopes) else None
        
        results.append({
            "name": name,
            "kind": "dimension",
            "value": value,
            "raw_value": f"{value}.{suffix}",
            "line": line_num,
            "column": column,
            "registry": "BridgeDimensionRegistry",
            "scope_object": scope_obj,
        })
    if not results:
        for match in STANDARD_DIMENSION.finditer(content):
            line_num = content[:match.start()].count("\n") + 1
            # Ignore local variables declared inside functions/composables/lambdas
            if line_num <= len(scopes) and scopes[line_num - 1]["is_inside_function"]:
                continue
            
            name = match.group(1)
            value = match.group(2)
            suffix = match.group(3) if match.lastindex >= 3 else "dp"
            line_start = content.rfind("\n", 0, match.start()) + 1
            column = match.start() - line_start + 1
            scope_obj = scopes[line_num - 1]["enclosing_object"] if line_num <= len(scopes) else None
            
            results.append({
                "name": name,
                "kind": "dimension",
                "value": value,
                "raw_value": f"{value}.{suffix}",
                "line": line_num,
                "column": column,
                "registry": "StandardTheme",
                "scope_object": scope_obj,
            })
    return results


def scan_file_colors(content: str) -> List[dict]:
    """Scan for registered colors."""
    scopes = get_file_line_scopes(content)
    results = []
    for match in COLOR_REGISTRY.finditer(content):
        name = match.group(1)
        value = match.group(2)
        line_num = content[:match.start()].count("\n") + 1
        line_start = content.rfind("\n", 0, match.start()) + 1
        column = match.start() - line_start + 1
        scope_obj = scopes[line_num - 1]["enclosing_object"] if line_num <= len(scopes) else None
        
        raw_val = value if (value.startswith("Color(") or value.startswith("Color.")) else f"Color({value})"
        results.append({
            "name": name,
            "kind": "color",
            "value": value,
            "raw_value": raw_val,
            "line": line_num,
            "column": column,
            "registry": "BridgeThemeRegistry",
            "scope_object": scope_obj,
        })
    if not results:
        for match in STANDARD_COLOR.finditer(content):
            line_num = content[:match.start()].count("\n") + 1
            # Ignore local variables inside functions/composables/lambdas
            if line_num <= len(scopes) and scopes[line_num - 1]["is_inside_function"]:
                continue
                
            name = match.group(1)
            value = match.group(2)
            line_start = content.rfind("\n", 0, match.start()) + 1
            column = match.start() - line_start + 1
            scope_obj = scopes[line_num - 1]["enclosing_object"] if line_num <= len(scopes) else None
            
            raw_val = value if (value.startswith("Color(") or value.startswith("Color.")) else f"Color({value})"
            results.append({
                "name": name,
                "kind": "color",
                "value": value,
                "raw_value": raw_val,
                "line": line_num,
                "column": column,
                "registry": "StandardTheme",
                "scope_object": scope_obj,
            })
    return results


def scan_file_hardcoded(content: str, exclude_names: set) -> List[dict]:
    """
    Scan for hardcoded values that could become tokens.
    
    exclude_names: set of registered token names (to avoid duplicates)
    """
    results = []
    lines = content.splitlines()
    
    # Hardcoded dimensions
    for match in HARDCODED_DP.finditer(content):
        value = match.group(1)
        line_num = content[:match.start()].count("\n") + 1
        line_text = lines[line_num - 1] if line_num <= len(lines) else ""
        
        # تخطَّ إذا كان جزءاً من BridgeDimensionRegistry.get
        if "BridgeDimensionRegistry" in line_text:
            continue
        
        # تخطَّ 0.dp
        if value == "0":
            continue
        
        category = detect_category(line_text)
        suggestion = suggest_token_name(category, f"{value}.dp", "dimension")
        
        line_start = content.rfind("\n", 0, match.start()) + 1
        column = match.start() - line_start + 1
        
        results.append({
            "value": f"{value}.dp",
            "kind": "dimension",
            "line": line_num,
            "column": column,
            "context": line_text.strip(),
            "category": category,
            "suggestion_name": suggestion,
        })
    
    # Hardcoded hex colors
    for match in HARDCODED_COLOR_HEX.finditer(content):
        value = match.group(1)
        line_num = content[:match.start()].count("\n") + 1
        line_text = lines[line_num - 1] if line_num <= len(lines) else ""
        
        if "BridgeThemeRegistry" in line_text:
            continue
        
        category = detect_category(line_text)
        suggestion = suggest_token_name(category, value, "color")
        
        line_start = content.rfind("\n", 0, match.start()) + 1
        column = match.start() - line_start + 1
        
        results.append({
            "value": value,
            "kind": "color",
            "line": line_num,
            "column": column,
            "context": line_text.strip(),
            "category": category,
            "suggestion_name": suggestion,
        })
    
    # Hardcoded font sizes
    for match in HARDCODED_SP.finditer(content):
        value = match.group(1)
        line_num = content[:match.start()].count("\n") + 1
        line_text = lines[line_num - 1] if line_num <= len(lines) else ""
        
        category = "font_size"
        suggestion = suggest_token_name(category, f"{value}.sp", "font_size")
        
        line_start = content.rfind("\n", 0, match.start()) + 1
        column = match.start() - line_start + 1
        
        results.append({
            "value": f"{value}.sp",
            "kind": "font_size",
            "line": line_num,
            "column": column,
            "context": line_text.strip(),
            "category": category,
            "suggestion_name": suggestion,
        })
    
    return results


# ═══════════════════════════════════════════════════════════
# Composable Detection & Token Usages
# ═══════════════════════════════════════════════════════════

COMPOSABLE_FUNC = re.compile(
    r'@Composable\s+(?:private\s+|public\s+|internal\s+)?fun\s+(\w+)\s*\(',
    re.MULTILINE
)


def build_composable_tree(content: str) -> List[dict]:
    """
    Build a tree of @Composable functions with parent-child relationships.
    
    Returns list of:
    {
        "name": "HeroCard",
        "start_line": 21,
        "end_line": 100,
        "parent": None | "DashboardPage",
        "children": ["Card", "Text", ...],
    }
    """
    lines = content.splitlines()
    composables = []
    
    for match in COMPOSABLE_FUNC.finditer(content):
        name = match.group(1)
        start_line = content[:match.start()].count("\n") + 1
        
        # ابحث عن نهاية الدالة (عدد { و })
        brace_count = 0
        end_line = start_line
        started = False
        
        for i in range(start_line - 1, len(lines)):
            line = lines[i]
            brace_count += line.count("{") - line.count("}")
            if "{" in line:
                started = True
            if started and brace_count == 0:
                end_line = i + 1
                break
        
        composables.append({
            "name": name,
            "start_line": start_line,
            "end_line": end_line,
        })
    
    # بناء العلاقات الأبوية
    for c in composables:
        c["parent"] = None
        c["children"] = []
        for other in composables:
            if other is c:
                continue
            if other["start_line"] < c["start_line"] and other["end_line"] >= c["end_line"]:
                # other يحتوي c
                if c["parent"] is None or other["start_line"] > composables[[x["name"] for x in composables].index(c["parent"])]["start_line"]:
                    c["parent"] = other["name"]
    
    for c in composables:
        if c["parent"]:
            parent = next((x for x in composables if x["name"] == c["parent"]), None)
            if parent:
                parent["children"].append(c["name"])
    
    return composables


EXCLUDE_COMP_CALLS = {
    "Modifier", "Color", "Dp", "Arrangement", "Alignment", "Brush", "FontWeight",
    "Icons", "BridgeDimensionRegistry", "BridgeThemeRegistry", "AppDimens", "AppColors",
    "String", "Boolean", "Int", "Float", "Double", "Long", "Unit", "List", "Set", "Map",
    "MutableList", "State", "MutableState", "Composable", "Preview", "OptIn",
}


def get_hierarchy_path(content: str, line_number: int) -> List[str]:
    """
    Get the full composable hierarchy path for a given line.
    
    Example: ["DashboardPage", "HeroCard", "Card", "Button", "Icon"]
    """
    tree = build_composable_tree(content)
    lines = content.splitlines()
    
    # ابحث عن كل composables التي تحتوي line_number
    containing = []
    for c in tree:
        if c["start_line"] <= line_number <= c["end_line"]:
            containing.append(c)
    
    if not containing:
        return ["_root"]
    
    # رتب حسب العمق (الأب أولاً)
    containing.sort(key=lambda x: x["start_line"])
    path = [c["name"] for c in containing]
    
    # ابحث عن المكونات الحاوية داخل الدالة (مثل Card, Button, Column, Box, etc.)
    innermost = containing[-1]
    start_idx = innermost["start_line"] - 1
    target_idx = line_number - 1
    
    comp_stack = []
    for i in range(start_idx, target_idx + 1):
        line = lines[i]
        # ابحث عن استدعاءات مكونات تبدأ بحرف كبير
        matches = re.finditer(r'\b([A-Z][a-zA-Z0-9_]*)\s*(?:[\(\{]|\.\w+)', line)
        for m in matches:
            name = m.group(1)
            if name not in EXCLUDE_COMP_CALLS and name not in path:
                comp_stack.append(name)
    
    if comp_stack:
        last_comp = comp_stack[-1]
        if last_comp not in path:
            path.append(last_comp)
    
    return path


def find_enclosing_composable(content: str, line_number: int) -> Tuple[str, int]:
    """
    Find the enclosing @Composable function for a given line.
    
    Returns:
        (composable_name, start_line) or ("_unknown", 0)
    """
    lines = content.splitlines()
    
    # ابحث عن كل @Composable functions قبل line_number
    composables = []
    for match in COMPOSABLE_FUNC.finditer(content):
        name = match.group(1)
        start_line = content[:match.start()].count("\n") + 1
        if start_line <= line_number:
            composables.append((name, start_line, match.end()))
    
    if not composables:
        return ("_unknown", 0)
    
    # ابحث عن أقرب composable قبل السطر (آخر واحد)
    composables.sort(key=lambda x: x[1], reverse=True)
    
    return (composables[0][0], composables[0][1])


def scan_file_usages(
    content: str,
    token_names: Set[str],
    token_scopes: Optional[Dict[str, Optional[str]]] = None,
) -> List[dict]:
    """
    Scan file for qualified usages of the given tokens.
    
    Prevents false positives by strictly requiring qualified references
    (e.g. AppColors.token, DesignSystem.token) or direct registry access.
    Does NOT search for bare variable names project-wide.
    """
    usages = []
    lines = content.splitlines()
    
    candidate_tokens = [t for t in token_names if t in content]
    if not candidate_tokens:
        return []

    token_scopes = token_scopes or {}
    patterns = []
    for token in candidate_tokens:
        # 1. Registry access
        patterns.append((token, re.compile(rf'BridgeDimensionRegistry\.get\(\s*"{re.escape(token)}"')))
        patterns.append((token, re.compile(rf'BridgeThemeRegistry\.getColor\(\s*["\']{re.escape(token)}["\']')))
        
        # 2. Scope-qualified references: e.g. AppColors.token or DesignSystem.token
        scope_obj = token_scopes.get(token)
        if scope_obj:
            patterns.append((token, re.compile(rf'\b{re.escape(scope_obj)}\.{re.escape(token)}\b')))
        
        # Common design system prefixes
        patterns.append((token, re.compile(rf'\b(?:AppColors|AppDimens|AppDesign|DesignSystem|Theme|Tokens|AppTheme|AppTokens|Dimensions|Spacing|AppSpacing)\.{re.escape(token)}\b')))
        
        # 3. If file has a direct static import of the token, allow unqualified reference
        # (NOT matching named parameter assignments like "strokeWidth = 2.dp")
        has_direct_import = bool(re.search(rf'import\s+[\w.]+\.{re.escape(token)}\b', content))
        has_wildcard_import = bool(scope_obj and re.search(rf'import\s+[\w.]+\.{re.escape(scope_obj)}\.\*', content))
        if has_direct_import or has_wildcard_import:
            patterns.append((token, re.compile(rf'(?<!\.)\b{re.escape(token)}\b(?!\s*=)')))
    
    seen = set()
    for token_name, pattern in patterns:
        for match in pattern.finditer(content):
            line_num = content[:match.start()].count("\n") + 1
            line_start = content.rfind("\n", 0, match.start()) + 1
            column = match.start() - line_start + 1
            
            line_text = lines[line_num - 1].strip() if line_num <= len(lines) else ""
            if line_text.startswith("import ") or line_text.startswith("package "):
                continue
            if re.search(rf'\bval\s+{re.escape(token_name)}\b', line_text):
                continue

            # Ignore comments
            line_before_match = content[line_start:match.start()]
            if '//' in line_before_match or '/*' in line_before_match:
                continue
            if line_text.startswith("//") or line_text.startswith("*") or line_text.startswith("/*"):
                continue

            # Ignore strings
            if not ("BridgeDimensionRegistry" in match.group() or "BridgeThemeRegistry" in match.group()):
                raw_line = lines[line_num - 1] if line_num <= len(lines) else ""
                if '"' in raw_line:
                    match_on_line_idx = match.start() - line_start
                    in_quoted_str = False
                    for m_str in re.finditer(r'"[^"]*"', raw_line):
                        if m_str.start() <= match_on_line_idx < m_str.end():
                            in_quoted_str = True
                            break
                    if in_quoted_str:
                        continue

            key = (token_name, line_num)
            if key in seen:
                continue
            seen.add(key)
            
            comp_name, comp_line = find_enclosing_composable(content, line_num)
            hierarchy_path = get_hierarchy_path(content, line_num)
            
            usages.append({
                "token_name": token_name,
                "line": line_num,
                "column": column,
                "line_content": line_text,
                "enclosing_composable": comp_name,
                "enclosing_line": comp_line,
                "hierarchy_path": hierarchy_path,
                "depth": len(hierarchy_path),
            })
    
    return usages
