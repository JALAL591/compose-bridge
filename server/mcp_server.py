import re
# -*- coding: utf-8 -*-
"""
ComposeBridge MCP Server — Diagnostic Version
Logs all events to ~/composebridge-mcp.log for debugging.
"""

import asyncio
import json
import logging
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import traceback
from pathlib import Path
from datetime import datetime
import websockets
from core.state_manager import StateManager

# ============================================================
# Security: Gradle Tasks Allowlist
# ============================================================
ALLOWED_GRADLE_TASKS = {"assembleDebug", "assembleRelease", "test", "lint", "clean"}

def is_gradle_task_allowed(task: str) -> bool:
    """Strictly validate task to prevent arbitrary execution or injection."""
    if not task or not isinstance(task, str):
        return False
    # Reject shell metacharacters, spaces, options/flags
    if not re.match(r"^:?[a-zA-Z0-9_\-]+(?::[a-zA-Z0-9_\-]+)*$", task.strip()):
        return False
    if task in ALLOWED_GRADLE_TASKS:
        return True
    parts = task.strip(":").split(":")
    base_task = parts[-1] if parts else ""
    return base_task in ALLOWED_GRADLE_TASKS


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

# ═══ State Manager instance ═══
from core.project_root import get_project_root
PROJECT_ROOT = get_project_root()
state_manager = StateManager(PROJECT_ROOT)
state_manager.init()

# ═══ Notify Bridge Server ═══
async def notify_bridge_server(token: str, value: str) -> bool:
    """
    After editing a file, notify the Bridge Server.
    Bridge will broadcast to connected phones.
    """
    try:
        async with websockets.connect(
            "ws://127.0.0.1:8711",
            open_timeout=2,
        ) as ws:
            # Auth
            await ws.send(json.dumps({
                "type": "auth",
                "token": "test-token-local-dev",
            }))
            await asyncio.wait_for(ws.recv(), timeout=2)

            # Send mcp_state_update
            await ws.send(json.dumps({
                "type": "mcp_state_update",
                "property": f"AppColors.{token}",
                "value": value,
                "source": "mcp",
            }))
            ack = await asyncio.wait_for(ws.recv(), timeout=2)
            return True
    except Exception as e:
        print(f"[MCP] Bridge notify failed: {e}", file=sys.stderr)
        return False


async def notify_agent_lifecycle(event: str) -> bool:
    """
    Notify Bridge Server about agent session start/end.
    
    Args:
        event: "agent_start" or "agent_end"
    """
    try:
        async with websockets.connect(
            "ws://127.0.0.1:8711",
            open_timeout=2,
        ) as ws:
            # Auth
            await ws.send(json.dumps({
                "type": "auth",
                "token": "test-token-local-dev",
            }))
            await asyncio.wait_for(ws.recv(), timeout=2)
            
            # Send lifecycle event
            await ws.send(json.dumps({"type": event}))
            ack = await asyncio.wait_for(ws.recv(), timeout=2)
            return True
    except Exception as e:
        print(f"[MCP] Lifecycle notify failed: {e}", file=sys.stderr)
        return False

