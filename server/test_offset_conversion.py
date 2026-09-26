"""
Test script — Test Convert utf16Offset byte_offset.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.utils import utf16_to_byte_offset, read_file_as_utf8
from core.ast_finder import parse_file, find_node_at_byte, find_all_call_expressions


PROJECT_ROOT = Path(r"C:\Users\thinkpad\StudioProjects\StudentApp")
TARGET_FILE = PROJECT_ROOT / "app" / "src" / "main" / "java" / "com" / "student" / "app" / "test" / "HomeScreenForTest.kt"


def print_header(title: str):
 print()
 print("=" * 60)
 print(f" {title}")
 print("=" * 60)


def main():
 print_header("Phase 3 — UTF-16 → Byte Conversion Test")
 print(f"Target: {TARGET_FILE}")

 # File text
 text = read_file_as_utf8(str(TARGET_FILE))
 print(f"\n📖 File info:")
 print(f" Text length (chars): {len(text)}")
 print(f" Text length (UTF-16): {sum(2 if ord(c) > 0xFFFF else 1 for c in text)}")
 print(f" File size (bytes): {len(text.encode('utf-8'))}")

 # ========================================
 # Test 
 # ========================================
 print_header("Conversion Test")

 test_cases = [
 # (utf16_offset, expected_byte_offset, description)
 (0, 0, "Start File"),
 (987, 1061, "Card @ line 35"),
 (1232, None, "Row @ line 41"),
 (1266, None, "Text @ line 42"),
 ]

 for utf16_off, expected_byte, desc in test_cases:
 try:
 byte_off = utf16_to_byte_offset(text, utf16_off)
 status = "✅"
 if expected_byte is not None:
 match = "✓" if byte_off == expected_byte else "✗"
 print(f"{status} UTF-16 {utf16_off:4} → byte {byte_off:4} "
 f"[expected {expected_byte}] {match} ({desc})")
 else:
 print(f"{status} UTF-16 {utf16_off:4} → byte {byte_off:4} ({desc})")
 except ValueError as e:
 print(f"❌ UTF-16 {utf16_off} → ERROR: {e}")

 # ========================================
 # Conversion AST
 # ========================================
 print_header("Full Chain: utf16Offset → AST Node")

 # Card: utf16Offset = 987
 card_utf16 = 987
 card_byte = utf16_to_byte_offset(text, card_utf16)
 print(f"\n🎯 Card utf16Offset={card_utf16} → byte {card_byte}")

 tree, source_bytes = parse_file(str(TARGET_FILE))
 node = find_node_at_byte(tree, source_bytes, card_byte)

 if node:
 line = node.start_point[0] + 1
 print(f" Node found: type={node.type}")
 print(f" Line: {line}")
 print(f" Bytes: {node.start_byte}-{node.end_byte}")
 print(f" Text: {node.text[:80]}...")
 else:
 print(f" ⚠️ No node found at byte {card_byte}")

 # ========================================
 # Card 
 # ========================================
 print_header("Compare with Tree-sitter's Card")

 cards = find_all_call_expressions(tree, source_bytes, "Card")
 if cards:
 card = cards[0]
 print(f" Tree-sitter's Card:")
 print(f" start_byte: {card.start_byte}")
 print(f" end_byte: {card.end_byte}")
 print(f" line: {card.start_point[0] + 1}")
 print()
 print(f" Agent's utf16Offset: 987")
 print(f" Converted to byte: {card_byte}")
 print(f" Tree-sitter byte: {card.start_byte}")
 print()
 if card_byte == card.start_byte:
 print(" ✅ MATCH! Conversion is correct.")
 else:
 print(f" ⚠️ Mismatch: {card.start_byte - card_byte} bytes difference")

 print()
 print("=" * 60)
 print("✅ Test complete")
 print("=" * 60)


if __name__ == "__main__":
 main()
def test_emoji_roundtrip():
    """Test emoji offset conversion."""
    from core.utf_mapper import Utf16Utf8Mapper
    content = "Hello 😀 World".encode("utf-8")
    mapper = Utf16Utf8Mapper(content)
    assert mapper.byte_to_utf16(6) == 6, f"Expected 6, got {mapper.byte_to_utf16(6)}"
    assert mapper.byte_to_utf16(10) == 8, f"Expected 8, got {mapper.byte_to_utf16(10)}"
    print("✅ test_emoji_roundtrip passed")


def test_arabic_roundtrip():
    """Test Arabic text offset conversion."""
    from core.utf_mapper import Utf16Utf8Mapper
    content = "مرحباً بك".encode("utf-8")
    mapper = Utf16Utf8Mapper(content)
    assert mapper.byte_to_utf16(0) == 0
    assert mapper.byte_to_utf16(2) == 1
    assert mapper.byte_to_utf16(4) == 2
    print("✅ test_arabic_roundtrip passed")
