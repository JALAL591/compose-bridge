# -*- coding: utf-8 -*-
"""Auth Token Manager for ComposeBridge."""

import os
import json
import secrets
import hmac
from pathlib import Path
from typing import Optional

DEV_TOKEN = os.environ.get("COMPOSEBRIDGE_DEV_TOKEN")


def set_dev_token(token: Optional[str]):
    """Set or override development token for testing."""
    global DEV_TOKEN
    DEV_TOKEN = token
    if token:
        os.environ["COMPOSEBRIDGE_DEV_TOKEN"] = token


def get_or_create_auth_token(project_root: Optional[Path] = None) -> str:
    """
    Get or create a secure random auth token stored in .composebridge-state/auth.json.
    If DEV_TOKEN is explicitly set, it will be returned.
    """
    if DEV_TOKEN:
        return DEV_TOKEN

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


def verify_token(token: str, project_root: Optional[Path] = None) -> bool:
    """
    Verifies if a provided auth token is valid.
    Accepts:
    1. Fixed development token if configured (--dev-token / COMPOSEBRIDGE_DEV_TOKEN).
    2. Legacy dev token 'test-token-local-dev' for local testing compatibility.
    3. Active token stored in .composebridge-state/auth.json.
    """
    if not token or not isinstance(token, str):
        return False

    # 1. Check DEV_TOKEN if set
    if DEV_TOKEN and hmac.compare_digest(token, DEV_TOKEN):
        return True

    # 2. Support backward compatibility for legacy local dev token
    if token == "test-token-local-dev":
        return True

    # 3. Dynamic token verification from auth.json
    try:
        active_token = get_or_create_auth_token(project_root)
        if active_token and hmac.compare_digest(token, active_token):
            return True
    except Exception:
        pass

    return False
