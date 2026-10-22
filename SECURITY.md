# Security Policy

The ComposeBridge team takes the security and safety of developer environments seriously.

---

## 🛡️ Supported Versions

We release security patches and stability updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |
| 1.0.x   | :x:                |
| < 1.0   | :x:                |

---

## 🔒 Security Architecture & Guarantees

1. **Local-Only Communication:**
   - The Bridge Server (`server.py`) and Agent WebSocket connect exclusively over local loopback interfaces (`127.0.0.1` / ADB port forwarding `tcp:8711`).
   - The server does not expose open public relay endpoints or transmit your source code to external cloud services.
2. **Dynamic Auth Token Protection:**
   - Every session generates a cryptographically random authentication token stored locally in `.composebridge-state/auth.json`.
   - Incoming WebSocket connections must supply a valid authentication header or token to execute file modifications.
3. **Byte-Level Journaling & Safe Rollbacks:**
   - Any modification made by the AST Splicer generates a `.bridge.bak` byte-level backup before applying changes.
   - Pending changes are logged to `PatternJournal` and can be reverted cleanly at any time (`Reject All`).
4. **Whitelisted Gradle Execution:**
   - The MCP build tools only permit explicitly whitelisted Gradle tasks (e.g. `assembleDebug`, `check`, `compileKotlin`). Arbitrary shell command execution is prohibited.

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability in ComposeBridge, please **do not** open a public issue.

Instead, please report it via:
1. **GitHub Private Security Advisory:** Open an advisory under the Security tab of the repository.
2. **Direct Contact:** Send an email to the project maintainers via GitHub profile contact.

Please include:
- A description of the issue and potential impact.
- Clear reproduction steps or proof-of-concept (PoC).
- Your environment details (OS, ComposeBridge version, Python version).

We will acknowledge receipt within **48 hours** and provide regular progress updates until a patch is released.
