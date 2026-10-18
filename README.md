# ComposeBridge 🌉

**Real-time on-device visual editor for Jetpack Compose + MCP Server for AI agents. Live UI tuning, AST-guided surgical source splicing, and standalone AI-driven code edits.**

[![Kotlin](https://img.shields.io/badge/Kotlin-2.1.20+-purple.svg)](https://kotlinlang.org)
[![Jetpack Compose](https://img.shields.io/badge/Jetpack%20Compose-1.7.3+-4285F4.svg)](https://developer.android.com/jetpack/compose)
[![Zero Rebuild](https://img.shields.io/badge/DevEx-Zero--Rebuild%20Preview-brightgreen.svg)]()
[![Latency](https://img.shields.io/badge/Latency-%3C50ms-success.svg)]()
[![Version](https://img.shields.io/badge/Version-1.0.0-blue.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/JALAL591/compose-bridge/blob/main/LICENSE)
[![M8ven Score](https://m8ven.ai/badge/mcp/jalal591-compose-bridge-rapm1x)](https://m8ven.ai/mcp/jalal591-compose-bridge-rapm1x?s=readme)

## 📰 Featured In

<p align="left">
  <a href="https://androidweekly.net/issues/issue-746" title="Android Weekly Issue #746">
    <img alt="Android Weekly" src="https://androidweekly.net/issues/issue-746/badge" height="24">
  </a>
</p>

[English](https://github.com/JALAL591/compose-bridge/blob/main/README.md) | [العربية](https://github.com/JALAL591/compose-bridge/blob/main/README_AR.md)

---

### 📥 Direct Downloads & Quick Install (v1.0.0)

| Package | Asset (.zip / .aar) | Installation |
|---|---|---|
| **IDE Plugin (Android Studio / IntelliJ)** | [📥 **ComposeBridgeIntelliJ-1.0.0.zip**](https://github.com/JALAL591/compose-bridge/raw/main/dist/ComposeBridgeIntelliJ-1.0.0.zip) | In Android Studio: `Settings` ➔ `Plugins` ➔ `⚙️` ➔ `Install Plugin from Disk...` |
| **Compose Agent Library** | [📦 **composebridge-agent-release.aar**](https://github.com/JALAL591/compose-bridge/raw/main/dist/composebridge-agent-release.aar) | Copy to `app/libs/` or add to project dependencies |

**ComposeBridge** is a developer tooling suite that bridges a running Compose app (KMP/Android) with your IDE or AI Agent.

> [!NOTE]
> **KMP / Desktop Support Status**: KMP/Desktop support is currently in **Beta**. Focus is on **Android stability** for v1.0.0.


### 🎯 What's New in v1.0.0?
- **Focus Mode:** The BottomSheet now shows **only** the colors and dimensions of the tapped element. No more digging through long lists.
- **Global vs. Split:** Change a value across the whole project, or create an isolated token just for this element.
- **Pending Edits Queue:** Batch multiple UI tweaks locally and hit **Sync** once.
- **Dimensions Support:** Live-edit heights, widths, paddings, and font sizes — not just colors.
- **Review & Reject:** A full `git status`-like review in the IDE. Approve to keep, or Reject All for a byte-for-byte rollback.
- **17+ MCP Tools:** AI agents can now run Gradle builds, detect patterns, and rollback changes autonomously. See the full [**MCP Tools Reference**](docs/mcp-tools-reference.md).

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

#### 1. Add the Agent to your project
```kotlin
// build.gradle.kts (Android or commonMain)
debugImplementation("com.composebridge:agent:1.0.0")
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

## ⚠️ Platform Support (v1.0.0)

| Feature | Android | Desktop | iOS |
|---------|:-------:|:-------:|:---:|
| **MCP Server (AI)** | ✅ | ✅ | ✅ |
| **IDE Plugin (5 Tabs)** | ✅ | ✅ | ✅ |
| **Phone Live Editing** | ✅ | ❌ | ❌ |

*Desktop and iOS on-device overlays are planned for v1.1.0.*

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
