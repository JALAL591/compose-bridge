# -*- coding: utf-8 -*-
"""
ComposeBridge MCP Server — Diagnostic Version
Logs all events to ~/composebridge-mcp.log for debugging.
"""

import asyncio
import json
import logging
import sys
import traceback
from pathlib import Path
from datetime import datetime

# === DIAGNOSTIC LOGGING ===
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
    # Also to stderr
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
log(f"Script: {__file__}")
log("=" * 60)

# === IMPORTS ===
try:
    from mcp.server.mcpserver import MCPServer
    log("✅ MCP imports OK (MCPServer)")
except Exception as e:
    log(f"❌ MCP import failed: {e}")
    log(traceback.format_exc())
    sys.exit(1)

# === CORE IMPORTS ===
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from core.state_editor import rollback_last as _rollback_last
    from core.theme_indexer import get_index, init as init_theme_indexer
    init_theme_indexer()
    log("✅ Core imports OK & Indexer initialized")
except Exception as e:
    log(f"❌ Core import failed: {e}")
    log(traceback.format_exc())
    sys.exit(1)

# === SERVER ===
log("Creating MCPServer instance...")
app = MCPServer("composebridge")
log("✅ MCPServer created")


@app.tool(
    name="find_token_by_color",
    description="Reverse lookup: which token has this hex color?",
)
def find_token_by_color(hex_color: str) -> str:
    log(f"🔧 find_token_by_color: {hex_color}")
    try:
        idx = get_index()
        token = idx.find_token_by_color(hex_color)
        return json.dumps({"token": token})
    except Exception as e:
        log(f"❌ find_token_by_color error: {e}")
        log(traceback.format_exc())
        return json.dumps({"error": str(e)})


@app.tool(
    name="rollback_last",
    description="Undo last surgical edit.",
)
def rollback_last() -> str:
    log("🔧 rollback_last")
    try:
        ok = _rollback_last()
        return json.dumps({"rolled_back": ok})
    except Exception as e:
        log(f"❌ rollback_last error: {e}")
        log(traceback.format_exc())
        return json.dumps({"error": str(e)})


@app.tool(
    name="set_token",
    description="Update a theme token value (dimensions in AppDimens.kt, colors in AppColors.kt, or typography in AppTypography.kt).",
)
def set_token(token_name: str, value: str) -> str:
    log(f"🔧 set_token: {token_name} = {value}")
    try:
        from core.state_editor import (
            update_token_default,
            update_theme_color,
            is_theme_color_property,
            extract_theme_key,
        )

        # Check if color token
        if is_theme_color_property(token_name):
            key = extract_theme_key(token_name)
            success, msg, info = update_theme_color(key, value)
            if success:
                from core.theme_indexer import reload_index
                reload_index()
            return json.dumps({"success": success, "message": msg, "info": info})

        # Default dimension token (e.g. welcomeCardHeight)
        success, msg, info = update_token_default(token_name, value)
        return json.dumps({"success": success, "message": msg, "info": info})
    except Exception as e:
        log(f"❌ set_token error: {e}")
        log(traceback.format_exc())
        return json.dumps({"error": str(e)})


def main():
    log("🚀 Starting MCPServer stdio...")
    try:
        app.run(transport="stdio")
    except Exception as e:
        log(f"❌ main() error: {e}")
        log(traceback.format_exc())
        raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Shutdown requested (Ctrl+C)")
    except Exception as e:
        log(f"❌ Top-level error: {e}")
        log(traceback.format_exc())