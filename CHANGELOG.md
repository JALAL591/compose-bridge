# Changelog

All notable changes to ComposeBridge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
