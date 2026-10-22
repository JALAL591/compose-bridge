# -*- coding: utf-8 -*-
"""
MCP File diff, review, approval, and rejection tools.
"""

import sys
import json
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Any

from mcp.app import app, log, PROJECT_ROOT, state_manager
from core.pattern_journal import PatternJournal
from core.state_editor import rollback_last as _rollback_last
from common.file_ops import acquire_write_lock

@app.tool(
    name="rollback_last",
    description="Reverts the LAST surgical edit made in the current session.",
)
def rollback_last() -> str:
    """
    Reverts the LAST surgical edit made in the current session.
    
    What it does: Undoes the most recent single edit recorded in the session journal.
    When to use: Immediately after an edit made with set_token or add_token that had unintended results.
    When NOT to use: Do not use for pattern-wide rollbacks (use rollback_pattern) or specific file reverts (use reject_file_changes).
    Side effects: Destructive rollback. Modifies the target file back to its previous content byte-for-byte.
    Parameters: None.
    Returns:
      JSON string {"rolled_back": true/false}. Returns error if no previous edit exists in session. Only ONE edit is reverted.
    """
    log("🔧 rollback_last")
    try:
        ok = _rollback_last()
        return json.dumps({"rolled_back": ok})
    except Exception as e:
        log(f"❌ rollback_last error: {e}")
        log(traceback.format_exc())
        return json.dumps({"error": str(e)})


@app.tool()
def list_modified_files() -> str:
    """
    Read-only. Lists files modified by recent replace_pattern operations in the current session.
    
    What it does: Queries the session journal to return all files currently in a modified state.
    When to use: To see what files have unapproved changes before approving or rejecting.
    When NOT to use: Does NOT persist across sessions. For git-based modifications use get_file_diff. Returns files in journal (not git status).
    Side effects: Read-only. No files modified.
    Parameters: None.
    Returns:
      JSON string with list of relative file paths.
    """
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
    """
    Destructive: Reverts pending changes for a SINGLE file using .bridge.bak backup.
    
    What it does: Rolls back byte-for-byte to the state before the recent surgical edit or replace_pattern.
    When to use: When modifications to a specific file are incorrect and need to be discarded.
    When NOT to use: File must be currently modified. Use reject_all_files for all files.
    Side effects: Destructive rollback. Overwrites file with original backup and removes entry from journal.
    Parameters:
      - file_path: relative path to project root (e.g., 'QuickActionsWidget.kt' or 'ui/theme/AppStrings.kt').
    Returns:
      JSON string confirming rollback of the file.
    """
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
    """
    Approves pending changes for a SPECIFIC file. Removes its entry from journal.
    
    What it does: Marks changes as accepted and discards the backup so the file is no longer in pending state.
    When to use: When changes to a specific file have been inspected (via get_file_diff) and verified correct.
    When NOT to use: File must be modified. To approve all files use approve_all_files.
    Side effects: Clears the journal entry and backup for this file. Modifications remain permanently on disk.
    Parameters:
      - file_path: relative to project root (e.g., 'QuickActionsWidget.kt' or 'ui/theme/AppStrings.kt').
    Returns:
      JSON string confirming file approval.
    """
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
    """
    Destructive: Approves ALL pending changes permanently. Removes them from journal.
    
    What it does: Permanently accepts all pending changes in the journal across all modified files.
    When to use: When all modifications from recent operations are verified and accepted.
    When NOT to use: No rollback after this action. Use approve_file_changes for single files. Use reject_all_files to discard instead.
    Side effects: Destructive: Permanently clears all backups and journal entries. Changes cannot be rolled back.
    Parameters: None.
    Returns:
      JSON string confirming all files approved.
    """
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
    """
    Destructive: Reverts ALL pending changes using byte-level backup (.bridge.bak).
    
    What it does: Rolls back byte-for-byte all files modified in the current journal session.
    When to use: To completely discard all recent changes and return every file to its exact prior state.
    When NOT to use: Use reject_file_changes for a single file. Use reject_all_files_force if some rollbacks may fail.
    Side effects: Destructive rollback. Overwrites all modified files with their .bridge.bak backups and clears journal.
    Parameters: None.
    Returns:
      JSON string with list of reverted files and status.
    """
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
    """
    Destructive + Forceful. Clears the entire journal EVEN IF some rollbacks fail.
    
    What it does: Forcefully attempts rollback and clears the journal unconditionally.
    When to use: Use only when reject_all_files fails due to missing backups or file corruption.
    When NOT to use: May leave files in inconsistent state. For safe rollback use reject_all_files.
    Side effects: Destructive + Forceful: Clears all journal tracking regardless of whether every file reverted cleanly.
    Parameters: None.
    Returns:
      JSON string with forced rollback results.
    """
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
    """
    Read-only. Returns before/after content and unified diff for a specific modified file.
    
    What it does: Computes unified diff comparing original backup (.bridge.bak) with current on-disk content.
    When to use: To inspect exact changes before approving (approve_file_changes) or rejecting (reject_file_changes).
    When NOT to use: Use list_modified_files first to get valid paths. file_path should match the entry from list_modified_files (relative to project root).
    Side effects: Read-only. No files modified.
    Parameters:
      - file_path: relative path to project root (e.g., 'QuickActionsWidget.kt' or 'ui/theme/AppStrings.kt').
    Returns:
      JSON string with original content, modified content, and unified diff.
    """
    from core.pattern_journal import PatternJournal
    try:
        journal = PatternJournal(PROJECT_ROOT)
        result = journal.get_file_diff(file_path)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

