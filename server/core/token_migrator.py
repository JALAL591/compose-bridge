# -*- coding: utf-8 -*-
"""
منسق ترحيل القيم إلى توكنز (Token Migrator Coordinator) لخادم ComposeBridge.
Coordinates replacing hardcoded values with design tokens, creating tokens, and modifying AST.
"""

import re
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from core.token.naming_advisor import NamingAdvisorMixin, CONTEXT_RULES, COLOR_CONTEXT_RULES
from core.token.import_injector import ImportInjectorMixin

# -*- coding: utf-8 -*-
"""
Token Migrator — Convert hardcoded values to design tokens.

Safety:
- Uses filelock for cross-process safety
- Verifies token_name doesn't exist
- Verifies line contains expected value
- Backup before edit
- Only modifies the specified line
"""

import re
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from datetime import datetime

try:
    from common.file_ops import _atomic_write_text, _find_registry_file, is_ignored_path, assert_inside
except ImportError:
    try:
        from server.common.file_ops import _atomic_write_text, _find_registry_file, is_ignored_path, assert_inside
    except ImportError:
        from ..common.file_ops import _atomic_write_text, _find_registry_file, is_ignored_path, assert_inside
from .write_lock import acquire_write_lock





class TokenMigrator(NamingAdvisorMixin, ImportInjectorMixin):
    """
    منسق ترحيل القيم المكررة واستبدالها بتوكنز في نظام التصميم.
    Coordinates migrating raw hardcoded values into Design System tokens.
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.state_dir = project_root / ".composebridge-state"
        self.state_dir.mkdir(exist_ok=True)
        self.backup_dir = self.state_dir / "migration_backups"
        self.backup_dir.mkdir(exist_ok=True)
        from .state_events import EventLog
        self.events = EventLog(self.state_dir / "events.jsonl")
        self.package_name = self.detect_package_name(self.project_root)

    def detect_package_name(self, project_root: Path) -> str:
        """
        Detect the project's package name.
        
        Priority:
        1. From AndroidManifest.xml (package="...")
        2. From build.gradle.kts (namespace = "...")
        3. From first .kt file's package declaration
        """
        # Try AndroidManifest.xml
        for manifest in project_root.rglob("AndroidManifest.xml"):
            if is_ignored_path(manifest, project_root):
                continue
            try:
                content = manifest.read_text(encoding="utf-8")
                match = re.search(r'package="([^"]+)"', content)
                if match:
                    return match.group(1)
            except Exception:
                pass
        
        # Try build.gradle.kts
        for gradle in project_root.rglob("build.gradle.kts"):
            if is_ignored_path(gradle, project_root):
                continue
            try:
                content = gradle.read_text(encoding="utf-8")
                match = re.search(r'namespace\s*=\s*"([^"]+)"', content)
                if match:
                    return match.group(1)
            except Exception:
                pass
        
        # Try first .kt file
        for kt in project_root.rglob("*.kt"):
            if is_ignored_path(kt, project_root):
                continue
            try:
                content = kt.read_text(encoding="utf-8")
                match = re.search(r'^\s*package\s+([\w.]+)', content, re.MULTILINE)
                if match:
                    return match.group(1)
            except Exception:
                pass
        
        return "com.example.app"  # fallback
    
    def _find_registry_file(self, token_type: str) -> Optional[Path]:
        """
        Find the file where tokens are stored.
        
        Priority:
        1. AppDimens.kt / AppColors.kt (Standard Design System style)
        2. Theme.kt / Color.kt / Dimens.kt (standard Compose)
        3. Any file with 'val .*Color' pattern
        4. None (needs creation)
        """
        candidates = {
            "dimension": ["AppDimens.kt", "DesignSystem.kt", "Dimens.kt", "Dimensions.kt", "Theme.kt"],
            "color": ["AppColors.kt", "DesignSystem.kt", "Color.kt", "Colors.kt", "Theme.kt"],
        }

        def _rank(p):
            norm = str(p).replace("\\", "/").lower()
            if "/commonmain/" in norm: return 0
            if "/main/" in norm: return 1
            if "/src/" in norm: return 2
            return 3

        for name in candidates.get(token_type, []):
            found = _find_registry_file(name, self.project_root)
            if found and not is_ignored_path(found, self.project_root):
                return found
            matches = [f for f in self.project_root.rglob(name) if not is_ignored_path(f, self.project_root)]
            if matches:
                matches.sort(key=lambda p: (_rank(p), len(str(p))))
                return matches[0]

        # Fallback: search for patterns
        if token_type == "color":
            pattern = re.compile(r'val\s+\w+\s*[:=].*Color\(')
        else:
            pattern = re.compile(r'val\s+\w+\s*[:=].*\.dp')

        matches = []
        for kt in self.project_root.rglob("*.kt"):
            if is_ignored_path(kt, self.project_root):
                continue
            try:
                content = kt.read_text(encoding="utf-8")
                if pattern.search(content):
                    matches.append(kt)
            except Exception:
                continue
        if matches:
            matches.sort(key=lambda p: (_rank(p), len(str(p))))
            return matches[0]

        return None

    def _find_design_system(self) -> Optional[Path]:
        """Find the DesignSystem.kt, AppColors.kt, or mapped design file in the project."""
        try:
            from analysis.universal_scanner import resolve_target_design_file
            target, _ = resolve_target_design_file("color", self.project_root)
            if target and target.exists():
                return target
        except Exception:
            pass
        return self._find_registry_file("color")

    def create_color_token(
        self,
        token_name: str,
        value_expr: str,              # new value (لـ Registry override)
        original_value: str = None,   # default في DesignSystem
    ) -> Dict:
        """
        Create a color token safely.
        
        CRITICAL: Ensure clean Kotlin syntax.
        - Normalize hex → Color(0xAARRGGBB)
        - Ensure single set of parentheses
        - Validate token_name (Kotlin identifier)
        """
        try:
            with acquire_write_lock():
                # ⭐ 1. Validate token_name — Kotlin identifier
                if not re.match(r'^[A-Za-z][A-Za-z0-9_]*$', token_name):
                    return {
                        "success": False,
                        "error": f"Invalid token name: '{token_name}' (must be a valid Kotlin identifier)",
                    }
            
                # ⭐ 2. Normalize values
                def _normalize(val: str) -> str:
                    """Return clean 'Color(0xAARRGGBB)' or 'Color.Name'."""
                    if not val:
                        return "Color.Transparent"
                    val = val.strip()
                
                    # Already clean
                    if val.startswith("Color."):
                        return val
                
                    # Color(0x...) — ensure single parens
                    if val.startswith("Color("):
                        match = re.search(r'0x([0-9A-Fa-f]+)', val)
                        if not match:
                            return "Color.Transparent"
                        hex_str = match.group(1).upper()
                    elif val.startswith("0x") or val.startswith("0X"):
                        hex_str = val[2:].upper()
                    elif val.startswith("#"):
                        hex_str = val[1:].upper()
                    else:
                        hex_str = val.upper()
                
                    # Ensure 8 chars (ARGB)
                    if len(hex_str) == 6:
                        hex_str = "FF" + hex_str
                    elif len(hex_str) == 3:
                        hex_str = "FF" + "".join(c * 2 for c in hex_str)
                    elif len(hex_str) != 8:
                        return "Color.Transparent"
                
                    return f"Color(0x{hex_str})"
            
                default_expr = _normalize(original_value) if original_value else _normalize(value_expr)
                override_expr = _normalize(value_expr)
            
                # ⭐ 3. Find DesignSystem.kt
                design_system = self._find_design_system()
                if not design_system or not design_system.exists():
                    return {
                        "success": False,
                        "error_code": "NEEDS_MANUAL_MAPPING",
                        "error": "NEEDS_MANUAL_MAPPING: No design system file found. Use set_design_file_mapping to configure it.",
                    }
            
                content = design_system.read_text(encoding="utf-8")
            
                # ⭐ 4. Check if token exists
                if re.search(rf'\bval\s+{re.escape(token_name)}\b', content):
                    return {
                        "success": True,
                        "already_existed": True,
                        "token_name": token_name,
                        "default_value": default_expr,
                        "override_value": override_expr,
                        "file": str(design_system.relative_to(self.project_root)),
                    }
            
                # ⭐ 5. Find object AppColors
                match = re.search(r'object\s+AppColors\s*\{', content)
                if not match:
                    return {
                        "success": False,
                        "error_code": "NEEDS_MANUAL_MAPPING",
                        "error": "NEEDS_MANUAL_MAPPING: 'object AppColors' not found in design file. Configure an appropriate registry file using set_design_file_mapping.",
                    }
            
                # ⭐ 6. Build CLEAN token line
                token_line = (
                    f'    val {token_name}: Color get() = '
                    f'BridgeThemeRegistry.getColor("{token_name}", {default_expr})'
                )
            
                # ⭐ 7. Validate token_line with helper
                is_valid, error = self._validate_kotlin_syntax(token_line)
                if not is_valid:
                    return {
                        "success": False,
                        "error": f"Generated invalid Kotlin: {error}",
                        "generated_line": token_line,
                    }
            
                # ⭐ 8. Insert after object AppColors {
                insert_pos = match.end()
                newline_pos = content.find('\n', insert_pos)
                if newline_pos < 0:
                    return {"success": False, "error": "Invalid DesignSystem structure"}
            
                # ⭐ 9. Build new content
                new_content = (
                    content[:newline_pos + 1]
                    + token_line + '\n'
                    + content[newline_pos + 1:]
                )
            
                # ⭐ 10. VALIDATE final syntax
                if ')))' in new_content:
                    return {
                        "success": False,
                        "error": "Generated content has malformed parens",
                        "generated_line": token_line,
                    }
            
                # ═══ Safe Backup of DesignSystem Before Adding Token ═══
                try:
                    from core.ast_finder import safe_create_backup
                    safe_create_backup(design_system, project_root=self.project_root)
                except Exception:
                    pass

                # ⭐ 11. Journal (for rollback)
                try:
                    try:
                        from core.pattern_journal import PatternJournal
                    except ImportError:
                        from .pattern_journal import PatternJournal
                    journal = PatternJournal(self.project_root)
                    journal.record_change(
                        file=str(design_system.relative_to(self.project_root)),
                        line=content[:newline_pos + 1].count('\n') + 1,
                        old_line="",
                        new_line=token_line,
                        pattern_id=f"create_token_{token_name}",
                    )
                except Exception as e:
                    import logging
                    logging.error(f"[TOKEN_MIGRATOR] Journal record failed: {e}")
            
                # ⭐ 12. Write
                _atomic_write_text(design_system, new_content)
            
                return {
                    "success": True,
                    "token_name": token_name,
                    "default_value": default_expr,
                    "override_value": override_expr,
                    "token_line": token_line,
                    "file": str(design_system.relative_to(self.project_root)),
                }
        
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }

    @staticmethod
    def _validate_kotlin_syntax(token_line: str) -> Tuple[bool, str]:
        """
        Basic sanity check for Kotlin token declaration syntax.
        Returns (is_valid, error_message).
        """
        pattern = r'^\s*val\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*Color\s+get\(\)\s*=\s*.+$'
        if not re.match(pattern, token_line):
            return False, f"Doesn't match 'val X: Color get() = ...' pattern"
        
        if token_line.count("(") != token_line.count(")"):
            return False, "Unbalanced parentheses"
        
        if ")))" in token_line:
            return False, "Triple parentheses detected"
        
        if not token_line.rstrip().endswith(")"):
            return False, "Line must end with )"
        
        return True, ""

    def find_all_token_files(self, token_type: str) -> List[Path]:
        """
        Find ALL files that contain tokens of the given type.
        
        Returns list of paths sorted by preference.
        """
        candidates = []
        
        for kt in self.project_root.rglob("*.kt"):
            if is_ignored_path(kt, self.project_root):
                continue
            try:
                content = kt.read_text(encoding="utf-8")
            except Exception:
                continue
            
            # هل يحتوي على tokens من النوع المطلوب؟
            if token_type == "dimension":
                # ابحث عن val.*=.*\.dp أو BridgeDimensionRegistry
                if re.search(r'val\s+\w+.*[:=].*[\d.]+\.dp', content) or \
                   "BridgeDimensionRegistry" in content:
                    candidates.append(kt)
            elif token_type == "color":
                if re.search(r'val\s+\w+.*[:=].*Color\(', content) or \
                   "BridgeThemeRegistry" in content:
                    candidates.append(kt)
        
        # Sort: files with pattern indicators first
        def sort_key(path):
            name = path.stem.lower()
            score = 0
            if "token" in name: score -= 100
            if "theme" in name: score -= 50
            if "dimens" in name or "colors" in name: score -= 25
            return score
        
        candidates.sort(key=sort_key)
        return candidates


    def _check_token_exists(self, token_name: str) -> bool:
        """Check if token already exists anywhere."""
        for kt in self.project_root.rglob("*.kt"):
            if is_ignored_path(kt, self.project_root):
                continue
            try:
                content = kt.read_text(encoding="utf-8")
            except Exception:
                continue
            if f'"{token_name}"' in content or re.search(rf'\bval\s+{re.escape(token_name)}\b', content):
                return True
        return False
    
    def _backup_file(self, file_path: Path) -> Path:
        """Create a backup of the file using a single fixed .bridge.bak after syntax validation."""
        from core.ast_finder import safe_create_backup
        ok, err_msg, backup = safe_create_backup(file_path)
        if not ok:
            raise ValueError(err_msg)
        return backup


    def _is_safe_to_replace(self, line_content: str, value: str) -> Tuple[bool, str]:
        """
        Check if line is safe to replace.
        
        Returns:
            (is_safe: bool, reason: str)
        """
        # ═══ 1. Check if value is in a comment ═══
        if "//" in line_content:
            comment_idx = line_content.index("//")
            value_idx = line_content.find(value)
            if value_idx != -1 and value_idx > comment_idx:
                return (False, f"Value '{value}' is in a comment")
        
        if "/*" in line_content and "*/" in line_content:
            comment_start = line_content.index("/*")
            comment_end = line_content.index("*/")
            value_idx = line_content.find(value)
            if comment_start < value_idx < comment_end:
                return (False, f"Value '{value}' is in a comment")

        # ═══ 2. Check if value is in a string ═══
        strings = re.findall(r'"[^"]*"', line_content)
        for s in strings:
            if value in s:
                return (False, f"Value '{value}' is inside a string")
        
        # ⭐ Check for parameter default (requires type annotation before =)
        # مثال: fun foo(x: Dp = 16.dp) → رفض
        # مثال: padding(horizontal = 16.dp) → قبول
        if re.search(rf':\s*[\w<>?\.]+\s*=\s*{re.escape(value)}\b', line_content):
            return (False, f"Value '{value}' appears to be a parameter default")
        
        return (True, "OK")

    def _extract_package(self, content: str) -> str:
        """Extract package name from Kotlin source."""
        match = re.search(r'package\s+([\w.]+)', content)
        return match.group(1) if match else ""


    def migrate(
        self,
        file_name: str,
        line: int,
        value: str,
        token_name: str,
        token_type: str,
        preferred_token_file: Optional[str] = None,
        force_create: bool = False,
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        Migrate hardcoded value to token.
        
        Args:
            file_name: "DashboardPage.kt"
            line: line number (1-indexed)
            value: expected value in that line ("16.dp" or "0xFF7C3AED")
            token_name: new token name ("padding_md")
            token_type: "dimension" | "color"
            force_create: bypass duplicate token value check
        
        Returns:
            (success, message, info)
        """
        with acquire_write_lock():
            # Ensure line is integer
            try:
                line = int(line)
            except (ValueError, TypeError):
                return (False, f"Invalid line number: {line}", None)

            # ═══ 0. Target File & Syntax Validation ═══
            target_matches = [f for f in self.project_root.rglob(Path(file_name).name)
                              if not is_ignored_path(f, self.project_root)]
            if target_matches:
                from core.ast_finder import validate_kotlin_syntax
                is_valid, err_msg = validate_kotlin_syntax(target_matches[0])
                if not is_valid:
                    return (False, err_msg, None)

            # ═══ 1. Validate token_type ═══
            if token_type not in ("dimension", "color"):
                return (False, f"Invalid token_type: {token_type}", None)
            
            # ⭐ التحقق من نوع القيمة
            if token_type == "dimension":
                # الأبعاد المدعومة: أرقام فقط تنتهي بـ .dp
                if not re.match(r'^\d+(\.\d+)?\.dp$', value):
                    return (False, f"Unsupported dimension value: '{value}'. Only numeric .dp values are supported.", None)
            elif token_type == "color":
                # الألوان المدعومة: hex, Color(hex), Color(r,g,b), Color(named args), Color.White, Color.LightGray, etc.
                pass
            
            # ═══ 2. Check token_name not exists ═══
            # ─── 2. Check token_name exists / Smart Token Reuse ───
            if self._check_token_exists(token_name):
                token_info = self._get_existing_token_info(token_name, token_type)
                existing_value = token_info["value"] if token_info else self._get_existing_token_value(token_name, token_type)
                
                new_value_clean = value.replace(".dp", "").replace(".sp", "").strip()
                new_value_clean = new_value_clean.replace("Color(", "").replace(")", "").strip()
                if new_value_clean.startswith("0x") or new_value_clean.startswith("0X"):
                    new_value_clean = new_value_clean.upper()
                    
                existing_value_clean = (existing_value or "").replace(".dp", "").replace(".sp", "").strip()
                existing_value_clean = existing_value_clean.replace("Color(", "").replace(")", "").strip()
                if existing_value_clean.startswith("0x") or existing_value_clean.startswith("0X"):
                    existing_value_clean = existing_value_clean.upper()

                if existing_value and (existing_value_clean == new_value_clean or existing_value == value):
                    # ⭐ Reuse existing token!
                    target_files = [f for f in self.project_root.rglob(Path(file_name).name)
                                  if not is_ignored_path(f, self.project_root)]
                    if not target_files:
                        return (False, f"File not found: {file_name}", None)
                    target_file = target_files[0]
                    target_file = assert_inside(self.project_root, target_file)
                    
                    try:
                        content = target_file.read_text(encoding="utf-8")
                    except Exception as e:
                        return (False, f"Cannot read file: {e}", None)

                    lines = content.splitlines()
                    if line < 1 or line > len(lines):
                        return (False, f"Line {line} out of range (file has {len(lines)} lines)", None)
                    
                    target_line = lines[line - 1]
                    if value not in target_line:
                        return (False, f"Line {line} does not contain '{value}'", {
                            "line_content": target_line.strip(),
                        })
                    
                    is_safe, reason = self._is_safe_to_replace(target_line, value)
                    if not is_safe:
                        return (False, f"Cannot replace: {reason}", {
                            "line_content": target_line.strip(),
                            "reason": reason,
                        })

                    target_backup = self._backup_file(target_file)
                    try:
                        from core.ast_finder import safe_create_backup
                        safe_create_backup(target_file, project_root=self.project_root)
                    except Exception:
                        pass
                    try:
                        reg_file = token_info["file"] if token_info else None
                        reg_content = token_info["content"] if token_info else (reg_file.read_text(encoding="utf-8") if reg_file else "")
                        reg_pkg = self._extract_package(reg_content)
                        target_pkg = self._extract_package(content)
                        
                        obj_name = token_info.get("object_name") if token_info else (reg_file.stem if reg_file else None)
                        if obj_name:
                            scoped_name = f"{obj_name}.{token_name}"
                            if reg_pkg and reg_pkg != target_pkg:
                                new_import = f"import {reg_pkg}.{obj_name}"
                            else:
                                new_import = None
                        else:
                            scoped_name = token_name
                            if reg_pkg and reg_pkg != target_pkg:
                                new_import = f"import {reg_pkg}.{token_name}"
                            else:
                                new_import = None

                        old_line = lines[line - 1]
                        if token_type == "dimension":
                            pattern = re.compile(rf'\b{re.escape(value)}\b')
                        else:
                            if f"Color({value})" in old_line:
                                pattern = re.compile(rf'Color\(\s*{re.escape(value)}\s*\)')
                            else:
                                pattern = re.compile(rf'(?<![\w]){re.escape(value)}(?![\w])')

                        new_line = pattern.sub(scoped_name, old_line, count=1)
                        if new_line == old_line:
                            shutil.copy2(target_backup, target_file)
                            return (False, f"Replacement failed: '{value}' not found as standalone", None)
                        
                        lines[line - 1] = new_line
                        target_line_ending = "\r\n" if "\r\n" in content else "\n"
                        updated_target_content = target_line_ending.join(lines) + target_line_ending
                        if new_import and self._needs_import(updated_target_content, new_import):
                            updated_target_content = self._add_import(updated_target_content, new_import)

                        _atomic_write_text(target_file, updated_target_content)
                        try:
                            try:
                                from core.pattern_journal import PatternJournal
                            except ImportError:
                                from .pattern_journal import PatternJournal
                            pj = PatternJournal(self.project_root)
                            rel_target = str(target_file.relative_to(self.project_root)).replace("\\", "/")
                            if new_import and self._needs_import(content, new_import):
                                pj.record_change(file=rel_target, line=1, old_line="", new_line=new_import.strip(), pattern_id=f"reuse_token_{token_name}")
                            pj.record_change(file=rel_target, line=line, old_line=old_line.strip(), new_line=new_line.strip(), pattern_id=f"reuse_token_{token_name}")
                        except Exception as e:
                            import sys
                            sys.stderr.write(f"[TOKEN_MIGRATOR] Journal record failed on reuse: {e}\n")
                        return (
                            True,
                            f"Reused existing token '{token_name}' in {file_name}:{line}",
                            {
                                "action": "reuse_existing",
                                "token_name": token_name,
                                "replaced_in": f"{file_name}:{line}",
                                "reused": True,
                                "old_line": old_line.strip(),
                                "new_line": new_line.strip(),
                            }
                        )
                    except Exception as e:
                        shutil.copy2(target_backup, target_file)
                        return (False, f"Target edit failed: {e}", None)
                else:
                    return (
                        False,
                        f"Token '{token_name}' exists with different value '{existing_value}'",
                        {
                            "conflict_type": "same_name_different_value",
                            "existing_token": token_name,
                            "existing_value": existing_value,
                            "new_value": value,
                        }
                    )
            
            # ═══ 3. Find target file ═══
            target_files = [f for f in self.project_root.rglob(Path(file_name).name) 
                          if not is_ignored_path(f, self.project_root)]
            if not target_files:
                return (False, f"File not found: {file_name}", None)
            
            target_file = target_files[0]
            target_file = assert_inside(self.project_root, target_file)
            
            # ═══ 4. Read target file ═══
            try:
                with open(target_file, "r", encoding="utf-8", newline="") as tf_in:
                    content = tf_in.read()
            except Exception as e:
                return (False, f"Cannot read file: {e}", None)
            
            lines = content.splitlines()
            if line < 1 or line > len(lines):
                return (False, f"Line {line} out of range (file has {len(lines)} lines)", None)
            
            # ═══ 5. Verify line contains expected value ═══
            target_line = lines[line - 1]
            if value not in target_line:
                return (False, f"Line {line} does not contain '{value}'", {
                    "line_content": target_line.strip(),
                })
            
            # ⭐ Context safety check
            is_safe, reason = self._is_safe_to_replace(target_line, value)
            if not is_safe:
                return (False, f"Cannot replace: {reason}", {
                    "line_content": target_line.strip(),
                    "reason": reason,
                })
            
            # ⭐ Context-based naming validation (bypassed if force_create)
            if not force_create:
                is_valid, suggestion, reason = self._validate_token_name(
                    target_line, token_name, token_type=token_type, value=value
                )
                if not is_valid:
                    return (
                        False,
                        f"Token name invalid: {reason}",
                        {
                            "line_content": target_line.strip(),
                            "given_name": token_name,
                            "suggested_name": suggestion,
                            "safe_alternative": suggestion,
                            "recommended_name": suggestion,
                            "validation_type": "semantic",
                        }
                    )
            
            # ⭐ NEW: Semantic conflict detection
            if not force_create:
                conflict = self.detect_semantic_conflict(
                    token_name, token_type, value
                )
                if conflict:
                    info_dict = {
                        "conflict_type": conflict["type"],
                        "existing_token": conflict["existing_token"],
                        "existing_value": conflict["existing_value"],
                        "existing_file": conflict["existing_file"],
                        "new_name": token_name,
                        "new_value": value,
                        "suggestions": conflict["suggestions"],
                    }
                    if "safe_alternative" in conflict:
                        info_dict["safe_alternative"] = conflict["safe_alternative"]
                        info_dict["recommended_name"] = conflict["safe_alternative"]
                    return (
                        False,
                        conflict["message"],
                        info_dict,
                    )

            # ⭐ Duplicate detection (Consolidation fallback)
            if not force_create:
                existing_tokens = self._find_existing_tokens(value, token_type)
                if existing_tokens:
                    prefix = "AppDimens" if token_type == "dimension" else "AppColors"
                    if len(existing_tokens) > 1:
                        tokens_str = ", ".join(existing_tokens)
                        return (
                            False,
                            f"Multiple tokens with same value already exist: {tokens_str}. "
                            f"Use {prefix}.{existing_tokens[0]} or {prefix}.{existing_tokens[1]} instead of creating '{token_name}'.",
                            {
                                "existing_tokens": existing_tokens,
                                "value": value,
                                "suggestion": f"Use {prefix}.{existing_tokens[0]}",
                            }
                        )
                    else:
                        existing = existing_tokens[0]
                        return (
                            False,
                            f"Token with same value already exists: '{existing}'. "
                            f"Use {prefix}.{existing} instead of creating '{token_name}'.",
                            {
                                "existing_token": existing,
                                "value": value,
                                "suggestion": f"Use {prefix}.{existing}",
                            }
                        )
            
            # ═══ 6. Find registry file ═══
            if preferred_token_file:
                matches = [m for m in self.project_root.rglob(Path(preferred_token_file).name)
                           if not is_ignored_path(m, self.project_root)]
                def _rank(p):
                    norm = str(p).replace("\\", "/").lower()
                    if "/commonmain/" in norm: return 0
                    if "/main/" in norm: return 1
                    if "/src/" in norm: return 2
                    return 3
                matches.sort(key=lambda p: (_rank(p), len(str(p))))
                registry_file = matches[0] if matches else None
                if not registry_file:
                    return (False, f"Preferred file not found: {preferred_token_file}", None)
            else:
                # ابحث عن الملف القياسي أولاً (مثل AppColors أو DesignSystem)
                registry_file = self._find_registry_file(token_type)
                if not registry_file:
                    all_files = self.find_all_token_files(token_type)
                    registry_file = all_files[0] if all_files else None

            if not registry_file or not registry_file.exists():
                return (False, f"NEEDS_MANUAL_MAPPING: Registry file not found for type: {token_type}. Use 'set_design_file_mapping' to configure.", {
                    "error_code": "NEEDS_MANUAL_MAPPING",
                    "token_type": token_type,
                })
            
            registry_file = assert_inside(self.project_root, registry_file)
            style = self.detect_storage_style(registry_file)

            # ═══ 7. Generate new registry entry ═══
            new_entry = self._generate_registry_entry(token_name, value, token_type, style=style)
            if not new_entry:
                return (False, "Cannot generate registry entry", None)
            
            # ═══ 8. Backup both files ═══
            target_backup = self._backup_file(target_file)
            registry_backup = self._backup_file(registry_file)
            try:
                from core.ast_finder import safe_create_backup
                safe_create_backup(target_file, project_root=self.project_root)
                safe_create_backup(registry_file, project_root=self.project_root)
            except Exception:
                pass
            
            # ═══ 9. Modify registry file ═══
            try:
                reg_content = registry_file.read_text(encoding="utf-8")
                reg_content = self._ensure_registry_imports(reg_content, token_type, style)
                insert_idx = self._find_registry_insertion_point(reg_content, token_type=token_type, style=style)
                reg_lines = reg_content.splitlines()
                reg_lines.insert(insert_idx, new_entry)
                _atomic_write_text(registry_file, "\n".join(reg_lines) + "\n")

                # Verify token definition exists in registry file
                saved_reg = registry_file.read_text(encoding="utf-8")
                if token_name not in saved_reg:
                    shutil.copy2(registry_backup, registry_file)
                    return (False, f"Verification failed: token '{token_name}' was not found in {registry_file.name} after write", None)
            except Exception as e:
                # Rollback registry
                shutil.copy2(registry_backup, registry_file)
                return (False, f"Registry edit failed: {e}", None)
            
            # ═══ 10. Replace in target file with scoping and auto-import ═══
            try:
                reg_pkg = self._extract_package(reg_content)
                target_pkg = self._extract_package(content)
                
                obj_match = re.search(r'\bobject\s+(\w+)', reg_content)
                if obj_match:
                    obj_name = obj_match.group(1)
                else:
                    obj_name = None

                if style in ("registry", "object") or obj_name:
                    actual_obj = obj_name if obj_name else registry_file.stem
                    scoped_name = f"{actual_obj}.{token_name}"
                    if reg_pkg and reg_pkg != target_pkg:
                        new_import = f"import {reg_pkg}.{actual_obj}"
                    else:
                        new_import = None
                else:  # top-level
                    scoped_name = token_name
                    if reg_pkg and reg_pkg != target_pkg:
                        new_import = f"import {reg_pkg}.{token_name}"
                    else:
                        new_import = None

                old_line = lines[line - 1]
                
                # ⭐ استخدام regex مع حدود الكلمة لمنع الاستبدال الخاطئ للأجزاء (مثل 16.dp داخل 116.dp)
                if token_type == "dimension":
                    pattern = re.compile(rf'\b{re.escape(value)}\b')
                else:
                    if f"Color({value})" in old_line:
                        pattern = re.compile(rf'Color\(\s*{re.escape(value)}\s*\)')
                    else:
                        pattern = re.compile(rf'(?<![\w]){re.escape(value)}(?![\w])')
                
                new_line = pattern.sub(scoped_name, old_line, count=1)
                
                # ⭐ تحقق أن الاستبدال حدث
                if new_line == old_line:
                    # rollback
                    shutil.copy2(target_backup, target_file)
                    shutil.copy2(registry_backup, registry_file)
                    return (False, f"Replacement failed: '{value}' not found as standalone", None)
                
                lines[line - 1] = new_line
                
                # Add import if needed
                import_added = False
                target_line_ending = "\r\n" if "\r\n" in content else "\n"
                updated_target_content = target_line_ending.join(lines) + target_line_ending
                if new_import and self._needs_import(updated_target_content, new_import):
                    updated_target_content = self._add_import(updated_target_content, new_import)
                    import_added = True

                _atomic_write_text(target_file, updated_target_content)
            except Exception as e:
                # Rollback both files
                shutil.copy2(target_backup, target_file)
                shutil.copy2(registry_backup, registry_file)
                return (False, f"Target edit failed: {e}", None)
            
            # ═══ 11. Record in PatternJournal for Changes tab & Rollback ═══
            try:
                try:
                    from core.pattern_journal import PatternJournal
                except ImportError:
                    from .pattern_journal import PatternJournal
                journal = PatternJournal(self.project_root)
                pid = f"create_token_{token_name}"
                
                # 1. Record token added in registry file
                rel_reg = str(registry_file.relative_to(self.project_root)).replace("\\", "/")
                journal.record_token_added(
                    pattern_id=pid,
                    token_name=token_name,
                    token_value=value,
                    file=rel_reg
                )
                journal.record_change(
                    file=rel_reg,
                    line=insert_idx + 1,
                    old_line="",
                    new_line=new_entry.strip(),
                    pattern_id=pid,
                )

                # 2. Record change in target file (both import if added, and line change)
                rel_target = str(target_file.relative_to(self.project_root)).replace("\\", "/")
                if import_added and new_import:
                    journal.record_change(
                        file=rel_target,
                        line=1,
                        old_line="",
                        new_line=new_import.strip(),
                        pattern_id=pid,
                    )
                journal.record_change(
                    file=rel_target,
                    line=line,
                    old_line=old_line.strip(),
                    new_line=new_line.strip(),
                    pattern_id=pid,
                )
            except Exception as e:
                import sys
                sys.stderr.write(f"[TOKEN_MIGRATOR] PatternJournal record failed: {e}\n")

            # ═══ 12. Success ═══
            if force_create:
                self.events.log(
                    "token_created_force",
                    {
                        "token_name": token_name,
                        "value": value,
                        "type": token_type,
                        "warning": "force_create used — bypassed duplicate detection",
                    },
                    source="user",
                )
            
            info = {
                "target_file": str(target_file.relative_to(self.project_root)),
                "target_line": line,
                "old_line": old_line.strip(),
                "new_line": new_line.strip(),
                "scoped_name": scoped_name,
                "import_added": import_added,
                "registry_file": str(registry_file.relative_to(self.project_root)),
                "registry_entry": new_entry.strip(),
                "backup_target": str(target_backup),
                "backup_registry": str(registry_backup),
            }
            
            return (
                True,
                f"Added token '{token_name}' and updated {file_name}:{line}",
                info,
            )

    def remove_token(self, token_name: str, token_type: str = "color") -> bool:
        """
        Remove a token definition from the registry file.
        Returns True if removed successfully.
        """
        import re
        with acquire_write_lock():
            files = self.find_all_token_files(token_type)
            for f in files:
                try:
                    content = f.read_text(encoding="utf-8")
                    
                    patterns = [
                        # val Xxx: Color\n    get() = BridgeThemeRegistry.getColor("Xxx", ...)
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\s*:\s*Color\s*\n[ \t]*get\(\)\s*=\s*BridgeThemeRegistry\.getColor\("[^"]+",\s*[^)]+\)',
                        # val Xxx: Dp\n    get() = BridgeDimensionRegistry.get("Xxx", ...)
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\s*:\s*Dp\s*\n[ \t]*get\(\)\s*=\s*BridgeDimensionRegistry\.get\("[^"]+",\s*[^)]+\)',
                        # val Xxx: Color get() = BridgeThemeRegistry...
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\s*:\s*Color\s+get\(\)\s*=\s*[^\n]+',
                        # val Xxx: Dp get() = BridgeDimensionRegistry...
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\s*:\s*Dp\s+get\(\)\s*=\s*[^\n]+',
                        # val Xxx = Color(...)
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\s*=\s*Color\([^)]+\)',
                        # val Xxx = ...dp / ...sp
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\s*=\s*[\d.]+\.(?:dp|sp)',
                        # Generic multiline val TokenName: ... get() = ...
                        rf'\n?[ \t]*val\s+{re.escape(token_name)}\b.*?(?:\n[ \t]*)?get\(\)\s*=\s*[^\n]+',
                    ]
                    
                    new_content = content
                    for pattern in patterns:
                        new_content = re.sub(pattern, "", new_content)
                    
                    if new_content != content:
                        # ⭐ Journal save before modification (for rollback)
                        try:
                            try:
                                from core.pattern_journal import PatternJournal
                            except ImportError:
                                from .pattern_journal import PatternJournal
                            journal = PatternJournal(self.project_root)
                            rel_file = str(f.relative_to(self.project_root)) if f.is_relative_to(self.project_root) else f.name
                            journal.record_change(
                                file=rel_file,
                                line=1,
                                old_line=content,
                                new_line=new_content,
                                pattern_id=f"remove_token_{token_name}",
                            )
                        except Exception as jerr:
                            import logging
                            logging.error(f"[TOKEN_MIGRATOR] Journal record failed in remove_token: {jerr}")
                        
                        _atomic_write_text(f, new_content)
                        return True
                except Exception as e:
                    continue
            return False


CONTEXT_RULES = TokenMigrator.CONTEXT_RULES
COLOR_CONTEXT_RULES = TokenMigrator.COLOR_CONTEXT_RULES
