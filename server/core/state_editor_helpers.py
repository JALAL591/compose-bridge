# -*- coding: utf-8 -*-
"""
State Editor Helpers — Find tokens and apply values.

Re-anchors tokens by NAME, not by location.
"""

import re
from pathlib import Path
from typing import Optional, Tuple


def find_token_in_project(project_root: Path, token_name: str) -> Optional[str]:
    """
    Find a token in the project by its NAME.
    
    Returns:
        "file.kt:line" or None
    """
    patterns = [
        re.compile(rf'BridgeDimensionRegistry\.get\(\s*"{re.escape(token_name)}"'),
        re.compile(rf'BridgeThemeRegistry\.getColor\(\s*"{re.escape(token_name)}"'),
    ]
    
    for kt in project_root.rglob("*.kt"):
        if "build" in str(kt) or ".composebridge-state" in str(kt):
            continue
        try:
            content = kt.read_text(encoding="utf-8")
        except Exception:
            continue
        
        for pattern in patterns:
            match = pattern.search(content)
            if match:
                line = content[:match.start()].count("\n") + 1
                return f"{kt.name}:{line}"
    
    return None


def apply_value_to_token(
    location: str,
    token_name: str,
    new_value: str,
) -> Tuple[bool, str]:
    """
    Apply a new value to a token by calling the real state_editor.
    
    Args:
        location: "file.kt:line" (للتوثيق — لا يُستخدم للبحث)
        token_name: "welcomeCardHeight"
        new_value: "500"
    
    Returns:
        (success, message)
    """
    try:
        # ⭐ استخدم الدالة الحقيقية من state_editor
        from core.state_editor import update_token_default
        
        ok, msg, info = update_token_default(token_name, new_value)
        
        if ok:
            return (True, f"Applied {token_name} = {new_value} @ {location}")
        else:
            return (False, msg)
    except Exception as e:
        return (False, f"Exception: {e}")
