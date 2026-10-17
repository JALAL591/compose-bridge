# -*- coding: utf-8 -*-
"""
State Snapshot — Captures a full picture of all tokens.
"""

import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from .project_scanner import ProjectScanner
from .token_migrator import TokenMigrator


class TokenSnapshot:
    """Snapshot of all design tokens in the project."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.captured_at: Optional[str] = None
        self.version: int = 0
        self.tokens: Dict[str, dict] = {}
    
    def capture(self) -> dict:
        """
        Scan all .kt files and extract tokens using ProjectScanner.
        
        Returns:
            {
                "captured_at": "ISO timestamp",
                "version": 1,
                "tokens": {
                    "tokenName": {
                        "value": "...",
                        "file": "...",
                        "line": ...,
                        "kind": "dimension" | "color",
                        "registry": "StandardTheme"
                    }
                }
            }
        """
        self.captured_at = datetime.utcnow().isoformat()
        self.version += 1
        self.tokens = {}
        
        # ⭐ استخدام ProjectScanner لقراءة tokens بأي نمط
        scanner = ProjectScanner(self.project_root)
        report = scanner.scan(include_hardcoded=False)
        
        for token in report.registered_tokens:
            self.tokens[token.name] = {
                "value": token.value,
                "file": token.file,
                "line": token.line,
                "kind": token.kind,
                "registry": getattr(token, 'registry', 'StandardTheme'),
            }
        
        return self.to_dict()

    def to_dict(self) -> dict:
        return {
            "captured_at": self.captured_at,
            "version": self.version,
            "tokens": self.tokens,
        }
    
    def save(self, path: Path):
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    
    def load(self, path: Path):
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self.captured_at = data.get("captured_at")
        self.version = data.get("version", 0)
        self.tokens = data.get("tokens", {})
