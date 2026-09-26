"""
Utility functions for ComposeBridge Python Bridge.
"""

from pathlib import Path
from typing import Optional


def utf16_to_byte_offset(text: str, target_utf16: int) -> int:
    utf16_count = 0
    byte_count = 0

    for ch in text:
        if utf16_count >= target_utf16:
            break

        code_point = ord(ch)
        utf16_count += 2 if code_point > 0xFFFF else 1
        byte_count += len(ch.encode("utf-8"))

    if utf16_count != target_utf16:
        raise ValueError(
            f"UTF-16 offset {target_utf16} not aligned with character boundary "
            f"(reached {utf16_count})"
        )

    return byte_count


def byte_to_utf16_offset(text: str, target_byte: int) -> int:
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
    with open(file_path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def utf16_offset_to_byte_offset(file_path: Path, utf16_offset: int) -> Optional[int]:
    """Convert UTF-16 code unit offset to UTF-8 byte offset."""
    from .utf_mapper import get_mapper
    mapper = get_mapper(file_path)
    if mapper is None:
        return None
    return mapper.utf16_to_byte(utf16_offset)


def byte_offset_to_utf16_offset(file_path: Path, byte_offset: int) -> Optional[int]:
    """Convert UTF-8 byte offset to UTF-16 code unit offset."""
    from .utf_mapper import get_mapper
    mapper = get_mapper(file_path)
    if mapper is None:
        return None
    return mapper.byte_to_utf16(byte_offset)
