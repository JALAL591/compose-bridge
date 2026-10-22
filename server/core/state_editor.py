# -*- coding: utf-8 -*-
"""
State Editor Facade.
Re-exports all symbols from modular editor subpackages for backwards compatibility.
"""

from editor.journal_helpers import *
from editor.state_editor_core import *
from editor.color_editor import *
from editor.dimension_editor import *
from editor.text_editor import *
from common.file_ops import _atomic_write_text, _find_registry_file

# Explicit re-exports for IDEs and type-checkers
from editor.journal_helpers import (
    JOURNAL_FILE,
    MAX_JOURNAL,
    SPLICE_JOURNAL,
    with_write_lock,
    _journal_save,
    _validate_after_splice,
    rollback_last,
)

from editor.state_editor_core import (
    get_config_paths,
    get_bridge_state_file,
    get_app_typography_file,
    BRIDGE_STATE_FILE,
    APP_TYPOGRAPHY_FILE,
    find_mutable_state_property,
    normalize_value,
    update_bridge_state,
    apply_state_update,
    update_typography_property,
    is_typography_property,
    parse_typography_property,
)

from editor.color_editor import (
    get_app_colors_file,
    APP_COLORS_FILE,
    _build_color_pattern,
    _find_color_file_for_key,
    update_theme_color,
    is_theme_color_property,
    extract_theme_key,
    update_color,
)

from editor.dimension_editor import (
    edit_dimension_in_source,
    update_token_default,
)

from editor.text_editor import (
    escape_kotlin_string,
    update_text_in_source,
)

__all__ = [
    "JOURNAL_FILE",
    "MAX_JOURNAL",
    "SPLICE_JOURNAL",
    "with_write_lock",
    "_journal_save",
    "_validate_after_splice",
    "rollback_last",
    "get_config_paths",
    "get_bridge_state_file",
    "get_app_typography_file",
    "BRIDGE_STATE_FILE",
    "APP_TYPOGRAPHY_FILE",
    "find_mutable_state_property",
    "normalize_value",
    "update_bridge_state",
    "apply_state_update",
    "update_typography_property",
    "is_typography_property",
    "parse_typography_property",
    "get_app_colors_file",
    "APP_COLORS_FILE",
    "_build_color_pattern",
    "_find_color_file_for_key",
    "update_theme_color",
    "is_theme_color_property",
    "extract_theme_key",
    "update_color",
    "edit_dimension_in_source",
    "update_token_default",
    "escape_kotlin_string",
    "update_text_in_source",
    "_atomic_write_text",
    "_find_registry_file",
]
