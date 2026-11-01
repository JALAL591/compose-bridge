# -*- coding: utf-8 -*-
"""
Kotlin source code validation and import hygiene utilities.
Re-exports from common.kotlin_utils for backwards compatibility.
"""

from common.kotlin_utils import (
    validate_kotlin_line,
    clean_duplicate_modifier,
    ensure_bridge_dimension_registry_import,
    clean_duplicate_imports,
    validate_modified_file,
    _validate_kotlin_line,
    _clean_duplicate_modifier,
    _ensure_bridge_dimension_registry_import,
    _clean_duplicate_imports,
    _validate_modified_file,
)

__all__ = [
    "validate_kotlin_line",
    "clean_duplicate_modifier",
    "ensure_bridge_dimension_registry_import",
    "clean_duplicate_imports",
    "validate_modified_file",
    "_validate_kotlin_line",
    "_clean_duplicate_modifier",
    "_ensure_bridge_dimension_registry_import",
    "_clean_duplicate_imports",
    "_validate_modified_file",
]
