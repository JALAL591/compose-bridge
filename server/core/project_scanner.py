import os
# -*- coding: utf-8 -*-
"""
Project Scanner — Full scan of Compose project tokens with caching and parallel execution.

Usage:
    from core.project_scanner import ProjectScanner
    scanner = ProjectScanner(project_root)
    report = scanner.scan()
"""

import json
import logging
import multiprocessing
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import List, Dict, Set, Optional

from .scanner_models import (
    Token, HardcodedValue, DuplicateGroup, OrphanToken, ScanReport, TokenUsage, TokenImpact
)
from . import scanner_kotlin_parser as parser

logger = logging.getLogger(__name__)

EXCLUDED_DIRS = {
    "build", ".gradle", ".idea", ".git", "node_modules",
    "backup", "backups", ".bak", "project_backups_archive",
    "test", "tests", "androidTest", "iosTest",
    ".composebridge-state", "composebridge-agent", "bridge",
}

# ⭐ استبعاد Backend modules
EXCLUDED_MODULES = {
    "SerajServer",       # Ktor Backend
    "SuperAdminWeb",     # Next.js
    "developer_tools",   # أدوات
    "scripts",           # Scripts
}


class ScanResultDict(dict):
    """Dictionary supporting dot-access and .to_dict() / .summary() for compatibility."""
    def to_dict(self) -> dict:
        return dict(self)

    def summary(self) -> dict:
        return {
            "registered_count": len(self.get("registered_tokens", [])),
            "hardcoded_count": len(self.get("hardcoded_values", [])),
            "duplicate_groups": len(self.get("duplicates", [])),
            "orphan_count": len(self.get("orphans", [])),
            "files_scanned": self.get("files_scanned", 0),
            "scan_duration_ms": self.get("scan_duration_ms", 0),
        }


