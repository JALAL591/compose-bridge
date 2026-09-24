"""
Data models for ComposeBridge Python Bridge.
All messages between phone and Python use these shapes.
"""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class EditRequest:
 """
 From device .

 Attributes:
 file: Kotlin ( "HomeScreenForTest.kt")
 utf16_offset: Start File ( UTF-16 code units)
 utf16_length: ( UTF-16 code units)
 composable: composable ( "Card" "Text")
 property: ( "padding" "color")
 current_value: ( Edit)
 new_value: 
 request_id: (UUID)
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
 Python .

 Attributes:
 request_id: request_id 
 status: "success" "error"
 old_value: ( Success)
 new_value: ( Success)
 error_code: Error ( Failure)
 error_message: Error ( Failure)
 """
 request_id: str
 status: str # "success" | "error"
 old_value: Optional[str] = None
 new_value: Optional[str] = None
 error_code: Optional[str] = None
 error_message: Optional[str] = None


@dataclass
class SourceLocation:
 """
 Kotlin.
 Python.
 """
 file: str
 utf16_offset: int
 utf16_length: int
 byte_offset: Optional[int] = None
 byte_length: Optional[int] = None
 line: Optional[int] = None


# ============================================================
# Error codes — 
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