# ═══ Run async safely ═══
def run_async(coro):
    """Run async coroutine safely from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.create_task(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


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
    
    try:
        migrator = TokenMigrator(PROJECT_ROOT)
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
            
            # Notify bridge for phone
            try:
                asyncio.run(notify_bridge_server(
                    token_name, value
                ))
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
    Detect the naming convention used in the project.
    
    Args:
        token_type: "dimension" or "color"
    
    Returns:
        JSON with detected style, examples, and suggestions.
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
    Surgically edit a token value.
    Notifies Bridge + phones live.
    Uses agent_start/agent_end for session tracking.
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
            
            # Hold agent session window for race coordination
            import time
            time.sleep(0.8)
            
            # ═══ 2. Apply surgical edit ═══
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
            notified = False
            try:
                notified = asyncio.run(
                    notify_bridge_server(token_name, value)
                )
            except Exception as e:
                print(f"[MCP] notify error: {e}", file=sys.stderr)
            
            # ═══ 5. Notify Bridge: agent_end ═══
            ended = False
            try:
                ended = asyncio.run(notify_agent_lifecycle("agent_end"))
                print(f"[MCP] agent_end notified: {ended}", file=sys.stderr)
            except Exception as e:
                print(f"[MCP] agent_end failed: {e}", file=sys.stderr)
            
            return json.dumps({
                "success": True,
                "token": token_name,
                "value": value,
                "notified_live": notified,
                "agent_started": started,
                "agent_ended": ended,
            })
        
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
    Suggest splitting tokens that are used in multiple contexts.

    Args:
        token_name: optional — analyze a specific token only.
        project_path: optional — explicit path to project root.

    Returns:
        JSON with split suggestions.
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
def replace_pattern(pattern_id: str, dry_run: bool = False) -> str:
    """
    Replace all occurrences of a detected pattern.
    Creates the suggested token + replaces all usages.
    
    Args:
        pattern_id: from detect_conditional_variants.
        
    Returns:
        JSON with replacements made.
    """
    from core.pattern_detector import PatternDetector
    from core.token_migrator import TokenMigrator
    from core.write_lock import acquire_write_lock
    try:
        detector = PatternDetector(PROJECT_ROOT)
        patterns = detector.detect()
        pattern = next((p for p in patterns if p.pattern_id == pattern_id), None)
        if not pattern:
            return json.dumps({"success": False, "error": f"Pattern '{pattern_id}' not found"})

        if dry_run:
            planned = []
            for idx, occ in enumerate(pattern.occurrences):
                if idx == 0:
                    planned.append({
                        "file": occ.file,
                        "line": occ.line,
                        "action": "create_and_replace",
                        "token_name": pattern.suggested_token_name,
                        "token_value": pattern.suggested_token_value,
                        "new_usage": f"AppColors.{pattern.suggested_token_name}"
                    })
                else:
                    planned.append({
                        "file": occ.file,
                        "line": occ.line,
                        "action": "replace_usage",
                        "old_value": occ.value_if_dark,
                        "new_usage": f"AppColors.{pattern.suggested_token_name}"
                    })
            return json.dumps({
                "success": True,
                "dry_run": True,
                "pattern_id": pattern_id,
                "token_name": pattern.suggested_token_name,
                "token_value": pattern.suggested_token_value,
                "replacements_count": len(planned),
                "planned_replacements": planned,
            }, indent=2, ensure_ascii=False)

        with acquire_write_lock():
            from core.pattern_journal import PatternJournal
            journal = PatternJournal(PROJECT_ROOT)

            migrator = TokenMigrator(PROJECT_ROOT)
            ok, msg, info = migrator.migrate(
                file_name=pattern.occurrences[0].file,
                line=pattern.occurrences[0].line,
                value=pattern.suggested_token_value,
                token_name=pattern.suggested_token_name,
                token_type="color",
                force_create=True,
            )
            if not ok:
                return json.dumps({
                    "success": False,
                    "error": f"Failed to create token '{pattern.suggested_token_name}'. "
                             f"Value '{pattern.suggested_token_value}' may not be supported. ({msg})",
                    "suggested_token": pattern.suggested_token_name,
                    "suggested_value": pattern.suggested_token_value,
                })

            # ⭐ Record added token in journal
            journal.record_token_added(
                pattern_id=pattern.pattern_id,
                token_name=pattern.suggested_token_name,
                token_value=pattern.suggested_token_value,
                file=str(info.get("registry_file", "")) if info else "",
            )
            journal.record_pattern_summary(
                pattern_id=pattern.pattern_id,
                token_name=pattern.suggested_token_name,
                token_file=str(info.get("registry_file", "")) if info else "",
                occurrences=[(occ.file, occ.line) for occ in pattern.occurrences],
            )

            if info:
                old_line = info.get("old_line", "")
                new_line = info.get("new_line", "")
                if not old_line or not new_line:
                    for f in detector._find_kt_files():
                        if f.name == pattern.occurrences[0].file:
                            c = f.read_text(encoding="utf-8").splitlines()
                            t_line = pattern.occurrences[0].line
                            if 1 <= t_line <= len(c):
                                new_line = c[t_line - 1]
                                old_line = new_line.replace(f"AppColors.{pattern.suggested_token_name}", pattern.occurrences[0].value_if_dark)
                            break
                journal.record(
                    pattern_id=pattern.pattern_id,
                    file=pattern.occurrences[0].file,
                    line=pattern.occurrences[0].line,
                    old_content=old_line,
                    new_content=new_line,
                )

            replacements = [{"file": pattern.occurrences[0].file, "line": pattern.occurrences[0].line}]
            for occ in pattern.occurrences[1:]:
                fp = None
                for f in detector._find_kt_files():
                    if f.name == occ.file:
                        fp = f
                        break
                if not fp:
                    continue
                content = fp.read_text(encoding="utf-8")
                lines = content.splitlines()

                # Find line with occ.value_if_dark: check occ.line - 1 first, or scan file if shifted
                target_idx = -1
                if occ.line <= len(lines) and occ.value_if_dark in lines[occ.line - 1]:
                    target_idx = occ.line - 1
                else:
                    for idx, line_str in enumerate(lines):
                        if occ.value_if_dark in line_str and f"AppColors.{pattern.suggested_token_name}" not in line_str:
                            target_idx = idx
                            break

                if target_idx != -1:
                    old = lines[target_idx]
                    new = old.replace(occ.value_if_dark, f"AppColors.{pattern.suggested_token_name}")
                    if new != old:
                        lines[target_idx] = new
                        replacements.append({"file": occ.file, "line": target_idx + 1})
                        fp.write_text("\n".join(lines) + "\n", encoding="utf-8")
                        journal.record(
                            pattern_id=pattern.pattern_id,
                            file=occ.file,
                            line=target_idx + 1,
                            old_content=old,
                            new_content=new,
                        )

            if len(replacements) == 0:
                return json.dumps({
                    "success": False,
                    "error": f"Failed to create token '{pattern.suggested_token_name}'. "
                             f"Value '{pattern.suggested_token_value}' may not be supported.",
                    "suggested_token": pattern.suggested_token_name,
                    "suggested_value": pattern.suggested_token_value,
                })

            return json.dumps({
                "success": True,
                "token_name": pattern.suggested_token_name,
                "replacements_count": len(replacements),
                "replacements": replacements[:20],
            }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def list_applied_patterns() -> str:
    """List all applied patterns that can be rolled back."""
    from core.pattern_journal import PatternJournal
    try:
        journal = PatternJournal(PROJECT_ROOT)
        patterns = journal.list_patterns()
        return json.dumps({
            "success": True,
            "count": len(patterns),
            "patterns": patterns,
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def rollback_pattern(pattern_id: str) -> str:
    """
    Rollback all changes for a specific pattern.
    Reverts every file modification made by replace_pattern.
    """
    from core.pattern_journal import PatternJournal
    from core.write_lock import acquire_write_lock
    try:
        with acquire_write_lock():
            journal = PatternJournal(PROJECT_ROOT)
            result = journal.rollback_pattern(pattern_id)
            return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def get_token_siblings(token_name: str) -> str:
    """
    Get semantic siblings of a token.
    Example: Primary → [PrimaryDark, PrimaryLight]
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
    """Get all semantic groups in the project."""
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


