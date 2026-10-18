# ComposeBridge MCP Tools Reference 🛠️

Complete reference for all MCP (Model Context Protocol) tools provided by the ComposeBridge server. These tools allow AI agents (such as Claude, Codex, Gemini, Antigravity) to safely inspect, refactor, and tune Jetpack Compose UI code with AST awareness.

> **KMP / Desktop Status Note:**
> KMP/Desktop support is currently in **Beta**. Focus for v1.0.0 is on **Android stability**.

---

## 🔒 Security & Destructive Operations Overview

- **Read-Only / Safe Tools:** Only inspect AST, source files, or state. Cannot break project code.
- **Destructive / Write Tools:** Modify source files or apply AST changes. Always protected by write locks and atomic backups in `.composebridge/backups/`.
- **Dry-Run Mode:** Destructive tools such as `replace_pattern` support `dry_run=True` to simulate and preview diffs before applying changes.
- **Gradle Allowlist:** `run_gradle_build` enforces a strict task allowlist to prevent arbitrary execution or command injection.

---

## 📋 Comprehensive Tools Table

| Tool Name | Type | Destructive? | Description | Parameters | Returns | Security / Caution Note |
|---|---|:---:|---|---|---|---|
| `list_tokens` | Discovery | No | Lists all defined design tokens (colors and dimensions) and hardcoded literals. | `project_path` (optional string) | JSON list of tokens with name, value, file, line | Read-only. Safe to call anytime. |
| `get_token_impact` | Discovery | No | Finds all Composable files and line numbers where a specific token is used. | `token_name` (string, required), `project_path` (optional) | JSON with usage count and list of occurrences | Read-only. Essential before modifying shared tokens. |
| `get_naming_convention` | Discovery | No | Analyzes the project tokens to detect naming patterns (e.g. `sm`/`md`/`lg`). | `token_type` ("dimension" or "color") | JSON with detected naming style and examples | Read-only. Helps agent adhere to existing conventions. |
| `get_token_siblings` | Discovery | No | Returns related tokens in the same scale or family (e.g. `padding_sm` for `padding_md`). | `token_name` (string, required) | JSON list of sibling tokens | Read-only. Useful for choosing proportional values. |
| `get_all_token_groups` | Discovery | No | Groups all project tokens into semantic families (spacing, typography, surface, etc.). | None | JSON with grouped token hierarchy | Read-only. |
| `list_orphans` | Analysis | No | Detects tokens defined in theme files but never used in any Composable. | `project_path` (optional string) | JSON list of unused tokens | Read-only. Identifies dead design tokens. |
| `suggest_token_split` | Analysis | No | Analyzes if a single token is used in conflicting semantic contexts (e.g. padding and icon size). | `token_name` (optional), `project_path` (optional) | JSON with split suggestions and context breakdown | Read-only. Recommended before making global edits. |
| `detect_conditional_variants` | Analysis | No | Detects ternary or conditional patterns (e.g. `if (isDark) ColorA else ColorB`). | `token_name` (optional string) | JSON list of detected patterns with unique IDs | Read-only. Prepares input for `replace_pattern`. |
| `add_token` | Mutation | **Yes** | Converts a hardcoded literal value into a new design token in the theme and updates the call site. | `file` (string), `line` (int), `value` (string), `token_name` (string), `token_type` ("dimension"\|"color"), `preferred_token_file` (optional), `force_create` (bool) | JSON with success status, old line, and new line | **Destructive.** Modifies theme and call site. Preserves formatting. |
| `set_token` | Mutation | **Yes** | Updates the value of an existing design token definition in its source file. | `token_name` (string), `value` (string) | JSON with old value, new value, and file path | **Destructive.** Affects all Composables referencing this token. |
| `replace_pattern` | Mutation / Refactor | **Yes** (unless dry_run) | Extracts a conditional pattern into a design token and replaces occurrences across the codebase. | `pattern_id` (string), `dry_run` (bool, default `false`) | JSON with created token, replacement count, and diffs | **Destructive when dry_run=False.** Always test with `dry_run=True` first. |
| `list_applied_patterns` | Review | No | Lists all patterns that have been applied and are currently recorded in the journal. | None | JSON list of applied pattern IDs and timestamps | Read-only. |
| `rollback_pattern` | Rollback | **Yes** | Reverts all file changes and tokens created by a specific `replace_pattern` execution. | `pattern_id` (string, required) | JSON with reverted files and restore status | **Destructive.** Restores files to pre-pattern state. |
| `list_modified_files` | Review | No | Lists all files currently modified by MCP mutations that have uncommitted changes. | None | JSON list of modified file paths | Read-only. Equivalent to `git status` for Bridge edits. |
| `get_file_diff` | Review | No | Generates a unified git-style diff for a modified file showing changes made by Bridge. | `file_path` (string, required) | JSON with original content, current content, and unified diff | Read-only. Essential for reviewing before approval. |
| `approve_file_changes` | Review | No | Accepts the modifications for a specific file and removes it from the rollback journal. | `file_path` (string, required) | JSON confirmation | Keeps file changes permanently in the project. |
| `approve_all_files` | Review | No | Accepts all pending modifications across all files. | None | JSON confirmation with approved count | Clears journal; changes are kept permanently. |
| `reject_file_changes` | Rollback | **Yes** | Reverts a specific file to its exact state before Bridge edits. | `file_path` (string, required) | JSON confirmation | **Destructive.** Reverts file byte-for-byte. |
| `reject_all_files` | Rollback | **Yes** | Reverts all modified files to their original pre-edit state. | None | JSON confirmation with reverted files | **Destructive.** Safe full undo for all edits. |
| `reject_all_files_force` | Rollback | **Yes** | Forcefully clears journal and restores files even if conflicts exist. | None | JSON confirmation | **Destructive.** Use when standard revert encounters conflicts. |
| `run_gradle_build` | Build / Verify | No (Build) | Executes an allowlisted Gradle task and returns structured errors, warnings, and exit code. | `task` (string, default "assembleDebug"), `timeout_seconds` (int, default 300) | JSON with `{success, exit_code, errors, warnings, duration_ms}` | **Security Enforced.** Only allowed tasks (`assembleDebug`, `assembleRelease`, `test`, `lint`, `clean`) can run. |
| `list_allowed_gradle_tasks` | Security | No | Returns the strict allowlist of Gradle tasks permitted to run via `run_gradle_build`. | None | JSON list of allowed task names | Read-only. |
| `trigger_user_sync` | Sync | **Yes** | Flushes all pending phone overlay tweaks (colors & dimensions) into physical source files. | None | JSON with applied count and errors | Applies phone session tweaks to local code. |
| `get_sync_status` | Sync | No | Checks the status of the edit queue and whether the server is waiting for sync. | None | JSON with queue length and pending edit details | Read-only. |

