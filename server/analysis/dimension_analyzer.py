# -*- coding: utf-8 -*-
"""
Dimension analysis and refactoring module.
Handles dp/sp dimensions, padding/size parameters, BridgeDimensionRegistry imports,
and global/element-level dimension adjustments.
"""

import os
import re
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Set, Any

try:
    from core.project_root import get_project_root
    PROJECT_ROOT = get_project_root()
except Exception:
    PROJECT_ROOT = Path(os.environ.get("COMPOSEBRIDGE_ROOT", "."))

from .ast_scope_resolver import (
    _clean_duplicate_imports,
    _find_file,
    _is_safe_compose_file,
    _validate_modified_file,
)

try:
    from common.file_ops import _atomic_write_text, _find_registry_file
except ImportError:
    try:
        from server.common.file_ops import _atomic_write_text, _find_registry_file
    except ImportError:
        from ..common.file_ops import _atomic_write_text, _find_registry_file

def _normalize_dim_value(val: str) -> List[str]:
    """
    Generate all possible representations of a dimension value.
    "24.0" -> ["24", "24.0", "24f", "24.0f"]
    "24.5" -> ["24.5", "24.5f"]
    """
    clean = str(val).replace(".dp", "").replace(".sp", "").strip()
    try:
        f = float(clean)
    except (ValueError, TypeError):
        return [clean]
    
    variants = []
    if f == int(f):
        int_val = int(f)
        variants.append(str(int_val))
        variants.append(f"{int_val}.0")
        variants.append(f"{int_val}f")
        variants.append(f"{int_val}.0f")
    else:
        variants.append(str(f))
        variants.append(f"{f}f")
    
    return variants


def _find_dimension_usage(project_root: Path, value: float, kind: str, kt_cache: Optional[List[Tuple[str, str]]] = None) -> Tuple[int, List[Dict]]:
    """ابحث عن كل استخدامات value.dp أو value.sp في المشروع مع مواقعها."""
    variants = _normalize_dim_value(str(value))
    count = 0
    locations = []
    
    if kt_cache is None:
        kt_cache = []
        for kt_file in project_root.rglob("*.kt"):
            if any(x in str(kt_file).lower() for x in ["build", "backup", ".composebridge", ".bak"]):
                continue
            try:
                kt_cache.append((str(kt_file.relative_to(project_root)).replace("\\", "/"), kt_file.read_text(encoding="utf-8")))
            except Exception:
                pass
                
    for rel_file, content in kt_cache:
        lines = content.splitlines()
        for line_idx, line in enumerate(lines, 1):
            found_in_line = False
            for variant in variants:
                pattern = rf'\b{re.escape(variant)}\.{kind}\b'
                matches = list(re.finditer(pattern, line))
                if matches:
                    count += len(matches)
                    if not found_in_line:
                        locations.append({
                            "file": rel_file,
                            "line": line_idx,
                            "property": "",
                        })
                        found_in_line = True
                        
    return count, locations


