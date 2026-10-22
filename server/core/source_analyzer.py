# -*- coding: utf-8 -*-
"""
Source Analyzer Facade.
Re-exports all symbols from modular analysis subpackages for backwards compatibility.
"""

import sys
from pathlib import Path

# Support relative or absolute server imports
try:
    from analysis.color_analyzer import *
    from analysis.dimension_analyzer import *
    from analysis.text_ref_analyzer import *
    from analysis.ast_scope_resolver import *
except ImportError:
    try:
        from server.analysis.color_analyzer import *
        from server.analysis.dimension_analyzer import *
        from server.analysis.text_ref_analyzer import *
        from server.analysis.ast_scope_resolver import *
    except ImportError:
        from ..analysis.color_analyzer import *
        from ..analysis.dimension_analyzer import *
        from ..analysis.text_ref_analyzer import *
        from ..analysis.ast_scope_resolver import *

# Explicit re-exports for documentation and IDE type-checkers
from analysis.color_analyzer import (
    NAMED_COLORS_HEX,
    NAMED_COLOR_VARIANTS,
    _normalize_color_literals,
    _clean_hex,
    _find_color_locations,
    _hex_to_color_expr,
    _is_valid_kotlin_identifier,
    _detect_app_colors_pkg,
    _ensure_app_colors_import,
    preview_global_color_edit,
    global_color_edit,
    split_token_for_element,
)

from analysis.dimension_analyzer import (
    _normalize_dim_value,
    _find_dimension_usage,
    _extract_dimensions_with_property,
    _ensure_bridge_dimension_registry_import,
    global_dimension_edit,
    split_dimension_edit,
)

from analysis.text_ref_analyzer import (
    _resolve_app_strings_value,
    _find_ref_in_app_strings,
    _detect_composable_name,
)

from analysis.ast_scope_resolver import (
    RISKY_FILE_PATTERNS,
    _USAGE_GLOBAL_CACHE,
    _find_enclosing_function_or_class,
    _extract_composable_scope,
    _line_context_with_start,
    _extract_utf16_range,
    _count_function_calls,
    _detect_property,
    _is_theme_dependent,
    _is_safe_compose_file,
    _is_safe_line,
    _validate_modified_file,
    _clean_duplicate_imports,
    _find_token_by_value,
    _update_existing_token,
    _find_all_occurrences,
    _find_file,
    _empty_result,
    get_token_value_map,
    get_global_usage_counts,
    analyze_element_range,
)
