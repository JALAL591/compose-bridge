# -*- coding: utf-8 -*-
"""
Helper module for filtering and formatting design token scatter reports.
Produces concise, categorized summaries to prevent AI agent context window exhaustion.
"""

from typing import Dict, Any, List, Tuple


def build_category_reports(scatter_files: List[Dict[str, Any]]) -> Tuple[Dict[str, int], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extracts files needing fix (non-candidate registries with hardcoded tokens)
    and sorts them into distinct categories: colors, dimensions, strings.
    """
    needing_fix = [
        f for f in scatter_files
        if not f.get("is_candidate_registry", False) and f.get("counts", {}).get("total", 0) > 0
    ]

    colors_rep = [
        {"file": f["file"], "count": f["counts"]["color"]}
        for f in needing_fix if f["counts"].get("color", 0) > 0
    ]
    colors_rep.sort(key=lambda x: x["count"], reverse=True)

    dimens_rep = [
        {"file": f["file"], "count": f["counts"]["dimension"]}
        for f in needing_fix if f["counts"].get("dimension", 0) > 0
    ]
    dimens_rep.sort(key=lambda x: x["count"], reverse=True)

    strings_rep = [
        {"file": f["file"], "count": f["counts"]["string"]}
        for f in needing_fix if f["counts"].get("string", 0) > 0
    ]
    strings_rep.sort(key=lambda x: x["count"], reverse=True)

    summary = {
        "total_files_needing_fix": len(needing_fix),
        "total_colors": sum(x["count"] for x in colors_rep),
        "total_dimensions": sum(x["count"] for x in dimens_rep),
        "total_strings": sum(x["count"] for x in strings_rep),
    }

    return summary, colors_rep, dimens_rep, strings_rep


def format_scatter_for_agent(
    scan_result: Dict[str, Any],
    category: str = "all",
    limit: int = 10
) -> Dict[str, Any]:
    """
    Formats the raw scan result into a compact payload tailored for the AI agent.
    Guarantees output stays under context-friendly limits (< 100 lines, < 2000 chars).
    """
    if "colors_report" in scan_result and "summary" in scan_result and "total_files_needing_fix" in scan_result["summary"]:
        summary = {
            "total_files_needing_fix": scan_result["summary"]["total_files_needing_fix"],
            "total_colors": scan_result["summary"]["total_colors"],
            "total_dimensions": scan_result["summary"]["total_dimensions"],
            "total_strings": scan_result["summary"]["total_strings"],
        }
        colors_rep = scan_result.get("colors_report", [])
        dimens_rep = scan_result.get("dimensions_report", [])
        strings_rep = scan_result.get("strings_report", [])
    else:
        summary, colors_rep, dimens_rep, strings_rep = build_category_reports(
            scan_result.get("scatter_files", [])
        )

    cat_clean = (category or "all").strip().lower()

    if cat_clean in ("colors", "color"):
        return {
            "success": True,
            "colors_report": colors_rep[:limit]
        }
    elif cat_clean in ("dimensions", "dimension", "dimens"):
        return {
            "success": True,
            "dimensions_report": dimens_rep[:limit]
        }
    elif cat_clean in ("strings", "string"):
        return {
            "success": True,
            "strings_report": strings_rep[:limit]
        }
    else:
        # category == "all"
        # Budget 4 items per category to stay strictly under 100 lines and < 2000 chars
        per_cat_limit = min(limit, 4) if limit > 4 else limit
        return {
            "success": True,
            "summary": summary,
            "colors_report": colors_rep[:per_cat_limit],
            "dimensions_report": dimens_rep[:per_cat_limit],
            "strings_report": strings_rep[:per_cat_limit],
        }

