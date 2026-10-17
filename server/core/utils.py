"""
Utility functions for ComposeBridge Python Bridge.
"""


def utf16_to_byte_offset(text: str, target_utf16: int) -> int:
    """
    يحول offset من UTF-16 code units إلى UTF-8 bytes.

    Compose يعطي offsets بـ UTF-16 code units.
    Python يقرأ الملفات بـ UTF-8 bytes.
    هذه الدالة تصلح الفرق.

    Args:
        text: محتوى الملف كـ str
        target_utf16: offset المطلوب بـ UTF-16 units

    Returns:
        offset مقابل بـ UTF-8 bytes

    Raises:
        ValueError: إذا كان offset غير متوافق مع حدود الأحرف

    Example:
        text = "Hello مرحبا"
        utf16_to_byte_offset(text, 6) # 6
        utf16_to_byte_offset(text, 8) # 8 (بعد "م")
    """
    utf16_count = 0
    byte_count = 0

    for ch in text:
        if utf16_count >= target_utf16:
            break

        code_point = ord(ch)

        # الأحرف خارج BMP (مثل الإيموجي) تشغل وحدتي UTF-16
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
    العملية العكسية: من UTF-8 bytes إلى UTF-16 code units.
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
    يقرأ ملفاً كنص UTF-8 مع الحفاظ على نهايات الأسطر كما هي.
    """
    with open(file_path, "r", encoding="utf-8", newline="") as f:
        return f.read()
