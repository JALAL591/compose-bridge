# -*- coding: utf-8 -*-
"""
Token Linker — يكتشف العلاقات الدلالية بين التوكنات.
"""

import re
from pathlib import Path
from typing import Dict, List, Set, Optional
from .project_scanner import ProjectScanner


class TokenLinker:
    """
    يكشف العلاقات مثل:
    - Primary ↔ PrimaryDark
    - TextPrimary ↔ TextPrimaryDark
    - Background ↔ BackgroundDark
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def detect_groups(self) -> Dict[str, List[str]]:
        """
        Returns:
            {
                "Primary": ["Primary", "PrimaryDark", "PrimaryLight"],
                "TextPrimary": ["TextPrimary", "TextPrimaryDark"],
                ...
            }
        """
        scanner = ProjectScanner(self.project_root)
        report = scanner.scan(include_hardcoded=False)

        # اجمع أسماء كل التوكنات
        names = set()
        for token in report.registered_tokens:
            names.add(token.name)

        # كوّن groups بناءً على اللاحقات
        groups: Dict[str, Set[str]] = {}

        for name in names:
            # PrimaryDark → base "Primary"
            # TextPrimaryDark → base "TextPrimary"
            # BackgroundDark → base "Background"
            
            base = None
            if name.endswith("Dark"):
                base = name[:-4]
            elif name.endswith("Light"):
                base = name[:-5]
            elif name.endswith("Color"):
                base = name[:-5]
            else:
                # قد يكون الأساس
                base = name
            
            if base not in groups:
                groups[base] = set()
            
            groups[base].add(name)
            
            # إذا كان الأساس موجود كـ token
            if base in names:
                groups[base].add(base)

        # احتفظ فقط بالـ groups ذات أكثر من عضو
        final = {}
        for base, members in groups.items():
            if len(members) > 1:
                final[base] = sorted(list(members))

        return final

    def get_siblings(self, token_name: str) -> List[str]:
        """يرجع الأشقاء الدلاليين لـ token."""
        groups = self.detect_groups()
        for base, members in groups.items():
            if token_name in members:
                return [m for m in members if m != token_name]
        return []

    def suggest_color_variant(
        self,
        token_name: str,
        new_value: str,
        sibling_name: str,
    ) -> Optional[str]:
        """
        يقترح قيمة جديدة للـ sibling بناءً على القيمة الجديدة.
        
        مثال:
        Primary #4F46E5 → #EF4444
        PrimaryDark #818CF8 → يُقترح #FCA5A5 (lighter red)
        """
        # خريطة لتحويل hex → RGB
        def hex_to_rgb(hex_str):
            h = hex_str.replace("#", "").replace("0x", "")
            if len(h) == 8:
                h = h[2:]
            if len(h) != 6:
                return None
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        
        def rgb_to_hex(r, g, b):
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            return f"#{r:02X}{g:02X}{b:02X}"
        
        # احصل على اللون الجديد
        new_rgb = hex_to_rgb(new_value)
        if not new_rgb:
            return None
        
        # إذا كان sibling ينتهي بـ Dark → اجعله أفتح
        if sibling_name.endswith("Dark"):
            # اخلط مع White بنسبة 30%
            r, g, b = new_rgb
            r = int(r * 0.7 + 255 * 0.3)
            g = int(g * 0.7 + 255 * 0.3)
            b = int(b * 0.7 + 255 * 0.3)
            return rgb_to_hex(r, g, b)
        
        # إذا كان sibling ينتهي بـ Light → اجعله أغمق
        elif sibling_name.endswith("Light"):
            r, g, b = new_rgb
            r = int(r * 0.7)
            g = int(g * 0.7)
            b = int(b * 0.7)
            return rgb_to_hex(r, g, b)
        
        return new_value