---

## 🔍 Detailed Usage of Critical Tools

### 1. `run_gradle_build`
Verifies that Kotlin code compiles cleanly after mutations.
- **Allowed Tasks:** `assembleDebug`, `assembleRelease`, `test`, `lint`, `clean` (or subproject equivalents e.g. `:composeApp:assembleDebug`).
- **Security:** Arbitrary shell execution, flags, and unauthorized tasks are strictly rejected.

```json
// Example response
{
  "success": true,
  "task": "assembleDebug",
  "exit_code": 0,
  "duration_ms": 4210,
  "timed_out": false,
  "errors_count": 0,
  "warnings_count": 0,
  "errors": [],
  "warnings": [],
  "output_tail": "BUILD SUCCESSFUL in 4s"
}
```

### 2. `replace_pattern`
Refactors duplicated conditional styling into design tokens.
- **Recommended Workflow:** Always call with `dry_run=true` first to inspect `planned_replacements`. If satisfied, invoke with `dry_run=false`.

```json
// Example dry-run response
{
  "success": true,
  "dry_run": true,
  "pattern_id": "pattern_card_bg_001",
  "token_name": "CardBackgroundAdaptive",
  "token_value": "if (isDark) Color(0xFF1E293B) else Color.White",
  "replacements_count": 3,
  "planned_replacements": [
    {
      "file": "DashboardCard.kt",
      "line": 42,
      "action": "create_and_replace",
      "new_usage": "AppColors.CardBackgroundAdaptive"
    }
  ]
}
```

### 3. Review & Rollback Flow (`get_file_diff` -> `approve_all_files` / `reject_all_files`)
Provides full git-like safety for automated agents:
1. `list_modified_files()` to see what changed.
2. `get_file_diff(file_path)` to inspect line-by-line diffs.
3. If valid: `approve_all_files()` to keep.
4. If invalid: `reject_all_files()` to instantly rollback all files byte-for-byte.