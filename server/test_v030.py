# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.utf_mapper import Utf16Utf8Mapper
from core.ignore_rules import get_ignore_rules
from core.state_editor import _journal_save, rollback_last, SPLICE_JOURNAL


def test_emoji_roundtrip():
    content = "Hello 😀 World".encode("utf-8")
    mapper = Utf16Utf8Mapper(content)
    assert mapper.byte_to_utf16(6) == 6, f"Expected 6, got {mapper.byte_to_utf16(6)}"
    assert mapper.byte_to_utf16(10) == 8, f"Expected 8, got {mapper.byte_to_utf16(10)}"
    print("✅ test_emoji_roundtrip passed")


def test_arabic_roundtrip():
    content = "مرحباً بك".encode("utf-8")
    mapper = Utf16Utf8Mapper(content)
    assert mapper.byte_to_utf16(0) == 0
    assert mapper.byte_to_utf16(2) == 1
    assert mapper.byte_to_utf16(4) == 2
    print("✅ test_arabic_roundtrip passed")


def test_refuses_generated_code():
    rules = get_ignore_rules(Path("."))
    assert rules.is_ignored(Path("build/generated/foo.kt"))[0] is True
    assert rules.is_ignored(Path("app/src/main/java/Foo_Impl.kt"))[0] is True
    assert rules.is_ignored(Path("app/src/main/java/HeroCard.kt"))[0] is False
    print("✅ test_refuses_generated_code passed")


def test_journal_rollback():
    SPLICE_JOURNAL.clear()
    p = Path("test_dummy.kt")
    p.write_text("original", encoding="utf-8")
    _journal_save(p, "original", "modified")
    assert len(SPLICE_JOURNAL) == 1
    ok = rollback_last()
    assert ok is True
    assert p.read_text(encoding="utf-8") == "original"
    p.unlink(missing_ok=True)
    print("✅ test_journal_rollback passed")


if __name__ == "__main__":
    test_emoji_roundtrip()
    test_arabic_roundtrip()
    test_refuses_generated_code()
    test_journal_rollback()
    print("🎉 All v0.3.0 unit tests passed successfully!")
