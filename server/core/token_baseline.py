# -*- coding: utf-8 -*-
"""
Token Baseline Manager for ComposeBridge (Whole-Project Token Baseline).

Maintains an immutable snapshot of pre-existing tokens discovered across ALL Kotlin files
in the project BEFORE any interactive modifications or sessions occur.

Responsibilities:
1. Whole-Project Indexing: Scans ALL .kt files in the project from RAM (PROJECT_CACHE)
   to index declared design tokens (Colors, Dimensions, Strings, Shapes, TextStyles)
   regardless of which file or package they reside in (e.g. DesignSystem.kt, Theme.kt, Colors.kt).
2. Persists baseline state to `.composebridge/token_baseline.json`.
3. Protects pre-existing tokens from cascade rollback or deletion:
   Any token present in this baseline index is considered pre-existing and immune to
   automatic removal during file or pattern rejection.
4. If a token was moved between files (e.g. from DesignSystem.kt to Theme.kt),
   the whole-project index continues to recognize it as a pre-existing token.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger("composebridge.token_baseline")

# High-precision regex matching design tokens across all Kotlin files
# Matches Colors, Dimensions (.dp/.sp), Strings, Shapes, and Bridge Theme registries
TOKEN_DECLARATION_REGEX = re.compile(
    r'\bval\s+([A-Za-z0-9_]+)\s*(?::\s*[A-Za-z0-9_<>?]+)?\s*(?:get\(\)\s*)?=\s*'
    r'(?:'
    r'Color\b|BridgeThemeRegistry\b|0x[0-9a-fA-F]{6,8}|'
    r'\d+(?:\.\d+)?\.(?:dp|sp)\b|BridgeDimensionRegistry\b|'
    r'"[^"\n]*"|stringResource\b|BridgeStringRegistry\b|'
    r'RoundedCornerShape\b|TextStyle\b'
    r')',
    re.MULTILINE
)

# Common variable names and keywords that should never be indexed as design tokens
EXCLUDED_NAMES = {
    "get", "set", "true", "false", "null", "this", "super", "it",
    "item", "index", "key", "value", "modifier", "scope", "state",
    "context", "color", "padding", "content", "result", "error",
}


class TokenBaselineManager:
    """Manages whole-project baseline indexing and queries for pre-existing tokens."""

    def __init__(self):
        # Maps root_path -> { token_name: file_path }
        self._memory_cache: Dict[str, Dict[str, str]] = {}

    def get_baseline_file(self, project_root: Path) -> Path:
        """Returns path to the baseline state file."""
        return project_root / ".composebridge" / "token_baseline.json"

    def build_baseline(self, project_root: Path, force: bool = False) -> Dict[str, str]:
        """
        Scans ALL Kotlin files in the project via PROJECT_CACHE and indexes declared tokens.
        If baseline file exists on disk and not force, loads from disk.
        """
        root = Path(project_root).resolve()
        root_str = str(root)

        baseline_file = self.get_baseline_file(root)

        # 1. Load from disk if available and not forced
        if not force and baseline_file.exists():
            try:
                data = json.loads(baseline_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._memory_cache[root_str] = data
                    logger.info(f"[BASELINE] Loaded {len(data)} baseline tokens from disk.")
                    return dict(data)
            except Exception as e:
                logger.warning(f"[BASELINE] Failed reading disk baseline, re-indexing: {e}")

        # 2. Whole-project scan: read all .kt files from RAM cache
        tokens: Dict[str, str] = {}
        files: Dict[str, str] = {}
        try:
            from common.project_cache import PROJECT_CACHE
            PROJECT_CACHE.populate_if_needed(root, force=force)
            # get_kt_cache returns List[Tuple[rel_path, content]]
            for rel_path, content in PROJECT_CACHE.get_kt_cache(root):
                files[rel_path] = content
        except Exception:
            pass

        if not files:
            from common.file_ops import is_ignored_path
            for p in root.rglob("*.kt"):
                if is_ignored_path(p, root):
                    continue
                try:
                    rel = str(p.relative_to(root)).replace("\\", "/")
                    files[rel] = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass

        # Scan every Kotlin file in the project
        for rel_path, content in files.items():
            # If an active .bridge.bak exists on disk, read from backup because it reflects original baseline
            full_p = root / rel_path
            bak_p = full_p.with_name(full_p.name + ".bridge.bak")
            if bak_p.exists():
                try:
                    content = bak_p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass

            found = self._extract_token_names_from_content(content)
            for tname in found:
                if tname not in tokens:
                    tokens[tname] = rel_path

        # If building on the fly while a session has active token_added in journal, exclude session tokens
        for j_path in [
            root / ".composebridge-state" / "pattern_journal.jsonl",
            root / ".composebridge" / "pattern_journal.jsonl",
            root / "pattern_journal.jsonl",
        ]:
            if j_path.exists():
                try:
                    with open(j_path, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                ent = json.loads(line.strip())
                                if ent.get("type") == "token_added" and ent.get("token_name"):
                                    tokens.pop(ent["token_name"], None)
                            except Exception:
                                pass
                except Exception:
                    pass

        # 3. Persist to disk
        try:
            baseline_file.parent.mkdir(parents=True, exist_ok=True)
            baseline_file.write_text(json.dumps(tokens, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[BASELINE] Could not persist baseline file: {e}")

        self._memory_cache[root_str] = tokens
        return dict(tokens)

    def _extract_token_names_from_content(self, content: str) -> List[str]:
        """Extracts valid token identifiers matching color, dimension, string or theme patterns."""
        results = []
        for match in TOKEN_DECLARATION_REGEX.finditer(content):
            tname = match.group(1)
            if len(tname) <= 1:
                continue
            if tname in EXCLUDED_NAMES:
                continue
            results.append(tname)
        return results

    def is_pre_existing(self, token_name: str, project_root: Optional[Path] = None) -> bool:
        """
        Returns True if `token_name` is present in the whole-project baseline index.
        Pre-existing tokens must never be cascade-deleted.
        Ignores original file location so moved tokens (e.g. into Theme.kt) remain protected.
        """
        if not token_name:
            return False

        root = project_root
        if root is None:
            try:
                from core.project_root import get_project_root
                root = get_project_root()
            except Exception:
                root = Path.cwd()

        root = Path(root).resolve()
        root_str = str(root)

        baseline_file = self.get_baseline_file(root)
        if baseline_file.exists():
            if root_str not in self._memory_cache:
                try:
                    self._memory_cache[root_str] = json.loads(baseline_file.read_text(encoding="utf-8"))
                except Exception:
                    self._memory_cache[root_str] = {}
            return token_name in self._memory_cache.get(root_str, {})

        # If baseline file does not exist, check active journal for session token
        for j_path in [
            root / ".composebridge-state" / "pattern_journal.jsonl",
            root / ".composebridge" / "pattern_journal.jsonl",
            root / "pattern_journal.jsonl",
        ]:
            if j_path.exists():
                try:
                    with open(j_path, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                ent = json.loads(line.strip())
                                if ent.get("type") == "token_added" and ent.get("token_name") == token_name:
                                    return False
                            except Exception:
                                pass
                except Exception:
                    pass

        if root_str not in self._memory_cache:
            self.build_baseline(root)

        baseline = self._memory_cache.get(root_str, {})
        return token_name in baseline

    def add_to_baseline(self, token_name: str, file_path: str, project_root: Optional[Path] = None) -> None:
        """
        Explicitly promotes a token into the baseline (e.g. upon user approval).
        """
        if not token_name:
            return

        root = project_root
        if root is None:
            try:
                from core.project_root import get_project_root
                root = get_project_root()
            except Exception:
                root = Path.cwd()

        root = Path(root).resolve()
        root_str = str(root)

        if root_str not in self._memory_cache:
            self.build_baseline(root)

        baseline = self._memory_cache.setdefault(root_str, {})
        baseline[token_name] = str(file_path).replace("\\", "/")

        # Save to disk
        try:
            b_file = self.get_baseline_file(root)
            b_file.write_text(json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def check_token_usages_in_project(
        self,
        token_name: str,
        project_root: Path,
        exclude_file: Optional[str] = None
    ) -> List[str]:
        """
        Fast in-memory check to see if any project file uses `token_name`.
        Excludes the token's defining file and optionally `exclude_file`.
        """
        root = Path(project_root).resolve()
        try:
            from common.project_cache import PROJECT_CACHE
            files = dict(PROJECT_CACHE.get_kt_cache(root))
        except Exception:
            files = {}

        if not files:
            from common.file_ops import is_ignored_path
            for p in root.rglob("*.kt"):
                if is_ignored_path(p, root):
                    continue
                try:
                    rel = str(p.relative_to(root)).replace("\\", "/")
                    files[rel] = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass

        # Check where token is defined according to baseline
        baseline = self._memory_cache.get(str(root), {})
        defining_file = baseline.get(token_name, "")
        def_norm = defining_file.lower().replace("\\", "/") if defining_file else ""
        def_name = Path(defining_file).name.lower() if defining_file else ""

        pattern = re.compile(
            rf'\b(?:AppColors|AppDimens|AppStrings|AppDesign|DesignSystem|Theme)\.{re.escape(token_name)}\b|\.{re.escape(token_name)}\b'
        )
        exclude_name = Path(exclude_file).name.lower() if exclude_file else None
        exclude_norm = str(exclude_file).replace("\\", "/").lower() if exclude_file else None

        usages = []
        for rel_path, code in files.items():
            name_lower = Path(rel_path).name.lower()
            norm_path = rel_path.lower()

            # Skip defining file
            if def_name and (name_lower == def_name or norm_path == def_norm):
                continue

            # Skip excluded file if specified
            if exclude_name and (name_lower == exclude_name or norm_path == exclude_norm):
                continue

            if pattern.search(code):
                usages.append(rel_path)

        return usages


# Global singleton instance
_BASELINE_MANAGER = TokenBaselineManager()


def build_baseline(project_root: Path, force: bool = False) -> Dict[str, str]:
    """Convenience facade to build whole-project baseline."""
    return _BASELINE_MANAGER.build_baseline(project_root, force=force)


def is_pre_existing(token_name: str, project_root: Optional[Path] = None) -> bool:
    """Convenience facade to check if token was pre-existing."""
    return _BASELINE_MANAGER.is_pre_existing(token_name, project_root)


def add_to_baseline(token_name: str, file_path: str, project_root: Optional[Path] = None) -> None:
    """Convenience facade to add token to baseline."""
    _BASELINE_MANAGER.add_to_baseline(token_name, file_path, project_root)


def check_token_usages_in_project(token_name: str, project_root: Path, exclude_file: Optional[str] = None) -> List[str]:
    """Convenience facade to check usages across project."""
    return _BASELINE_MANAGER.check_token_usages_in_project(token_name, project_root, exclude_file=exclude_file)


def get_token_baseline_manager() -> TokenBaselineManager:
    """Returns singleton manager instance."""
    return _BASELINE_MANAGER
