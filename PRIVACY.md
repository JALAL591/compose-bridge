# Privacy Policy for ComposeBridge

**Last Updated:** November 3, 2026

## Overview
ComposeBridge is an open-source development bridge and Model Context Protocol (MCP) tool suite connecting Jetpack Compose Android development environments with AI coding assistants.

Your privacy is paramount. ComposeBridge is designed with a **privacy-first, local-only architecture**.

## Data Collection
- **Zero Personal Data:** ComposeBridge does not collect, log, track, or share any personal identifying information (PII).
- **No Analytics / Telemetry:** There are no analytics trackers, diagnostic telemetry beacons, or advertising frameworks embedded in any part of ComposeBridge (agent, plugin, or server).

## Network and Communication Scope
- **Strictly Localhost:** All network transport (WebSocket and HTTP communication) between the Android Studio plugin, the Android runtime agent, and the local MCP server occurs exclusively over local loopback interfaces (`127.0.0.1` / `localhost`).
- **No Outbound Data Flow:** Code files, design tokens, syntax highlights, and AST inspection artifacts never leave your local machine and are never transmitted to external cloud servers or third parties.

## Local Filesystem Access
- ComposeBridge operates solely on files within the explicitly designated project workspace repository.
- Temporary diffs, pattern journals, and diagnostic states are stored locally within the project's `.composebridge-state/` folder.
- No access is performed on system files or directories outside the designated project boundaries.

## Third-Party AI Services
When you invoke ComposeBridge via an MCP client (such as Claude Desktop or OpenAI tools), your interaction with the underlying LLM provider is governed by that provider's respective privacy policy. ComposeBridge itself does not store or proxy your LLM conversations.

## Open Source & Auditability
ComposeBridge is open source under the Apache-2.0 License. You can inspect all source code directly in the repository to verify our privacy and security guarantees.

## Contact
For security disclosures or privacy inquiries, please open an issue on the official GitHub repository:
https://github.com/JALAL591/compose-bridge

