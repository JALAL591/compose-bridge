# -*- coding: utf-8 -*-
"""
MCP Server Application Instance & Central Logging.
"""

import sys
import traceback
from pathlib import Path
from datetime import datetime

# Diagnostic log file
LOG_FILE = Path.home() / "composebridge-mcp.log"


def log(msg):
    """Write to diagnostic log file + stderr."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] {msg}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    try:
        sys.stderr.write(line)
        sys.stderr.flush()
    except Exception:
        pass


log("=" * 60)
log("MCP SERVER STARTING")
log(f"Python: {sys.version}")
log(f"Executable: {sys.executable}")
log(f"CWD: {Path.cwd()}")
log("=" * 60)

try:
    from mcp.server.mcpserver import MCPServer
    log("✅ MCP imports OK (MCPServer)")
except Exception as e:
    log(f"❌ MCP import failed: {e}")
    log(traceback.format_exc())
    sys.exit(1)

try:
    from core.theme_indexer import get_index, init as init_theme_indexer
    init_theme_indexer()
    log("✅ Core imports OK & Indexer initialized")
except Exception as e:
    log(f"❌ Core import failed: {e}")
    log(traceback.format_exc())
    sys.exit(1)

log("Creating MCPServer instance...")
app = MCPServer("composebridge")
log("✅ MCPServer created")

from core.project_root import get_project_root
from core.state_manager import StateManager

PROJECT_ROOT = get_project_root()
state_manager = StateManager(PROJECT_ROOT)
state_manager.init()
