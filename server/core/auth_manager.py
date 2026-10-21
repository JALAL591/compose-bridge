# -*- coding: utf-8 -*-
"""Auth Token Manager for ComposeBridge."""

import os
import json
import secrets
from pathlib import Path
from typing import Optional


def get_or_create_auth_token(project_root: Optional[Path] = None) -> str:
    """
    Get or create a secure random auth token stored in .composebridge-state/auth.json.
    """
    if project_root is None:
        try:
            from core.project_root import get_project_root
            project_root = get_project_root()
        except Exception:
            project_root = Path.cwd()

    project_root = Path(project_root)
    state_dir = project_root / ".composebridge-state"
    auth_file = state_dir / "auth.json"

    if auth_file.exists():
        try:
            data = json.loads(auth_file.read_text(encoding="utf-8"))
            token = data.get("token")
            if token and isinstance(token, str) and len(token) >= 8:
                return token
        except Exception:
            pass

    # Generate new random 32-character hex token
    token = secrets.token_hex(16)
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        auth_file.write_text(json.dumps({"token": token}, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[AUTH] Warning creating auth.json: {e}")

    return token
