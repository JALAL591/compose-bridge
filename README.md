# ComposeBridge 🌉

**Real-time on-device visual editor for Jetpack Compose.**
Live UI tuning + schema-driven screen compiler + AST-guided source splicing.

[![Kotlin](https://img.shields.io/badge/Kotlin-2.1.20+-purple.svg)](https://kotlinlang.org)
[![Jetpack Compose](https://img.shields.io/badge/Jetpack%20Compose-1.7.3+-4285F4.svg)](https://developer.android.com/jetpack/compose)
[![Zero Rebuild](https://img.shields.io/badge/DevEx-Zero--Rebuild%20Preview-brightgreen.svg)]()
[![Latency](https://img.shields.io/badge/Latency-%3C50ms-success.svg)]()
[![Engine](https://img.shields.io/badge/Engine-AST--Guided%20Byte--Splice-orange.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

[English](README.md) | [العربية](README_AR.md)

---

**ComposeBridge** is a developer tooling suite that bridges a running Android app on a physical device with your IDE over a local WebSocket. You can:

- 🎯 **Tap any Composable** on the phone to inspect it in real time
- 🎨 **Tune colors, dimensions, and paddings live** at 60fps — no Gradle build required
- 💾 **Persist tweaks to your Kotlin source** (`AppDimens.kt`, `AppColors.kt`) via a surgical byte-splice that preserves file formatting
- 🧩 **Generate full Compose screens** from a declarative JSON schema
- 🔍 **Navigate the runtime tree** — tap a parent, drill into children

> **Live preview is truly zero-rebuild.** Persisting the change into the final APK artifact requires one standard rebuild, after which the new value becomes the source of truth.

<!-- Add Demo GIF here -->
![ComposeBridge Demo](docs/assets/demo.gif)

---

## 🚀 Key Features

| Feature | Description |
|---------|-------------|
| **⚡ Zero-Rebuild Preview** | Tweak colors, paddings, corner radii, and font sizes at **<50ms latency** while the app runs. |
| **🎯 On-Device Visual Inspector** | Tap any Composable to see its source file, line number, and used design tokens. |
| **💾 AST-Guided Source Splicing** | Locates the exact byte range via Tree-sitter, then performs a surgical replace that keeps a **single-line `git diff`**. |
| **🧩 Dynamic UI Compiler** | Feed it a JSON schema (`dashboard.json`) — get a full, production-ready Compose screen with theme, components, and tokens wired up. |
| **🌳 Runtime Tree Navigation** | Walk the composition tree from parent to children — no XML, no reflection. |
| **🔌 Local WebSocket Daemon** | A lightweight Python bridge between the runtime agent and your file system. |

---

## 📦 What's Inside

```
composebridge/
├── cli/         # CLI tool + JSON → Compose screen compiler
├── agent/       # Android runtime library (:composebridge-agent)
├── server/      # Python WebSocket daemon + source byte-splicer
├── examples/    # Complete reference app (StudentApp)
└── docs/        # Architecture + setup guides
```

**Three components, one workflow:**
1. **CLI** — generates a full project from JSON
2. **Agent** — captures touches and pushes live updates on the device
3. **Server** — coordinates messages + writes changes back to `.kt` files

---

## ✅ Compatibility

| Component | Version |
|-----------|---------|
| Kotlin | 2.1.20+ |
| Jetpack Compose | 1.7.3+ |
| Compose Multiplatform | 1.7.3+ |
| Gradle | 8.5+ |
| Android Gradle Plugin | 8.5+ |
| Min SDK | 24 |
| Python | 3.10+ |
| Target | Android (real device or emulator) |

---

## 🛠️ Quick Start

### 1. Start the local server

```bash
cd server
pip install -r requirements.txt
python server.py
```

### 2. Generate a Compose project

```bash
cd cli
python generate.py screens/dashboard.json
```

The CLI will produce a full Android project under `output/` — including:
- ✅ Theme files (`AppColors.kt`, `AppDimens.kt`, `AppTypography.kt`, `AppStrings.kt`)
- ✅ UI components (`HeroCard`, `StatCard`, `DashboardHeader`, ...)
- ✅ The full `DashboardPage.kt`
- ✅ The `composebridge-agent` module
- ✅ The `bridge/` Python server, wired to the new project's path
- ✅ `MainActivity.kt` with the agent already wired up
- ✅ `AndroidManifest.xml` with `INTERNET` permission

### 3. Open in Android Studio

Open the generated project, deploy it to a physical device, then:

```bash
adb reverse tcp:8711 tcp:8711
```

Tap the **🔧 floating button** → Design Mode ON.
Tap any element → the panel opens → slide/tap to tune live.

---

## 🎬 Demo

A 38-second demo shows:
1. Tap an element on the phone
2. Change a color from a swatch
3. Watch the UI update instantly
4. See the single-line diff appear in `AppColors.kt`

[Watch the demo →](docs/assets/demo.mp4)

---

## 🤔 Why not just wait for Compose Hot Reload?

| | Compose Hot Reload (JetBrains) | **ComposeBridge** |
|---|---|---|
| Availability | Preview / experimental | ✅ Works today (Kotlin 2.1.20) |
| Target | Emulator-first | ✅ Real device |
| Persistence | Preview only | ✅ Writes back to source |
| Interaction | Textual | ✅ Visual — tap elements |
| Code safety | Full reload | ✅ Single-line `git diff` |

---

## 🧠 Under the Hood

- **Bidirectional runtime-to-source mapping** — every visual change is traceable to its exact Kotlin byte range.
- **AST-guided inspection, byte-splice editing** — Tree-sitter locates; regex + byte replace edits. No source formatting is lost.
- **Deterministic layout compilation** — the CLI emits structured, tokenized Compose code — no AI hallucinations.
- **Low-latency WebSocket daemon** — sub-50ms round-trip between the device and the file system.

---

## 🤖 Coming Soon

- **AI-Powered Suggestions** (Qwen integration)
  Describe a change in natural language — the tool finds the right token and applies it.
- **Natural Language Editing**
  "Make this card taller." "Use the gold accent here."
- **More component templates** — e-commerce, forms, profile screens.
- **Typography tokens** — full typography token live editing.

---

## 🔎 Search Terms This Project Solves

If you've searched for any of these, this project is for you:

- Jetpack Compose edit without recompile
- Compose hot reload alternative
- Interactive layout inspector for Android
- Live UI tweaking on a real Android device
- Sync design tokens to Kotlin source
- Generate Compose UI from a JSON schema

---

## 📜 License

Distributed under the [Apache License 2.0](LICENSE).
