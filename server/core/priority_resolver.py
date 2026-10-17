# -*- coding: utf-8 -*-
"""
Priority Resolver — Resolves token state based on priority rules.

Priority (highest first):
1. User Intent (from queue or applied)
2. Agent Proposal (if accepted)
3. Snapshot (default)
"""

from typing import Optional, Tuple


class PriorityResolver:
    """
    Resolves the final value/location of a token.
    
    Key insight: Value and Location are independent.
    """
    
    def __init__(self, state_manager):
        self.sm = state_manager
    
    def resolve_value(self, token: str) -> Tuple[Optional[str], str]:
        """
        Resolve the current value of a token.
        
        Returns:
            (value, source) — value is None if not found
            source ∈ {"user", "agent", "snapshot", "unknown"}
        """
        # Priority 1: User Intent (applied)
        user_val = self.sm.history.get_current_value(token)
        if user_val is not None:
            # Check if latest applied was from user
            history = self.sm.history.value_history.get(token, [])
            for entry in reversed(history):
                if entry["status"] == "applied":
                    return (entry["new"], entry["source"])
        
        # Priority 2: Snapshot
        snap = self.sm.snapshot.tokens.get(token)
        if snap:
            return (snap["value"], "snapshot")
        
        return (None, "unknown")
    
    def resolve_location(self, token: str) -> Tuple[Optional[str], str]:
        """
        Resolve the current location of a token.
        
        Returns:
            (location, source) — location format: "file.kt:line"
        """
        # Priority 1: Non-rejected location from history
        loc = self.sm.history.get_current_location(token)
        if loc is not None:
            history = self.sm.history.location_history.get(token, [])
            for entry in reversed(history):
                if entry["status"] in ("accepted", "pending", "applied"):
                    return (entry["new"], entry["source"])
        
        # Priority 2: Snapshot
        snap = self.sm.snapshot.tokens.get(token)
        if snap:
            return (f"{snap['file']}:{snap['line']}", "snapshot")
        
        return (None, "unknown")
    
    def resolve_all(self) -> dict:
        """Resolve all tokens."""
        result = {}
        for token in self.sm.snapshot.tokens.keys():
            val, val_src = self.resolve_value(token)
            loc, loc_src = self.resolve_location(token)
            result[token] = {
                "value": val,
                "value_source": val_src,
                "location": loc,
                "location_source": loc_src,
            }
        return result