def _extract_dimensions_with_property(scope_text: str) -> List[Dict]:
    """
    Extract dimensions with their property (width, height, padding, etc.).
    Supports:
      1. Ternary + Registry: if (isDesktop) X.dp else BridgeDimensionRegistry.get("Key", Y.dp)
      2. Ternary normal: if (isDesktop) X.dp else Y.dp
      3. Direct Registry: BridgeDimensionRegistry.get("Key", X.dp)
      4. Simple: X.dp
    """
    dimensions = []
    processed_offsets = set()
    
    property_patterns = [
        ('height', r'\.height\('),
        ('width', r'\.width\('),
        ('size', r'\.size\('),
        ('cornerRadius', r'RoundedCornerShape\('),
        ('cornerRadius', r'cornerRadius\('),
        ('padding_horizontal', r'horizontal\s*=\s*'),
        ('padding_vertical', r'vertical\s*=\s*'),
        ('padding', r'\.padding\(\s*(?!horizontal|vertical)'),
        ('minHeight', r'\.heightIn\('),
        ('minWidth', r'\.widthIn\('),
        ('borderWidth', r'\.border\([^,]+,\s*'),
        ('fontSize', r'fontSize\s*=\s*'),
        ('letterSpacing', r'letterSpacing\s*=\s*'),
    ]
    
    for prop, prefix_pattern in property_patterns:
        for prefix_match in re.finditer(prefix_pattern, scope_text):
            prefix_end = prefix_match.end()
            rel_off = prefix_match.start()
            
            if rel_off in processed_offsets:
                continue
                
            snippet = scope_text[prefix_end:prefix_end + 200]
            depth = scope_text[:rel_off].count('{') - scope_text[:rel_off].count('}')
            
            # 1. Ternary + Registry
            reg_ternary_match = re.match(
                r'\s*if\s*\([^)]+\)\s*(\d+(?:\.\d+)?)\.(dp|sp)\s*else\s*BridgeDimensionRegistry\.get\(\s*"([^"]+)"\s*,\s*(\d+(?:\.\d+)?)\.(dp|sp)',
                snippet,
            )
            if reg_ternary_match:
                desktop_val = float(reg_ternary_match.group(1))
                registry_key = reg_ternary_match.group(3)
                mobile_val = float(reg_ternary_match.group(4))
                kind = reg_ternary_match.group(5)
                mob_str = str(int(mobile_val)) if mobile_val.is_integer() else str(mobile_val)
                dimensions.append({
                    "property": prop,
                    "value": f"{mob_str}.{kind}",
                    "number": mobile_val,
                    "kind": kind,
                    "relative_offset": rel_off,
                    "depth": depth,
                    "is_ternary": True,
                    "desktop_value": desktop_val,
                    "mobile_value": mobile_val,
                    "platform_target": "mobile",
                    "registry_key": registry_key,
                    "is_registry_wrapped": True,
                })
                processed_offsets.add(rel_off)
                continue
                
            # 2. Ternary normal
            ternary_match = re.match(
                r'\s*if\s*\([^)]+\)\s*(\d+(?:\.\d+)?)\.(dp|sp)\s*else\s*(\d+(?:\.\d+)?)\.(dp|sp)',
                snippet,
            )
            if ternary_match:
                desktop_val = float(ternary_match.group(1))
                mobile_val = float(ternary_match.group(3))
                kind = ternary_match.group(4)
                mob_str = str(int(mobile_val)) if mobile_val.is_integer() else str(mobile_val)
                dimensions.append({
                    "property": prop,
                    "value": f"{mob_str}.{kind}",
                    "number": mobile_val,
                    "kind": kind,
                    "relative_offset": rel_off,
                    "depth": depth,
                    "is_ternary": True,
                    "desktop_value": desktop_val,
                    "mobile_value": mobile_val,
                    "platform_target": "mobile",
                    "registry_key": "",
                    "is_registry_wrapped": False,
                })
                processed_offsets.add(rel_off)
                continue
                
            # 3. Direct Registry
            reg_match = re.match(
                r'\s*BridgeDimensionRegistry\.get\(\s*"([^"]+)"\s*,\s*(\d+(?:\.\d+)?)\.(dp|sp)',
                snippet,
            )
            if reg_match:
                registry_key = reg_match.group(1)
                mobile_val = float(reg_match.group(2))
                kind = reg_match.group(3)
                mob_str = str(int(mobile_val)) if mobile_val.is_integer() else str(mobile_val)
                dimensions.append({
                    "property": prop,
                    "value": f"{mob_str}.{kind}",
                    "number": mobile_val,
                    "kind": kind,
                    "relative_offset": rel_off,
                    "depth": depth,
                    "is_ternary": False,
                    "mobile_value": mobile_val,
                    "registry_key": registry_key,
                    "is_registry_wrapped": True,
                })
                processed_offsets.add(rel_off)
                continue
                
            # 4. Simple literal
            simple_match = re.match(
                r'\s*(\d+(?:\.\d+)?)\.(dp|sp)',
                snippet,
            )
            if simple_match:
                val = float(simple_match.group(1))
                kind = simple_match.group(2)
                val_str = str(int(val)) if val.is_integer() else str(val)
                dimensions.append({
                    "property": prop,
                    "value": f"{val_str}.{kind}",
                    "number": val,
                    "kind": kind,
                    "relative_offset": rel_off,
                    "depth": depth,
                    "is_ternary": False,
                    "mobile_value": val,
                    "registry_key": "",
                    "is_registry_wrapped": False,
                })
                processed_offsets.add(rel_off)
                continue
                
    dimensions.sort(key=lambda x: x.get("relative_offset", 0))
    seen = set()
    unique = []
    for d in dimensions:
        key = (d["property"], d["value"], d.get("relative_offset", 0))
        if key not in seen:
            seen.add(key)
            unique.append(d)
    
    return unique


