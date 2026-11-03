# Changelog

All notable changes to ComposeBridge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.7] - 2026-11-03
### Fixed
- **Text Reference Path Resolution (P0):** Correctly prioritizes `AppStrings.kt` (and centralized string files) when editing reference strings (`AppStrings.*`), preventing "Declaration not found" failures when triggered from UI composable call-site files (such as `DashboardScreen.kt`).
- **M8ven.ai Protocol Optimizations & Complete Tool Annotations:**
  - Added strict Model Context Protocol hints (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) across all 34 MCP tools.
  - Enhanced docstrings for AI coding agents with explicit `When to use`, `When NOT to use`, and `Side effects` guidance.
  - Added dedicated test suite `test_mcp_tools_coverage.py` ensuring 100% execution and annotation test coverage.

## [1.1.6] - 2026-11-01
### Added
- **Full Architecture Modularization (Agent & IDE):**
  - Android Agent: Decomposed legacy monolithic files into specialized packages:
    - `ui.panels`: `ColorEditPanel.kt`, `DimensionEditPanel.kt`, `TextEditPanel.kt`, `AgentStatusBar.kt`, `ExternalWarningDialog.kt`.
    - `transport`: `WebSocketClient.kt`, `ApkChunkReceiver.kt`, `AgentMessageDispatcher.kt`.
    - `state`: `ConnectionState.kt`, `ApkDeliveryState.kt`, `ElementSelectionState.kt`, `PendingEditsQueue.kt`.
    - `services`: `ApkBuilder.kt`.
    - `util`: `ColorUtils.kt`, `PreferenceHelper.kt`.
  - IDE Plugin: Decomposed `ComposeBridgeToolWindowFactory.kt` into modular tab views under `plugin/toolwindow/tabs/` (`ChangesTab`, `TokensTab`, `OrphansTab`, `PatternsTab`, `StatusTab`) and dedicated background services.
- **Dynamic Host App Integration:** `RemoteConnectionDialog` now reflects the host application's package name (`context.packageName`) dynamically to discover `QrScannerActivity`, eliminating hardcoded target application coupling.
- **Dedicated Test Suites:** Added automated tests for color token re-edits (`test_color_token_reedit.py`), rate limiter enforcement (`test_rate_limiter_auth.py`), and cascade file rejections.

### Changed
- **Comprehensive UI Localization (English):** All 68 user-facing Arabic UI strings in the Android Agent (dialogs, toasts, OTA build screens, snackbars) were translated into English for international production use.
- **Codebase De-bloat & God File Shrinkage:**
  - `GlobalPanels.kt`: Reduced from 2,127 lines to 277 lines (-86%).
  - `BridgeTransport.kt`: Reduced from 1,326 lines to 99 lines (-92%).
  - `BridgeState.kt`: Reduced from 665 lines to 421 lines (-36%).
  - `message_router.py`: Reduced from 1,460 lines into distinct network and dispatch handlers.
- **Generic Project Discovery:** Cleared hardcoded absolute developer paths from `.composebridge/config.json`. The Python server now resolves target repositories strictly via `--project` CLI flag or `COMPOSEBRIDGE_ROOT` environment variable.
- **Unified Color Parsing:** Centralized hex color conversions across all agent overlays into `ColorUtils.parseHexColor()`.

### Fixed
- **Color Token Re-edit Bug (P0):** Fixed critical logic in `server/analysis/color_analyzer.py` where re-editing an existing color token whose current value was in hex format (`0x` or `#`) was mistakenly bypassed as a literal, causing subsequent modifications to drop silently.
- **IDE Notification Copy:** Fixed residual Arabic text inside broken file notification popups within the IntelliJ/Android Studio plugin.
- **CRLF Stream Consistency:** Resolved line-ending normalization discrepancies between Android-side WebSocket payloads and Python file watchers.

### Removed
- Removed hardcoded developer environment paths and application-specific references across documentation and core packages.

## [1.1.3] - 2026-10-26
### Critical Fixes & Hardening (P0)
- **Pre-Backup Syntax Validation:** Integrated Tree-sitter Kotlin AST syntax validation (alidate_kotlin_syntax) across all editors (color_editor, dimension_editor, 	oken_migrator, 	ext_editor, state_editor_core, st_finder). Prevents taking backups from broken files and rejects edits on files containing syntax errors until resolved.
- **Pristine Backup Preservation:** Strictly enforces single fixed .bridge.bak creation only on first valid edit (if not backup.exists()), preventing intermediate or corrupt code from polluting backups.
- **Git-First Rollback Priority:** Updated PatternJournal.reject_file_changes to query Git tracking first (git ls-files) and execute git checkout -- <file> as the primary rock-solid recovery mechanism, falling back to validated .bridge.bak when untracked.

