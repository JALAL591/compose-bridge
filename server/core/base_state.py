# -*- coding: utf-8 -*-
"""
Base Persistent State — Common JSON persistence utility for ComposeBridge state models.
نموذج حفظ واسترجاع الحالة العامة بتنسيق JSON.
"""

import json
from pathlib import Path
from typing import Any, Optional


class JsonPersistentState:
    """
    Base class providing standardized JSON state persistence.
    يوفر وظائف قراءة وحفظ الكائنات بتنسيق JSON بشكل آمن وموحد.
    """

    @staticmethod
    def save_json(file_path: Path, data: Any, indent: int = 2) -> None:
        """Write JSON data to file with UTF-8 encoding."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(data, indent=indent, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def load_json(file_path: Path, default: Any = None) -> Any:
        """Read JSON data from file safely with fallback to default."""
        if not file_path.exists():
            return default
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return default