def _ensure_bridge_dimension_registry_import(
    file_path: Path,
    project_root: Optional[Path] = None,
) -> Tuple[bool, int]:
    """
    تأكد من وجود import BridgeDimensionRegistry.
    Returns (was_added, line_number).
    """
    content = file_path.read_text(encoding="utf-8")
    
    import_stmt = "import com.composebridge.agent.BridgeDimensionRegistry"
    
    # ⭐ افحص إذا موجود
    if import_stmt in content:
        return False, -1
    
    # ⭐ لا يوجد — أضف
    lines = content.splitlines()
    
    # ابحث عن آخر import أو package
    last_import_idx = -1
    package_idx = -1
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('package '):
            package_idx = i
        elif stripped.startswith('import '):
            last_import_idx = i
    
    # ⭐ الموقع الصحيح للإدراج
    if last_import_idx >= 0:
        insert_idx = last_import_idx + 1
        lines.insert(insert_idx, import_stmt)
        inserted_line = insert_idx + 1
    elif package_idx >= 0:
        insert_idx = package_idx + 1
        lines.insert(insert_idx, "")
        lines.insert(insert_idx + 1, import_stmt)
        inserted_line = insert_idx + 2
    else:
        insert_idx = 0
        lines.insert(insert_idx, import_stmt)
        inserted_line = insert_idx + 1
    
    new_content = "\n".join(lines)
    if not new_content.endswith("\n"):
        new_content += "\n"
    
    file_path.write_text(new_content, encoding="utf-8")
    
    return True, inserted_line


