"""
Utility functions for ComposeBridge Python Bridge.
"""


def utf16_to_byte_offset(text: str, target_utf16: int) -> int:
 """
 offset UTF-16 code units UTF-8 bytes.

 Compose offsets UTF-16 code units.
 Python File UTF-8 bytes.
 .

 Args:
 text: File str
 target_utf16: offset UTF-16 units

 Returns:
 offset UTF-8 bytes

 Raises:
 ValueError: offset 

 Example:
 text = "Hello "
 utf16_to_byte_offset(text, 6) # 6
 utf16_to_byte_offset(text, 8) # 8 ( " ")
 """
 utf16_count = 0
 byte_count = 0

 for ch in text:
 if utf16_count >= target_utf16:
 break

 code_point = ord(ch)

 # BMP ( ) UTF-16
 utf16_count += 2 if code_point > 0xFFFF else 1
 byte_count += len(ch.encode("utf-8"))

 if utf16_count != target_utf16:
 raise ValueError(
 f"UTF-16 offset {target_utf16} not aligned with character boundary "
 f"(reached {utf16_count})"
 )

 return byte_count


def byte_to_utf16_offset(text: str, target_byte: int) -> int:
 """
 : UTF-8 bytes UTF-16 code units.
 """
 utf16_count = 0
 byte_count = 0

 for ch in text:
 if byte_count >= target_byte:
 break

 char_bytes = len(ch.encode("utf-8"))
 byte_count += char_bytes
 code_point = ord(ch)
 utf16_count += 2 if code_point > 0xFFFF else 1

 if byte_count != target_byte:
 raise ValueError(
 f"Byte offset {target_byte} not aligned with character boundary "
 f"(reached {byte_count})"
 )

 return utf16_count


def read_file_as_utf8(file_path: str) -> str:
 """
 UTF-8 .
 """
 with open(file_path, "r", encoding="utf-8", newline="") as f:
 return f.read()