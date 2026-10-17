# -*- coding: utf-8 -*-
"""
Pattern Detector — يكتشف الأنماط المتكررة في Compose code.
الأنماط المدعومة:
1. if (isDark) X else AppColors.Y
2. if (isDark) Color(0x...) else AppColors.Y
3. if (isDark) X.copy(...) else AppColors.Y.copy(...)
"""

import re
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class PatternOccurrence:
    """Single occurrence of a pattern."""
    file: str
    line: int
    raw_line: str
    value_if_dark: str          # "0xFF818CF8" or "Color(0xFF818CF8)"
    value_else: str             # "AppColors.Primary"
    enclosing_composable: str = "_unknown"


@dataclass
class DetectedPattern:
    """A detected pattern group."""
    pattern_id: str
    pattern_type: str           # "conditional_dark_variant"
    template: str               # "if (isDark) X else AppColors.Primary"
    occurrences: List[PatternOccurrence] = field(default_factory=list)
    suggested_token_name: str = ""
    suggested_token_value: str = ""
    suggested_import: str = ""


class PatternDetector:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.patterns: Dict[str, DetectedPattern] = {}

    def _find_kt_files(self) -> List[Path]:
        files = []
        for f in self.project_root.rglob("*.kt"):
            s = str(f)
            if "\\build\\" in s or "/build/" in s:
                continue
            if ".composebridge-state" in s:
                continue
            if "/composebridge-agent/" in s or "\\composebridge-agent\\" in s:
                continue
            if "\\bridge\\" in s or "/bridge/" in s:
                continue
            if any(ext in s.lower() for ext in [".bak", ".backup", "_backup", ".bridge_backup"]):
                continue
            files.append(f)
        return files

    def detect(self, token_hint: Optional[str] = None) -> List[DetectedPattern]:
        """Detect all patterns."""
        self.patterns = {}
        kt_files = self._find_kt_files()
        for f in kt_files:
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                continue
            self._scan_content(content, f)

        patterns_list = list(self.patterns.values())
        if token_hint:
            patterns_list = [
                p for p in patterns_list
                if token_hint.lower() in p.suggested_token_name.lower() or token_hint.lower() in p.template.lower()
            ]
        return patterns_list

    def _scan_content(self, content: str, file_path: Path):
        """Scan file for conditional dark variant patterns."""
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            if "isDark" not in line and "isDarkMode" not in line:
                continue
            if "if" not in line or "else" not in line:
                continue

            match = re.search(
                r'if\s*\(\s*(?:isDark|isDarkMode)\s*\)\s*'
                r'(Color\s*\([^)]+\)|Color\.\w+|0x[0-9A-Fa-f]{8})\s*'
                r'(\.\w+\([^)]*\))?\s*'
                r'else\s+'
                r'(App\w+\.\w+(?:\.\w+\([^)]*\))?)',
                line
            )
            if not match:
                continue

            value_if_dark = match.group(1).strip()
            modifier = match.group(2) or ""
            value_else = match.group(3).strip()

            # استخرج اسم token من value_else
            token_match = re.search(r'App\w+\.(\w+)', value_else)
            if not token_match:
                continue
            base_token = token_match.group(1)

            pattern_key = f"dark_{base_token}_{value_if_dark}{modifier}"

            if pattern_key not in self.patterns:
                suggested_name = f"{base_token}Dark"
                self.patterns[pattern_key] = DetectedPattern(
                    pattern_id=pattern_key,
                    pattern_type="conditional_dark_variant",
                    template=f"if (isDark) {value_if_dark}{modifier} else {value_else}",
                    suggested_token_name=suggested_name,
                    suggested_token_value=value_if_dark + modifier,
                )

            comp = self._find_enclosing_composable(content, idx)
            self.patterns[pattern_key].occurrences.append(
                PatternOccurrence(
                    file=file_path.name,
                    line=idx,
                    raw_line=line.strip(),
                    value_if_dark=value_if_dark + modifier,
                    value_else=value_else,
                    enclosing_composable=comp,
                )
            )

    def _find_enclosing_composable(self, content: str, line_number: int) -> str:
        """Find enclosing @Composable function."""
        composable_re = re.compile(
            r'@Composable\s+(?:private\s+|public\s+|internal\s+)?fun\s+(\w+)',
            re.MULTILINE
        )
        best = ("_unknown", 0)
        for m in composable_re.finditer(content):
            start = content[:m.start()].count("\n") + 1
            if start <= line_number and start > best[1]:
                best = (m.group(1), start)
        return best[0]
