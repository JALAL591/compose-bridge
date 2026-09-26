# -*- coding: utf-8 -*-
"""
UTF-16 ↔ UTF-8 Offset Mapper.
Tree-sitter uses UTF-8 byte offsets.
Kotlin/JVM uses UTF-16 code units.
This module bridges the two via a prefix array.
"""

from pathlib import Path
from typing import Optional


class Utf16Utf8Mapper:
    """
    O(n) build, O(1) query.

    Maps byte offsets (UTF-8) to UTF-16 code unit offsets.
    """

    def __init__(self, content: bytes):
        self.content = content
        self._build_prefix_array()

    def _build_prefix_array(self):
        """Build prefix array: byte_pos → utf16_units."""
        self.utf8_to_utf16 = [0] * (len(self.content) + 1)
        utf16_units = 0
        i = 0

        while i < len(self.content):
            byte = self.content[i]

            if byte < 0x80:  # ASCII
                byte_len = 1
                utf16_len = 1
            elif byte < 0xE0:  # 2-byte
                byte_len = 2
                utf16_len = 1
            elif byte < 0xF0:  # 3-byte
                byte_len = 3
                utf16_len = 1
            else:  # 4-byte (astral plane, e.g., emoji)
                byte_len = 4
                utf16_len = 2

            for j in range(byte_len):
                if i + j < len(self.utf8_to_utf16):
                    self.utf8_to_utf16[i + j] = utf16_units

            utf16_units += utf16_len
            i += byte_len

        if len(self.utf8_to_utf16) > len(self.content):
            self.utf8_to_utf16[len(self.content)] = utf16_units

    def byte_to_utf16(self, byte_pos: int) -> int:
        """Convert UTF-8 byte offset to UTF-16 code unit offset."""
        if byte_pos < 0:
            return 0
        if byte_pos >= len(self.utf8_to_utf16):
            return self.utf8_to_utf16[-1]
        return self.utf8_to_utf16[byte_pos]

    def utf16_to_byte(self, utf16_pos: int) -> int:
        """Convert UTF-16 code unit offset to UTF-8 byte offset (binary search)."""
        lo, hi = 0, len(self.content)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.utf8_to_utf16[mid] < utf16_pos:
                lo = mid + 1
            else:
                hi = mid
        return lo


_mapper_cache: dict = {}


def get_mapper(file_path: Path) -> Optional[Utf16Utf8Mapper]:
    """Get or build mapper for a file, cached by mtime."""
    try:
        mtime = file_path.stat().st_mtime
        cache_key = str(file_path)

        if cache_key in _mapper_cache:
            cached_mtime, cached_mapper = _mapper_cache[cache_key]
            if cached_mtime == mtime:
                return cached_mapper

        content = file_path.read_bytes()
        mapper = Utf16Utf8Mapper(content)
        _mapper_cache[cache_key] = (mtime, mapper)
        return mapper
    except Exception:
        return None


def clear_cache():
    """Clear the mapper cache."""
    _mapper_cache.clear()
