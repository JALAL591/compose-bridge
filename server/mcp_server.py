# -*- coding: utf-8 -*-
"""
ComposeBridge MCP Server (Standalone & Modular)
Re-exports all tools, security helpers, and the server application instance.
"""

import sys
import os
import traceback
from pathlib import Path

# Ensure repository root and server directory are in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# MCP Application Context and State
from mcp.app import app, log, LOG_FILE, PROJECT_ROOT, state_manager

# Re-export all tools so they register with @app.tool() and are accessible externally
from mcp.tools.tokens import (
    find_token_by_color,
    add_token,
    get_naming_convention,
    list_tokens,
    set_token,
    list_orphans,
    get_token_impact,
    suggest_token_split,
    detect_conditional_variants,
    get_token_siblings,
    get_all_token_groups,
)

from mcp.tools.files import (
    rollback_last,
    list_modified_files,
    reject_file_changes,
    approve_file_changes,
    approve_all_files,
    reject_all_files,
    reject_all_files_force,
    get_file_diff,
    approve_change,
    reject_change,
    clean_cache,
)

from mcp.tools.patterns import (
    replace_pattern,
    list_applied_patterns,
    rollback_pattern,
)

from mcp.tools.gradle import (
    run_gradle_build,
    get_gradle_status,
    list_allowed_gradle_tasks,
    trigger_user_sync,
    get_sync_status,
    ALLOWED_GRADLE_TASKS,
    is_gradle_task_allowed,
)

from mcp.tools.text import (
    set_text,
)

from mcp.tools.discovery import (
    analyze_design_scatter,
    set_design_file_mapping,
    get_design_file_mappings,
)

from mcp.network_client import (
    notify_bridge_server,
    notify_agent_lifecycle,
    run_async,
)


def main():
    log("MCP Server starting run(transport='stdio')...")
    try:
        app.run(transport="stdio")
    except Exception as e:
        log(f"Server exited with error: {e}")
        log(traceback.format_exc())


if __name__ == "__main__":
    main()
