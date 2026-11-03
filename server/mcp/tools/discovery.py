# -*- coding: utf-8 -*-
"""
MCP Tools for Universal Discovery & Design File Mapping.
Enables AI Agents to analyze scattered tokens and configure custom registry mappings.
"""

import json
from pathlib import Path
from typing import Optional

from mcp.app import app, log, PROJECT_ROOT
from mcp.types import ToolAnnotations
from core.project_root import get_project_root
from analysis.universal_scanner import (
    scan_design_scatter,
    save_design_file_mapping,
    get_design_file_mappings as fetch_design_file_mappings,
    resolve_target_design_file,
)


@app.tool(
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
)
def analyze_design_scatter(
    category: str = "all",
    limit: int = 10,
    project_root: Optional[str] = None
) -> str:
    """
    Analyzes scattered hardcoded design tokens (colors, dimensions, strings) across the project.
    Returns a compact, categorized report to avoid context window exhaustion.

    When to use:
    - Call during project onboarding, architecture audits, or before major UI refactorings.
    - Call to locate hardcoded color literals, raw Dp values, and string literals across Jetpack Compose files.

    When NOT to use:
    - Do not use if you already know the exact token name or file (use find_token_by_color or list_tokens instead).
    - Do not use for applying code changes directly (use set_token, add_token, or set_text instead).

    Side effects:
    - None (strictly read-only AST inspection, does not modify any source code or configuration).

    Args:
        category: 'all', 'colors', 'dimensions', or 'strings'.
        limit: Maximum number of files to return per category (default: 10).
        project_root: Optional path to project root.
    """
    try:
        if category and (Path(category).exists() or "/" in category or "\\" in category):
            project_root = category
            category = "all"

        p_root = Path(project_root) if project_root else (PROJECT_ROOT or get_project_root())
        scan_res = scan_design_scatter(p_root)
        from analysis.scatter_formatter import format_scatter_for_agent
        formatted = format_scatter_for_agent(scan_res, category=category, limit=limit)
        return json.dumps(formatted, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Error in analyze_design_scatter: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@app.tool(
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=True,
        idempotent_hint=True,
        open_world_hint=False,
    )
)
def set_design_file_mapping(token_type: str, file_path: str, project_root: Optional[str] = None) -> str:
    """
    Sets a designated design/registry file in .composebridge/config.json for a token type.

    When to use:
    - Call when ComposeBridge stops with NEEDS_MANUAL_MAPPING because design system files are in non-standard paths.
    - Call to lock designated target files for colors, dimensions, or strings.

    When NOT to use:
    - Do not use if the project uses standard design file locations (e.g., Color.kt, AppStrings.kt).
    - Do not use for reading existing token mappings (use get_design_file_mappings instead).

    Side effects:
    - Modifies .composebridge/config.json on disk to persist file mappings.

    Args:
        token_type: 'color', 'dimension', 'string', or 'all'.
        file_path: Relative path to the Kotlin file (e.g. 'composeApp/src/commonMain/kotlin/.../Color.kt').
        project_root: Optional path to project root.
    """
    try:
        p_root = Path(project_root) if project_root else (PROJECT_ROOT or get_project_root())
        result = save_design_file_mapping(token_type, file_path, p_root)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Error in set_design_file_mapping: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@app.tool(
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
)
def get_design_file_mappings(project_root: Optional[str] = None) -> str:
    """
    Returns current design/registry file mappings configured in .composebridge/config.json.

    When to use:
    - Call before modifying design tokens to inspect which files are mapped for colors, dimensions, and strings.
    - Call to verify current target files when debugging token resolution issues.

    When NOT to use:
    - Do not use to configure or modify file mappings (use set_design_file_mapping instead).
    - Do not use to list token names and values (use list_tokens instead).

    Side effects:
    - None (strictly read-only configuration lookup, does not modify any files).

    Args:
        project_root: Optional path to project root.
    """
    try:
        p_root = Path(project_root) if project_root else (PROJECT_ROOT or get_project_root())
        mappings = fetch_design_file_mappings(p_root)
        return json.dumps({
            "success": True,
            "project_root": str(p_root),
            "mappings": mappings,
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Error in get_design_file_mappings: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
