# -*- coding: utf-8 -*-
"""
Dimension edit application handler.
Applies surgical regex/AST edits to dimension references in Kotlin sources.
"""

import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from core.pattern_journal import PatternJournal
from core.project_root import get_project_root
from analysis.dimension_analyzer import _normalize_dim_value
from handlers.kotlin_validation import (
    _validate_kotlin_line,
    _clean_duplicate_modifier,
    _ensure_bridge_dimension_registry_import,
    _clean_duplicate_imports,
    _validate_modified_file,
)
from network.ws_server import log_info, log_error

def _apply_dimension_edit(edit: dict, project_root: Path) -> dict:
    """Apply dimension edit at specific line with PatternJournal recording."""
    from core.pattern_journal import PatternJournal
    import re
    
    file_rel = edit.get("file")
    line = edit.get("line", 0)
    property_name = edit.get("property", "")
    old_value = str(edit.get("old_value", "")).replace(".dp", "").replace(".sp", "").strip()
    new_value = str(edit.get("new_value", "")).replace(".dp", "").replace(".sp", "").strip()
    
    if not file_rel or line < 1:
        return {"success": False, "error": "Invalid file/line"}
    
    file_path = project_root / file_rel
    if not file_path.exists():
        matches = [m for m in project_root.rglob(Path(file_rel).name) 
                   if "build" not in str(m) and ".composebridge" not in str(m) 
                   and "backup" not in str(m).lower()]
        if not matches:
            return {"success": False, "error": f"File not found: {file_rel}"}
        file_path = matches[0]
    
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        if line > len(lines):
            return {"success": False, "error": f"Line {line} out of range"}
        
        target_idx = line - 1
        
        try:
            num = float(new_value)
            new_val_str = str(int(num)) if num.is_integer() else str(num)
        except Exception:
            new_val_str = new_value

        from core.source_analyzer import _normalize_dim_value
        old_val_variants = _normalize_dim_value(old_value)
        is_ternary = edit.get("is_ternary", False)
        registry_key = str(edit.get("registry_key", "")).strip()
        kind = edit.get("dimension_kind", "dp")

        # 0. Check if target_idx itself is a match
        found_idx = -1
        exact_line = lines[target_idx]
        has_val = any(re.search(rf'\b{re.escape(v)}\.(?:dp|sp)\b', exact_line) for v in old_val_variants)
        has_prop = (property_name in exact_line) if property_name else False

        if has_val:
            found_idx = target_idx
        elif has_prop and ("BridgeDimensionRegistry" in exact_line or re.search(r'\d+(?:\.\d+)?\.(?:dp|sp)\b', exact_line)):
            found_idx = target_idx

        # Search range ±5 lines if not directly at target_idx
        if found_idx < 0:
            search_range = range(
                max(0, target_idx - 5),
                min(len(lines), target_idx + 6),
            )
            # 1. First: line that matches property and old value
            for i in search_range:
                content_line = lines[i]
                prop_matches = False
                if property_name == "padding_horizontal" and "horizontal" in content_line:
                    prop_matches = True
                elif property_name == "padding_vertical" and "vertical" in content_line:
                    prop_matches = True
                elif property_name and property_name in content_line:
                    prop_matches = True
                
                if prop_matches:
                    for variant in old_val_variants:
                        if re.search(rf'\b{re.escape(variant)}\.(?:dp|sp)\b', content_line):
                            found_idx = i
                            break
                    if found_idx >= 0:
                        break

            # 2. Second: line that matches property and BridgeDimensionRegistry
            if found_idx < 0:
                for i in search_range:
                    content_line = lines[i]
                    if property_name and property_name in content_line and "BridgeDimensionRegistry" in content_line:
                        found_idx = i
                        break

            # 3. Third: line that matches old value with dp/sp
            if found_idx < 0:
                for i in search_range:
                    content_line = lines[i]
                    for variant in old_val_variants:
                        if re.search(rf'\b{re.escape(variant)}\.(?:dp|sp)\b', content_line):
                            found_idx = i
                            break
                    if found_idx >= 0:
                        break

        if found_idx < 0:
            return {
                "success": False,
                "error": f"Could not find line for {property_name}={old_value}",
                "search_range": f"{target_idx-5}..{target_idx+5}",
            }

        target_idx = found_idx
        actual_line = target_idx + 1
        old_line = lines[target_idx]
        new_line = old_line

        replaced = False

        # 1. If already wrapped in registry with this exact key, update value inside
        if registry_key and f'BridgeDimensionRegistry.get("{registry_key}"' in old_line:
            new_line = re.sub(
                rf'BridgeDimensionRegistry\.get\(\s*"{re.escape(registry_key)}"\s*,\s*[^)]+\)',
                f'BridgeDimensionRegistry.get("{registry_key}", {new_val_str}.{kind})',
                old_line,
                count=1,
            )
            replaced = new_line != old_line

        # 2. Precise regex matching for property named parameter (e.g. padding_vertical, vertical, padding_horizontal, horizontal, top, etc.)
        if not replaced and property_name:
            prop_kws = [property_name]
            if property_name.startswith("padding_"):
                prop_kws.append(property_name.replace("padding_", ""))
            if "vertical" in property_name:
                prop_kws.extend(["vertical", "padding_vertical"])
            if "horizontal" in property_name:
                prop_kws.extend(["horizontal", "padding_horizontal"])
            for kw in ("start", "end", "top", "bottom", "width", "height", "size"):
                if kw in property_name:
                    prop_kws.append(kw)
            prop_pattern = '|'.join(map(re.escape, sorted(set(prop_kws), key=len, reverse=True)))

            # 2a. Check if already wrapped for this property keyword (e.g. vertical = BridgeDimensionRegistry.get(...))
            already_m = re.search(rf'(\b(?:{prop_pattern})\s*=\s*)BridgeDimensionRegistry\.get\(\s*"([^"]+)"\s*,\s*[^)]+\)', old_line)
            if already_m:
                key_to_use = registry_key or already_m.group(2)
                new_line = re.sub(
                    rf'(\b(?:{prop_pattern})\s*=\s*)BridgeDimensionRegistry\.get\(\s*"([^"]+)"\s*,\s*[^)]+\)',
                    rf'\g<1>BridgeDimensionRegistry.get("{key_to_use}", {new_val_str}.{kind})',
                    old_line,
                    count=1,
                )
                replaced = new_line != old_line

            # 2b. Wrap named parameter: e.g. vertical = 8.dp
            if not replaced:
                named_m = re.search(rf'(\b(?:{prop_pattern})\s*=\s*)(\d+(?:\.\d+)?\.(?:dp|sp)\b)', old_line)
                if named_m:
                    repl_val = (
                        f'BridgeDimensionRegistry.get("{registry_key}", {new_val_str}.{kind})'
                        if registry_key
                        else f'{new_val_str}.{kind}'
                    )
                    new_line = re.sub(
                        rf'(\b(?:{prop_pattern})\s*=\s*)(\d+(?:\.\d+)?\.(?:dp|sp)\b)',
                        rf'\g<1>{repl_val}',
                        old_line,
                        count=1,
                    )
                    replaced = new_line != old_line

        # 3. Fallback: try replacing matching old value variant
        if not replaced:
            for variant in old_val_variants:
                pattern = rf'(\b{re.escape(variant)})(\.(?:dp|sp)\b)'
                if re.search(pattern, old_line):
                    repl_str = (
                        f'BridgeDimensionRegistry.get("{registry_key}", {new_val_str}.{kind})'
                        if registry_key
                        else f'{new_val_str}.{kind}'
                    )
                    new_line = re.sub(pattern, repl_str, old_line, count=1)
                    replaced = True
                    break

        # 4. Fallback: search full pattern prefix
        if not replaced:
            pattern = rf'(\.\w+\s*\(\s*|\b\w+\s*=\s*)(\d+(?:\.\d+)?\.(?:dp|sp))(\s*\)?)'
            def _repl(m):
                prefix = m.group(1)
                suffix = m.group(3)
                val = (
                    f'BridgeDimensionRegistry.get("{registry_key}", {new_val_str}.{kind})'
                    if registry_key
                    else f'{new_val_str}.{kind}'
                )
                return f'{prefix}{val}{suffix}'

            new_line = re.sub(pattern, _repl, old_line, count=1)
            replaced = new_line != old_line

        if not replaced:
            return {
                "success": False,
                "error": f"Could not replace in line {line}",
                "line_content": old_line.strip(),
            }

        # Clean duplicate modifier in line
        new_line = _clean_duplicate_modifier(new_line)

        # ⭐ 5. Validate Kotlin line before writing
        is_valid, error = _validate_kotlin_line(new_line)
        if not is_valid:
            return {
                "success": False,
                "error": f"Invalid Kotlin: {error}",
                "new_line": new_line,
            }

        # Clean up any leftover duplicate modifier line if previous line is duplicated
        if target_idx > 0 and "modifier =" in lines[target_idx - 1] and "modifier =" in new_line:
            prev_line = lines[target_idx - 1].strip()
            if "BridgeDimensionRegistry" not in prev_line and "modifier = Modifier.size" in prev_line:
                lines.pop(target_idx - 1)
                target_idx -= 1
                actual_line = target_idx + 1

        lines[target_idx] = new_line
        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        journal = PatternJournal(project_root)
        try:
            rel_file = str(file_path.relative_to(project_root)).replace("\\", "/")
        except Exception:
            rel_file = file_rel

        journal.record_change(
            file=rel_file,
            line=actual_line,
            old_line=old_line,
            new_line=new_line,
            pattern_id=f"dimension_{property_name}_{actual_line}",
        )

        # ⭐ تأكد من import
        was_added, import_line = _ensure_bridge_dimension_registry_import(
            file_path=file_path,
            project_root=project_root,
        )

        if was_added:
            # ⭐ سجّل في Journal
            journal.record_change(
                file=rel_file,
                line=import_line,
                old_line="",
                new_line="import com.composebridge.agent.BridgeDimensionRegistry",
                pattern_id=f"import_bridge_dim_{registry_key}",
            )
            log_info(f"[DIMENSION] Added BridgeDimensionRegistry import to {file_path.name}")

        _clean_duplicate_imports(file_path)

        final_content = file_path.read_text(encoding="utf-8")
        is_file_valid, file_err = _validate_modified_file(file_path, final_content)
        if not is_file_valid:
            log_error(f"[DIMENSION] File validation warning: {file_err}")

        return {
            "success": True,
            "file": rel_file,
            "line": actual_line,
            "old": old_value,
            "new": new_val_str,
            "property": property_name,
            "registry_key": registry_key,
            "wrapped_in_registry": bool(registry_key),
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()[:500],
        }

