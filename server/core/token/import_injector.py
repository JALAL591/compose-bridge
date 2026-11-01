# -*- coding: utf-8 -*-
"""
وحدة حقن الـ Imports وتوليد مدخلات الـ Registry ونقاط الإدراج في ملفات Kotlin.
Handles import statement injections, registry entries, and AST insertion points.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

class ImportInjectorMixin:
    """Mixin class providing import injection and registry entry formatting for TokenMigrator."""

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
            if "import androidx.compose.ui.unit.Dp" not in reg_content:
                reg_content = self._add_import(reg_content, "import androidx.compose.ui.unit.Dp")
            if "import com.composebridge.agent.BridgeDimensionRegistry" not in reg_content:
                reg_content = self._add_import(reg_content, "import com.composebridge.agent.BridgeDimensionRegistry")
        elif token_type == "color":
            if "import androidx.compose.ui.graphics.Color" not in reg_content:
                reg_content = self._add_import(reg_content, "import androidx.compose.ui.graphics.Color")
            if "import com.composebridge.agent.BridgeThemeRegistry" not in reg_content:
                reg_content = self._add_import(reg_content, "import com.composebridge.agent.BridgeThemeRegistry")
        return reg_content


    def _find_registry_insertion_point(self, registry_content: str, token_type: str = "color", style: str = "registry") -> int:
        """Find the line to insert the new token."""
        lines = registry_content.splitlines()
        
        if style == "registry":
            target_reg = "BridgeThemeRegistry.getColor" if token_type == "color" else "BridgeDimensionRegistry.get"
            last_idx = -1
            for i, line in enumerate(lines):
                if target_reg in line:
                    last_idx = i
            if last_idx != -1:
                return last_idx + 1

            for i, line in enumerate(lines):
                if "BridgeDimensionRegistry.get" in line or "BridgeThemeRegistry.getColor" in line:
                    last_idx = i
            if last_idx != -1:
                return last_idx + 1

        if style in ("registry", "object"):
            pref_names = ["AppColors", "Colors", "Theme"] if token_type == "color" else ["AppDimens", "AppDesign", "AppDimensions", "Dimensions", "Spacing"]
            obj_idx = -1
            for p_name in pref_names:
                for i, line in enumerate(lines):
                    if re.search(rf'\bobject\s+{re.escape(p_name)}\b', line):
                        obj_idx = i
                        break
                if obj_idx != -1:
                    break

            if obj_idx == -1:
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

