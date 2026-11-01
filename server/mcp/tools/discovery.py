# -*- coding: utf-8 -*-
"""
MCP Tools for Universal Discovery & Design File Mapping.
Enables AI Agents to analyze scattered tokens and configure custom registry mappings.
"""

import json
from pathlib import Path
from typing import Optional

from mcp.app import app, log, PROJECT_ROOT
from core.project_root import get_project_root
from analysis.universal_scanner import (
    scan_design_scatter,
    save_design_file_mapping,
    get_design_file_mappings as fetch_design_file_mappings,
    resolve_target_design_file,
)


@app.tool()
def analyze_design_scatter(
    category: str = "all",
    limit: int = 10,
    project_root: Optional[str] = None
) -> str:
    """
    Analyzes scattered design tokens (colors, dimensions, strings) across the project.
    Returns a compact, categorized report to avoid context window exhaustion.

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


@app.tool()
def set_design_file_mapping(token_type: str, file_path: str, project_root: Optional[str] = None) -> str:
    """
    Sets a designated design/registry file in .composebridge/config.json for a token type.
    token_type: 'color', 'dimension', 'string', or 'all'.
    file_path: relative path to the Kotlin file (e.g. 'composeApp/src/commonMain/kotlin/.../Color.kt').
    Prevents token scatter and protects projects with non-standard design system structures.
    """
    try:
        p_root = Path(project_root) if project_root else (PROJECT_ROOT or get_project_root())
        result = save_design_file_mapping(token_type, file_path, p_root)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Error in set_design_file_mapping: {e}")
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


@app.tool()
def get_design_file_mappings(project_root: Optional[str] = None) -> str:
    """
    Returns current design/registry file mappings configured in .composebridge/config.json.
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

