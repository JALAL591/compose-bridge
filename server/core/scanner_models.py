# -*- coding: utf-8 -*-
"""
Scanner Data Models — Type-safe structures for scan results.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class Token:
    """A registered token (dimension or color)."""
    name: str
    kind: str              # "dimension" | "color"
    value: str             # "240" or "0xFFEC4899"
    raw_value: str         # "240.dp" or "Color(0xFFEC4899)"
    file: str              # "AppDimens.kt"
    full_path: str         # absolute path
    line: int              # 16
    column: int            # 40
    usage_count: int = 0   # كم مرة استُخدم
    registry: str = ""
    scope_object: Optional[str] = None     # "BridgeDimensionRegistry" | "BridgeThemeRegistry"


@dataclass
class HardcodedValue:
    """A hardcoded value that could become a token."""
    value: str             # "16.dp" or "0xFF7C3AED"
    kind: str              # "dimension" | "color" | "font_size"
    file: str
    full_path: str
    line: int
    column: int
    context: str           # السطر كاملاً
    category: str          # "padding" | "size" | "background" | "text_color" | ...
    suggestion_name: str = ""  # اقتراح اسم token
    matched_token: Optional[str] = None  # إذا كانت القيمة موجودة كـ token


@dataclass
class DuplicateGroup:
    """Group of tokens with the same value."""
    value: str
    kind: str
    tokens: List[str]      # أسماء الـ tokens المتكررة
    locations: List[str]   # ["AppDimens.kt:9", "AppDimens.kt:45"]


@dataclass
class OrphanToken:
    """A registered token that is never used."""
    name: str
    kind: str
    value: str
    file: str
    line: int


@dataclass
class TokenUsage:
    """A single usage of a token."""
    token_name: str
    file: str
    line: int
    column: int
    line_content: str          # السطر الكامل
    enclosing_composable: str  # "HeroCard" | "DashboardPage" | "_unknown"
    enclosing_file: str
    enclosing_line: int
    hierarchy_path: List[str] = field(default_factory=list)  # ["HeroCard", "Card", "Button", "Icon"]
    depth: int = 0  # len(hierarchy_path)


@dataclass
class TokenImpact:
    """Impact analysis for a token."""
    token_name: str
    token_value: str
    token_kind: str
    token_location: str        # "AppDimens.kt:16"
    usages: List[TokenUsage]
    affected_composables: List[str]  # ["HeroCard", "StatGrid"]
    total_impact: int


@dataclass
class SplitSuggestion:
    """اقتراح فصل token إلى عدة توكنات حسب السياق."""
    token_name: str
    token_value: str
    token_kind: str
    contexts: Dict[str, List[dict]]  # {context: [usages]}
    suggested_tokens: List[dict]     # [{name, context, usages}]


@dataclass
class ScanReport:
    """Complete scan report."""
    project_root: str
    scanned_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    scan_duration_ms: int = 0
    files_scanned: int = 0
    
    registered_tokens: List[Token] = field(default_factory=list)
    hardcoded_values: List[HardcodedValue] = field(default_factory=list)
    duplicates: List[DuplicateGroup] = field(default_factory=list)
    orphans: List[OrphanToken] = field(default_factory=list)
    token_impacts: List[TokenImpact] = field(default_factory=list)
    split_suggestions: List[SplitSuggestion] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return asdict(self)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key):
        return getattr(self, key)
    
    def summary(self) -> dict:
        """Quick summary."""
        return {
            "registered_count": len(self.registered_tokens),
            "hardcoded_count": len(self.hardcoded_values),
            "duplicate_groups": len(self.duplicates),
            "orphan_count": len(self.orphans),
            "files_scanned": self.files_scanned,
            "scan_duration_ms": self.scan_duration_ms,
        }