def global_dimension_edit(
    value: float,
    kind: str,  # "dp" | "sp"
    new_value: float,
    project_root: Path,
    property_name: Optional[str] = None,
) -> Dict:
    """
    Global: wrap in BridgeDimensionRegistry.get + update all occurrences.
    """
    from core.pattern_journal import PatternJournal
    
    val_num = float(value)
    val_int = int(val_num) if val_num.is_integer() else val_num
    variants = _normalize_dim_value(str(value))
    journal = PatternJournal(project_root)
    
    count = 0
    files_affected = set()
    errors = []
    
    try:
        new_val_num = float(new_value)
        new_val_str = str(int(new_val_num)) if new_val_num.is_integer() else str(new_val_num)
    except Exception:
        new_val_str = str(new_value)
    
    for kt_file in project_root.rglob("*.kt"):
        if any(x in str(kt_file).lower() for x in ["build", "backup", ".composebridge", ".bak"]):
            continue
        
        try:
            content = kt_file.read_text(encoding="utf-8")
            lines = content.splitlines()
            new_lines = []
            file_changed = False
            file_changes_to_record = []
            
            for line_idx, line in enumerate(lines, 1):
                old_l = line
                new_l = old_l
                
                # First: if already wrapped in BridgeDimensionRegistry.get, update it
                if 'BridgeDimensionRegistry.get' in new_l:
                    p_reg = rf'(BridgeDimensionRegistry\.get\(\s*"(?:global_[^"]+_{re.escape(str(val_int))}|global_[^"]+_{re.escape(str(value))})"\s*,\s*)[^)]+(\))'
                    if re.search(p_reg, new_l):
                        new_l = re.sub(p_reg, rf'\g<1>{new_val_str}.{kind}\g<2>', new_l)
                
                if new_l == old_l:
                    # Target property determination
                    # 1. RoundedCornerShape / cornerRadius
                    if property_name in (None, "cornerRadius", "shape"):
                        for variant in variants:
                            p_rcs = rf'(\b(?:RoundedCornerShape|cornerRadius)\(\s*)((?:if\s*\([^)]+\)\s*\d+(?:\.\d+)?\.(?:dp|sp)\s*else\s+)?)({re.escape(variant)}\.(?:dp|sp))(\s*\))'
                            if re.search(p_rcs, new_l):
                                reg_key = f"global_cornerRadius_{val_int}"
                                new_l = re.sub(p_rcs, rf'\g<1>\g<2>BridgeDimensionRegistry.get("{reg_key}", {new_val_str}.{kind})\g<4>', new_l)
                                break
                    
                    # 2. Modifiers: height, width, size, padding
                    if new_l == old_l:
                        mod_props = [property_name] if property_name in ['height', 'width', 'size', 'padding'] else ['height', 'width', 'size', 'padding']
                        for prop in mod_props:
                            if prop and (property_name is None or property_name == prop):
                                for variant in variants:
                                    p_mod = rf'(\.{prop}\(\s*)((?:if\s*\([^)]+\)\s*\d+(?:\.\d+)?\.(?:dp|sp)\s*else\s+)?)({re.escape(variant)}\.(?:dp|sp))(\s*\))'
                                    if re.search(p_mod, new_l):
                                        reg_key = f"global_{prop}_{val_int}"
                                        new_l = re.sub(p_mod, rf'\g<1>\g<2>BridgeDimensionRegistry.get("{reg_key}", {new_val_str}.{kind})\g<4>', new_l)
                                        break
                                if new_l != old_l:
                                    break
                    
                    # 3. Named parameters: horizontal, vertical, start, end, top, bottom
                    if new_l == old_l:
                        named_props = ['horizontal', 'vertical', 'start', 'end', 'top', 'bottom']
                        for prop in named_props:
                            if property_name is None or prop in property_name:
                                for variant in variants:
                                    p_named = rf'(\b{prop}\s*=\s*)((?:if\s*\([^)]+\)\s*\d+(?:\.\d+)?\.(?:dp|sp)\s*else\s+)?)({re.escape(variant)}\.(?:dp|sp))'
                                    if re.search(p_named, new_l):
                                        reg_key = f"global_{prop}_{val_int}"
                                        new_l = re.sub(p_named, rf'\g<1>\g<2>BridgeDimensionRegistry.get("{reg_key}", {new_val_str}.{kind})', new_l)
                                        break
                                if new_l != old_l:
                                    break
                    
                    # 4. Fallback: if property_name is explicitly given or line contains variant.kind
                    if new_l == old_l and property_name is not None:
                        for variant in variants:
                            p_fallback = rf'((?:else\s+)?)({re.escape(variant)}\.{kind}\b)'
                            if re.search(p_fallback, new_l):
                                reg_key = f"global_{property_name}_{val_int}"
                                new_l = re.sub(p_fallback, rf'\g<1>BridgeDimensionRegistry.get("{reg_key}", {new_val_str}.{kind})', new_l, count=1)
                                break

                if new_l != old_l:
                    file_changed = True
                    file_changes_to_record.append((line_idx, old_l, new_l))
                    count += 1
                new_lines.append(new_l)
            
            if file_changed:
                kt_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                rel_file = str(kt_file.relative_to(project_root)).replace("\\", "/")
                
                for l_idx, old_line_str, new_line_str in file_changes_to_record:
                    journal.record_change(
                        file=rel_file,
                        line=l_idx,
                        old_line=old_line_str,
                        new_line=new_line_str,
                        pattern_id=f"global_dim_{val_int}{kind}",
                    )
                
                content = kt_file.read_text(encoding="utf-8")
                if "BridgeDimensionRegistry.get" in content:
                    was_added, import_line = _ensure_bridge_dimension_registry_import(
                        file_path=kt_file,
                        project_root=project_root,
                    )
                    if was_added:
                        journal.record_change(
                            file=rel_file,
                            line=import_line,
                            old_line="",
                            new_line="import com.composebridge.agent.BridgeDimensionRegistry",
                            pattern_id=f"import_bridge_dim_global_{val_int}",
                        )
                    _clean_duplicate_imports(kt_file)
                
                files_affected.add(rel_file)
        
        except Exception as e:
            errors.append({"file": str(kt_file), "error": str(e)})
    
    return {
        "success": True,
        "value": value,
        "kind": kind,
        "new_value": new_val_str,
        "property": property_name or "dimension",
        "registry_key": f"global_{property_name or 'dimension'}_{val_int}",
        "replaced_count": count,
        "files_affected": len(files_affected),
        "errors": errors,
    }