@app.tool()
def list_modified_files() -> str:
    """List all files modified by replace_pattern."""
    from core.pattern_journal import PatternJournal
    try:
        journal = PatternJournal(PROJECT_ROOT)
        files = journal.list_modified_files()
        return json.dumps({
            "success": True,
            "count": len(files),
            "files": files,
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def reject_file_changes(file_path: str) -> str:
    """Revert all changes for a specific file."""
    from core.pattern_journal import PatternJournal
    from core.write_lock import acquire_write_lock
    try:
        with acquire_write_lock():
            journal = PatternJournal(PROJECT_ROOT)
            result = journal.reject_file_changes(file_path)
            return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def approve_file_changes(file_path: str) -> str:
    """Approve changes for a specific file (remove from journal)."""
    from core.pattern_journal import PatternJournal
    from core.write_lock import acquire_write_lock
    try:
        with acquire_write_lock():
            journal = PatternJournal(PROJECT_ROOT)
            result = journal.approve_file_changes(file_path)
            return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def approve_all_files() -> str:
    """Approve all pending changes."""
    from core.pattern_journal import PatternJournal
    from core.write_lock import acquire_write_lock
    try:
        with acquire_write_lock():
            journal = PatternJournal(PROJECT_ROOT)
            result = journal.approve_all_files()
            return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def reject_all_files() -> str:
    """Revert all pending changes."""
    from core.pattern_journal import PatternJournal
    from core.write_lock import acquire_write_lock
    try:
        with acquire_write_lock():
            journal = PatternJournal(PROJECT_ROOT)
            result = journal.reject_all_files()
            return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def reject_all_files_force() -> str:
    """Force reject — clear journal even if some reverts fail."""
    from core.pattern_journal import PatternJournal
    from core.write_lock import acquire_write_lock
    try:
        with acquire_write_lock():
            journal = PatternJournal(PROJECT_ROOT)
            result = journal.reject_all_files(force=True)
            return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def get_file_diff(file_path: str) -> str:
    """Get before/after content and diff for a modified file."""
    from core.pattern_journal import PatternJournal
    try:
        journal = PatternJournal(PROJECT_ROOT)
        result = journal.get_file_diff(file_path)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def run_gradle_build(
    task: str = "assembleDebug",
    timeout_seconds: int = 300,
) -> str:
    """
    Run a Gradle task and return structured result.
    
    This lets the agent verify that code changes compile successfully
    before continuing with more changes.
    
    Args:
        task: gradle task to run (whitelist enforced: assembleDebug, assembleRelease, test, lint, clean).
        timeout_seconds: max execution time (default 5 min).
    
    Returns:
        JSON with {success, exit_code, duration_ms, errors, warnings}.
    """
    if not is_gradle_task_allowed(task):
        return json.dumps({
            "success": False,
            "error": f"Task '{task}' is not allowed. Allowed tasks: {sorted(ALLOWED_GRADLE_TASKS)}"
        }, indent=2, ensure_ascii=False)

    from core.gradle_runner import run_gradle_build as _run
    
    try:
        result = _run(PROJECT_ROOT, task, timeout_seconds)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def list_allowed_gradle_tasks() -> str:
    """List gradle tasks that can be run via run_gradle_build."""
    return json.dumps({
        "success": True,
        "tasks": sorted(ALLOWED_GRADLE_TASKS),
    }, indent=2, ensure_ascii=False)


@app.tool()
def trigger_user_sync() -> str:
    """
    Trigger user_sync on the Bridge Server.
    
    Applies all queued edits (dimension + color) to the files.
    Only works when the AI agent is not busy.
    
    Returns:
        JSON with {success, applied, skipped, errors}.
    """
    from core.sync_client import trigger_user_sync as _sync
    try:
        result = _sync()
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
def get_sync_status() -> str:
    """
    Get the current sync status from the Bridge Server:
    agent_busy, queue_count, snapshot_version.
    """
    from core.sync_client import get_state_info
    try:
        result = get_state_info()
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


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