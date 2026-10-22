# -*- coding: utf-8 -*-
"""
ComposeBridge MCP Server Facade.
Re-exports all tools, security helpers, and the server application instance.
"""

import sys
import traceback
from pathlib import Path

# Central app instance
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
)

from mcp.tools.patterns import (
    replace_pattern,
    list_applied_patterns,
    rollback_pattern,
)

from mcp.tools.gradle import (
    ALLOWED_GRADLE_TASKS,
    is_gradle_task_allowed,
    run_gradle_build,
    list_allowed_gradle_tasks,
    trigger_user_sync,
    get_sync_status,
)

from mcp.tools.misc import (
    set_text,
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
