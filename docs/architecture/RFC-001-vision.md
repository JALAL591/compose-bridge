# RFC-001: ComposeBridge Vision & Architecture

> **Status:** Accepted  
> **Author:** Jalal (@JALAL591)  
> **Date:** 2026-10-21  
> **Target Release:** v1.1.0 (current), v2.0.0 (vision)  
> **License:** MIT

---

## 1. The Problem

Jetpack Compose developers face four unsolved challenges:

1. **Visual Blindness of AI Agents.** Tools like Cursor, Claude Code, and Antigravity write Compose code but cannot see the runtime screen. They iterate blind, often producing incorrect UI that compiles but looks wrong.

2. **Laptop Dependency.** Editing a single color or text string requires opening Android Studio on a laptop. This breaks flow and prevents "on-the-go" iteration.

3. **Slow Feedback Loop.** The cycle of "Design → Code → Build → Install → Test → Review" can take hours for a single-line change.

4. **Isolated Collaboration.** Designers, QA engineers, and clients cannot interact with the live app. They wait for the developer to make changes and share new builds manually.

---

## 2. The Vision

> **"Build Jetpack Compose apps from your phone. Anywhere. Anytime. With your AI agent."**

ComposeBridge is not just a visual editor. It is a **Mobile-Native Development Studio** that:

- Lets developers edit UI (colors, dimensions, text) directly on the phone.
- Uses the developer's **existing AI agent** (Cursor, Claude, Antigravity) via MCP to fix build errors automatically.
- Builds APK files and shares them via QR codes.
- Works locally (LAN) or remotely (via Tailscale Funnel), with zero cloud dependency.

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│               📱 Phone (Control Center)                      │
│  ┌─────────┬───────────┬──────────┬──────────┬──────────┐    │
│  │ Colors  │ Dimensions│   Text   │ Changes  │  Build   │    │
│  └─────────┴───────────┴──────────┴──────────┴──────────┘    │
│                                                              │
│         │ WebSocket (Local 127.0.0.1 or Tailscale Funnel)    │
│         ▼                                                    │
├──────────────────────────────────────────────────────────────┤
│         💻 Local Server (Python + MCP)                       │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  • Surgical AST Editing (byte-level precision)         │  │
│  │  • Pending Edits Queue (batch atomic commits)          │  │
│  │  • Gradle Build Pipeline                               │  │
│  │  • MCP Server (17+ tools for AI agents)                │  │
│  │  • File-based Agent Bridge (.composebridge/*.json)     │  │
│  └────────────────────────────────────────────────────────┘  │
│         │                                                    │
│         ▼                                                    │
├──────────────────────────────────────────────────────────────┤
│         🤖 Developer's Existing AI Agent                     │
│      (Cursor / Claude Desktop / Antigravity - via MCP)       │
└──────────────────────────────────────────────────────────────┘
```

### 3.1 The Three Layers

**Layer 1: The Phone (Runtime)**
- The `ComposeBridgeAgent` AAR is embedded in the developer's app.
- It captures touch events, extracts element properties (colors, dimensions, text), and communicates via WebSocket.
- It provides `BridgeThemeRegistry`, `BridgeDimensionRegistry`, and `BridgeTextRegistry` for live preview without rebuild.

**Layer 2: The Local Server (Python)**
- Handles all logic and file system access.
- Performs surgical byte-level AST edits to `.kt` files.
- Manages the pending edits queue and rollback journal.
- Exposes an MCP server (17+ tools) for AI agent integration.
- Runs Gradle builds in the background and serves APKs.

**Layer 3: The AI Agent (Developer's Choice)**
- Any MCP-compatible agent: Cursor, Claude Desktop, Antigravity, etc.
- Reads `.composebridge/build_error.json` when a build fails.
- Analyzes errors, applies fixes, writes reports to `.composebridge/build_report.json`.
- The server reads the report and forwards it to the phone.

---

## 4. Roadmap

| Version | Features | Status |
|:--------|:---------|:------:|
| **v1.0.0** | Colors, Dimensions, MCP Server, IDE Plugin | ✅ Released |
| **v1.1.0** | Text Editing, Live Preview, Auto-Migration, RFC-001 | ✅ Current |
| **v1.2.0** | Changes Screen (Approve/Reject on phone), Build APK from phone, Chat Bridge with AI Agent | 🚧 Planned |
| **v1.3.0** | History & Reports, Remote Access via Tailscale Funnel | 📅 Planned |
| **v2.0.0** | Full Mobile-Native Development Studio | 🎯 Vision |

---

## 5. Security & Privacy

- **Local-only by default.** No cloud required.
- **Remote via Tailscale Funnel** (optional, encrypted with WireGuard).
- **JWT authentication** for all remote sessions.
- **Rate limiting** (60 requests/min per IP).
- **Zero telemetry.** No code, text, or images leave the developer's machine.
- **Byte-level rollback** (`.bridge.bak`) for every edit — 100% safe.

---

## 6. Contributing

We welcome contributions. Please read [CONTRIBUTING.md](../../CONTRIBUTING.md) before opening a PR.

---

## 7. Reference Implementations

- [Jetpack Compose](https://developer.android.com/jetpack/compose) — The framework.
- [Model Context Protocol](https://modelcontextprotocol.io/) — For AI agent integration.
- [Tailscale Funnel](https://tailscale.com/kb/1223/funnel/) — For remote access.

---

*This is a living document. Last updated: 2026-10-21.*
