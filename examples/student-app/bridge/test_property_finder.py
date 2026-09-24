"""
Test — Property Finder.
 composables.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.ast_finder import (
 parse_file,
 find_composable_at_line,
 find_property_in_node,
 extract_literal_value,
 find_all_call_expressions_in_node,
)


PROJECT_ROOT = Path(r"C:\Users\thinkpad\StudioProjects\StudentApp")
TARGET_FILE = PROJECT_ROOT / "app" / "src" / "main" / "java" / "com" / "student" / "app" / "test" / "HomeScreenForTest.kt"


def print_header(title: str):
 print()
 print("=" * 60)
 print(f" {title}")
 print("=" * 60)


def main():
 print_header("GATE 3 — Property Finder Test")

 tree, source_bytes = parse_file(str(TARGET_FILE))

 # S-expression
 print_header("Full Tree (S-expression)")
 sexp = tree.root_node.sexp() if hasattr(tree.root_node, 'sexp') else str(tree.root_node)
 print(sexp)

 # sexp 
 if not hasattr(tree.root_node, 'sexp'):
 print("sexp() not available, trying alternative...")
 try:
 from tree_sitter import Query
 print(tree.root_node)
 except:
 pass

 # : Card
 print_header("Debug: Card structure (depth=5)")
 card_for_debug = find_composable_at_line(tree, source_bytes, 35, "Card")
 if card_for_debug:
 from core.ast_finder import debug_dump_structure
 debug_dump_structure(card_for_debug, source_bytes, max_depth=6)

 # ========================================
 # 1: Card → padding
 # ========================================
 print_header("Scenario 1: Card @ line 35 → find 'padding'")

 card = find_composable_at_line(tree, source_bytes, 35, "Card")
 if not card:
 print("❌ Card not found")
 return

 print(f"✅ Card found: bytes {card.start_byte}-{card.end_byte}")

 padding = find_property_in_node(card, source_bytes, "padding")
 if padding:
 print(f"✅ Padding found: bytes {padding.start_byte}-{padding.end_byte}")
 print(f" Text: {padding.text}")

 result = extract_literal_value(padding)
 if result:
 value_text, byte_start, byte_end = result
 print(f" ✅ Value: '{value_text}'")
 print(f" 📍 Bytes: {byte_start}-{byte_end}")
 else:
 print(" ❌ Could not extract value")
 else:
 print("❌ Padding not found inside Card")

 # ========================================
 # 2: Text @ line 25 → fontSize
 # ========================================
 print_header("Scenario 2: Text @ line 25 → find 'fontSize'")

 text25 = find_composable_at_line(tree, source_bytes, 25, "Text")
 if text25:
 print(f"✅ Text found: bytes {text25.start_byte}-{text25.end_byte}")

 # fontSize argument call
 # 
 print(" (fontSize is an argument, not a call - skip for now)")

 # ========================================
 # 3: Text @ line 42 → find nested calls
 # ========================================
 print_header("Scenario 3: Text @ line 42 → all nested calls")

 text42 = find_composable_at_line(tree, source_bytes, 42, "Text")
 if text42:
 print(f"✅ Text found: bytes {text42.start_byte}-{text42.end_byte}")

 # Text
 for fn_name in ["sp", "dp", "name"]:
 calls = find_all_call_expressions_in_node(text42, source_bytes, fn_name)
 if calls:
 print(f" Found {len(calls)} call(s) to '{fn_name}':")
 for c in calls:
 print(f" bytes {c.start_byte}-{c.end_byte}: {c.text[:50]}")

 # ========================================
 # 4: Card → 
 # ========================================
 print_header("Scenario 4: All 'calls' inside Card")

 # call expressions Card
 if card:
 for fn_name in ["padding", "fillMaxWidth", "height", "width", "size"]:
 calls = find_all_call_expressions_in_node(card, source_bytes, fn_name)
 if calls:
 for c in calls:
 print(f" ✅ {fn_name}: {c.text[:60]}")

 print()
 print("=" * 60)
 print("✅ Test complete")
 print("=" * 60)


if __name__ == "__main__":
 main()