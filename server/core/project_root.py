# -*- coding: utf-8 -*-
"""
Unified Project Root Resolver

Precedence:
1. Explicit argument (passed by caller)
2. Environment variable COMPOSEBRIDGE_ROOT
3. Config file .composebridge/config.json
4. Auto-detect from file location
"""

import os
import json
from pathlib import Path
from typing import Optional


def _auto_detect_root() -> Path:
    """Auto-detect project root based on file location."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        # If we find bridge/ or app/ or server/ — it's likely the root
        if (parent / "bridge").exists() or (parent / "app").exists() or (parent / "server").exists():
            return parent
    # Fallback: current working directory
    return Path.cwd()


def _from_env() -> Optional[Path]:
    env = os.environ.get("COMPOSEBRIDGE_ROOT")
    if env:
        p = Path(env)
        if p.exists():
            return p
    return None


def _from_config() -> Optional[Path]:
    # Check .composebridge/config.json in current dir or auto-detected root
    candidates = [
        Path.cwd() / ".composebridge" / "config.json",
        _auto_detect_root() / ".composebridge" / "config.json",
    ]
    for cfg in candidates:
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text(encoding="utf-8"))
                root = data.get("project_root")
                if root:
                    p = Path(root)
                    if p.exists():
                        return p
            except Exception:
                pass
    return None


def get_project_root(explicit: Optional[Path] = None, no_config: bool = False) -> Path:
    """
    Get the project root using the precedence rules.

    Args:
        explicit: explicit path (highest priority)
        no_config: if True, ignore .composebridge/config.json

    Returns:
        Path to project root
    """
    if explicit:
        p = Path(explicit).resolve()
        if p.exists():
            return p

    env = _from_env()
    if env:
        return env.resolve()

    if not no_config:
        cfg = _from_config()
        if cfg:
            return cfg.resolve()

    return _auto_detect_root()
