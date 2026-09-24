"""
Source Analyzer — Analyzes element source code scope.
- utf16Offset utf16Length 
- padding BridgeSpacing
"""

import re
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(r"C:\Users\thinkpad\StudioProjects\StudentApp")


def analyze_element_range(
 source_file: str,
 line_number: int,
 utf16_offset: int = 0,
 utf16_length: int = 0,
) -> dict:
 """
 Analyzes literal element range.

 Args:
 source_file: Path ( )
 line_number: 1-based
 utf16_offset: Start File
 utf16_length: 
 """
 # File
 full_path = _find_file(source_file)
 if full_path is None:
 return _empty_result(error=f"File not found: {source_file}")

 try:
 content = full_path.read_text(encoding="utf-8")
 except Exception as e:
 return _empty_result(error=f"Read failed: {e}")

 # 
 if utf16_offset > 0 and utf16_length > 0:
 # UTF-16 offset Python (code points)
 element_code = _extract_utf16_range(content, utf16_offset, utf16_length)
 search_scope = element_code if element_code else _line_context(content, line_number)
 else:
 search_scope = _line_context(content, line_number)

 if not search_scope:
 return _empty_result(error="Empty scope")

 # 1. — AppColors.X
 token_pattern = re.compile(r'AppColors\.(\w+)')
 tokens = list(set(token_pattern.findall(search_scope)))

 # 2. literal
 literal_pattern = re.compile(r'Color\s*\(\s*(0x[0-9A-Fa-f]+)')
 literals = list(set(literal_pattern.findall(search_scope)))

 # 3. — 
 dimension_details = []

 # 3.1: dp — 
 dp_pattern = re.compile(r'(\d+(?:\.\d+)?)\.dp')
 for m in dp_pattern.finditer(search_scope):
 value = m.group(1)
 dimension_details.append({
 "value": f"{value}.dp",
 "kind": "dp",
 "number": float(value),
 "absolute_offset": utf16_offset + m.start() if utf16_offset > 0 else 0,
 })

 # 3.2: sp — 
 sp_pattern = re.compile(r'(\d+(?:\.\d+)?)\.sp')
 for m in sp_pattern.finditer(search_scope):
 value = m.group(1)
 dimension_details.append({
 "value": f"{value}.sp",
 "kind": "sp",
 "number": float(value),
 "absolute_offset": utf16_offset + m.start() if utf16_offset > 0 else 0,
 })

 # 3.3: f — (0.0 - 1.0)
 f_pattern = re.compile(r'\b(0?\.\d+)f\b')
 for m in f_pattern.finditer(search_scope):
 value = m.group(1)
 dimension_details.append({
 "value": f"{value}f",
 "kind": "fraction",
 "number": float(value),
 "absolute_offset": utf16_offset + m.start() if utf16_offset > 0 else 0,
 })

 # 3.4: width/height/size — 
 wh_pattern = re.compile(r'\.(width|height|size)\s*\(\s*(\d+(?:\.\d+)?)\.dp')
 for m in wh_pattern.finditer(search_scope):
 dimension_details.append({
 "value": f"{m.group(2)}.dp",
 "kind": m.group(1),
 "number": float(m.group(2)),
 "absolute_offset": utf16_offset + m.start(2) if utf16_offset > 0 else 0,
 })

 # 4. BridgeSpacing tokens
 bridge_token_pattern = re.compile(r'BridgeSpacing\.(\w+)')
 bridge_tokens = list(set(bridge_token_pattern.findall(search_scope)))

 # 5. ( )
 sps = [d["value"] for d in dimension_details if d["kind"] == "sp"]

 # 6. fontWeight
 weight_pattern = re.compile(r'FontWeight\.(\w+)')
 weights = list(set(weight_pattern.findall(search_scope)))

 # 7. 
 prop_pattern = re.compile(
 r'\.(background|padding|width|height|size|fillMaxWidth|fontSize|'
 r'lineHeight|letterSpacing|fontWeight|color|tint|containerColor|'
 r'cornerRadius|shape|border)\s*[=(]'
 )
 properties = list(set(prop_pattern.findall(search_scope)))

 # 8. composables ( )
 composable_pattern = re.compile(r'\b([A-Z][A-Za-z0-9]+)\s*\(')
 composables = list(set(composable_pattern.findall(search_scope)))
 # Kotlin standard + Compose utilities
 composables = [c for c in composables if c not in {
 'Color', 'Dp', 'TextStyle', 'Typography', 'Modifier', 'Brush',
 'RoundedCornerShape', 'CircleShape', 'Offset', 'Size', 'Rect',
 'Weight', 'FontWeight', 'Box', 'Row', 'Column'
 }][:8] # 8

 return {
 "tokens_used": [f"AppColors.{t}" for t in tokens],
 "literals": literals,
 "dimensions": list({d["value"] for d in dimension_details})[:20],
 "dimension_details": dimension_details[:20],
 "bridge_spacing_tokens": bridge_tokens,
 "font_sizes": list(set(sps))[:10],
 "font_weights": weights,
 "properties": properties,
 "composables": composables,
 "scope_size": len(search_scope),
 "used_exact_range": utf16_offset > 0 and utf16_length > 0,
 }


def _find_file(source_file: str) -> Optional[Path]:
 """Finds file in project."""
 full_path = PROJECT_ROOT / source_file
 if full_path.exists():
 return full_path

 # 
 filename = Path(source_file).name
 candidates = [
 c for c in PROJECT_ROOT.rglob(filename)
 if 'build/' not in str(c).replace('\\', '/')
 ]
 return candidates[0] if candidates else None


def _extract_utf16_range(content: str, offset: int, length: int) -> str:
 """
 Extracts range from content using UTF-16 offset.
 """
 try:
 # string UTF-16 code units
 encoded = content.encode('utf-16-le')

 # 
 start_byte = offset * 2
 end_byte = (offset + length) * 2

 if end_byte > len(encoded):
 end_byte = len(encoded)

 sub = encoded[start_byte:end_byte]
 return sub.decode('utf-16-le', errors='ignore')
 except Exception as e:
 print(f"[source_analyzer] UTF-16 extract failed: {e}")
 return ""


def _line_context(content: str, line_number: int, before: int = 3, after: int = 15) -> str:
 """Returns lines around line_number."""
 lines = content.splitlines()
 idx = line_number - 1
 if idx < 0 or idx >= len(lines):
 return ""
 start = max(0, idx - before)
 end = min(len(lines), idx + after)
 return "\n".join(lines[start:end])


def _empty_result(error: str = "") -> dict:
 return {
 "tokens_used": [],
 "literals": [],
 "dimensions": [],
 "dimension_details": [],
 "bridge_spacing_tokens": [],
 "font_sizes": [],
 "font_weights": [],
 "properties": [],
 "composables": [],
 "scope_size": 0,
 "error": error,
 }