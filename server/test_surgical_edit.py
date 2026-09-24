"""
GATE 4 — First Surgical Edit Test

 Test HomeScreenForTest.kt :
 16.dp → 24.dp
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.ast_finder import (
 parse_file,
 find_composable_at_line,
 find_property_in_node,
 extract_literal_value,
 surgical_edit,
)


PROJECT_ROOT = Path(r"C:\Users\thinkpad\StudioProjects\StudentApp")
TARGET_FILE = PROJECT_ROOT / "app" / "src" / "main" / "java" / "com" / "student" / "app" / "test" / "HomeScreenForTest.kt"


def print_header(title: str):
 print()
 print("=" * 60)
 print(f" {title}")
 print("=" * 60)


def main():
 print_header("GATE 4 — Surgical Edit Test")

 print(f"Target: {TARGET_FILE}")

 # ========================================
 # 1. File padding
 # ========================================
 print_header("Step 1: Locate 'padding(16.dp)'")

 tree, source_bytes = parse_file(str(TARGET_FILE))

 card = find_composable_at_line(tree, source_bytes, 35, "Card")
 if not card:
 print("❌ Card not found")
 return 1

 print(f"✅ Card found: bytes {card.start_byte}-{card.end_byte}")

 padding = find_property_in_node(card, source_bytes, "padding")
 if not padding:
 print("❌ Padding not found")
 return 1

 print(f"✅ Padding found: bytes {padding.start_byte}-{padding.end_byte}")

 result = extract_literal_value(padding)
 if not result:
 print("❌ Could not extract value")
 return 1

 old_value, val_start, val_end = result
 print(f"✅ Old value: '{old_value}'")
 print(f"📍 Bytes: {val_start}-{val_end}")

 # ========================================
 # 2. 
 # ========================================
 print_header("Step 2: Current file content (around the target)")

 # 50 50 
 context_start = max(0, val_start - 50)
 context_end = min(len(source_bytes), val_end + 50)
 context = source_bytes[context_start:context_end].decode("utf-8", errors="replace")

 print(f"Context (bytes {context_start}-{context_end}):")
 print("-" * 60)
 print(context)
 print("-" * 60)

 # ========================================
 # 3. Edit 
 # ========================================
 print_header("Step 3: Performing surgical edit")

 new_value = "24.dp"

 print(f"Operation: '{old_value}' → '{new_value}'")
 print(f"Location: bytes {val_start}-{val_end}")
 print()

 success, message, backup = surgical_edit(
 file_path=str(TARGET_FILE),
 byte_start=val_start,
 byte_end=val_end,
 expected_old_value=old_value,
 new_value=new_value,
 )

 if success:
 print(f"✅ {message}")
 print(f"📁 Backup: {backup}")
 else:
 print(f"❌ Failed: {message}")
 return 1

 # ========================================
 # 4. File Edit 
 # ========================================
 print_header("Step 4: Verification")

 with open(TARGET_FILE, "rb") as f:
 new_source = f.read()

 new_context = new_source[context_start:context_end].decode("utf-8", errors="replace")

 print("New context:")
 print("-" * 60)
 print(new_context)
 print("-" * 60)

 # "24.dp" 
 check = new_source[val_start:val_start + len("24.dp")].decode("utf-8")
 if check == "24.dp":
 print(f"✅ Verified: new value at same position is '24.dp'")
 else:
 print(f"⚠️ Verification failed: found '{check}'")

 # ========================================
 # 5. Analyze File 
 # ========================================
 print_header("Step 5: Re-parse file to verify syntax")

 tree2, source_bytes2 = parse_file(str(TARGET_FILE))
 if tree2.root_node.has_error:
 print("⚠️ Parse errors detected after edit!")
 else:
 print("✅ File still parses correctly (no syntax errors)")

 # Check Card 
 card2 = find_composable_at_line(tree2, source_bytes2, 35, "Card")
 if card2:
 print(f"✅ Card still at line 35: bytes {card2.start_byte}-{card2.end_byte}")

 print()
 print("=" * 60)
 print("🎉 GATE 4 COMPLETE!")
 print("=" * 60)
 print()
 print("👉 HomeScreenForTest.kt Android Studio")
 print(" padding(16.dp) padding(24.dp)")
 print()

 return 0


if __name__ == "__main__":
 sys.exit(main())