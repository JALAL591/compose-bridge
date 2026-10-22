# ComposeBridge 🌉

> 📖 **Where is ComposeBridge heading?** Read our [Vision & Architecture RFC](docs/architecture/RFC-001-vision.md).

**Real-time on-device visual editor for Jetpack Compose + MCP Server for AI agents. Live UI tuning, AST-guided surgical source splicing, and standalone AI-driven code edits.**

[![Kotlin](https://img.shields.io/badge/Kotlin-2.1.20+-purple.svg)](https://kotlinlang.org)
[![Jetpack Compose](https://img.shields.io/badge/Jetpack%20Compose-1.7.3+-4285F4.svg)](https://developer.android.com/jetpack/compose)
[![Zero Rebuild](https://img.shields.io/badge/DevEx-Zero--Rebuild%20Preview-brightgreen.svg)]()
[![Latency](https://img.shields.io/badge/Latency-%3C50ms-success.svg)]()
[![Status](https://img.shields.io/badge/Status-Production%20Ready%20(v1.1.2)-success.svg)]()
[![Scanner Speed](https://img.shields.io/badge/Scanner%20Speed-137ms%20%2F%20146%20files-brightgreen.svg)]()
[![Version](https://img.shields.io/badge/Version-1.1.2-blue.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/JALAL591/compose-bridge/blob/main/LICENSE)
[![M8ven Score](https://m8ven.ai/badge/mcp/jalal591-compose-bridge-rapm1x)](https://m8ven.ai/mcp/jalal591-compose-bridge-rapm1x?s=readme)
[![Reviewed by HOL Guard](https://img.shields.io/badge/HOL_Guard%20|%20compose_bridge-2E5AAC?logo=shield&logoColor=white)](https://hol.org/guard/extensions/mcp.compose-bridge)
[![compose-bridge MCP server – quality and maintenance score on Glama](https://glama.ai/mcp/servers/JALAL591/compose-bridge/badges/score.svg)](https://glama.ai/mcp/servers/JALAL591/compose-bridge)

## 📰 Featured In

<p align="left">
  <a href="https://androidweekly.net/issues/issue-746" title="Android Weekly Issue #746">
    <img alt="Android Weekly" src="https://androidweekly.net/issues/issue-746/badge" height="24">
  </a>
</p>

[English](https://github.com/JALAL591/compose-bridge/blob/main/README.md) | [العربية](https://github.com/JALAL591/compose-bridge/blob/main/README_AR.md)

---

### 📥 Direct Downloads & Quick Install (v1.1.2)

| Package | Asset (.zip / .aar) | Installation |
|---|---|---|
| **IDE Plugin (Android Studio / IntelliJ)** | [📥 **ComposeBridgeIntelliJ-1.1.1.zip**](https://github.com/JALAL591/compose-bridge/raw/main/dist/ComposeBridgeIntelliJ-1.1.1.zip) | In Android Studio: `Settings` ➔ `Plugins` ➔ `⚙️` ➔ `Install Plugin from Disk...` |
| **Compose Runtime Library (Release & Debug)** | [📦 **composebridge-runtime-release.aar**](https://github.com/JALAL591/compose-bridge/raw/main/dist/composebridge-runtime-release.aar) | Copy to `app/libs/` as `implementation` (Zero overhead, production-safe registries) |
| **Compose Agent Library (Debug Inspector)** | [📦 **composebridge-agent-release.aar**](https://github.com/JALAL591/compose-bridge/raw/main/dist/composebridge-agent-release.aar) | Copy to `app/libs/` as `debugImplementation` (Live overlays, WebSocket, UI tools) |

**ComposeBridge** is a developer tooling suite that bridges a running Compose app (KMP/Android) with your IDE or AI Agent.

> [!NOTE]
> **KMP / Desktop Support Status**: KMP/Desktop support is currently in **Beta**. Focus is on **Android stability** for v1.1.1.


### 🎯 What's New in v1.1.1?
- **📝 Text Editing with Live Preview:** Tap any text element on device, edit its content directly in the inspector BottomSheet, and preview changes instantly with zero latency via `BridgeTextRegistry`.
- **⚡ On-the-Fly Auto-Migration:** Intelligent AST engine automatically wraps edited strings into `BridgeTextRegistry` upon first touch—no manual code wrapping required.
- **🤖 Autonomous AI Agent Integration (MCP):** Connect Claude, Cursor, Antigravity or any Model Context Protocol agent with 17+ deep-inspection and code refactoring tools.
- **🗺️ Architectural Vision (RFC-001):** Published comprehensive technical architecture and roadmap (`docs/architecture/RFC-001-vision.md`).
- **🛡️ Cross-Platform Reliability:** Fixed navigation backstack resets, normalized Windows CRLF line-endings, and added precision regex extraction for single-pattern getters.

### 🎬 See it in action & Screenshots

Click the preview below to watch ComposeBridge visually edit a running Jetpack Compose UI and persist the change back to Kotlin source.

<p align="center">
  <a href="https://youtu.be/Hywyq7cBdDM">
    <img src="https://img.youtube.com/vi/Hywyq7cBdDM/hqdefault.jpg" alt="Watch ComposeBridge live demo" width="70%" style="border-radius: 8px;" />
  </a>
</p>

#### 📸 Studio Plugin & Live Device Integration

| 1. Studio ToolWindow & Token Scanner | 2. Surgical Pattern Refactoring & Diff | 3. Live On-Device Preview & Inspector |
|:---:|:---:|:---:|
| <a href="https://github.com/JALAL591/compose-bridge/blob/main/docs/screenshots/1_composebridge_main_ui.jpg"><img src="https://raw.githubusercontent.com/JALAL591/compose-bridge/main/docs/screenshots/1_composebridge_main_ui.jpg" width="100%" alt="ComposeBridge Main UI" /></a> | <a href="https://github.com/JALAL591/compose-bridge/blob/main/docs/screenshots/2_composebridge_patterns_diff.jpg"><img src="https://raw.githubusercontent.com/JALAL591/compose-bridge/main/docs/screenshots/2_composebridge_patterns_diff.jpg" width="100%" alt="ComposeBridge Patterns Diff" /></a> | <a href="https://github.com/JALAL591/compose-bridge/blob/main/docs/screenshots/3_composebridge_live_device_sync.jpg"><img src="https://raw.githubusercontent.com/JALAL591/compose-bridge/main/docs/screenshots/3_composebridge_live_device_sync.jpg" width="100%" alt="ComposeBridge Live Sync" /></a> |

---

## 🚀 Key Features

| Feature | Description |
|---------|-------------|
| **⚡ Live Preview** | Tweak colors and dimensions at **<50ms latency**. Changes reflect instantly on the phone (after one initial rebuild). |
| **🎯 Focus Mode** | Smart BottomSheet shows **only** the properties of the selected element (e.g., `c1`, `c2`, `padding`). |
| **🧠 Semantic Intelligence** | Detects if a value is shared. Offers **Split** (isolate to this card) or **Global** (change everywhere). |
| **💾 Safe Refactoring** | AST-Guided Splicing. Changes tracked in a `PatternJournal`. **Reject All** reverts byte-for-byte. |
| **🔌 IDE Plugin** | 5 Tabs: Scan, Impact, Split, Patterns, and **Changes** (Approve/Reject UI). |
| **🤖 Standalone MCP** | Works without the phone. AI agents can scan, refactor, and build the project. |

---

## 📦 Repository Structure

```text
composebridge/
├── agent/       # Compose runtime library (:composebridge-agent)
├── server/      # Python WebSocket daemon + MCP server + AST splicer
├── plugin/      # Android Studio Plugin (5 Tabs)
└── docs/        # Architecture + setup guides
```

---

## 🛠️ Quick Start (Android / KMP)

You can launch and connect ComposeBridge in two ways depending on your workflow:

### 🔹 Option 1: Using the Android Studio Plugin (Recommended)

No manual terminal commands are needed. The IDE plugin manages the background server and ADB reverse forwarding automatically.

1. **Open the ToolWindow**: In Android Studio, open the **ComposeBridge** tool window on the right sidebar.
2. **Start the Server**: Click **▶ Start Bridge**.
   - The plugin launches `server.py` in the background and executes `adb reverse tcp:8711 tcp:8711` automatically.
   - The status updates to `🟢 Bridge Running`.
   - *(Optional)* In **Settings → ComposeBridge**, check **Auto-start Bridge Server** to launch automatically when you open your project.
3. **Add the Agent** to your app's dependencies and initialize (see steps below).

---

### 🔹 Option 2: Standalone Server / AI Agents (MCP)

Ideal for AI coding assistants (Claude Desktop, Cursor, Antigravity IDE) or terminal workflows:

1. **Start the local server**:
   ```bash
   cd server
   pip install -r requirements.txt
   python server.py
   ```
2. **Setup ADB reverse port forwarding** (for Android phone connection):
   ```bash
   adb reverse tcp:8711 tcp:8711
   ```
*(Note: If you are solely using AI Agents via MCP tools, no phone or ADB reverse is needed — see the [MCP Server](#-mcp-server-ai-agents) section below).*

---

### 📲 App Integration Steps

#### 1. Add dependencies to your project
```kotlin
// build.gradle.kts (Android or commonMain)
dependencies {
    // Core runtime registries (BridgeTextRegistry, BridgeThemeRegistry, BridgeDimensionRegistry)
    // Required in both Debug and Release builds so production APK builds cleanly
    implementation("com.composebridge:runtime:1.1.1") // or files("libs/composebridge-runtime-release.aar")

    // On-device UI inspector and bridge (Debug only)
    debugImplementation("com.composebridge:agent:1.1.1") // or files("libs/composebridge-agent-release.aar")
}
```

#### 2. Initialize in MainActivity
```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    ComposeBridgeAgent.start(serverUrl = "ws://127.0.0.1:8711")
    setContent {
        ComposeBridgeAgent.Root {
            App()
        }
    }
}
```

#### 3. Connect & Tune
1. Deploy and run the app on your Android device (or emulator).
2. Tap the **🔧 FAB** → Design Mode ON.
3. Tap any Composable → Focus Mode opens.
4. Tweak colors/dimensions live → Hit **Sync**.

> **Note on Live Preview:** Changing a hardcoded value or creating a new token requires **one rebuild** to update the compiled bytecode. After this, all future tweaks via the Registry are instant.

---

## 🤖 MCP Server (AI Agents)

ComposeBridge exposes its tools to AI agents via the Model Context Protocol (MCP). **No phone is required for MCP.**

### Supported Clients
- ✅ Antigravity IDE (Gemini)
- ✅ Claude Desktop
- ✅ Cursor
- ✅ Cline / Continue

### Setup

**1. Install dependencies**
```bash
cd server
pip install -r requirements.txt
```

**2. Configure your AI client**
Antigravity IDE — edit `~/.gemini/config/mcp_config.json`:
```json
{
  "mcpServers": {
    "composebridge": {
      "command": "python",
      "args": ["C:\\path\\to\\composebridge\\server\\mcp_server.py"]
    }
  }
}
```

### Available Tools (17+)

| Category | Tools |
|----------|-------|
| **Discovery** | `list_tokens`, `find_token_by_color`, `get_token_impact`, `get_token_siblings`, `get_naming_convention` |
| **Editing** | `set_token`, `add_token`, `rollback_last` |
| **Refactoring** | `detect_conditional_variants`, `replace_pattern`, `rollback_pattern`, `global_color_edit`, `split_token_for_element` |
| **Build** | `run_gradle_build`, `list_allowed_gradle_tasks` |
| **Change Mgmt**| `list_modified_files`, `approve_all_files`, `reject_all_files` |

---

## ⚠️ Platform Support (v1.1.2)

| Feature | Android | Desktop | iOS |
|---------|:-------:|:-------:|:---:|
| **MCP Server (AI)** | ✅ | ✅ | ✅ |
| **IDE Plugin (5 Tabs)** | ✅ | ✅ | ✅ |
| **Phone Live Editing** | ✅ | ❌ | ❌ |

*Desktop and iOS on-device overlays are planned for v1.1.1.*

---

## 🔎 Search Terms This Project Solves
- Jetpack Compose edit without recompile
- Compose hot reload alternative
- Interactive layout inspector for Android
- Live UI tweaking on a real Android device
- Sync design tokens to Kotlin source
- Generate Compose UI from a JSON schema

---

## 📜 License
Distributed under the [Apache License 2.0](https://github.com/JALAL591/compose-bridge/blob/main/LICENSE).
