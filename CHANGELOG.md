# Changelog

All notable changes to ComposeBridge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
