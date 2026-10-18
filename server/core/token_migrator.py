# -*- coding: utf-8 -*-
"""
Token Migrator — Convert hardcoded values to design tokens.

Safety:
- Uses filelock for cross-process safety
- Verifies token_name doesn't exist
- Verifies line contains expected value
- Backup before edit
- Only modifies the specified line
"""

import re
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from datetime import datetime

from .write_lock import acquire_write_lock


class TokenMigrator:
    """Migrate hardcoded value to a design token."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.state_dir = project_root / ".composebridge-state"
        self.state_dir.mkdir(exist_ok=True)
        self.backup_dir = self.state_dir / "migration_backups"
        self.backup_dir.mkdir(exist_ok=True)
        from .state_events import EventLog
        self.events = EventLog(self.state_dir / "events.jsonl")
        self.package_name = self.detect_package_name(self.project_root)

    def detect_package_name(self, project_root: Path) -> str:
        """
        Detect the project's package name.
        
        Priority:
        1. From AndroidManifest.xml (package="...")
        2. From build.gradle.kts (namespace = "...")
        3. From first .kt file's package declaration
        """
        # Try AndroidManifest.xml
        for manifest in project_root.rglob("AndroidManifest.xml"):
            if "build" in str(manifest):
                continue
            try:
                content = manifest.read_text(encoding="utf-8")
                match = re.search(r'package="([^"]+)"', content)
                if match:
                    return match.group(1)
            except Exception:
                pass
        
        # Try build.gradle.kts
        for gradle in project_root.rglob("build.gradle.kts"):
            if "build" in str(gradle):
                continue
            try:
                content = gradle.read_text(encoding="utf-8")
                match = re.search(r'namespace\s*=\s*"([^"]+)"', content)
                if match:
                    return match.group(1)
            except Exception:
                pass
        
        # Try first .kt file
        for kt in project_root.rglob("*.kt"):
            if "build" in str(kt) or ".composebridge-state" in str(kt):
                continue
            try:
                content = kt.read_text(encoding="utf-8")
                match = re.search(r'^\s*package\s+([\w.]+)', content, re.MULTILINE)
                if match:
                    return match.group(1)
            except Exception:
                pass
        
        return "com.example.app"  # fallback
    
    def _find_registry_file(self, token_type: str) -> Optional[Path]:
        """
        Find the file where tokens are stored.
        
        Priority:
        1. AppDimens.kt / AppColors.kt (StudentApp style)
        2. Theme.kt / Color.kt / Dimens.kt (standard Compose)
        3. Any file with 'val .*Color' pattern
        4. None (needs creation)
        """
        candidates = {
            "dimension": ["AppDimens.kt", "DesignSystem.kt", "Dimens.kt", "Dimensions.kt", "Theme.kt"],
            "color": ["AppColors.kt", "DesignSystem.kt", "Color.kt", "Colors.kt", "Theme.kt"],
        }
        
        for name in candidates.get(token_type, []):
            for f in self.project_root.rglob(name):
                s = str(f)
                if "build" not in s and ".composebridge" not in s and "composebridge-agent" not in s and "backup" not in s.lower():
                    return f
        
        # Fallback: search for patterns
        if token_type == "color":
            pattern = re.compile(r'val\s+\w+\s*[:=].*Color\(')
        else:
            pattern = re.compile(r'val\s+\w+\s*[:=].*\.dp')
        
        for kt in self.project_root.rglob("*.kt"):
            s = str(kt)
            if "build" in s or ".composebridge" in s or "composebridge-agent" in s or "backup" in s.lower():
                continue
            try:
                content = kt.read_text(encoding="utf-8")
                if pattern.search(content):
                    return kt
            except Exception:
                continue
        
        return None

    def _find_design_system(self) -> Optional[Path]:
        """Find the DesignSystem.kt or AppColors.kt file in the project."""
        return self._find_registry_file("color")

    def create_color_token(
        self,
        token_name: str,
        value_expr: str,              # new value (لـ Registry override)
        original_value: str = None,   # default في DesignSystem
    ) -> Dict:
        """
        Create a color token safely.
        
        CRITICAL: Ensure clean Kotlin syntax.
        - Normalize hex → Color(0xAARRGGBB)
        - Ensure single set of parentheses
        - Validate token_name (Kotlin identifier)
        """
        try:
            # ⭐ 1. Validate token_name — Kotlin identifier
            if not re.match(r'^[A-Za-z][A-Za-z0-9_]*$', token_name):
                return {
                    "success": False,
                    "error": f"Invalid token name: '{token_name}' (must be a valid Kotlin identifier)",
                }
            
            # ⭐ 2. Normalize values
            def _normalize(val: str) -> str:
                """Return clean 'Color(0xAARRGGBB)' or 'Color.Name'."""
                if not val:
                    return "Color.Transparent"
                val = val.strip()
                
                # Already clean
                if val.startswith("Color."):
                    return val
                
                # Color(0x...) — ensure single parens
                if val.startswith("Color("):
                    match = re.search(r'0x([0-9A-Fa-f]+)', val)
                    if not match:
                        return "Color.Transparent"
                    hex_str = match.group(1).upper()
                elif val.startswith("0x") or val.startswith("0X"):
                    hex_str = val[2:].upper()
                elif val.startswith("#"):
                    hex_str = val[1:].upper()
                else:
                    hex_str = val.upper()
                
                # Ensure 8 chars (ARGB)
                if len(hex_str) == 6:
                    hex_str = "FF" + hex_str
                elif len(hex_str) == 3:
                    hex_str = "FF" + "".join(c * 2 for c in hex_str)
                elif len(hex_str) != 8:
                    return "Color.Transparent"
                
                return f"Color(0x{hex_str})"
            
            default_expr = _normalize(original_value) if original_value else _normalize(value_expr)
            override_expr = _normalize(value_expr)
            
            # ⭐ 3. Find DesignSystem.kt
            design_system = self._find_design_system()
            if not design_system or not design_system.exists():
                return {"success": False, "error": "DesignSystem.kt not found"}
            
            content = design_system.read_text(encoding="utf-8")
            
            # ⭐ 4. Check if token exists
            if re.search(rf'\bval\s+{re.escape(token_name)}\b', content):
                return {
                    "success": True,
                    "already_existed": True,
                    "token_name": token_name,
                    "default_value": default_expr,
                    "override_value": override_expr,
                    "file": str(design_system.relative_to(self.project_root)),
                }
            
            # ⭐ 5. Find object AppColors
            match = re.search(r'object\s+AppColors\s*\{', content)
            if not match:
                return {"success": False, "error": "object AppColors not found"}
            
            # ⭐ 6. Build CLEAN token line
            token_line = (
                f'    val {token_name}: Color get() = '
                f'BridgeThemeRegistry.getColor("{token_name}", {default_expr})'
            )
            
            # ⭐ 7. Validate token_line with helper
            is_valid, error = self._validate_kotlin_syntax(token_line)
            if not is_valid:
                return {
                    "success": False,
                    "error": f"Generated invalid Kotlin: {error}",
                    "generated_line": token_line,
                }
            
            # ⭐ 8. Insert after object AppColors {
            insert_pos = match.end()
            newline_pos = content.find('\n', insert_pos)
            if newline_pos < 0:
                return {"success": False, "error": "Invalid DesignSystem structure"}
            
            # ⭐ 9. Build new content
            new_content = (
                content[:newline_pos + 1]
                + token_line + '\n'
                + content[newline_pos + 1:]
            )
            
            # ⭐ 10. VALIDATE final syntax
            if ')))' in new_content:
                return {
                    "success": False,
                    "error": "Generated content has malformed parens",
                    "generated_line": token_line,
                }
            
            # ⭐ 11. Journal (for rollback)
            try:
                try:
                    from core.pattern_journal import PatternJournal
                except ImportError:
                    from .pattern_journal import PatternJournal
                journal = PatternJournal(self.project_root)
                journal.record_change(
                    file=str(design_system.relative_to(self.project_root)),
                    line=content[:newline_pos + 1].count('\n') + 1,
                    old_line="",
                    new_line=token_line,
                    pattern_id=f"create_token_{token_name}",
                )
            except Exception as e:
                import logging
                logging.error(f"[TOKEN_MIGRATOR] Journal record failed: {e}")
            
            # ⭐ 12. Write
            design_system.write_text(new_content, encoding="utf-8")
            
            return {
                "success": True,
                "token_name": token_name,
                "default_value": default_expr,
                "override_value": override_expr,
                "token_line": token_line,
                "file": str(design_system.relative_to(self.project_root)),
            }
        
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }

    @staticmethod
    def _validate_kotlin_syntax(token_line: str) -> Tuple[bool, str]:
        """
        Basic sanity check for Kotlin token declaration syntax.
        Returns (is_valid, error_message).
        """
        pattern = r'^\s*val\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*Color\s+get\(\)\s*=\s*.+$'
        if not re.match(pattern, token_line):
            return False, f"Doesn't match 'val X: Color get() = ...' pattern"
        
        if token_line.count("(") != token_line.count(")"):
            return False, "Unbalanced parentheses"
        
        if ")))" in token_line:
            return False, "Triple parentheses detected"
        
        if not token_line.rstrip().endswith(")"):
            return False, "Line must end with )"
        
        return True, ""

    def find_all_token_files(self, token_type: str) -> List[Path]:
        """
        Find ALL files that contain tokens of the given type.
        
        Returns list of paths sorted by preference.
        """
        candidates = []
        
        for kt in self.project_root.rglob("*.kt"):
            s = str(kt)
            if "build" in s or ".composebridge-state" in s or "\\bridge\\" in s or "/bridge/" in s or "composebridge-agent" in s:
                continue
            try:
                content = kt.read_text(encoding="utf-8")
            except Exception:
                continue
            
            # هل يحتوي على tokens من النوع المطلوب؟
            if token_type == "dimension":
                # ابحث عن val.*=.*\.dp أو BridgeDimensionRegistry
                if re.search(r'val\s+\w+.*[:=].*[\d.]+\.dp', content) or \
                   "BridgeDimensionRegistry" in content:
                    candidates.append(kt)
            elif token_type == "color":
                if re.search(r'val\s+\w+.*[:=].*Color\(', content) or \
                   "BridgeThemeRegistry" in content:
                    candidates.append(kt)
        
        # Sort: files with pattern indicators first
        def sort_key(path):
            name = path.stem.lower()
            score = 0
            if "token" in name: score -= 100
            if "theme" in name: score -= 50
            if "dimens" in name or "colors" in name: score -= 25
            return score
        
        candidates.sort(key=sort_key)
        return candidates

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
        - "registry": uses BridgeDimensionRegistry (StudentApp style)
        - "object": object AppDimens { val x = 16.dp }
        - "top-level": val x = 16.dp (top-level)
        """
        try:
            content = registry_file.read_text(encoding="utf-8")
        except Exception:
            return "top-level"
        
        if "BridgeDimensionRegistry" in content or "BridgeThemeRegistry" in content:
            return "registry"
        
        if re.search(r'\bobject\s+\w+\s*\{', content):
            return "object"
        
        return "top-level"
    
    def _check_token_exists(self, token_name: str) -> bool:
        """Check if token already exists anywhere."""
        for kt in self.project_root.rglob("*.kt"):
            if "build" in str(kt) or ".composebridge-state" in str(kt):
                continue
            try:
                content = kt.read_text(encoding="utf-8")
            except Exception:
                continue
            if f'"{token_name}"' in content or re.search(rf'\bval\s+{re.escape(token_name)}\b', content):
                return True
        return False
    
    def _backup_file(self, file_path: Path) -> Path:
        """Create a backup of the file."""
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        backup = self.backup_dir / f"{file_path.stem}_{ts}{file_path.suffix}.bak"
        shutil.copy2(file_path, backup)
        return backup
    
    def _generate_registry_entry(
        self,
        token_name: str,
        value: str,
        token_type: str,
        style: str = "registry",
    ) -> Optional[str]:
        """Generate registry entry based on storage style."""
        if token_type == "dimension":
            numeric = value.replace(".dp", "")
            value_expr = f"{numeric}.dp"
        else:
            # Color(0x...) أو Color(r,g,b)
            if value.startswith("Color("):
                value_expr = value
            # Color.White, Color.Black, Color.LightGray, Color.Gray, etc.
            elif value.startswith("Color.") and not value.startswith("Color("):
                value_expr = value
            # 0xFF... أو #...
            elif value.startswith("0x") or value.startswith("#"):
                value_expr = f"Color({value})"
            else:
                value_expr = value
        
        if style == "registry":
            if token_type == "dimension":
                return f'    val {token_name}: Dp get() = BridgeDimensionRegistry.get("{token_name}", {value_expr})'
            else:
                return f'    val {token_name}: Color get() = BridgeThemeRegistry.getColor("{token_name}", {value_expr})'
        elif style == "object":
            return f'    val {token_name} = {value_expr}'
        else:  # top-level
            return f'val {token_name} = {value_expr}'
    
    def _is_safe_to_replace(self, line_content: str, value: str) -> Tuple[bool, str]:
        """
        Check if line is safe to replace.
        
        Returns:
            (is_safe: bool, reason: str)
        """
        # ═══ 1. Check if value is in a comment ═══
        if "//" in line_content:
            comment_idx = line_content.index("//")
            value_idx = line_content.find(value)
            if value_idx != -1 and value_idx > comment_idx:
                return (False, f"Value '{value}' is in a comment")
        
        if "/*" in line_content and "*/" in line_content:
            comment_start = line_content.index("/*")
            comment_end = line_content.index("*/")
            value_idx = line_content.find(value)
            if comment_start < value_idx < comment_end:
                return (False, f"Value '{value}' is in a comment")

        # ═══ 2. Check if value is in a string ═══
        strings = re.findall(r'"[^"]*"', line_content)
        for s in strings:
            if value in s:
                return (False, f"Value '{value}' is inside a string")
        
        # ⭐ Check for parameter default (requires type annotation before =)
        # مثال: fun foo(x: Dp = 16.dp) → رفض
        # مثال: padding(horizontal = 16.dp) → قبول
        if re.search(rf':\s*[\w<>?\.]+\s*=\s*{re.escape(value)}\b', line_content):
            return (False, f"Value '{value}' appears to be a parameter default")
        
        return (True, "OK")

    def _extract_package(self, content: str) -> str:
        """Extract package name from Kotlin source."""
        match = re.search(r'package\s+([\w.]+)', content)
        return match.group(1) if match else ""

    def _needs_import(self, file_content: str, import_line: Optional[str]) -> bool:
        """Check if import is needed."""
        if not import_line:
            return False
        if import_line in file_content:
            return False
        pkg = import_line.rsplit(".", 1)[0]
        if f"{pkg}.*" in file_content:
            return False
        return True

    def _add_import(self, content: str, import_line: str) -> str:
        """Insert import in correct position (after package, among imports)."""
        lines = content.splitlines()
        last_import = -1
        package_idx = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("package "):
                package_idx = i
            elif stripped.startswith("import "):
                last_import = i
            elif stripped and not stripped.startswith("//") and not stripped.startswith("/*") and not stripped.startswith("*"):
                if package_idx != -1 and last_import == -1:
                    break
        
        if last_import != -1:
            lines.insert(last_import + 1, import_line)
        elif package_idx != -1:
            lines.insert(package_idx + 1, import_line)
        else:
            lines.insert(0, import_line)
            
        return "\n".join(lines)

    def _ensure_registry_imports(self, reg_content: str, token_type: str, style: str) -> str:
        """Ensure required imports are present in registry file."""
        if token_type == "dimension":
            if "import androidx.compose.ui.unit.dp" not in reg_content:
                reg_content = self._add_import(reg_content, "import androidx.compose.ui.unit.dp")
            if style == "registry" and "import androidx.compose.ui.unit.Dp" not in reg_content:
                reg_content = self._add_import(reg_content, "import androidx.compose.ui.unit.Dp")
        elif token_type == "color":
            if "import androidx.compose.ui.graphics.Color" not in reg_content:
                reg_content = self._add_import(reg_content, "import androidx.compose.ui.graphics.Color")
            if "import com.composebridge.agent.BridgeThemeRegistry" not in reg_content:
                reg_content = self._add_import(reg_content, "import com.composebridge.agent.BridgeThemeRegistry")
        return reg_content

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

    def _find_registry_insertion_point(self, registry_content: str, style: str = "registry") -> int:
        """Find the line to insert the new token."""
        lines = registry_content.splitlines()
        
        if style == "registry":
            last_idx = -1
            for i, line in enumerate(lines):
                if "BridgeDimensionRegistry.get" in line or "BridgeThemeRegistry.getColor" in line:
                    last_idx = i
            if last_idx != -1:
                return last_idx + 1

        if style in ("registry", "object"):
            # Look for closing brace of object
            obj_idx = -1
            for i, line in enumerate(lines):
                if re.search(r'\bobject\s+\w+', line):
                    obj_idx = i
                    break
            if obj_idx != -1:
                brace_count = 0
                started = False
                for i in range(obj_idx, len(lines)):
                    brace_count += lines[i].count("{") - lines[i].count("}")
                    if "{" in lines[i]:
                        started = True
                    if started and brace_count == 0:
                        return i
                for i in range(len(lines) - 1, -1, -1):
                    if "}" in lines[i]:
                        return i

        # top-level style or fallback:
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip():
                return i + 1
        return len(lines)
    
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

    def migrate(
        self,
        file_name: str,
        line: int,
        value: str,
        token_name: str,
        token_type: str,
        preferred_token_file: Optional[str] = None,
        force_create: bool = False,
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        Migrate hardcoded value to token.
        
        Args:
            file_name: "DashboardPage.kt"
            line: line number (1-indexed)
            value: expected value in that line ("16.dp" or "0xFF7C3AED")
            token_name: new token name ("padding_md")
            token_type: "dimension" | "color"
            force_create: bypass duplicate token value check
        
        Returns:
            (success, message, info)
        """
        with acquire_write_lock():
            # Ensure line is integer
            try:
                line = int(line)
            except (ValueError, TypeError):
                return (False, f"Invalid line number: {line}", None)

            # ═══ 1. Validate token_type ═══
            if token_type not in ("dimension", "color"):
                return (False, f"Invalid token_type: {token_type}", None)
            
            # ⭐ التحقق من نوع القيمة
            if token_type == "dimension":
                # الأبعاد المدعومة: أرقام فقط تنتهي بـ .dp
                if not re.match(r'^\d+(\.\d+)?\.dp$', value):
                    return (False, f"Unsupported dimension value: '{value}'. Only numeric .dp values are supported.", None)
            elif token_type == "color":
                # الألوان المدعومة: hex, Color(hex), Color(r,g,b), Color(named args), Color.White, Color.LightGray, etc.
                pass
            
            # ═══ 2. Check token_name not exists ═══
            # ─── 2. Check token_name exists / Smart Token Reuse ───
            if self._check_token_exists(token_name):
                token_info = self._get_existing_token_info(token_name, token_type)
                existing_value = token_info["value"] if token_info else self._get_existing_token_value(token_name, token_type)
                
                new_value_clean = value.replace(".dp", "").replace(".sp", "").strip()
                new_value_clean = new_value_clean.replace("Color(", "").replace(")", "").strip()
                if new_value_clean.startswith("0x") or new_value_clean.startswith("0X"):
                    new_value_clean = new_value_clean.upper()
                    
                existing_value_clean = (existing_value or "").replace(".dp", "").replace(".sp", "").strip()
                existing_value_clean = existing_value_clean.replace("Color(", "").replace(")", "").strip()
                if existing_value_clean.startswith("0x") or existing_value_clean.startswith("0X"):
                    existing_value_clean = existing_value_clean.upper()

                if existing_value and (existing_value_clean == new_value_clean or existing_value == value):
                    # ⭐ Reuse existing token!
                    target_files = list(self.project_root.rglob(file_name))
                    target_files = [f for f in target_files 
                                  if "build" not in str(f) and ".composebridge-state" not in str(f)]
                    if not target_files:
                        return (False, f"File not found: {file_name}", None)
                    target_file = target_files[0]
                    
                    try:
                        content = target_file.read_text(encoding="utf-8")
                    except Exception as e:
                        return (False, f"Cannot read file: {e}", None)

                    lines = content.splitlines()
                    if line < 1 or line > len(lines):
                        return (False, f"Line {line} out of range (file has {len(lines)} lines)", None)
                    
                    target_line = lines[line - 1]
                    if value not in target_line:
                        return (False, f"Line {line} does not contain '{value}'", {
                            "line_content": target_line.strip(),
                        })
                    
                    is_safe, reason = self._is_safe_to_replace(target_line, value)
                    if not is_safe:
                        return (False, f"Cannot replace: {reason}", {
                            "line_content": target_line.strip(),
                            "reason": reason,
                        })

                    target_backup = self._backup_file(target_file)
                    try:
                        reg_file = token_info["file"] if token_info else None
                        reg_content = token_info["content"] if token_info else (reg_file.read_text(encoding="utf-8") if reg_file else "")
                        reg_pkg = self._extract_package(reg_content)
                        target_pkg = self._extract_package(content)
                        
                        obj_name = token_info.get("object_name") if token_info else (reg_file.stem if reg_file else None)
                        if obj_name:
                            scoped_name = f"{obj_name}.{token_name}"
                            if reg_pkg and reg_pkg != target_pkg:
                                new_import = f"import {reg_pkg}.{obj_name}"
                            else:
                                new_import = None
                        else:
                            scoped_name = token_name
                            if reg_pkg and reg_pkg != target_pkg:
                                new_import = f"import {reg_pkg}.{token_name}"
                            else:
                                new_import = None

                        old_line = lines[line - 1]
                        if token_type == "dimension":
                            pattern = re.compile(rf'\b{re.escape(value)}\b')
                        else:
                            if f"Color({value})" in old_line:
                                pattern = re.compile(rf'Color\(\s*{re.escape(value)}\s*\)')
                            else:
                                pattern = re.compile(rf'(?<![\w]){re.escape(value)}(?![\w])')

                        new_line = pattern.sub(scoped_name, old_line, count=1)
                        if new_line == old_line:
                            shutil.copy2(target_backup, target_file)
                            return (False, f"Replacement failed: '{value}' not found as standalone", None)
                        
                        lines[line - 1] = new_line
                        updated_target_content = "\n".join(lines) + "\n"
                        if new_import and self._needs_import(updated_target_content, new_import):
                            updated_target_content = self._add_import(updated_target_content, new_import)

                        target_file.write_text(updated_target_content, encoding="utf-8")
                        return (
                            True,
                            f"Reused existing token '{token_name}' in {file_name}:{line}",
                            {
                                "action": "reuse_existing",
                                "token_name": token_name,
                                "replaced_in": f"{file_name}:{line}",
                                "reused": True,
                                "old_line": old_line.strip(),
                                "new_line": new_line.strip(),
                            }
                        )
                    except Exception as e:
                        shutil.copy2(target_backup, target_file)
                        return (False, f"Target edit failed: {e}", None)
                else:
                    return (
                        False,
                        f"Token '{token_name}' exists with different value '{existing_value}'",
                        {
                            "conflict_type": "same_name_different_value",
                            "existing_token": token_name,
                            "existing_value": existing_value,
                            "new_value": value,
                        }
                    )
            
            # ═══ 3. Find target file ═══
            target_files = list(self.project_root.rglob(file_name))
            target_files = [f for f in target_files 
                          if "build" not in str(f) and ".composebridge-state" not in str(f)]
            if not target_files:
                return (False, f"File not found: {file_name}", None)
            
            target_file = target_files[0]
            
            # ═══ 4. Read target file ═══
            try:
                content = target_file.read_text(encoding="utf-8")
            except Exception as e:
                return (False, f"Cannot read file: {e}", None)
            
            lines = content.splitlines()
            if line < 1 or line > len(lines):
                return (False, f"Line {line} out of range (file has {len(lines)} lines)", None)
            
            # ═══ 5. Verify line contains expected value ═══
            target_line = lines[line - 1]
            if value not in target_line:
                return (False, f"Line {line} does not contain '{value}'", {
                    "line_content": target_line.strip(),
                })
            
            # ⭐ Context safety check
            is_safe, reason = self._is_safe_to_replace(target_line, value)
            if not is_safe:
                return (False, f"Cannot replace: {reason}", {
                    "line_content": target_line.strip(),
                    "reason": reason,
                })
            
            # ⭐ Context-based naming validation (bypassed if force_create)
            if not force_create:
                is_valid, suggestion, reason = self._validate_token_name(
                    target_line, token_name, token_type=token_type, value=value
                )
                if not is_valid:
                    return (
                        False,
                        f"Token name invalid: {reason}",
                        {
                            "line_content": target_line.strip(),
                            "given_name": token_name,
                            "suggested_name": suggestion,
                            "safe_alternative": suggestion,
                            "recommended_name": suggestion,
                            "validation_type": "semantic",
                        }
                    )
            
            # ⭐ NEW: Semantic conflict detection
            if not force_create:
                conflict = self.detect_semantic_conflict(
                    token_name, token_type, value
                )
                if conflict:
                    info_dict = {
                        "conflict_type": conflict["type"],
                        "existing_token": conflict["existing_token"],
                        "existing_value": conflict["existing_value"],
                        "existing_file": conflict["existing_file"],
                        "new_name": token_name,
                        "new_value": value,
                        "suggestions": conflict["suggestions"],
                    }
                    if "safe_alternative" in conflict:
                        info_dict["safe_alternative"] = conflict["safe_alternative"]
                        info_dict["recommended_name"] = conflict["safe_alternative"]
                    return (
                        False,
                        conflict["message"],
                        info_dict,
                    )

            # ⭐ Duplicate detection (Consolidation fallback)
            if not force_create:
                existing_tokens = self._find_existing_tokens(value, token_type)
                if existing_tokens:
                    prefix = "AppDimens" if token_type == "dimension" else "AppColors"
                    if len(existing_tokens) > 1:
                        tokens_str = ", ".join(existing_tokens)
                        return (
                            False,
                            f"Multiple tokens with same value already exist: {tokens_str}. "
                            f"Use {prefix}.{existing_tokens[0]} or {prefix}.{existing_tokens[1]} instead of creating '{token_name}'.",
                            {
                                "existing_tokens": existing_tokens,
                                "value": value,
                                "suggestion": f"Use {prefix}.{existing_tokens[0]}",
                            }
                        )
                    else:
                        existing = existing_tokens[0]
                        return (
                            False,
                            f"Token with same value already exists: '{existing}'. "
                            f"Use {prefix}.{existing} instead of creating '{token_name}'.",
                            {
                                "existing_token": existing,
                                "value": value,
                                "suggestion": f"Use {prefix}.{existing}",
                            }
                        )
            
            # ═══ 6. Find registry file ═══
            if preferred_token_file:
                # ابحث عن الملف المحدد
                matches = list(self.project_root.rglob(preferred_token_file))
                registry_file = next(
                    (m for m in matches if "build" not in str(m) and ".composebridge-state" not in str(m)),
                    None,
                )
                if not registry_file:
                    return (False, f"Preferred file not found: {preferred_token_file}", None)
            else:
                # ابحث عن الملف القياسي أولاً (مثل AppColors أو DesignSystem)
                registry_file = self._find_registry_file(token_type)
                if not registry_file:
                    all_files = self.find_all_token_files(token_type)
                    registry_file = all_files[0] if all_files else None

            if not registry_file:
                return (False, f"Registry file not found for type: {token_type}", None)
            
            style = self.detect_storage_style(registry_file)

            # ═══ 7. Generate new registry entry ═══
            new_entry = self._generate_registry_entry(token_name, value, token_type, style=style)
            if not new_entry:
                return (False, "Cannot generate registry entry", None)
            
            # ═══ 8. Backup both files ═══
            target_backup = self._backup_file(target_file)
            registry_backup = self._backup_file(registry_file)
            
            # ═══ 9. Modify registry file ═══
            try:
                reg_content = registry_file.read_text(encoding="utf-8")
                reg_content = self._ensure_registry_imports(reg_content, token_type, style)
                insert_idx = self._find_registry_insertion_point(reg_content, style=style)
                reg_lines = reg_content.splitlines()
                reg_lines.insert(insert_idx, new_entry)
                registry_file.write_text("\n".join(reg_lines) + "\n", encoding="utf-8")
            except Exception as e:
                # Rollback registry
                shutil.copy2(registry_backup, registry_file)
                return (False, f"Registry edit failed: {e}", None)
            
            # ═══ 10. Replace in target file with scoping and auto-import ═══
            try:
                reg_pkg = self._extract_package(reg_content)
                target_pkg = self._extract_package(content)
                
                obj_match = re.search(r'\bobject\s+(\w+)', reg_content)
                if obj_match:
                    obj_name = obj_match.group(1)
                else:
                    obj_name = None

                if style in ("registry", "object") or obj_name:
                    actual_obj = obj_name if obj_name else registry_file.stem
                    scoped_name = f"{actual_obj}.{token_name}"
                    if reg_pkg and reg_pkg != target_pkg:
                        new_import = f"import {reg_pkg}.{actual_obj}"
                    else:
                        new_import = None
                else:  # top-level
                    scoped_name = token_name
                    if reg_pkg and reg_pkg != target_pkg:
                        new_import = f"import {reg_pkg}.{token_name}"
                    else:
                        new_import = None

                old_line = lines[line - 1]
                
                # ⭐ استخدام regex مع حدود الكلمة لمنع الاستبدال الخاطئ للأجزاء (مثل 16.dp داخل 116.dp)
                if token_type == "dimension":
                    pattern = re.compile(rf'\b{re.escape(value)}\b')
                else:
                    if f"Color({value})" in old_line:
                        pattern = re.compile(rf'Color\(\s*{re.escape(value)}\s*\)')
                    else:
                        pattern = re.compile(rf'(?<![\w]){re.escape(value)}(?![\w])')
                
                new_line = pattern.sub(scoped_name, old_line, count=1)
                
                # ⭐ تحقق أن الاستبدال حدث
                if new_line == old_line:
                    # rollback
                    shutil.copy2(target_backup, target_file)
                    shutil.copy2(registry_backup, registry_file)
                    return (False, f"Replacement failed: '{value}' not found as standalone", None)
                
                lines[line - 1] = new_line
                
                # Add import if needed
                import_added = False
                updated_target_content = "\n".join(lines) + "\n"
                if new_import and self._needs_import(updated_target_content, new_import):
                    updated_target_content = self._add_import(updated_target_content, new_import)
                    import_added = True

                target_file.write_text(updated_target_content, encoding="utf-8")
            except Exception as e:
                # Rollback both files
                shutil.copy2(target_backup, target_file)
                shutil.copy2(registry_backup, registry_file)
                return (False, f"Target edit failed: {e}", None)
            
            # ═══ 11. Success ═══
            if force_create:
                self.events.log(
                    "token_created_force",
                    {
                        "token_name": token_name,
                        "value": value,
                        "type": token_type,
                        "warning": "force_create used — bypassed duplicate detection",
                    },
                    source="user",
                )
            
            info = {
                "target_file": str(target_file.relative_to(self.project_root)),
                "target_line": line,
                "old_line": old_line.strip(),
                "new_line": new_line.strip(),
                "scoped_name": scoped_name,
                "import_added": import_added,
                "registry_file": str(registry_file.relative_to(self.project_root)),
                "registry_entry": new_entry.strip(),
                "backup_target": str(target_backup),
                "backup_registry": str(registry_backup),
            }
            
            return (
                True,
                f"Added token '{token_name}' and updated {file_name}:{line}",
                info,
            )

    def remove_token(self, token_name: str, token_type: str = "color") -> bool:
        """
        Remove a token definition from the registry file.
        Returns True if removed successfully.
        """
        import re
        with acquire_write_lock():
            files = self.find_all_token_files(token_type)
            for f in files:
                try:
                    content = f.read_text(encoding="utf-8")
                    
                    patterns = [
                        # val Xxx: Color\n    get() = BridgeThemeRegistry.getColor("Xxx", ...)
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\s*:\s*Color\s*\n[ \t]*get\(\)\s*=\s*BridgeThemeRegistry\.getColor\("[^"]+",\s*[^)]+\)',
                        # val Xxx: Dp\n    get() = BridgeDimensionRegistry.get("Xxx", ...)
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\s*:\s*Dp\s*\n[ \t]*get\(\)\s*=\s*BridgeDimensionRegistry\.get\("[^"]+",\s*[^)]+\)',
                        # val Xxx: Color get() = BridgeThemeRegistry...
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\s*:\s*Color\s+get\(\)\s*=\s*[^\n]+',
                        # val Xxx: Dp get() = BridgeDimensionRegistry...
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\s*:\s*Dp\s+get\(\)\s*=\s*[^\n]+',
                        # val Xxx = Color(...)
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\s*=\s*Color\([^)]+\)',
                        # val Xxx = ...dp / ...sp
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\s*=\s*[\d.]+\.(?:dp|sp)',
                        # Generic multiline val TokenName: ... get() = ...
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\b.*?(?:\n[ \t]*)?get\(\)\s*=\s*[^\n]+',
                    ]
                    
                    new_content = content
                    for pattern in patterns:
                        new_content = re.sub(pattern, "", new_content)
                    
                    if new_content != content:
                        f.write_text(new_content, encoding="utf-8")
                        return True
                except Exception as e:
                    continue
            return False


# Module-level alias for backward compatibility and split analyzer
CONTEXT_RULES = TokenMigrator.CONTEXT_RULES
COLOR_CONTEXT_RULES = TokenMigrator.COLOR_CONTEXT_RULES

