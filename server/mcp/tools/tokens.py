# -*- coding: utf-8 -*-
"""
MCP Token manipulation and inspection tools.
"""

import sys
import json
import asyncio
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Any

from mcp.app import app, log, PROJECT_ROOT, state_manager
from mcp.tools.misc import notify_bridge_server, notify_agent_lifecycle, notify_refresh_to_bridge, run_async, send_refresh_signal

from core.token_migrator import TokenMigrator
from core.theme_indexer import get_index
from core.project_scanner import ProjectScanner
from core.token_split_analyzer import TokenSplitAnalyzer
from core.pattern_detector import PatternDetector
from core.token_linker import TokenLinker
from core.state_editor import update_token_default
from core.project_root import get_project_root
from common.file_ops import acquire_write_lock

@app.tool(
    name="find_token_by_color",
    description="Reverse lookup: Find token(s) matching an exact hex color.",
)
def find_token_by_color(hex_color: str) -> str:
    """
    Reverse lookup: Find token(s) matching a hex color. Match is EXACT (case-insensitive).
    
    What it does: Searches the design system color tokens to find which token names have this exact color.
    When to use: When you have a hardcoded hex color (e.g. from design mockup or code) and want to check if a token already exists for it.
    When NOT to use: Do not use for fuzzy or perceptual color matching. Use list_tokens to explore all available colors.
    Side effects: Read-only. No files modified.
    Parameters:
      - hex_color: '#RRGGBB' or 'RRGGBB' (hash optional, case-insensitive).
    Returns:
      JSON string with {"token": "Primary"} or {"token": None} if no match found. Does not do color distance matching.
    """
    log(f"🔧 find_token_by_color: {hex_color}")
    try:
        idx = get_index()
        token = idx.find_token_by_color(hex_color)
        return json.dumps({"token": token})
    except Exception as e:
        log(f"❌ find_token_by_color error: {e}")
        log(traceback.format_exc())
        return json.dumps({"error": str(e)})


@app.tool()
def add_token(
    file: str,
    line: int,
    value: str,
    token_name: str,
    token_type: str,
    preferred_token_file: str = None,
    force_create: bool = False,
) -> str:
    """
    Convert a hardcoded value to a design token.
    
    This tool:
    1. Adds a new token definition to AppDimens.kt or AppColors.kt
    2. Replaces ONLY the specified line with the new token
    3. Does NOT touch any other line in the project
    
    Use list_tokens() first to find hardcoded values that
    could become tokens.
    
    Args:
        file: File name (e.g., "DashboardPage.kt")
        line: Line number (1-indexed)
        value: Expected value (e.g., "16.dp" or "0xFF7C3AED")
        token_name: New token name (e.g., "padding_md")
        token_type: "dimension" or "color"
        preferred_token_file: Optional target token file (e.g. "Tokens.kt")
        force_create: ⚠️ force_create bypasses duplicate detection. Use ONLY for testing.
    
    Returns:
        JSON with success status and details.
    """
    from core.token_migrator import TokenMigrator
    from core.project_root import get_project_root
    p_root = get_project_root()

    if not preferred_token_file:
        if token_type == "color":
            for cand in ["DesignSystem.kt", "AppColors.kt", "Theme.kt", "Color.kt", "Colors.kt"]:
                if list(p_root.rglob(cand)):
                    preferred_token_file = cand
                    break
        elif token_type == "dimension":
            for cand in ["AppDimens.kt", "DesignSystem.kt", "Dimens.kt", "Dimensions.kt", "Spacing.kt"]:
                if list(p_root.rglob(cand)):
                    preferred_token_file = cand
                    break

    try:
        migrator = TokenMigrator(p_root)
        success, message, info = migrator.migrate(
            file_name=file,
            line=line,
            value=value,
            token_name=token_name,
            token_type=token_type,
            preferred_token_file=preferred_token_file,
            force_create=force_create,
        )
        
        if success:
            # Record in state manager
            state_manager.events.log(
                "token_added",
                {
                    "token_name": token_name,
                    "value": value,
                    "type": token_type,
                    "file": file,
                    "line": line,
                },
                source="agent",
            )
            state_manager.save_all()
            
            # Notify bridge for phone & IDE plugin refresh
            try:
                run_async(notify_bridge_server(token_name, value))
            except Exception:
                pass
            try:
                send_refresh_signal()
            except Exception:
                pass
            
            return json.dumps({
                "success": True,
                "message": message,
                "info": info,
                "warning": "force_create was used. This bypassed duplicate detection." if force_create else None,
            }, indent=2, ensure_ascii=False)
        else:
            # كشف نوع الخطأ
            error_type = "unknown"
            if "Token name invalid" in message:
                error_type = "semantic_validation"
            elif "already exists as" in message:
                error_type = "same_value_different_name"
            elif "may cause semantic confusion" in message:
                error_type = "same_base_different_value"
            elif "already exists" in message:
                error_type = "duplicate"
            
            if info and "safe_alternative" in info:
                info["recommended_name"] = info["safe_alternative"]

            recommended_name = None
            if info:
                recommended_name = info.get("safe_alternative") or info.get("recommended_name") or info.get("suggested_name")

            return json.dumps({
                "success": False,
                "error": message,
                "error_type": error_type,
                "info": info,
                "recommended_name": recommended_name,
            }, indent=2, ensure_ascii=False)
    
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
        }, indent=2, ensure_ascii=False)


