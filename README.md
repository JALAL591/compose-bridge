# ComposeBridge 🌉

**ComposeBridge** is a real-time, bidirectional live design and editing toolkit for **Jetpack Compose** applications. It connects your running Android app directly to a local Python design hub over WebSockets, enabling real-time visual inspection, dimension overrides, and instant source code persistence.

---

## 🚀 Key Features

- **🎯 Live Design Mode**: Select any Composable element on-screen with visual selection overlays and drag handles.
- **⚡ Instant State Overrides**: Tweak dimensions, colors, paddings, and typography on device without rebuilding.
- **💾 Source Code Persistence**: Commit live visual edits directly back into Kotlin source files (`AppDimens.kt`, `AppColors.kt`, etc.).
- **🧩 Dynamic UI Compiler**: Generate full Android Compose screens and components from JSON schema specifications.
- **🔌 Multi-Client Broadcast**: Bidirectional WebSocket server broadcasting live state updates across tools and connected devices.

---

## 📁 Repository Structure

```text
composebridge-en/
├── cli/         # Python CLI & dynamic UI compiler
├── agent/       # Android Agent Kotlin module (:composebridge-agent)
├── server/      # Local WebSocket bridge server & AST state editor
├── examples/    # Sample student dashboard app (StudentApp)
└── docs/        # Documentation & architecture guides
```

---

## 🛠️ Quick Start

### 1. Start the Bridge Server
```bash
cd server
pip install -r requirements.txt
python server.py
```

### 2. Generate an App via CLI
```bash
cd cli
python generate.py screens/dashboard.json
```

### 3. Open & Run in Android Studio
Open the generated project or the provided example at `examples/student-app` in Android Studio and run it on your emulator or physical device.

---

## 📜 License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

---

## 🔒 Security

- **Debug Builds Only**: The ComposeBridge Agent is bundled using `debugImplementation`, ensuring zero overhead and complete removal from production release builds.
- **Token Authentication**: WebSocket connections require secure token verification on handshake to prevent unauthorized local connections.

## ⚠️ Limitations

- **AST Validation**: Surgical edits are restricted to simple literal values (`integer_literal`, `float_literal`, `string_literal`, `simple_identifier`, `long_literal`) to prevent parser syntax corruption.
- **Journal Rollback**: Automatic rollback via journal occurs if AST syntax validation fails post-splice.
