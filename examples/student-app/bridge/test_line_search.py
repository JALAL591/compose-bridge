"""
Test — Line-Based Search for composables.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.ast_finder import (
 parse_file,
 find_composable_at_line,
 find_all_call_expressions,
)


PROJECT_ROOT = Path(r"C:\Users\thinkpad\StudioProjects\StudentApp")
TARGET_FILE = PROJECT_ROOT / "app" / "src" / "main" / "java" / "com" / "student" / "app" / "test" / "HomeScreenForTest.kt"


def print_header(title: str):
 print()
 print("=" * 60)
 print(f" {title}")
 print("=" * 60)


def main():
 print_header("Phase 3b — Line-Based Search")

 tree, source_bytes = parse_file(str(TARGET_FILE))

 # Agent
 scenarios = [
 # (composable, line, description)
 ("Card", 35, "Card @ line 35"),
 ("Row", 41, "Row @ line 41"),
 ("Text", 42, "Text @ line 42"),
 ("Text", 25, "Text @ line 25"),
 ("LazyColumn", 33, "LazyColumn @ line 33"),
 ("Column", 22, "Column @ line 22"),
 ("Spacer", 30, "Spacer @ line 30"),
 ]

 for name, line, desc in scenarios:
 print(f"\n🔍 Searching for {name} @ line {line}")
 node = find_composable_at_line(tree, source_bytes, line, name)

 if node:
 actual_line = node.start_point[0] + 1
 col = node.start_point[1]
 print(f" ✅ Found!")
 print(f" Line: {actual_line} (col {col})")
 print(f" Bytes: {node.start_byte}-{node.end_byte}")
 print(f" Text: {node.text[:70]}...")
 else:
 print(f" ❌ Not found")

 # ========================================
 # : 100% 
 # ========================================
 print_header("Comparison with Tree-sitter's direct search")

 for name in ["Card", "Row", "Text"]:
 nodes = find_all_call_expressions(tree, source_bytes, name)
 print(f"\n📋 All {name} calls in file:")
 for i, node in enumerate(nodes, 1):
 print(f" [{i}] line {node.start_point[0] + 1}, bytes {node.start_byte}-{node.end_byte}")

 print()
 print("=" * 60)
 print("✅ Test complete")
 print("=" * 60)


if __name__ == "__main__":
 main()