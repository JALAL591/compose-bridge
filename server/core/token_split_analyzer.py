# -*- coding: utf-8 -*-
"""
Token Split Analyzer — يقترح فصل التوكنات بناءً على السياق الدلالي والتحليل الهرمي.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional
from .scanner_models import TokenImpact, SplitSuggestion
from .token_migrator import CONTEXT_RULES, COLOR_CONTEXT_RULES

INTERNAL_UI_ELEMENTS = {
    "Card", "Button", "Column", "Row", "Box", "Spacer", "Text", "Icon",
    "Surface", "Scaffold", "LazyColumn", "LazyRow", "Item", "Divider",
    "Image", "IconButton", "FloatingActionButton", "TopAppBar", "BottomAppBar",
    "NavigationBar", "NavigationRail", "_root", "_unknown",
}


def to_snake_case(name: str) -> str:
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return s.lower()



class TokenSplitAnalyzer:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.dim_context_rules = CONTEXT_RULES
        self.color_context_rules = COLOR_CONTEXT_RULES

    def _detect_context(self, line_content: str, token_kind: str) -> str:
        """يحدد السياق الدلالي حسب نوع التوكن."""
        rules = self.color_context_rules if token_kind == "color" else self.dim_context_rules
        for keyword, prefixes in rules.items():
            if keyword in line_content:
                return prefixes[0]  # أول prefix
        return "unknown"

    def _analyze_hierarchical(self, impact: TokenImpact) -> bool:
        """
        Return True if usages are at different hierarchy levels.
        """
        # احسب مسارات هرمية للـ usages (عمق >= 2 أو مستويات مختلفة)
        hier_paths = set()
        for usage in impact.usages:
            path = getattr(usage, 'hierarchy_path', [])
            if len(path) >= 2:
                hier_paths.add(tuple(path))
        return len(hier_paths) > 1

    def analyze_token(self, impact: TokenImpact) -> Optional[SplitSuggestion]:
        """يحلل token واحد ويعيد اقتراحاً إذا لزم الفصل سياقياً أو هرمياً."""
        # ⭐ لا تقترح فصل color tokens — هي semantic بطبيعتها
        if impact.token_kind == "color":
            return None

        contexts: Dict[str, List[dict]] = {}
        for usage in impact.usages:
            ctx = self._detect_context(usage.line_content, impact.token_kind)
            contexts.setdefault(ctx, []).append({
                "file": usage.file,
                "line": usage.line,
                "line_content": usage.line_content,
                "enclosing_composable": usage.enclosing_composable,
                "hierarchy_path": getattr(usage, 'hierarchy_path', []),
                "depth": getattr(usage, 'depth', 0),
            })

        real_contexts = {k: v for k, v in contexts.items() if k != "unknown"}
        hierarchical_split = self._analyze_hierarchical(impact)

        # اقتراح الفصل إذا:
        # 1. هناك أكثر من سياق مختلف OR
        # 2. هناك مستويات هرمية مختلفة
        if len(real_contexts) <= 1 and not hierarchical_split:
            return None

        suggested_tokens = []
        if hierarchical_split:
            # اقتراح أسماء أقصر مع الحفاظ على الوضوح والتفرد
            items = []
            for ctx, usages in real_contexts.items():
                for usage in usages:
                    path = usage.get("hierarchy_path", [])
                    non_ui = [p for p in path if p not in INTERNAL_UI_ELEMENTS]
                    if non_ui:
                        comp_name = non_ui[-1]
                    else:
                        comp_name = usage.get("enclosing_composable")
                        if not comp_name or comp_name in INTERNAL_UI_ELEMENTS:
                            comp_name = impact.token_name
                    comp_snake = to_snake_case(comp_name)

                    elem_snake = ""
                    if path:
                        last_elem = path[-1]
                        if last_elem != comp_name and last_elem not in ("_root", "_unknown"):
                            elem_snake = to_snake_case(last_elem)

                    items.append({
                        "usage": usage,
                        "ctx": ctx,
                        "path": path,
                        "comp_snake": comp_snake,
                        "elem_snake": elem_snake,
                    })

            # فحص التعارض لنفس الـ composable بنفس السياق
            comp_ctx_elems = {}
            for it in items:
                key = (it["comp_snake"], it["ctx"])
                comp_ctx_elems.setdefault(key, set()).add(it["elem_snake"])

            seen = {}
            for it in items:
                key = (it["comp_snake"], it["ctx"])
                needs_elem = len(comp_ctx_elems[key]) > 1 and it["elem_snake"]
                if needs_elem:
                    suggested_name = f"{it['comp_snake']}_{it['elem_snake']}_{it['ctx']}"
                else:
                    suggested_name = f"{it['comp_snake']}_{it['ctx']}"

                # تجنب تكرار اسم الـ token الأصلي
                if suggested_name == impact.token_name.lower():
                    if it["elem_snake"]:
                        suggested_name = f"{it['comp_snake']}_{it['elem_snake']}_{it['ctx']}"
                    else:
                        suggested_name = f"{suggested_name}_split"

                if suggested_name in seen:
                    seen[suggested_name]["usages"].append(it["usage"])
                else:
                    item = {
                        "name": suggested_name,
                        "context": it["ctx"],
                        "hierarchy_path": it["path"],
                        "usages": [it["usage"]],
                    }
                    seen[suggested_name] = item
                    suggested_tokens.append(item)
        else:
            # استخدام المنطق القديم (سياقي)
            base_name = impact.token_name
            if impact.token_kind == "color":
                for ctx, usages in real_contexts.items():
                    ctx_camel = ctx.replace("_", " ").title().replace(" ", "")
                    suggested_name = f"{base_name}{ctx_camel}"
                    suggested_tokens.append({
                        "name": suggested_name,
                        "context": ctx,
                        "usages": usages,
                    })
            else:
                if "_" in base_name:
                    parts = base_name.split("_")
                    suffix = parts[-1]
                else:
                    suffix = base_name

                for ctx, usages in real_contexts.items():
                    suggested_name = f"{ctx}_{suffix}"
                    suggested_tokens.append({
                        "name": suggested_name,
                        "context": ctx,
                        "usages": usages,
                    })

        if len(suggested_tokens) <= 1:
            return None

        return SplitSuggestion(
            token_name=impact.token_name,
            token_value=impact.token_value,
            token_kind=impact.token_kind,
            contexts=real_contexts,
            suggested_tokens=suggested_tokens,
        )

    def analyze_all(self, impacts: List[TokenImpact]) -> List[SplitSuggestion]:
        """يحلل كل التوكنات ويعيد قائمة الاقتراحات."""
        suggestions = []
        for impact in impacts:
            suggestion = self.analyze_token(impact)
            if suggestion:
                suggestions.append(suggestion)
        return suggestions
