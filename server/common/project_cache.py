# -*- coding: utf-8 -*-
"""
Thread-safe in-memory cache for project files, paths, and contents.
Eliminates repeated disk rglob and file reads during UI element analysis.
"""

import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


class ProjectCache:
    """
    In-memory cache for Kotlin files and project structure.
    Caches:
      - kt_files: Dict[rel_path, content]
      - name_to_path: Dict[filename, Path]
      - token_map: Dict[token_name, hex_value]
      - global_counts: Dict[token_or_color, count]
    """

    DEFAULT_TTL = 60.0  # 60 seconds

    def __init__(self, ttl: float = DEFAULT_TTL):
        self._ttl = ttl
        self._lock = threading.RLock()
        self._root_path: Optional[str] = None
        self._timestamp: float = 0.0

        # Caches
        self._kt_files: Dict[str, str] = {}
        self._name_to_path: Dict[str, Path] = {}
        self._all_paths: List[Path] = []
        self._token_map: Optional[Dict[str, str]] = None
        self._global_counts: Optional[Dict[str, int]] = None

    def _is_valid(self, root: Path) -> bool:
        now = time.time()
        return (
            self._root_path == str(root)
            and (now - self._timestamp) < self._ttl
            and bool(self._kt_files)
        )

    def populate_if_needed(self, project_root: Path, force: bool = False) -> None:
        """Populates cache from disk if expired or forced."""
        root = Path(project_root)
        with self._lock:
            if not force and self._is_valid(root):
                return

            kt_files: Dict[str, str] = {}
            name_to_path: Dict[str, Path] = {}
            all_paths: List[Path] = []

            ignore_parts = {
                "build", ".git", ".composebridge", ".composebridge-state",
                ".bak", ".gradle", ".idea", ".kotlin", "__pycache__"
            }

            try:
                for p in root.rglob("*.kt"):
                    p_str_lower = str(p).lower()
                    if any(ign in p_str_lower for ign in ignore_parts) or "backup" in p_str_lower:
                        continue
                    try:
                        content = p.read_text(encoding="utf-8", errors="ignore")
                        rel = str(p.relative_to(root)).replace("\\", "/")
                        kt_files[rel] = content
                        all_paths.append(p)
                        if p.name not in name_to_path:
                            name_to_path[p.name] = p
                    except Exception:
                        pass
            except Exception:
                pass

            self._root_path = str(root)
            self._timestamp = time.time()
            self._kt_files = kt_files
            self._name_to_path = name_to_path
            self._all_paths = all_paths
            self._token_map = None
            self._global_counts = None

    def get_kt_cache(self, project_root: Path) -> List[Tuple[str, str]]:
        """Returns list of (rel_path, content) for fast iteration."""
        with self._lock:
            self.populate_if_needed(project_root)
            return list(self._kt_files.items())

    def get_kt_files(self, project_root: Path) -> Dict[str, str]:
        """Returns dictionary of {rel_path: content}."""
        with self._lock:
            self.populate_if_needed(project_root)
            return dict(self._kt_files)

    def find_file(self, filename: Union[str, Path], project_root: Path) -> Optional[Path]:
        """Finds file path by filename or relative path in O(1) from cache."""
        root = Path(project_root)
        p = Path(filename)

        # 1. Exact path if exists
        direct = root / p if not p.is_absolute() else p
        if direct.exists():
            return direct

        with self._lock:
            self.populate_if_needed(root)

            # 2. Check name_to_path dictionary
            base_name = p.name
            if base_name in self._name_to_path:
                return self._name_to_path[base_name]

            # 3. Check relative paths ending with filename
            norm = str(filename).replace("\\", "/").lower()
            for rel, path in self._name_to_path.items():
                if rel.lower() == norm or str(path).replace("\\", "/").lower().endswith(norm):
                    return path

        return None

    def get_file_content(self, file_path: Union[str, Path], project_root: Path) -> Optional[str]:
        """Gets file content directly from cache or disk fallback."""
        root = Path(project_root)
        with self._lock:
            self.populate_if_needed(root)

            try:
                rel = str(Path(file_path).relative_to(root)).replace("\\", "/")
                if rel in self._kt_files:
                    return self._kt_files[rel]
            except Exception:
                pass

            p_name = Path(file_path).name
            if p_name in self._name_to_path:
                resolved = self._name_to_path[p_name]
                try:
                    rel = str(resolved.relative_to(root)).replace("\\", "/")
                    if rel in self._kt_files:
                        return self._kt_files[rel]
                except Exception:
                    pass

        # Fallback to direct read
        resolved_path = self.find_file(file_path, root)
        if resolved_path and resolved_path.exists():
            try:
                return resolved_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
        return None

    def invalidate(self, file_path: Optional[Union[str, Path]] = None) -> None:
        """Invalidates entire cache or a specific file."""
        with self._lock:
            if file_path is None:
                self._timestamp = 0.0
                self._kt_files.clear()
                self._name_to_path.clear()
                self._all_paths.clear()
                self._token_map = None
                self._global_counts = None
            else:
                p = Path(file_path)
                p_name = p.name
                if p_name in self._name_to_path:
                    del self._name_to_path[p_name]
                norm = str(file_path).replace("\\", "/").lower()
                to_del = [k for k in self._kt_files if k.lower() == norm or k.lower().endswith(norm) or Path(k).name == p_name]
                for k in to_del:
                    self._kt_files.pop(k, None)
                self._token_map = None
                self._global_counts = None

    def update_file(self, file_path: Union[str, Path], content: str, project_root: Optional[Path] = None) -> None:
        """Updates cache entry for a file directly upon atomic write."""
        with self._lock:
            p = Path(file_path)
            p_name = p.name
            self._name_to_path[p_name] = p

            if project_root:
                try:
                    rel = str(p.relative_to(project_root)).replace("\\", "/")
                    self._kt_files[rel] = content
                except Exception:
                    self._kt_files[p_name] = content
            else:
                self._kt_files[p_name] = content

            self._token_map = None
            self._global_counts = None


# Global singleton instance
PROJECT_CACHE = ProjectCache()
