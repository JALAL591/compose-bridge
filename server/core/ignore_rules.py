# -*- coding: utf-8 -*-
"""
Ignore rules for generated code.
Prevents ComposeBridge from editing auto-generated files.
"""

import fnmatch
from pathlib import Path
from typing import List, Optional


DEFAULT_PATTERNS = [
    "**/build/generated/**",
    "**/build/tmp/**",
    "**/build/intermediates/**",
    "**/ksp/**",
    "**/kapt/**",
    "**/*_Impl.kt",
    "**/*_Generated.kt",
    "**/*.generated.kt",
    "**/R.kt",
    "**/BuildConfig.kt",
]


GENERATED_ANNOTATIONS = [
    "@Generated",
    "@javax.annotation.Generated",
    "@javax.annotation.processing.Generated",
    "@kotlin.jvm.JvmSynthetic",
]


class IgnoreRules:
    """Manage ignore rules for generated code."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.patterns: List[str] = list(DEFAULT_PATTERNS)
        self._load_bridgeignore()

    def _load_bridgeignore(self):
        """Load .bridgeignore from project root if exists."""
        bridgeignore = self.project_root / ".bridgeignore"
        if not bridgeignore.exists():
            return

        try:
            content = bridgeignore.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    self.patterns.append(line)
        except Exception as e:
            print(f"[IgnoreRules] ⚠️ Failed to load .bridgeignore: {e}")

    def is_ignored(self, file_path: Path) -> tuple:
        """
        Check if a file should be ignored.
        Returns: (ignored: bool, reason: str)
        """
        try:
            rel = file_path.relative_to(self.project_root)
        except ValueError:
            rel = file_path

        rel_str = str(rel).replace("\\", "/")

        for pattern in self.patterns:
            pat = pattern.replace("**/", "").replace("/**", "").strip("/")
            if fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(rel_str, f"**/{pattern}") or (pat and pat in rel_str):
                return (True, f"Matches pattern: {pattern}")

        if file_path.suffix == ".kt" and file_path.exists():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")[:2048]
                for annotation in GENERATED_ANNOTATIONS:
                    if annotation in content:
                        return (True, f"Contains annotation: {annotation}")
            except Exception:
                pass

        return (False, "")


_ignore_rules_cache: dict = {}


def get_ignore_rules(project_root: Path) -> IgnoreRules:
    """Get cached IgnoreRules for a project."""
    key = str(project_root)
    if key not in _ignore_rules_cache:
        _ignore_rules_cache[key] = IgnoreRules(project_root)
    return _ignore_rules_cache[key]


def reload_ignore_rules(project_root: Path):
    """Force reload (called when .bridgeignore changes)."""
    key = str(project_root)
    if key in _ignore_rules_cache:
        del _ignore_rules_cache[key]
