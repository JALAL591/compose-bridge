# -*- coding: utf-8 -*-
"""
Scanner CLI — Run from terminal.

Usage:
    python scanner_cli.py
    python scanner_cli.py --format json
    python scanner_cli.py --format markdown
    python scanner_cli.py --summary
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure bridge directory is in sys.path
BRIDGE_DIR = Path(__file__).resolve().parent
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

from core.project_scanner import ProjectScanner


def format_text(report) -> str:
    """Pretty-print for terminal."""
    lines = []
    lines.append("=" * 70)
    lines.append("  ComposeBridge — Project Scan Report")
    lines.append("=" * 70)
    lines.append("")
    
    s = report.summary()
    lines.append(f"  Files scanned:      {s['files_scanned']}")
    lines.append(f"  Scan duration:      {s['scan_duration_ms']} ms")
    lines.append(f"  Registered tokens:  {s['registered_count']}")
    lines.append(f"  Hardcoded values:   {s['hardcoded_count']}")
    lines.append(f"  Duplicate groups:   {s['duplicate_groups']}")
    lines.append(f"  Orphans:            {s['orphan_count']}")
    lines.append("")
    
    # Registered tokens
    dims = [t for t in report.registered_tokens if t.kind == "dimension"]
    colors = [t for t in report.registered_tokens if t.kind == "color"]
    
    lines.append("-" * 70)
    lines.append(f"  DIMENSIONS ({len(dims)})")
    lines.append("-" * 70)
    lines.append(f"  {'Token':<25} {'Value':<10} {'Location':<20} {'Used'}")
    for t in sorted(dims, key=lambda x: x.name):
        loc = f"{t.file}:{t.line}"
        lines.append(f"  {t.name:<25} {t.value:<10} {loc:<20} {t.usage_count}x")
    lines.append("")
    
    lines.append("-" * 70)
    lines.append(f"  COLORS ({len(colors)})")
    lines.append("-" * 70)
    lines.append(f"  {'Token':<25} {'Value':<12} {'Location':<20} {'Used'}")
    for t in sorted(colors, key=lambda x: x.name):
        loc = f"{t.file}:{t.line}"
        lines.append(f"  {t.name:<25} {t.value:<12} {loc:<20} {t.usage_count}x")
    lines.append("")
    
    # Hardcoded
    if report.hardcoded_values:
        lines.append("-" * 70)
        lines.append(f"  HARDCODED VALUES ({len(report.hardcoded_values)})")
        lines.append("-" * 70)
        lines.append(f"  {'File':<25} {'Line':<6} {'Value':<12} {'Suggestion'}")
        for h in report.hardcoded_values[:20]:
            loc = f"{h.file}"
            lines.append(f"  {loc:<25} {h.line:<6} {h.value:<12} {h.suggestion_name}")
        if len(report.hardcoded_values) > 20:
            lines.append(f"  ... +{len(report.hardcoded_values) - 20} more")
        lines.append("")
    
    # Duplicates
    if report.duplicates:
        lines.append("-" * 70)
        lines.append(f"  DUPLICATE GROUPS ({len(report.duplicates)})")
        lines.append("-" * 70)
        for d in report.duplicates:
            lines.append(f"  Value: {d.value} ({d.kind})")
            for name, loc in zip(d.tokens, d.locations):
                lines.append(f"    - {name}  ({loc})")
        lines.append("")
    
    # Orphans
    if report.orphans:
        lines.append("-" * 70)
        lines.append(f"  ORPHANS — Registered but unused ({len(report.orphans)})")
        lines.append("-" * 70)
        for o in report.orphans:
            lines.append(f"  {o.name:<25} {o.value:<12} {o.file}:{o.line}")
        lines.append("")
    
    lines.append("=" * 70)
    return "\n".join(lines)


def format_markdown(report) -> str:
    """Markdown format."""
    lines = []
    lines.append("# ComposeBridge — Project Scan Report")
    lines.append("")
    s = report.summary()
    lines.append(f"- **Files scanned:** {s['files_scanned']}")
    lines.append(f"- **Duration:** {s['scan_duration_ms']} ms")
    lines.append(f"- **Registered tokens:** {s['registered_count']}")
    lines.append(f"- **Hardcoded values:** {s['hardcoded_count']}")
    lines.append(f"- **Duplicates:** {s['duplicate_groups']}")
    lines.append(f"- **Orphans:** {s['orphan_count']}")
    lines.append("")
    
    lines.append("## Registered Tokens")
    lines.append("")
    lines.append("| Token | Kind | Value | Location | Used |")
    lines.append("|-------|------|-------|----------|------|")
    for t in sorted(report.registered_tokens, key=lambda x: (x.kind, x.name)):
        lines.append(f"| {t.name} | {t.kind} | {t.value} | {t.file}:{t.line} | {t.usage_count}x |")
    lines.append("")
    
    if report.hardcoded_values:
        lines.append("## Hardcoded Values")
        lines.append("")
        lines.append("| File | Line | Value | Suggestion |")
        lines.append("|------|------|-------|------------|")
        for h in report.hardcoded_values:
            lines.append(f"| {h.file} | {h.line} | {h.value} | {h.suggestion_name} |")
        lines.append("")
    
    return "\n".join(lines)


def format_impact_report(report, token_filter=None) -> str:
    """Format impact analysis report."""
    lines = []
    lines.append("=" * 70)
    lines.append("  ComposeBridge — Token Impact Analysis")
    lines.append("=" * 70)
    lines.append("")
    
    impacts = report.token_impacts
    if token_filter:
        impacts = [i for i in impacts if i.token_name == token_filter]
    
    for impact in impacts:
        lines.append(f"🔑 {impact.token_name} = {impact.token_value} ({impact.token_kind})")
        lines.append(f"   Location: {impact.token_location}")
        lines.append(f"")
        
        if impact.total_impact == 0:
            lines.append(f"   ⚠️ Not used anywhere!")
        else:
            lines.append(f"   Used in {impact.total_impact} place(s):")
            for u in impact.usages:
                lines.append(f"   ├─ {u.file}:{u.line}")
                lines.append(f"   │    {u.line_content}")
                if u.enclosing_composable != "_unknown":
                    lines.append(f"   │    Inside: {u.enclosing_composable} ({u.enclosing_file}:{u.enclosing_line})")
                lines.append(f"   │")
            
            lines.append(f"")
            lines.append(f"   ⚠️ Impact: Changing this token will affect:")
            for comp in impact.affected_composables:
                lines.append(f"      - {comp}")
        
        lines.append("")
        lines.append("-" * 70)
        lines.append("")
    
    return "\n".join(lines)


def format_split_report(report) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("  ComposeBridge — Token Split Suggestions")
    lines.append("=" * 70)
    lines.append("")

    if not report.split_suggestions:
        lines.append("✅ لا توجد اقتراحات للفصل. جميع التوكنات تستخدم في سياق واحد.")
        return "\n".join(lines)

    for split in report.split_suggestions:
        lines.append(f"🔑 {split.token_name} = {split.token_value} ({split.token_kind})")
        lines.append(f"   Mixed contexts: {', '.join(split.contexts.keys())}")
        lines.append(f"   Suggestion:")
        for st in split.suggested_tokens:
            path = st.get("hierarchy_path", [])
            if path:
                lines.append(f"     - {st['name']}")
                lines.append(f"       Path: {' → '.join(path)}")
                lines.append(f"       Composables: {', '.join(set(u['enclosing_composable'] for u in st['usages']))}")
            else:
                composables = set(u['enclosing_composable'] for u in st['usages'])
                lines.append(f"     - {st['name']}  → {', '.join(composables)}")
        lines.append("")
        lines.append("-" * 70)
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Scan Compose project tokens")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--summary", action="store_true", help="Show only summary")
    parser.add_argument("--root", type=str, default=None, help="Project root")
    parser.add_argument("--token-report", action="store_true",
                        help="Show token impact analysis")
    parser.add_argument("--token", type=str, default=None,
                        help="Filter by token name")
    parser.add_argument("--suggest-splits", action="store_true",
                        help="اقتراح فصل التوكنات متعددة السياقات")
    parser.add_argument("--convention", action="store_true",
                        help="Detect project naming convention")
    parser.add_argument("--check-conflict", type=str, default=None,
                        help="Check for semantic conflict: 'token_name:value:type'")
    parser.add_argument("--patterns", action="store_true",
                        help="Detect repeated conditional patterns (e.g. if (isDark))")
    parser.add_argument("--set-root", type=str, default=None,
                        help="Set project root in .composebridge/config.json")
    parser.add_argument("--no-config", action="store_true",
                        help="Ignore .composebridge/config.json")
    args = parser.parse_args()
    
    if args.set_root:
        cfg_dir = Path.cwd() / ".composebridge"
        cfg_dir.mkdir(exist_ok=True)
        (cfg_dir / "config.json").write_text(
            json.dumps({"project_root": str(Path(args.set_root).resolve())}, indent=2),
            encoding="utf-8",
        )
        print(f"✅ Project root set to: {args.set_root}")
        return

    from core.project_root import get_project_root
    project_root = get_project_root(Path(args.root) if args.root else None, no_config=args.no_config)

    if args.patterns:
        from core.pattern_detector import PatternDetector
        detector = PatternDetector(project_root)
        detected = detector.detect()
        detected.sort(key=lambda p: len(p.occurrences), reverse=True)
        print("=" * 70)
        print("  ComposeBridge — Pattern Detection")
        print("=" * 70)
        print(f"Found {len(detected)} pattern(s):\n")
        for p in detected:
            print(f"🔍 Pattern: {p.template}")
            print(f"   Occurrences: {len(p.occurrences)}")
            print(f"   Suggested:   {p.suggested_token_name} = {p.suggested_token_value}")
            print(f"   Files:       {len(set(o.file for o in p.occurrences))} files")
            for occ in p.occurrences[:3]:
                print(f"     - {occ.file}:{occ.line}")
            if len(p.occurrences) > 3:
                print(f"     ... +{len(p.occurrences) - 3} more")
            print("-" * 70)
        return

    if args.check_conflict:
        parts = args.check_conflict.split(":")
        if len(parts) != 3:
            print("Usage: --check-conflict 'token_name:value:type'")
            return
        token_name, value, token_type = parts
        
        from core.token_migrator import TokenMigrator
        migrator = TokenMigrator(project_root)
        conflict = migrator.detect_semantic_conflict(token_name, token_type, value)
        
        if conflict:
            print(f"⚠️ Conflict detected: {conflict['type']}")
            print(f"   {conflict['message']}")
            
            if "safe_alternative" in conflict:
                print(f"\n✅ Recommended name: {conflict['safe_alternative']}")
            
            print(f"\n💡 Suggestions:")
            for s in conflict["suggestions"]:
                print(f"   - {s}")
        else:
            print("✅ No conflict detected.")
        return

    if args.convention:
        from core.token_migrator import TokenMigrator
        migrator = TokenMigrator(project_root)
        
        for token_type in ["dimension", "color"]:
            conv = migrator.detect_naming_convention(token_type)
            print(f"\n=== {token_type.upper()} Convention ===")
            print(f"  Style: {conv['style']}")
            print(f"  Examples: {', '.join(conv['examples'][:5])}")
            print(f"  Token files: {[str(f.name) for f in migrator.find_all_token_files(token_type)]}")
        return
    
    scanner = ProjectScanner(project_root)
    report = scanner.scan()
    
    if args.suggest_splits:
        print(format_split_report(report))
        return
    elif args.token_report:
        print(format_impact_report(report, args.token))
        return
    elif args.summary:
        print(json.dumps(report.summary(), indent=2))
    elif args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(format_markdown(report))
    else:
        print(format_text(report))
    
    # Save report to state dir
    state_dir = project_root / ".composebridge-state"
    state_dir.mkdir(exist_ok=True)
    (state_dir / "scan_report.json").write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
