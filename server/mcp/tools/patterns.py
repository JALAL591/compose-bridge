# -*- coding: utf-8 -*-
"""
MCP Pattern replacement, tracking, and rollback tools.
"""

import sys
import json
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Any

from mcp.app import app, log, PROJECT_ROOT, state_manager
from core.pattern_journal import PatternJournal
from core.token_migrator import TokenMigrator
from core.pattern_detector import PatternDetector
from core.ast_finder import surgical_edit
from common.file_ops import acquire_write_lock

@app.tool()
def replace_pattern(pattern_id: str, dry_run: bool = False) -> str:
    """
    DESTRUCTIVE BATCH OPERATION: Replaces ALL occurrences of a pattern across the project.
    
    What it does: Creates new token + replaces usages. Can be rolled back via rollback_pattern(pattern_id).
    When to use: When replacing a recurring conditional or hardcoded pattern across all files.
    When NOT to use: USE dry_run=True FIRST to preview affected files. pattern_id must come from detect_conditional_variants.
    Side effects: DESTRUCTIVE: Modifies multiple .kt files simultaneously. Records changes in journal.
    Parameters:
      - pattern_id: Unique pattern identifier from detect_conditional_variants.
      - dry_run: If True (recommended first), previews changes without writing to disk.
    Returns:
      JSON string with replacements made, modified files, and created token name.
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

            from core.ast_finder import surgical_edit

            replacements = [{"file": pattern.occurrences[0].file, "line": pattern.occurrences[0].line}]
            for occ in pattern.occurrences[1:]:
                fp = None
                for f in detector._find_kt_files():
                    if f.name == occ.file:
                        fp = f
                        break
                if not fp:
                    continue

                source_bytes = fp.read_bytes()
                source_text = source_bytes.decode("utf-8", errors="replace")
                lines_with_ends = source_text.splitlines(keepends=True)

                target_line_idx = -1
                if occ.line <= len(lines_with_ends) and occ.value_if_dark in lines_with_ends[occ.line - 1]:
                    target_line_idx = occ.line - 1
                else:
                    for idx, line_str in enumerate(lines_with_ends):
                        if occ.value_if_dark in line_str and f"AppColors.{pattern.suggested_token_name}" not in line_str:
                            target_line_idx = idx
                            break

                if target_line_idx == -1:
                    # Occurrence target not found - rollback everything
                    journal.rollback_pattern(pattern.pattern_id)
                    return json.dumps({
                        "success": False,
                        "error": f"Failed to locate target pattern value '{occ.value_if_dark}' in {occ.file}. Rolled back all changes.",
                        "pattern_id": pattern.pattern_id,
                    })

                old_line = lines_with_ends[target_line_idx]
                col_in_line = old_line.find(occ.value_if_dark)
                if col_in_line == -1:
                    journal.rollback_pattern(pattern.pattern_id)
                    return json.dumps({
                        "success": False,
                        "error": f"Value '{occ.value_if_dark}' not found in target line in {occ.file}. Rolled back all changes.",
                        "pattern_id": pattern.pattern_id,
                    })

                # Calculate precise byte offsets preserving exact CRLF (\r\n) or LF (\n) line endings
                line_byte_start = len("".join(lines_with_ends[:target_line_idx]).encode("utf-8"))
                byte_start = line_byte_start + len(old_line[:col_in_line].encode("utf-8"))
                byte_end = byte_start + len(occ.value_if_dark.encode("utf-8"))

                # Validate byte boundaries
                if not (0 <= byte_start < byte_end <= len(source_bytes)):
                    journal.rollback_pattern(pattern.pattern_id)
                    return json.dumps({
                        "success": False,
                        "error": f"Invalid byte range [{byte_start}:{byte_end}] in {occ.file}. Rolled back all changes.",
                        "pattern_id": pattern.pattern_id,
                    })

                actual_bytes_val = source_bytes[byte_start:byte_end].decode("utf-8", errors="replace")
                if actual_bytes_val != occ.value_if_dark:
                    journal.rollback_pattern(pattern.pattern_id)
                    return json.dumps({
                        "success": False,
                        "error": f"Byte mismatch at {byte_start}..{byte_end} in {occ.file}: expected '{occ.value_if_dark}', found '{actual_bytes_val}'. Rolled back all changes.",
                        "pattern_id": pattern.pattern_id,
                    })

                # Apply atomic surgical edit
                new_usage = f"AppColors.{pattern.suggested_token_name}"
                s_ok, s_msg, s_backup = surgical_edit(
                    file_path=str(fp),
                    byte_start=byte_start,
                    byte_end=byte_end,
                    expected_old_value=occ.value_if_dark,
                    new_value=new_usage,
                )

                if not s_ok:
                    journal.rollback_pattern(pattern.pattern_id)
                    return json.dumps({
                        "success": False,
                        "error": f"Surgical edit failed on {occ.file}: {s_msg}. Rolled back all changes.",
                        "pattern_id": pattern.pattern_id,
                    })

                new_line = old_line[:col_in_line] + new_usage + old_line[col_in_line + len(occ.value_if_dark):]
                replacements.append({"file": occ.file, "line": target_line_idx + 1})
                journal.record(
                    pattern_id=pattern.pattern_id,
                    file=occ.file,
                    line=target_line_idx + 1,
                    old_content=old_line,
                    new_content=new_line,
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
    Rolls back ALL changes made by a specific replace_pattern call.
    
    What it does: Requires pattern_id from the original replace_pattern response. All files are reverted byte-for-byte.
    When to use: When a replace_pattern operation caused regressions and needs complete reversal.
    When NOT to use: Cannot undo if files were modified externally. Use rollback_last for single-edit undo.
    Side effects: Destructive rollback. Modifies all files touched by the pattern back to their prior state.
    Parameters:
      - pattern_id: The exact pattern_id from the original replace_pattern response.
    Returns:
      JSON string with list of reverted files and status.
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

