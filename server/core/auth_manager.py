# -*- coding: utf-8 -*-
"""Auth Token Manager for ComposeBridge."""

import os
import json
import secrets
import hmac
import time
from pathlib import Path
from typing import Optional

DEV_TOKEN = os.environ.get("COMPOSEBRIDGE_DEV_TOKEN")


def set_dev_token(token: Optional[str]):
    """Set or override development token for testing."""
    global DEV_TOKEN
    DEV_TOKEN = token
    if token:
        os.environ["COMPOSEBRIDGE_DEV_TOKEN"] = token


def get_auth_token_file_path(project_root: Optional[Path] = None) -> Path:
    """Return the path to auth_token.txt in .composebridge-state."""
    if project_root is None:
        try:
            from core.project_root import get_project_root
            project_root = get_project_root()
        except Exception:
            project_root = Path.cwd()
    project_root = Path(project_root)
    return project_root / ".composebridge-state" / "auth_token.txt"


def get_or_create_auth_token(project_root: Optional[Path] = None, regenerate: bool = False) -> str:
    """
    Get or create a secure random auth token (64 hex chars).
    Saved to:
    1. <project_root>/.composebridge-state/auth_token.txt
    2. <project_root>/.composebridge-state/auth.json
    3. ~/.composebridge-state/auth_token.txt (user home fallback)

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
    token_txt = state_dir / "auth_token.txt"
    auth_json = state_dir / "auth.json"

    if not regenerate:
        # 1. Try reading from auth_token.txt
        if token_txt.exists():
            try:
                t = token_txt.read_text(encoding="utf-8").strip()
                if len(t) >= 16:
                    return t
            except Exception:
                pass

        # 2. Try reading from auth.json
        if auth_json.exists():
            try:
                data = json.loads(auth_json.read_text(encoding="utf-8"))
                token = data.get("token")
                if token and isinstance(token, str) and len(token) >= 16:
                    # Sync to auth_token.txt
                    try:
                        token_txt.write_text(token, encoding="utf-8")
                    except Exception:
                        pass
                    return token
            except Exception:
                pass

    # 3. Try reading from ~/.composebridge-state/auth_token.txt as user-wide fallback before generating new
    if not regenerate:
        try:
            home_state_dir = Path.home() / ".composebridge-state"
            home_token_file = home_state_dir / "auth_token.txt"
            if home_token_file.exists():
                ht = home_token_file.read_text(encoding="utf-8").strip()
                if len(ht) >= 16:
                    state_dir.mkdir(parents=True, exist_ok=True)
                    token_txt.write_text(ht, encoding="utf-8")
                    auth_json.write_text(json.dumps({
                        "token": ht,
                        "created_at": time.time(),
                        "entropy_bytes": 32,
                    }, indent=2), encoding="utf-8")
                    return ht
        except Exception:
            pass

    # Generate new random 64-character (32-byte) hex token
    token = secrets.token_hex(32)

    # Save to project .composebridge-state
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        token_txt.write_text(token, encoding="utf-8")
        auth_json.write_text(json.dumps({
            "token": token,
            "created_at": time.time(),
            "entropy_bytes": 32,
        }, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[AUTH] Warning saving auth token in project: {e}")

    # Save to ~/.composebridge-state as user-wide fallback if not present
    try:
        home_state = Path.home() / ".composebridge-state"
        home_state.mkdir(parents=True, exist_ok=True)
        home_token_file = home_state / "auth_token.txt"
        if regenerate or not home_token_file.exists():
            home_token_file.write_text(token, encoding="utf-8")
    except Exception:
        pass

    return token


def verify_token(token: str, project_root: Optional[Path] = None) -> bool:
    """
    Verifies if a provided auth token matches the active server token.
    Uses constant-time comparison (hmac.compare_digest) to prevent timing attacks.
    """
    if not token or not isinstance(token, str):
        return False

    # 1. Check DEV_TOKEN if explicitly set (--dev-token or env var)
    if DEV_TOKEN and hmac.compare_digest(token, DEV_TOKEN):
        return True

    # 2. Check dynamic active token
    try:
        active_token = get_or_create_auth_token(project_root)
        if active_token and hmac.compare_digest(token, active_token):
            return True
    except Exception:
        pass

    return False