@app.tool()
def get_naming_convention(token_type: str = "dimension") -> str:
    """
    Read-only analysis. Detects if project uses camelCase, snake_case, or PascalCase for tokens.
    
    What it does: Analyzes existing tokens to detect whether project uses camelCase, snake_case, or PascalCase.
    When to use: Use BEFORE creating new tokens with add_token or replace_pattern to maintain project consistency.
    When NOT to use: Do not use to inspect actual token values; use list_tokens instead.
    Side effects: Read-only. No files modified.
    Parameters:
      - token_type: 'dimension' (default) or 'color'.
    Returns:
      JSON string with detected style (e.g. 'camelCase'), confidence score, examples, and recommendations.
    """
    from core.token_migrator import TokenMigrator
    
    try:
        migrator = TokenMigrator(PROJECT_ROOT)
        convention = migrator.detect_naming_convention(token_type)
        token_files = migrator.find_all_token_files(token_type)
        
        return json.dumps({
            "success": True,
            "token_type": token_type,
            "style": convention["style"],
            "total_tokens": convention.get("total_count", 0),
            "examples": convention["examples"],
            "common_suffixes": convention.get("common_suffixes", []),
            "token_files": [
                str(f.relative_to(PROJECT_ROOT)) for f in token_files
            ],
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def list_tokens(project_path: str = None) -> str:
    """
    List all design tokens in the project.
    
    Returns a comprehensive report:
    - Registered tokens (dimensions, colors)
    - Hardcoded values that could become tokens
    - Duplicate tokens (same value, different names)
    - Orphan tokens (registered but unused)
    
    Use this to understand the project's design system
    before making edits.

    Args:
        project_path: optional — explicit path to project root.
    """
    from core.project_scanner import ProjectScanner
    from core.project_root import get_project_root
    
    try:
        root = get_project_root(Path(project_path) if project_path else None)
        scanner = ProjectScanner(root)
        report = scanner.scan()
        
        return json.dumps({
            "success": True,
            "summary": report.summary(),
            "registered_tokens": [
                {
                    "name": t.name,
                    "kind": t.kind,
                    "value": t.value,
                    "location": f"{t.file}:{t.line}",
                    "usage_count": t.usage_count,
                }
                for t in report.registered_tokens
            ],
            "hardcoded_values": [
                {
                    "value": h.value,
                    "kind": h.kind,
                    "file": h.file,
                    "line": h.line,
                    "location": f"{h.file}:{h.line}",
                    "suggestion": h.suggestion_name,
                    "category": h.category,
                }
                for h in report.hardcoded_values
            ],
            "duplicates": [
                {
                    "value": d.value,
                    "kind": d.kind,
                    "tokens": d.tokens,
                    "locations": d.locations,
                }
                for d in report.duplicates
            ],
            "orphans": [
                {
                    "name": o.name,
                    "value": o.value,
                    "location": f"{o.file}:{o.line}",
                }
                for o in report.orphans
            ],
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def set_token(token_name: str, value: str) -> str:
    """
    DESTRUCTIVE: Modifies .kt files. Surgically edit a design token value in source code.
    
    What it does: Modifies .kt files containing the token definition. Notifies phone via WebSocket (live preview).
    When to use: When adjusting a design token (color or dimension) and immediately observing visual feedback.
    When NOT to use: Do not use for text strings (use set_text). Do not use for converting hardcoded values to tokens (use add_token).
    Side effects: DESTRUCTIVE: Modifies source code on disk. Requires approve_file_changes to commit changes or reject_file_changes to revert.
    Parameters:
      - token_name: exact token name OR 'AppColors.TokenName' (e.g., 'Primary', 'cardCorner').
      - value: '#RRGGBB' for colors or numeric for dimensions (e.g., '#FF1122', '24.dp').
    Returns:
      JSON string with update status, file path, and previous/new values.
    """
    from core.write_lock import acquire_write_lock
    with acquire_write_lock():
        try:
            from core.state_editor import update_token_default
            
            # ═══ 1. Notify Bridge: agent_start ═══
            started = False
            try:
                started = asyncio.run(notify_agent_lifecycle("agent_start"))
                print(f"[MCP] agent_start notified: {started}", file=sys.stderr)
            except Exception as e:
                print(f"[MCP] agent_start failed: {e}", file=sys.stderr)
            
            # Agent session active (coordinated via state_queue)
            
            # ═══ 2. Apply surgical edit ═══
            from core.state_editor import update_theme_color
            val_clean = value.strip()
            is_color = (
                val_clean.startswith(('#', '0x', '0X')) or
                val_clean.startswith('Color(') or
                val_clean.startswith('Color.') or
                token_name.startswith('AppColors.')
            )

            if is_color:
                color_val = val_clean
                if color_val.startswith('Color(') and color_val.endswith(')'):
                    color_val = color_val[6:-1].strip()
                color_key = token_name.split('.')[-1] if '.' in token_name else token_name
                ok, msg, info = update_theme_color(color_key, color_val)
            else:
                ok, msg, info = update_token_default(token_name, value)
            
            if not ok:
                state_manager.failures.record(
                    operation="set_token",
                    token=token_name,
                    location="unknown",
                    error=msg,
                    severity="error",
                )
                state_manager.save_all()
                
                # Notify end even on failure
                try:
                    asyncio.run(notify_agent_lifecycle("agent_end"))
                except Exception:
                    pass
                
                return json.dumps({"success": False, "error": msg})
            
            # ═══ 3. Record in State Manager ═══
            state_manager.history.record_value(
                token=token_name,
                old_value="",
                new_value=value,
                source="agent",
            )
            state_manager.events.log(
                "mcp_set_token",
                {"token": token_name, "value": value},
                source="agent",
            )
            state_manager.save_all()
            
            # ═══ 4. Notify Bridge: mcp_state_update ═══
            bridge_status = {"bridge_connected": False, "device_connected": False, "forwarded_to": 0}
            try:
                notify_res = asyncio.run(
                    notify_bridge_server(token_name, value)
                )
                if isinstance(notify_res, dict):
                    bridge_status = notify_res
                elif notify_res is True:
                    bridge_status = {"bridge_connected": True, "device_connected": True, "forwarded_to": 1}
            except Exception as e:
                print(f"[MCP] notify error: {e}", file=sys.stderr)

            device_connected = bridge_status.get("device_connected", False)
            live_applied = device_connected and ok
            
            # ═══ 5. Notify Bridge: agent_end & refresh ═══
            try:
                send_refresh_signal()
            except Exception as e:
                print(f"[MCP] refresh notify error: {e}", file=sys.stderr)

            ended = False
            try:
                ended = asyncio.run(notify_agent_lifecycle("agent_end"))
                print(f"[MCP] agent_end notified: {ended}", file=sys.stderr)
            except Exception as e:
                print(f"[MCP] agent_end failed: {e}", file=sys.stderr)

            warning_msg = None
            if not device_connected:
                warning_msg = "Code modified on disk, but live preview failed because no connected device was found."

            return json.dumps({
                "success": True,
                "token": token_name,
                "value": value,
                "disk_updated": True,
                "device_connected": device_connected,
                "live_applied": live_applied,
                "notified_live": device_connected,
                "warning": warning_msg,
                "agent_started": started,
                "agent_ended": ended,
                "auto_wrapped": info.get("auto_wrapped", False) if isinstance(info, dict) else False,
            }, indent=2, ensure_ascii=False)
        
        except Exception as e:
            state_manager.failures.record(
                operation="set_token",
                token=token_name,
                location="unknown",
                error=str(e),
                severity="error",
            )
            state_manager.save_all()
            
            try:
                asyncio.run(notify_agent_lifecycle("agent_end"))
            except Exception:
                pass
            
            return json.dumps({"error": str(e)})


@app.tool()
def list_orphans(project_path: str = None) -> str:
    """
    List all orphan tokens (registered but never used).
    
    Orphan tokens are a sign of design system clutter.
    Use this to identify tokens that can be safely removed
    or that need to be used in the codebase.
    
    Args:
        project_path: optional — explicit path to project root.

    Returns:
        JSON with list of orphan tokens and their locations.
    """
    from core.project_scanner import ProjectScanner
    from core.project_root import get_project_root
    
    try:
        root = get_project_root(Path(project_path) if project_path else None)
        scanner = ProjectScanner(root)
        report = scanner.scan(include_hardcoded=False)
        
        return json.dumps({
            "success": True,
            "count": len(report.orphans),
            "orphans": [
                {
                    "name": o.name,
                    "kind": o.kind,
                    "value": o.value,
                    "location": f"{o.file}:{o.line}",
                }
                for o in report.orphans
            ],
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def get_token_impact(token_name: str, project_path: str = None) -> str:
    """
    Get impact analysis for a specific token.
    
    Shows:
    - All places where the token is used (file:line)
    - The enclosing @Composable for each usage
    - Total number of affected UI elements
    
    Use this BEFORE changing a token to understand the impact.
    
    Args:
        token_name: "welcomeCardHeight" or "Primary"
        project_path: optional — explicit path to project root.
    
    Returns:
        JSON with full impact analysis.
    """
    from core.project_scanner import ProjectScanner
    from core.project_root import get_project_root
    
    try:
        root = get_project_root(Path(project_path) if project_path else None)
        scanner = ProjectScanner(root)
        report = scanner.scan(include_hardcoded=False)
        
        impact = next(
            (i for i in report.token_impacts if i.token_name == token_name),
            None,
        )
        
        if not impact:
            return json.dumps({
                "success": False,
                "error": f"Token '{token_name}' not found",
            })
        
        return json.dumps({
            "success": True,
            "token_name": impact.token_name,
            "token_value": impact.token_value,
            "token_kind": impact.token_kind,
            "token_location": impact.token_location,
            "total_impact": impact.total_impact,
            "affected_composables": impact.affected_composables,
            "usages": [
                {
                    "file": u.file,
                    "line": u.line,
                    "line_content": u.line_content,
                    "enclosing_composable": u.enclosing_composable,
                    "enclosing_line": u.enclosing_line,
                }
                for u in impact.usages
            ],
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def suggest_token_split(token_name: str = None, project_path: str = None) -> str:
    """
    Read-only analysis. Suggests splitting tokens used in multiple contexts.
    
    What it does: Detects if a token is used in different contexts (e.g. cards and buttons) and proposes contextual splits.
    When to use: Use BEFORE replace_pattern.
    When NOT to use: For token impact analysis use get_token_impact. For sibling tokens use get_token_siblings.
    Side effects: Read-only. No files modified.
    Parameters:
      - token_name: optional filter to analyze a specific token only.
      - project_path: optional override for project root path.
    Returns:
      JSON string with split suggestions, proposed token names, and affected call sites.
    """
    from core.project_scanner import ProjectScanner
    from core.project_root import get_project_root
    try:
        root = get_project_root(Path(project_path) if project_path else None)
        scanner = ProjectScanner(root)
        report = scanner.scan(include_hardcoded=False)

        suggestions = report.split_suggestions
        if token_name:
            suggestions = [s for s in suggestions if s.token_name == token_name]

        return json.dumps({
            "success": True,
            "count": len(suggestions),
            "suggestions": [
                {
                    "token_name": s.token_name,
                    "token_value": s.token_value,
                    "token_kind": s.token_kind,
                    "contexts": {k: len(v) for k, v in s.contexts.items()},
                    "suggested_tokens": [
                        {
                            "name": st["name"],
                            "context": st["context"],
                            "hierarchy_path": st.get("hierarchy_path", []),
                            "composables": list(set(u["enclosing_composable"] for u in st["usages"])),
                            "usage_count": len(st["usages"]),
                        }
                        for st in s.suggested_tokens
                    ],
                }
                for s in suggestions
            ],
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def detect_conditional_variants(token_name: str = None) -> str:
    """
    Detect repeated patterns like:
    if (isDark) Color(0xFF818CF8) else AppColors.Primary
    
    Args:
        token_name: optional — filter by base token name.
        
    Returns:
        JSON with detected patterns + occurrences + suggestions.
    """
    from core.pattern_detector import PatternDetector
    try:
        detector = PatternDetector(PROJECT_ROOT)
        patterns = detector.detect(token_name)
        if token_name:
            patterns = [p for p in patterns if token_name.lower() in p.suggested_token_name.lower()]
        patterns.sort(key=lambda p: len(p.occurrences), reverse=True)
        return json.dumps({
            "success": True,
            "count": len(patterns),
            "patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "template": p.template,
                    "occurrences": len(p.occurrences),
                    "suggested_token_name": p.suggested_token_name,
                    "suggested_token_value": p.suggested_token_value,
                    "affected_files": list(set(o.file for o in p.occurrences)),
                    "details": [
                        {"file": o.file, "line": o.line, "composable": o.enclosing_composable}
                        for o in p.occurrences[:20]
                    ],
                }
                for p in patterns
            ],
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def get_token_siblings(token_name: str) -> str:
    """
    Read-only. Returns semantically related tokens (e.g., Primary → PrimaryDark, PrimaryLight).
    
    What it does: Finds related variants of a token based on naming patterns and semantic links.
    When to use: When exploring related tokens or checking which color variants already exist.
    When NOT to use: Does NOT include the original token. Returns empty list if no siblings.
    Side effects: Read-only. No files modified.
    Parameters:
      - token_name: exact token name (e.g., 'Primary') or fully-qualified (e.g., 'AppColors.Primary').
    Returns:
      JSON string with list of sibling token names and current values.
    """
    from core.token_linker import TokenLinker
    try:
        linker = TokenLinker(PROJECT_ROOT)
        siblings = linker.get_siblings(token_name)
        return json.dumps({
            "success": True,
            "token_name": token_name,
            "siblings": siblings,
            "count": len(siblings),
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def get_all_token_groups() -> str:
    """
    Read-only. Returns ALL semantic token groups in the project (e.g., 'Actions', 'Dashboard', 'Settings').
    
    What it does: Lists all token groups discovered across design system objects.
    When to use: To inspect the high-level semantic grouping of design tokens.
    When NOT to use: Use list_tokens for individual tokens. Groups are based on object declarations in AppStrings/DesignSystem.
    Side effects: Read-only. No files modified.
    Parameters: None.
    Returns:
      JSON string with group names, member token counts, and parent objects.
    """
    from core.token_linker import TokenLinker
    try:
        linker = TokenLinker(PROJECT_ROOT)
        groups = linker.detect_groups()
        return json.dumps({
            "success": True,
            "groups": groups,
            "count": len(groups),
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

