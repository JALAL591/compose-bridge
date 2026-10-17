"""
Data models for ComposeBridge Python Bridge.
All messages between phone and Python use these shapes.
"""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class EditRequest:
    """
    رسالة من الهاتف تطلب تعديل خاصية في الكود.

    Attributes:
        file: اسم ملف Kotlin (بدون مسار كامل، مثل "HomeScreenForTest.kt")
        utf16_offset: موقع بداية التعبير في الملف (بـ UTF-16 code units)
        utf16_length: طول التعبير (بـ UTF-16 code units)
        composable: اسم الـ composable (مثل "Card"، "Text")
        property: اسم الخاصية المراد تعديلها (مثل "padding"، "color")
        current_value: القيمة الحالية (للتحقق قبل التعديل)
        new_value: القيمة الجديدة المطلوبة
        request_id: معرّف فريد للطلب (UUID)
    """
    file: str
    utf16_offset: int
    utf16_length: int
    composable: str
    property: str
    current_value: str
    new_value: str
    request_id: str


@dataclass
class EditResponse:
    """
    رد Python على الهاتف.

    Attributes:
        request_id: نفس request_id الذي وصل
        status: "success" أو "error"
        old_value: القيمة القديمة (عند النجاح)
        new_value: القيمة الجديدة (عند النجاح)
        error_code: كود الخطأ (عند الفشل)
        error_message: وصف الخطأ (عند الفشل)
    """
    request_id: str
    status: str  # "success" | "error"
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class SourceLocation:
    """
    معلومات موقع في ملف Kotlin.
    تُستخدم داخلياً في Python.
    """
    file: str
    utf16_offset: int
    utf16_length: int
    byte_offset: Optional[int] = None
    byte_length: Optional[int] = None
    line: Optional[int] = None


# ============================================================
# Error codes — معيارية
# ============================================================
class ErrorCode:
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    INVALID_OFFSET = "INVALID_OFFSET"
    NODE_NOT_FOUND = "NODE_NOT_FOUND"
    NODE_TYPE_MISMATCH = "NODE_TYPE_MISMATCH"
    PROPERTY_NOT_FOUND = "PROPERTY_NOT_FOUND"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    AMBIGUOUS_NODE = "AMBIGUOUS_NODE"
    PARSE_ERROR = "PARSE_ERROR"
    FILE_CHANGED = "FILE_CHANGED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