class ProjectScanner:
    """
    Scan entire project for design tokens and hardcoded values.
    Supports multithreaded scanning and mtime/size based caching.
    """
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.report: Optional[ScanReport] = None
        self.cache_dir = self.project_root / ".composebridge-state"
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "scan_cache.json"

    def _should_skip_file(self, path: Path, include_tests: bool = False) -> bool:
        parts = set(path.parts)
        if any(d in parts for d in EXCLUDED_DIRS):
            return True
        if any(m in parts for m in EXCLUDED_MODULES):
            return True
        s = str(path).lower()
        if any(ext in s for ext in [".bak", ".bridge_backup", ".backup", ".pre_", "_backup."]):
            return True
        if not include_tests and any(t in parts for t in ["test", "tests", "androidTest", "iosTest"]):
            return True
        return False

    def find_kt_files(self, include_tests: bool = False) -> List[Path]:
        """Find all relevant Kotlin files skipping excluded directories and modules."""
        import os
        files = []
        excluded_dir_names = set(EXCLUDED_DIRS) | set(EXCLUDED_MODULES)
        if not include_tests:
            excluded_dir_names.update(["test", "tests", "androidTest", "iosTest"])

        for root, dirs, filenames in os.walk(str(self.project_root)):
            dirs[:] = [
                d for d in dirs
                if d not in excluded_dir_names
                and not d.startswith(".")
                and not any(ext in d.lower() for ext in [".bak", "backup"])
            ]
            
            root_parts = set(Path(root).parts)
            if any(ed in root_parts for ed in excluded_dir_names):
                continue

            for filename in filenames:
                if filename.endswith(".kt"):
                    fpath = Path(root) / filename
                    if not self._should_skip_file(fpath, include_tests=include_tests):
                        files.append(fpath)
        return files

    def _find_kt_files(self, include_tests: bool = False) -> List[Path]:
        return self.find_kt_files(include_tests=include_tests)

    def _extract_from_file(self, f: Path, content: Optional[str] = None, include_hardcoded: bool = True) -> dict:
        """Extract tokens and hardcoded values from a single Kotlin file."""
        if content is None:
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                return {"dimensions": [], "colors": [], "hardcoded": []}
        
        dimensions = parser.scan_file_dimensions(content)
        colors = parser.scan_file_colors(content)
        hardcoded = []
        if include_hardcoded:
            hardcoded = parser.scan_file_hardcoded(content, set())
            
        return {
            "dimensions": dimensions,
            "colors": colors,
            "hardcoded": hardcoded,
        }

    def _compute_file_hashes(self, kt_files: Optional[List[Path]] = None) -> Dict[str, str]:
        """Compute fast mtime_size signatures for file cache invalidation."""
        if kt_files is None:
            kt_files = self.find_kt_files()
        hashes = {}
        for f in kt_files:
            try:
                st = f.stat()
                hashes[str(f)] = f"{st.st_mtime}_{st.st_size}"
            except Exception:
                continue
        return hashes

    def scan_parallel(
        self,
        max_workers: int = 4,
        include_hardcoded: bool = True,
        include_tests: bool = False,
    ) -> ScanResultDict:
        """
        Multithreaded project scan for registered tokens and hardcoded values.
        """
        start = time.time()
        kt_files = self.find_kt_files(include_tests=include_tests)
        
        registered_tokens = []
        hardcoded_values = []
        file_contents: Dict[Path, str] = {}

        def worker(file_path: Path):
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                return None
            res = self._extract_from_file(file_path, content, include_hardcoded=include_hardcoded)
            return file_path, content, res

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(worker, f) for f in kt_files]
            for future in as_completed(futures):
                item = future.result()
                if item is None:
                    continue
                file_path, content, res = item
                file_contents[file_path] = content
                
                for d in res["dimensions"]:
                    registered_tokens.append(Token(
                        name=d["name"],
                        kind=d["kind"],
                        value=d["value"],
                        raw_value=d["raw_value"],
                        file=file_path.name,
                        full_path=str(file_path),
                        line=d["line"],
                        column=d["column"],
                        registry=d["registry"],
                    ))
                for c in res["colors"]:
                    registered_tokens.append(Token(
                        name=c["name"],
                        kind=c["kind"],
                        value=c["value"],
                        raw_value=c["raw_value"],
                        file=file_path.name,
                        full_path=str(file_path),
                        line=c["line"],
                        column=c["column"],
                        registry=c["registry"],
                    ))
                for h in res["hardcoded"]:
                    hardcoded_values.append(HardcodedValue(
                        value=h["value"],
                        kind=h["kind"],
                        file=file_path.name,
                        full_path=str(file_path),
                        line=h["line"],
                        column=h["column"],
                        context=h["context"],
                        category=h["category"],
                        suggestion_name=h["suggestion_name"],
                    ))

        # ═══ Deduplicate tokens ═══
        registered_tokens = self._deduplicate_tokens(registered_tokens)
        
        # ═══ Build token impacts using cached file_contents ═══
        token_impacts = self._build_token_impacts_fast(registered_tokens, file_contents)
        
        # ═══ Split suggestions ═══
        from .token_split_analyzer import TokenSplitAnalyzer
        split_analyzer = TokenSplitAnalyzer(self.project_root)
        split_suggestions = split_analyzer.analyze_all(token_impacts)
        
        # ═══ Duplicates & Orphans ═══
        duplicates = self._find_duplicates(registered_tokens)
        orphans = self._find_orphans(registered_tokens)
        
        elapsed_ms = int((time.time() - start) * 1000)
        
        report = ScanReport(
            project_root=str(self.project_root),
            files_scanned=len(kt_files),
            registered_tokens=registered_tokens,
            hardcoded_values=hardcoded_values,
            duplicates=duplicates,
            orphans=orphans,
            token_impacts=token_impacts,
            split_suggestions=split_suggestions,
            scan_duration_ms=elapsed_ms,
        )
        self.report = report
        
        result_dict = ScanResultDict({
            "project_root": str(self.project_root),
            "files_scanned": len(kt_files),
            "registered_tokens": [asdict(t) if hasattr(t, "__dataclass_fields__") else t for t in registered_tokens],
            "hardcoded_values": [asdict(h) if hasattr(h, "__dataclass_fields__") else h for h in hardcoded_values],
            "duplicates": [asdict(d) if hasattr(d, "__dataclass_fields__") else d for d in duplicates],
            "orphans": [asdict(o) if hasattr(o, "__dataclass_fields__") else o for o in orphans],
            "token_impacts": [asdict(i) if hasattr(i, "__dataclass_fields__") else i for i in token_impacts],
            "split_suggestions": [asdict(s) if hasattr(s, "__dataclass_fields__") else s for s in split_suggestions],
            "scan_duration_ms": elapsed_ms,
            "from_cache": False,
        })
        
        # Save cache
        try:
            current_hashes = self._compute_file_hashes(kt_files)
            cache_payload = {
                "file_hashes": current_hashes,
                "result": dict(result_dict),
            }
            self.cache_file.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

        return result_dict

    def scan_with_cache(
        self,
        force_refresh: bool = False,
        max_workers: int = 4,
        include_hardcoded: bool = True,
        include_tests: bool = False,
    ) -> ScanResultDict:
        """
        Fast scan utilizing .composebridge-state/scan_cache.json if files have not changed.
        """
        kt_files = self.find_kt_files(include_tests=include_tests)
        current_hashes = self._compute_file_hashes(kt_files)
        
        if not force_refresh and self.cache_file.exists():
            try:
                cached_data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                saved_hashes = cached_data.get("file_hashes", {})
                if saved_hashes == current_hashes and "result" in cached_data:
                    res = ScanResultDict(cached_data["result"])
                    res["from_cache"] = True
                    return res
            except Exception as e:
                logger.warning(f"Failed to read cache: {e}")
        
        result = self.scan_parallel(
            max_workers=max_workers,
            include_hardcoded=include_hardcoded,
            include_tests=include_tests,
        )
        try:
            cache_payload = {
                "file_hashes": current_hashes,
                "result": dict(result),
            }
            self.cache_file.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
            
        result["from_cache"] = False
        return result

    def scan_with_progress(self, timeout_seconds: int = 120) -> ScanResultDict:
        """Scan with timeout monitoring."""
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.scan_with_cache)
            try:
                return future.result(timeout=timeout_seconds)
            except Exception as e:
                logger.error(f"Scan timed out or failed: {e}")
                raise

    def scan(
        self,
        include_hardcoded: bool = True,
        include_tests: bool = False,
    ) -> ScanReport:
        """
        Full scan returning ScanReport for backwards compatibility.
        """
        self.scan_parallel(
            max_workers=4,
            include_hardcoded=include_hardcoded,
            include_tests=include_tests,
        )
        return self.report

    # ─────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────
    
    def _deduplicate_tokens(self, tokens: List[Token]) -> List[Token]:
        """إذا وُجد نفس الاسم في ملفات متعددة، نأخذ التعريف من
        AppColors/AppDimens/DesignSystem بدلاً من Theme.kt (fallback)."""
        seen = {}
        for t in tokens:
            if t.name not in seen:
                seen[t.name] = t
            else:
                old_file = seen[t.name].file.lower()
                new_file = t.file.lower()
                if ("theme.kt" in old_file or "theme" in old_file) and (
                    "appcolors" in new_file or "appdimens" in new_file or 
                    "designsystem" in new_file):
                    seen[t.name] = t
        return list(seen.values())

    def _build_token_impacts_fast(
        self,
        registered_tokens: List[Token],
        file_contents: Dict[Path, str],
    ) -> List[TokenImpact]:
        """Build impact analysis for each token using in-memory file contents."""
        from .scanner_kotlin_parser import scan_file_usages
        
        token_names = {t.name for t in registered_tokens}
        
        all_usages = []
        for kt_file, content in file_contents.items():
            usages = scan_file_usages(content, token_names)
            for u in usages:
                u["file"] = kt_file.name
                u["enclosing_file"] = kt_file.name
                all_usages.append(u)
        
        token_impacts = []
        for token in registered_tokens:
            token_usages = [u for u in all_usages if u["token_name"] == token.name]
            
            affected = set()
            token_usage_objects = []
            
            for u in token_usages:
                if u["file"] == token.file and u["line"] == token.line:
                    continue
                
                comp = u["enclosing_composable"]
                if comp != "_unknown":
                    affected.add(comp)
                
                token_usage_objects.append(TokenUsage(
                    token_name=u["token_name"],
                    file=u["file"],
                    line=u["line"],
                    column=u["column"],
                    line_content=u["line_content"],
                    enclosing_composable=comp,
                    enclosing_file=u["enclosing_file"],
                    enclosing_line=u["enclosing_line"],
                    hierarchy_path=u.get("hierarchy_path", []),
                    depth=u.get("depth", 0),
                ))
            
            impact = TokenImpact(
                token_name=token.name,
                token_value=token.value,
                token_kind=token.kind,
                token_location=f"{token.file}:{token.line}",
                usages=token_usage_objects,
                affected_composables=sorted(list(affected)),
                total_impact=len(token_usage_objects),
            )
            token_impacts.append(impact)
            token.usage_count = len(token_usage_objects)

        return token_impacts

    def _build_token_impacts(self, report: ScanReport, kt_files: List[Path]):
        """Legacy helper for backwards compatibility."""
        file_contents = {}
        for f in kt_files:
            try:
                file_contents[f] = f.read_text(encoding="utf-8")
            except Exception:
                continue
        impacts = self._build_token_impacts_fast(report.registered_tokens, file_contents)
        report.token_impacts = impacts

    def _find_duplicates(self, tokens: List[Token]) -> List[DuplicateGroup]:
        """Find tokens with the same value."""
        groups: Dict[tuple, List[Token]] = {}
        for t in tokens:
            key = (t.kind, t.value)
            groups.setdefault(key, []).append(t)
        
        duplicates = []
        for (kind, value), token_list in groups.items():
            if len(token_list) > 1:
                duplicates.append(DuplicateGroup(
                    value=value,
                    kind=kind,
                    tokens=[t.name for t in token_list],
                    locations=[f"{t.file}:{t.line}" for t in token_list],
                ))
        return duplicates
    
    def _find_orphans(self, tokens: List[Token]) -> List[OrphanToken]:
        """Find registered tokens that are never used."""
        orphans = []
        for t in tokens:
            if t.usage_count == 0:
                orphans.append(OrphanToken(
                    name=t.name,
                    kind=t.kind,
                    value=t.value,
                    file=t.file,
                    line=t.line,
                ))
        return orphans
