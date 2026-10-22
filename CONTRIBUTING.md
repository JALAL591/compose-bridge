# Contributing to ComposeBridge

Thank you for your interest in contributing to **ComposeBridge**! We welcome contributions from developers, designers, and testers worldwide.

---

## 🛠️ Code of Conduct
We are committed to providing a friendly, safe, and welcoming environment for everyone, regardless of background or experience level. Please treat all community members with respect.

---

## 🚀 How Can I Contribute?

### 1. Reporting Bugs
- Search existing [GitHub Issues](https://github.com/JALAL591/compose-bridge/issues) to verify if the bug has already been reported.
- If not, use our **[Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md)** to provide comprehensive reproduction steps, environment details, and logs.

### 2. Suggesting Enhancements
- Open a feature request using our **[Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.md)**.
- For architectural proposals or major features, consider submitting an RFC to `docs/architecture/`.

### 3. Pull Requests (PRs)
- Fork the repository and create a branch from `main` (e.g., `feature/my-enhancement` or `fix/issue-description`).
- Keep PRs focused on a single concern.
- Ensure all existing unit tests pass before submitting.
- Follow our coding conventions described below.

---

## 💻 Development & Local Setup

### Repository Components:
```text
composebridge/
├── agent/       # Kotlin Multiplatform / Android Agent & Runtime (:composebridge-runtime)
├── server/      # Python 3.10+ WebSocket daemon, AST Splicer, and MCP Server
├── plugin/      # IntelliJ Platform / Android Studio Plugin
└── dist/        # Pre-packaged release archives
```

### 1. Python Server Development
```bash
cd server
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```
Run tests:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### 2. Kotlin Agent & Runtime Development
```bash
cd agent
./gradlew assembleRelease
```
To build only the ultra-lightweight release runtime:
```bash
./gradlew :composebridge-runtime:assembleRelease
```

### 3. Android Studio Plugin Development
```bash
cd plugin
./gradlew buildPlugin
```
To run a local sandbox instance of Android Studio with the plugin loaded:
```bash
./gradlew runIde
```

---

## 📐 Coding Conventions

1. **Modular Architecture & Facade Pattern:**
   - Core server logic is divided into specialized packages (`common/`, `analysis/`, `editor/`, `mcp/`, `network/`, `handlers/`, `cli/`).
   - Root files like `source_analyzer.py`, `state_editor.py`, `server.py`, and `mcp_server.py` act as **Facades** for backward compatibility. Never break external imports.
2. **Deterministic File Operations:**
   - Always use `acquire_write_lock` and `_atomic_write_text` with newline preservation (`newline=''`) when modifying source code.
   - Record modifications in `PatternJournal` so users can inspect and rollback changes.
3. **No Project Hardcoding:**
   - Never commit hardcoded user paths or project-specific package names. Always use dynamic resolution via `project_root` or current working directory.

---

## 📜 Licensing
By contributing to ComposeBridge, you agree that your contributions will be licensed under its **Apache License 2.0**.
