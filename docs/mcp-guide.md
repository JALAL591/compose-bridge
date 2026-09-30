# MCP Server Guide

## What is MCP?

The Model Context Protocol (MCP) is an open standard that lets AI agents
(Claude, Gemini, GPT-based tools) call external tools safely.

ComposeBridge implements an MCP Server that exposes Compose-aware editing
tools to any MCP-compatible AI client.

## Why it matters

**Before MCP:**
- AI could only suggest code changes
- Copy-paste was required
- No rollback, no surgical precision

**With ComposeBridge MCP:**
- AI edits files directly
- Single-line git diffs
- Persistent rollback
- No phone needed

## Standalone operation

Starting from v0.4.0, the MCP Server does not require:
- ❌ Android phone
- ❌ adb reverse
- ❌ WebSocket bridge
- ❌ Running app

It only needs:
- ✅ Python 3.10+
- ✅ An MCP-compatible AI client
- ✅ A Compose project on disk

## Architecture

```text
┌──────────────────┐
│  Antigravity     │
│  (AI Client)     │
└────────┬─────────┘
         │ MCP (stdio)
         ↓
┌──────────────────┐
│  mcp_server.py   │
│  • find_token    │
│  • set_token     │
│  • rollback      │
└────────┬─────────┘
         │ direct file I/O
         ↓
┌──────────────────┐
│  Your .kt files  │
└──────────────────┘
```

No phone. No WebSocket. Just files.

## Tools Reference

### `find_token_by_color(hex_color: str)`

Searches `AppColors.kt` for a token matching the given hex color.

- **Input:** `"#1E3A8A"`
- **Output:** `{"token": "Primary"}` or `{"token": null}`

### `set_token(token_name: str, value: str)`

Surgically edits `AppDimens.kt` or `AppColors.kt`.

- **Input:** `("welcomeCardHeight", "300")`
- **Output:** `{"success": true, "file": "AppDimens.kt"}`

**Safety features:**
- Backs up original (`*.bridge.bak`)
- Validates AST after edit
- Auto-rollback if parse fails

### `rollback_last()`

Undoes the most recent edit.

- **Output:** `{"rolled_back": true}`
- **Persistence:** Journal is written to disk, so rollback survives process restarts.

## Security Notes

- All edits are local (no network)
- Journal is git-ignored by default
- Backups preserved as `.bridge.bak`
- No telemetry, no external calls

## Limitations

- Only edits simple literals (`240.dp`, `#EF4444`)
- Complex expressions (`Dp(240f).coerceAtLeast(...)`) are skipped
- Inline composables may not map correctly

See main README for roadmap.
