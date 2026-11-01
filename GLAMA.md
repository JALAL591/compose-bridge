# Glama Deployment Guide (ComposeBridge MCP)

This guide documents the exact settings required in the **Glama Dashboard** for deploying the ComposeBridge MCP server.

---

## 📋 Glama Dashboard Configuration

Glama uses its own execution environment (specified in dashboard settings rather than the repository Dockerfile).

### 1. Build Steps
In the **Build Steps** configuration field, enter:

```json
["uv venv .venv && uv pip install -r server/requirements.txt"]
```

### 2. CMD Arguments
In the **CMD arguments** configuration field, enter:

```json
["mcp-proxy", "--", ".venv/bin/python", "server/mcp_server.py"]
```

> ⚠️ **Critical Note on Python Path:**  
> The Python binary **must** be specified as `.venv/bin/python` (not global `python`), because Glama provisions dependencies inside the isolated virtual environment (`.venv`).

---

## 🔍 Module Resolution Architecture

To ensure that both the project root (`/app`) and server root (`/app/server`) are always resolvable regardless of how Glama invokes the script, `server/mcp_server.py` dynamically ensures both paths in `sys.path`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

---

## 🧪 Verification Command

To verify the startup locally under the same conditions as Glama:

```bash
# From repository root:
python server/mcp_server.py
```

All imports will resolve with 0 errors.