def split_dimension_edit(
    value: float,
    kind: str,
    new_value: float,
    element_file: str,
    element_line: int,
    project_root: Path,
) -> Dict:
    """
    Split: edit only in this element (single line).
    """
    from core.pattern_journal import PatternJournal
    
    file_path = project_root / element_file
    if not file_path.exists():
        matches = [m for m in project_root.rglob(Path(element_file).name)
                   if "build" not in str(m) and ".bak" not in str(m)]
        if not matches:
            return {"success": False, "error": f"File not found: {element_file}"}
        file_path = matches[0]
    
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    
    if element_line > len(lines):
        return {"success": False, "error": "Line out of range"}
    
    target_idx = element_line - 1
    old_line = lines[target_idx]
    variants = _normalize_dim_value(str(value))
    
    try:
        new_val_num = float(new_value)
        new_val_str = str(int(new_val_num)) if new_val_num.is_integer() else str(new_val_num)
    except Exception:
        new_val_str = str(new_value)
    
    new_line = old_line
    for variant in variants:
        pattern = rf'\b{re.escape(variant)}(?=\.{kind}\b)'
        if re.search(pattern, old_line):
            new_line = re.sub(pattern, new_val_str, old_line, count=1)
            break
            
    if new_line == old_line:
        for variant in variants:
            if variant in old_line:
                new_line = old_line.replace(variant, new_val_str, 1)
                break
    
    if new_line == old_line:
        return {
            "success": False,
            "error": f"Could not find {value}.{kind} in line {element_line}",
        }
    
    lines[target_idx] = new_line
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    
    journal = PatternJournal(project_root)
    rel_file = str(file_path.relative_to(project_root)).replace("\\", "/")
    journal.record_change(
        file=rel_file,
        line=element_line,
        old_line=old_line,
        new_line=new_line,
        pattern_id=f"split_dim_{value}{kind}",
    )

    if "BridgeDimensionRegistry.get" in new_line or "BridgeDimensionRegistry.get" in file_path.read_text(encoding="utf-8"):
        was_added, import_line = _ensure_bridge_dimension_registry_import(
            file_path=file_path,
            project_root=project_root,
        )
        if was_added:
            journal.record_change(
                file=rel_file,
                line=import_line,
                old_line="",
                new_line="import com.composebridge.agent.BridgeDimensionRegistry",
                pattern_id=f"import_bridge_dim_{value}{kind}",
            )
        _clean_duplicate_imports(file_path)
    
    return {
        "success": True,
        "file": str(file_path.relative_to(project_root)),
        "line": element_line,
        "replaced_count": 1,
    }

