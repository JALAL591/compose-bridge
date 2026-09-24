"""
Test script — HomeScreenForTest.kt .
"""

import sys
from pathlib import Path

# Add 
sys.path.insert(0, str(Path(__file__).parent))

from core.ast_finder import (
 parse_file,
 find_all_call_expressions,
 find_node_at_byte,
 count_nodes_by_type,
)

# ============================================================
# Settings
# ============================================================

PROJECT_ROOT = Path(r"C:\Users\thinkpad\StudioProjects\StudentApp")
TARGET_FILE = PROJECT_ROOT / "app" / "src" / "main" / "java" / "com" / "student" / "app" / "test" / "HomeScreenForTest.kt"


def print_header(title: str):
 print()
 print("=" * 60)
 print(f" {title}")
 print("=" * 60)


def main():
 print_header("ComposeBridge — AST Test")
 print(f"Target file: {TARGET_FILE}")

 if not TARGET_FILE.exists():
 print(f"\n❌ File not found: {TARGET_FILE}")
 print("Check Path!")
 return 1

 # 1) Parse
 print("\n📖 Parsing...")
 tree, source_bytes = parse_file(str(TARGET_FILE))
 print(f"✅ Parsed successfully")
 print(f" File size: {len(source_bytes)} bytes")
 print(f" Root type: {tree.root_node.type}")
 print(f" Has errors: {tree.root_node.has_error}")

 # 2) Find Card, Row, Text
 print_header("Finding Composable Calls")
 for name in ["Card", "Row", "Text", "Column", "LazyColumn", "Spacer"]:
 nodes = find_all_call_expressions(tree, source_bytes, name)
 print(f"\n🔍 {name}: {len(nodes)} occurrence(s)")
 for i, node in enumerate(nodes, 1):
 line = node.start_point[0] + 1
 col = node.start_point[1]
 print(f" [{i}] line {line}, col {col}, bytes {node.start_byte}-{node.end_byte}")

 # 3) Test find_node_at_byte
 print_header("Testing find_node_at_byte")

 test_offsets = [0, 100, 500, 987, 1000]
 for offset in test_offsets:
 if offset >= len(source_bytes):
 continue
 node = find_node_at_byte(tree, source_bytes, offset)
 if node:
 line = node.start_point[0] + 1
 print(f" byte {offset} → {node.type} @ line {line}")
 else:
 print(f" byte {offset} → (no node)")

 # 4) Summary of node types
 print_header("Node Type Distribution")
 counts = count_nodes_by_type(tree)
 sorted_counts = sorted(counts.items(), key=lambda x: -x[1])
 for node_type, count in sorted_counts[:15]:
 print(f" {node_type:40} {count}")

 print()
 print("=" * 60)
 print("✅ Test completed successfully!")
 print("=" * 60)
 return 0


if __name__ == "__main__":
 sys.exit(main())