## [1.1.2] - 2026-10-22
### Architectural Refactoring (5 Phases)
- **Modular Monolith Decomposition:** Decomposed 4 monolithic monster files (over 6,000 lines) into 25+ clean, single-responsibility modules:
  - `source_analyzer.py` (2,116 lines → 72 lines Facade) → split into `analysis/`
  - `state_editor.py` (1,146 lines → 86 lines Facade) → split into `editor/`
  - `mcp_server.py` (1,209 lines → 59 lines Facade) → split into `mcp/`
  - `server.py` (1,493 lines → 67 lines Facade) → split into `network/`, `handlers/`, `cli/`
  - Extracted shared utilities into `common/file_ops.py` and `common/color_constants.py`.
- **Zero Circular Dependencies:** Eliminated all cyclic imports across network, handler, and core modules.
- **100% Backward Compatibility:** All existing entry points and external imports preserved using the Facade Pattern.

### Critical Fixes (P0)
- **Live Text Editing Restored:** Fixed broken relative imports in `editor/text_editor.py` (`ModuleNotFoundError`) that prevented live text changes from applying.
- **Multi-Registry Dimension Splicing:** Fixed regex parsing when multiple `BridgeDimensionRegistry.get(...)` calls exist in a single line (e.g., symmetric padding).
- **AppStrings Resolution:** Fixed value extraction for Kotlin properties with conditional getter expressions (`if/else`).
- **Release Build Decoupling:** Verified standalone `composebridge-runtime-release.aar` (~9KB) avoiding duplicate classes with agent.
- **Privacy & Hygiene Cleanup:** Removed all hardcoded absolute developer paths and package references from all tracked files.
- **MCP Tool Registration:** Restored `@app.tool()` decorators across all 27 MCP tools so `app.list_tools()` discovers full toolset.

### Documentation & Community
- Added `CONTRIBUTING.md`, `SECURITY.md`, and GitHub Issue templates.
- Overhauled `README.md` with technical architecture diagram, 60-second quickstart, limitations, and troubleshooting.

## [1.1.1] - 2026-10-21
### Added
- **Dedicated `composebridge-runtime` Artifact:** Created ultra-lightweight (~9KB) runtime module (`composebridge-runtime-release.aar`) containing `BridgeTextRegistry`, `BridgeThemeRegistry`, and `BridgeDimensionRegistry`. Apps now include `implementation(composebridge-runtime)` so `assembleRelease` builds compile cleanly without bundling debug UI tools.
- **Dynamic Auth Token Generation:** Generates a secure random auth token stored in `.composebridge-state/auth.json` on first run instead of static keys.
- **Comprehensive 5/5 TDQS MCP Documentation:** Upgraded all MCP tool docstrings in `mcp_server.py` with explicit descriptions, when-to-use, when-not-to-use, parameters, and side-effects.

### Fixed
- **NameError in `apply_state_update`:** Removed stray `return (False, f"Write failed: {e}", None)` statement that erroneously reported failure on successful writes.
- **Dynamic Registry Resolution:** Replaced hardcoded package lookup in `update_token_default` with dynamic `_find_registry_file`.
- **Atomic File Writing with CRLF Preservation:** Integrated `_atomic_write_text` preserving `newline=''` for on-the-fly text migration and import injections.

## [1.1.0] - 2026-10-21
### Added
- Text Editing mode with Live Preview (`BridgeTextRegistry`).
- On-the-Fly Auto-Migration for text (wrap any text in `BridgeTextRegistry` automatically).
- MCP Server integration for AI agents.
- `docs/architecture/RFC-001-vision.md` (architectural roadmap).
### Fixed
- Navigation backstack preservation.
- CRLF/LF line ending compatibility across operating systems.
- Text reference extraction for single-pattern strings (`val unit @Composable get() = "..."`).
### Changed
- UI titles translated to English.

## [1.0.0] - 2026-10-18
### Added
- Initial official release of ComposeBridge.
- Real-time on-device UI inspection for Jetpack Compose.
- Live Color and Dimension editing.
- Bi-directional sync between Android Studio and connected device.
- AST-based code updates and Design Token migration.
