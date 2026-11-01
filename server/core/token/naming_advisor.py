# -*- coding: utf-8 -*-
"""
وحدة فحص وتوليد أسماء التوكنز وكشف التعارضات الدلالية (Semantic Conflicts).
Handles token naming conventions, safe name suggestions, and semantic conflict detection.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

class NamingAdvisorMixin:
    """Mixin class providing token naming conventions and conflict detection for TokenMigrator."""

    CONTEXT_RULES = {
        # ═══ Spacing ═══
        "Spacer": ("spacing", "gap"),
        "Arrangement.spacedBy": ("spacing", "gap"),
        
        # ═══ Padding / Margin ═══
        "padding": ("padding",),
        "margin": ("margin",),
        
        # ═══ Sizes ═══
        "height": ("size", "height"),
        "width": ("size", "width"),
        "size": ("size", "icon"),
        "Modifier.size": ("size", "icon"),
        "Modifier.width": ("width", "size"),
        "Modifier.height": ("height", "size"),
        
        # ═══ Corners ═══
        "RoundedCornerShape": ("corner", "radius"),
        "CircleShape": ("radius",),
        
        # ═══ Typography ═══
        "fontSize": ("font_size", "text_size"),
        "fontWeight": ("font_weight",),
        
        # ═══ Colors ═══
        "Color(": ("color", "bg", "background", "text_color", "text", "accent", "hero", "primary", "secondary", "surface", "tertiary"),
        ".background(": ("bg", "background", "color", "hero", "primary", "secondary", "surface"),
        "contentColor": ("text_color", "text", "content_color"),
    }

    COMMON_SIZES = ("xs", "sm", "md", "lg", "xl", "2xl", "tiny", "small", "medium", "large", "huge", "mini", "compact", "none", "full")
    COMMON_COLORS = ("primary", "secondary", "tertiary", "surface", "background", "error", "outline", "tint", "accent", "pink", "blue", "green", "purple", "red", "yellow", "orange", "teal", "cyan", "gray", "grey", "black", "white")

    COLOR_CONTEXT_RULES = {
        # سياق الألوان: keyword → (prefix)
        "background": ("bg", "background"),
        "backgroundColor": ("bg", "background"),
        "containerColor": ("bg", "container"),
        "contentColor": ("text_color", "content"),
        "color =": ("text_color", "content"),
        "tint": ("tint", "icon_color"),
        "border": ("border", "stroke"),
        "borderColor": ("border", "stroke"),
        "Color(": ("color", "solid"),  # استخدام عام
        "Brush": ("brush", "gradient"),
    }



    def detect_naming_convention(self, token_type: str) -> dict:
        """
        Detect the naming convention used in existing tokens.
        
        Returns:
        {
            "style": "abbreviation" | "full" | "single" | "unknown",
            "examples": ["xs", "sm", "md", "lg", "xl"],
            "has_type_suffix": bool,  # مثل paddingSm, cornerMd
            "common_suffixes": ["_padding", "_corner", "_color"],
        }
        """
        files = self.find_all_token_files(token_type)
        all_names = []
        
        for f in files:
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                continue
            
            pattern = r'val\s+(\w+)\s*[:=]'
            for match in re.finditer(pattern, content):
                name = match.group(1)
                if name not in all_names:
                    all_names.append(name)
        
        if not all_names:
            return {"style": "unknown", "examples": []}
        
        # تحليل:
        abbreviations = {"xs", "sm", "md", "lg", "xl", "xxl", "2xl"}
        single_letter = {"s", "m", "l", "x"}
        common_words = {"small", "medium", "large", "extra_large", "tiny", "huge"}
        
        has_abbrev = any(n.lower() in abbreviations for n in all_names)
        has_single = any(n.lower() in single_letter for n in all_names)
        has_full = any(n.lower() in common_words for n in all_names)
        
        if has_single and not has_abbrev and not has_full:
            style = "single_letter"
        elif has_abbrev and not has_full:
            style = "abbreviation"
        elif has_full and not has_abbrev:
            style = "full"
        elif has_abbrev and has_full:
            style = "mixed"
        else:
            style = "custom"
        
        suffix_candidates = {}
        for name in all_names:
            for suffix in ["_padding", "_corner", "_color", "_bg", "_size",
                           "Padding", "Corner", "Color"]:
                if suffix in name:
                    suffix_candidates[suffix] = suffix_candidates.get(suffix, 0) + 1
        
        return {
            "style": style,
            "examples": all_names[:10],
            "total_count": len(all_names),
            "common_suffixes": list(suffix_candidates.keys()),
        }


    def suggest_token_name_by_convention(
        self,
        token_type: str,
        value: str,
        context: str = "padding",
    ) -> str:
        """
        Suggest a token name that follows existing naming convention.
        
        If existing tokens use abbreviation (xs, sm, md), 
        suggest "context_abbreviation".
        If existing tokens use full (small, medium),
        suggest "context_full".
        """
        convention = self.detect_naming_convention(token_type)
        style = convention["style"]
        
        if token_type == "dimension":
            num_match = re.match(r'([\d.]+)', value)
            if not num_match:
                return f"{context}_token"
            num = float(num_match.group(1))
            
            dimension_map = {
                "single_letter": {
                    4: "xs", 8: "s", 12: "m", 16: "m", 20: "l", 24: "l", 32: "xl"
                },
                "abbreviation": {
                    4: "xs", 8: "sm", 12: "sm", 16: "md", 20: "md",
                    24: "lg", 32: "xl", 40: "xxl"
                },
                "full": {
                    4: "tiny", 8: "small", 16: "medium", 
                    24: "large", 32: "extra_large"
                },
                "custom": {},
            }
            
            size_map = dimension_map.get(style, dimension_map["abbreviation"])
            
            size_name = "md"
            for size_value, name in sorted(size_map.items()):
                if num >= size_value:
                    size_name = name
            
            return f"{context}_{size_name}"
        
        elif token_type == "color":
            return f"{context}_color"
        
        return f"{context}_token"


    def detect_storage_style(self, registry_file: Path) -> str:
        """
        Detect how tokens are stored.
        
        Returns:
        - "registry": uses BridgeDimensionRegistry (Standard Design System style)
        - "object": object AppDimens { val x = 16.dp }
        - "top-level": val x = 16.dp (top-level)
        """
        try:
            content = registry_file.read_text(encoding="utf-8")
        except Exception:
            return "top-level"
        
        fname = registry_file.name
        if (
            "BridgeDimensionRegistry" in content or
            "BridgeThemeRegistry" in content or
            fname in ("DesignSystem.kt", "AppColors.kt", "AppDimens.kt") or
            "object AppColors" in content or
            "object AppDimens" in content
        ):
            return "registry"
        
        if re.search(r'\bobject\s+\w+\s*\{', content):
            return "object"
        
        return "top-level"


    def _suggest_safe_name(
        self,
        base_suggestion: str,
        token_type: str = "dimension",
        value: str = "",
    ) -> str:
        """
        Ensure the suggested name doesn't conflict with existing tokens.
        
        If the base suggestion conflicts, try alternatives:
        1. base_suggestion
        2. context + numeric value (e.g., padding_12)
        3. base_suggestion + numeric value (e.g., padding_sm_12)
        4. context + "new" (e.g., padding_new)
        5. context + "v2", context + "alt"
        
        Returns:
            A safe name that doesn't conflict.
        """
        candidates = [
            base_suggestion,
        ]
        
        clean_num = value.replace(".dp", "").replace(".sp", "").replace(".", "_")
        clean_num = clean_num.replace("Color(", "").replace(")", "").replace("0x", "").replace("0X", "").lower().strip()
        if not clean_num:
            clean_num = "1"

        parts = base_suggestion.split("_")
        if len(parts) >= 2:
            context = parts[0]
            suffix = parts[-1]
            candidates.append(f"{context}_{clean_num}")
            candidates.append(f"{base_suggestion}_{clean_num}")
            candidates.append(f"{context}_new")
            candidates.append(f"{context}_v2")
            candidates.append(f"{context}_alt")
        else:
            context = parts[0]
            candidates.append(f"{context}_{clean_num}")
            candidates.append(f"{context}_new")
            candidates.append(f"{context}_v2")
            candidates.append(f"{context}_alt")
        
        # ابحث عن أول اسم غير متناقض
        for candidate in candidates:
            # 1. تحقق أنه غير موجود
            if self._check_token_exists(candidate):
                continue
            
            # 2. تحقق من conflict دلالي
            conflict = self.detect_semantic_conflict(candidate, token_type, value)
            if conflict:
                continue
            
            return candidate
        
        # fallback: استخدم رقم متسلسل
        counter = 1
        while counter < 100:
            candidate = f"{base_suggestion}_{counter}"
            if not self._check_token_exists(candidate):
                return candidate
            counter += 1
        
        return base_suggestion


    def _validate_token_name(
        self,
        line_content: str,
        token_name: str,
        token_type: str = "dimension",
        value: str = "",
    ) -> Tuple[bool, str, str]:
        """
        Validate token_name against line context.
        Returns (is_valid, suggestion, reason).
        """
        matched_rules = []
        for keyword, expected_prefixes in self.CONTEXT_RULES.items():
            if keyword in line_content:
                matched_rules.append((keyword, expected_prefixes))
        
        if not matched_rules:
            return (True, token_name, "OK")
            
        # Check if token_name matches any expected prefix or suffix across all matched contexts
        all_expected = [p for _, prefixes in matched_rules for p in prefixes]
        if any(token_name.startswith(f"{p}_") or token_name.startswith(p) or token_name.endswith(f"_{p}") or token_name == p for p in all_expected):
            return (True, token_name, "OK")
            
        # Allow pure standalone standard T-shirt size names for dimensions (e.g. sm, md, lg, xs, xl)
        if token_name in self.COMMON_SIZES:
            return (True, token_name, "OK")

        # Allow pure standalone standard color names/roles
        if token_name in self.COMMON_COLORS:
            return (True, token_name, "OK")

        first_keyword, first_prefixes = matched_rules[0]
        suffix = token_name.split("_", 1)[1] if "_" in token_name else "md"
        base_suggested = f"{first_prefixes[0]}_{suffix}"
        
        # ⭐ NEW: ابحث عن اسم آمن غير متناقض
        safe_suggested = self._suggest_safe_name(
            base_suggested,
            token_type=token_type,
            value=value,
        )
        
        return (
            False,
            safe_suggested,
            f"Context '{first_keyword}' expects prefix {first_prefixes}. "
            f"'{token_name}' doesn't match. Suggested: '{safe_suggested}'"
        )


    def detect_semantic_conflict(
        self,
        token_name: str,
        token_type: str,
        value: str,
    ) -> Optional[dict]:
        """
        Detect if adding this token will create semantic confusion.
        
        Cases to detect:
        1. Same base name with different value exists
           - sm=8.dp exists, adding spacing_sm=12.dp
        2. Similar name that may confuse
           - sm=8.dp exists, adding sm=12.dp (would fail check_exists)
        3. Token with same value but different name exists
           - sm=8.dp exists, adding tiny=8.dp
        
        Returns:
            {
                "conflict": True,
                "type": "same_base_different_value" | "same_value_different_name",
                "existing_token": "sm",
                "existing_value": "8.dp",
                "message": "...",
                "suggestions": [...]
            }
            Or None if no conflict.
        """
        all_files = self.find_all_token_files(token_type)
        existing_tokens = []
        
        pattern = re.compile(
            r'val\s+(\w+)\s*(?::\s*[\w<>?.]+\s*)?(?:get\(\)\s*=\s*|=)[^\n]*?([\d.]+\.dp|Color\(0x[0-9A-Fa-f]+\)|0x[0-9A-Fa-f]+)'
        )
        for f in all_files:
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                continue
            
            for match in pattern.finditer(content):
                existing_tokens.append({
                    "name": match.group(1),
                    "value": match.group(2),
                    "file": f.name,
                })
        
        # فحص 1: نفس القيمة، اسم مختلف
        new_clean_value = value
        for token in existing_tokens:
            if token["value"] == new_clean_value:
                if token["name"] != token_name:
                    return {
                        "conflict": True,
                        "type": "same_value_different_name",
                        "existing_token": token["name"],
                        "existing_value": token["value"],
                        "existing_file": token["file"],
                        "new_name": token_name,
                        "safe_alternative": token["name"],
                        "message": (
                            f"Value '{value}' already exists as '{token['name']}' "
                            f"in {token['file']}. Creating '{token_name}' with same "
                            f"value may cause confusion."
                        ),
                        "suggestions": [
                            f"Use existing '{token['name']}' instead",
                            f"Rename existing '{token['name']}' to '{token_name}'",
                            f"Use force_create=True to add anyway",
                        ],
                    }
        
        # فحص 2: نفس الاسم الأساسي، قيمة مختلفة
        parts = token_name.split("_")
        if len(parts) >= 2:
            base_suffix = parts[-1]
            for token in existing_tokens:
                if token["name"] == base_suffix and token["value"] != value:
                    num = value.replace(".dp", "").replace(".sp", "").replace(".", "_")
                    safe_name = f"{parts[0]}_{num}"
                    counter = 1
                    while self._check_token_exists(safe_name):
                        safe_name = f"{parts[0]}_{num}_{counter}"
                        counter += 1

                    suggestions = [
                        f"Use '{token['name']}' (existing) with value {token['value']}",
                        f"Update '{token['name']}' to {value} if you want to change it",
                        f"Use '{safe_name}' instead (unique and context-aware)",
                        f"Use a different name like '{parts[0]}_other_{base_suffix}'",
                        f"Use force_create=True to add anyway",
                    ]

                    return {
                        "conflict": True,
                        "type": "same_base_different_value",
                        "existing_token": token["name"],
                        "existing_value": token["value"],
                        "existing_file": token["file"],
                        "new_name": token_name,
                        "new_value": value,
                        "safe_alternative": safe_name,
                        "message": (
                            f"'{base_suffix}' already exists with value "
                            f"'{token['value']}' in {token['file']}. Adding "
                            f"'{token_name}' with value '{value}' may cause "
                            f"semantic confusion."
                        ),
                        "suggestions": suggestions,
                    }
        
        return None


    def _find_existing_tokens(self, value: str, token_type: str) -> list:
        """
        Find all existing tokens with same value.
        Returns list of token names.
        """
        from .project_scanner import ProjectScanner
        scanner = ProjectScanner(self.project_root)
        report = scanner.scan(include_hardcoded=False)
        
        # Clean value for comparison
        clean = value.replace(".dp", "").replace(".sp", "").strip()
        clean = clean.replace("Color(", "").replace(")", "").strip()
        if clean.startswith("0x") or clean.startswith("0X"):
            clean = clean.upper()
        
        matches = []
        for token in report.registered_tokens:
            if token.kind == token_type:
                token_clean = token.value.replace(".dp", "").replace(".sp", "").strip()
                token_clean = token_clean.replace("Color(", "").replace(")", "").strip()
                if token_clean.startswith("0x") or token_clean.startswith("0X"):
                    token_clean = token_clean.upper()
                if token_clean == clean:
                    if token.name not in matches:
                        matches.append(token.name)
        return matches


    def _find_existing_token(self, value: str, token_type: str) -> Optional[str]:
        """Backward-compatible helper returning single or comma-separated token names."""
        matches = self._find_existing_tokens(value, token_type)
        return ", ".join(matches) if matches else None


    def _get_existing_token_info(self, token_name: str, token_type: str) -> Optional[dict]:
        """Get info of an existing token (value, registry file, object name)."""
        for f in self.find_all_token_files(token_type):
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                continue
            
            pattern = rf'\bval\s+{re.escape(token_name)}\b.*?(?:getColor\([^,]+,\s*(Color\([^)]+\)|Color\.\w+|0x[0-9A-Fa-f]+)|=\s*(Color\([^)]+\)|Color\.\w+|0x[0-9A-Fa-f]+|[\d.]+\.dp))'
            m = re.search(pattern, content, re.DOTALL)
            if m:
                val = m.group(1) or m.group(2)
                obj_match = re.search(r'\bobject\s+(\w+)', content)
                obj_name = obj_match.group(1) if obj_match else f.stem
                return {
                    "value": val,
                    "file": f,
                    "object_name": obj_name,
                    "content": content,
                }
            for line in content.splitlines():
                if re.search(rf'\bval\s+{re.escape(token_name)}\b', line):
                    m_reg = re.search(r'BridgeThemeRegistry\.getColor\([^,]+,\s*(Color\([^)]+\)|Color\.\w+|0x[0-9A-Fa-f]+)', line)
                    if m_reg:
                        val = m_reg.group(1)
                    else:
                        match = re.search(r'([\d.]+\.dp|Color\([^)]+\)|Color\.\w+|0x[0-9A-Fa-f]+)', line)
                        val = match.group(1) if match else None
                    obj_match = re.search(r'\bobject\s+(\w+)', content)
                    obj_name = obj_match.group(1) if obj_match else f.stem
                    return {
                        "value": val,
                        "file": f,
                        "object_name": obj_name,
                        "content": content,
                    }
        return None


    def _get_existing_token_value(self, token_name: str, token_type: str) -> Optional[str]:
        """Get the value of an existing token."""
        info = self._get_existing_token_info(token_name, token_type)
        return info["value"] if info else None


CONTEXT_RULES = NamingAdvisorMixin.CONTEXT_RULES
COLOR_CONTEXT_RULES = NamingAdvisorMixin.COLOR_CONTEXT_RULES
