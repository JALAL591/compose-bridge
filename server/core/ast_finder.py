"""
AST Finder — Tree-sitter integration for Kotlin parsing.
"""

from pathlib import Path
from typing import Optional, List
from tree_sitter import Language, Parser
import tree_sitter_kotlin


# ============================================================
# إعداد Tree-sitter
# ============================================================

try:
    KOTLIN_LANGUAGE = Language(tree_sitter_kotlin.language())
    PARSER = Parser(KOTLIN_LANGUAGE)
except Exception as e:
    raise RuntimeError(f"Failed to initialize tree-sitter-kotlin: {e}")


# ============================================================
# Data structures
# ============================================================

class AstNode:
    """يمثل عقدة في شجرة AST."""

    def __init__(self, node, source_bytes: bytes):
        self._node = node
        self._source = source_bytes

    @property
    def type(self) -> str:
        return self._node.type

    @property
    def start_byte(self) -> int:
        return self._node.start_byte

    @property
    def end_byte(self) -> int:
        return self._node.end_byte

    @property
    def start_point(self) -> tuple:
        return self._node.start_point

    @property
    def end_point(self) -> tuple:
        return self._node.end_point

    @property
    def text(self) -> str:
        return self._source[self.start_byte:self.end_byte].decode("utf-8", errors="replace")

    @property
    def children(self) -> list:
        return [AstNode(c, self._source) for c in self._node.children]

    @property
    def child_count(self) -> int:
        return self._node.child_count

    @property
    def is_named(self) -> bool:
        return self._node.is_named

    def __repr__(self):
        line = self.start_point[0] + 1
        col = self.start_point[1]
        return f"<{self.type} @ {line}:{col} bytes={self.start_byte}-{self.end_byte}>"


# ============================================================
# Parsing
# ============================================================

def parse_file(file_path: str) -> tuple:
    """
    يحلل ملف Kotlin ويعيد (tree, source_bytes).

    Args:
        file_path: المسار الكامل للملف

    Returns:
        (tree, source_bytes)

    Raises:
        FileNotFoundError: إذا كان الملف غير موجود
        RuntimeError: إذا فشل التحليل
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(path, "rb") as f:
        source_bytes = f.read()

    tree = PARSER.parse(source_bytes)

    if tree.root_node.has_error:
        # نطبع تحذيراً لكن نكمل
        print(f"[WARN] Parse errors detected in {file_path}")

    return tree, source_bytes


def find_node_at_byte(tree, source_bytes: bytes, byte_offset: int) -> Optional[AstNode]:
    """
    يجد أعمق عقدة تحتوي على byte_offset.

    Args:
        tree: شجرة tree-sitter
        source_bytes: محتوى الملف
        byte_offset: الموقع المطلوب

    Returns:
        AstNode أو None إذا لم توجد
    """
    root = tree.root_node

    if not (root.start_byte <= byte_offset <= root.end_byte):
        return None

    def find_deepest(node):
        if node.start_byte <= byte_offset <= node.end_byte:
            for child in node.children:
                if child.start_byte <= byte_offset <= child.end_byte:
                    return find_deepest(child)
            return node
        return None

    deepest = find_deepest(root)
    if deepest is None:
        return None

    return AstNode(deepest, source_bytes)


def _call_expression_has_name(node, source_bytes: bytes, target_name: str) -> bool:
    """
    يتحقق هل call_expression يحمل الاسم المستهدف.

    حالات:
      1. call_expression → identifier "Card"          ← children[0] type == identifier
      2. call_expression → navigation_expression → identifier "padding"  ← last identifier
      3. call_expression → call_expression + '.' + identifier "padding"   ← middle identifier
    """
    if node.child_count == 0:
        return False

    # الحالة 1: children[0] هو identifier
    first = node.children[0]
    if first.type == "identifier":
        name = source_bytes[first.start_byte:first.end_byte].decode("utf-8", errors="replace")
        if name == target_name:
            return True

    # الحالة 2: children[0] هو navigation_expression
    if first.type == "navigation_expression":
        # آخر identifier في navigation
        last_ident = None
        for sub in first.children:
            if sub.type == "identifier":
                last_ident = sub
        if last_ident:
            name = source_bytes[last_ident.start_byte:last_ident.end_byte].decode("utf-8", errors="replace")
            if name == target_name:
                return True

    # الحالة 3: البحث في كل الأبناء (method chain)
    # ابحث عن identifier يسبق value_arguments مباشرة
    children = list(node.children)
    for i, child in enumerate(children):
        if child.type == "identifier":
            name = source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
            if name == target_name:
                # تحقق أنه يسبق value_arguments
                if i + 1 < len(children) and children[i + 1].type == "value_arguments":
                    return True

    return False


def find_all_call_expressions(tree, source_bytes: bytes, function_name: str) -> list:
    """
    يجد كل استدعاءات دالة باسم معين.
    يدعم كلاً من:
      - استدعاء بسيط:    Card(...)
      - Method chain:    Modifier.padding(...)
      - Chain متعدد:     Modifier.fillMaxWidth().padding(...)
    """
    results = []

    def walk(node):
        if node.type == "call_expression":
            if _call_expression_has_name(node, source_bytes, function_name):
                results.append(AstNode(node, source_bytes))

        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return results


def count_nodes_by_type(tree) -> dict:
    """
    يُحصي كل أنواع العقد في الشجرة (للتشخيص).
    """
    counts = {}

    def walk(node):
        counts[node.type] = counts.get(node.type, 0) + 1
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return counts


def find_composable_at_line(
    tree,
    source_bytes: bytes,
    line: int,
    composable_name: str,
    line_tolerance: int = 1
) -> Optional[AstNode]:
    """
    يجد استدعاء composable على سطر معين (مع تسامح بسيط).

    هذه استراتيجية أكثر موثوقية من الاعتماد على offset،
    لأن line numbers تتطابق دائماً بين Compose و Tree-sitter.

    Args:
        tree: شجرة tree-sitter
        source_bytes: محتوى الملف
        line: رقم السطر (1-based)
        composable_name: اسم الدالة (مثل "Card")
        line_tolerance: عدد الأسطر حول الهدف للبحث

    Returns:
        AstNode إذا وُجد، أو None
    """
    candidates = find_all_call_expressions(tree, source_bytes, composable_name)

    if not candidates:
        return None

    target_line_0 = line - 1  # tree-sitter 0-based

    # ابحث عن أفضل مرشح
    best = None
    best_distance = line_tolerance + 1

    for node in candidates:
        node_line = node.start_point[0]  # 0-based
        distance = abs(node_line - target_line_0)

        if distance <= line_tolerance and distance < best_distance:
            best = node
            best_distance = distance
        elif distance == best_distance and best is not None:
            # عند التساوي، اختر الأقرب بالعمود (لو حصلنا على column لاحقاً)
            pass

    return best


def find_all_call_expressions_in_node(node, source_bytes: bytes, function_name: str) -> list:
    """
    يجد كل استدعاءات دالة معينة داخل node (متداخلة).
    يستخدم نفس منطق find_all_call_expressions لكن داخل نطاق محدد.
    """
    results = []
    ts_node = node._node
    source = source_bytes

    def walk(n):
        if n.type == "call_expression":
            if _call_expression_has_name(n, source, function_name):
                results.append(AstNode(n, source))

        for child in n.children:
            walk(child)

    walk(ts_node)
    return results


def extract_literal_value(call_node: AstNode) -> Optional[tuple]:
    """
    يستخرج القيمة الحرفية من call_expression.
    يعيد (value_text, byte_start, byte_end) أو None.

    يتعامل مع:
    - padding(16.dp) → ("16.dp", start, end)
    - Modifier.fillMaxWidth().padding(16.dp) → ("16.dp", start, end)
    - Card(modifier = Modifier.padding(16.dp)) → نفس النتيجة
    """
    ts_node = call_node._node
    source = call_node._source

    children = list(ts_node.children)

    # ابحث عن identifier يسبق value_arguments مباشرة
    # (هذا هو اسم الخاصية الحقيقية داخل الـ chain)
    for i, child in enumerate(children):
        if child.type == "identifier":
            # تحقق أن اللي بعده value_arguments
            if i + 1 < len(children) and children[i + 1].type == "value_arguments":
                value_args = children[i + 1]

                # ابحث عن أول value_argument داخل value_arguments
                for va in value_args.children:
                    if va.type == "value_argument":
                        text = source[va.start_byte:va.end_byte].decode("utf-8", errors="replace")
                        return (text, va.start_byte, va.end_byte)

    # حالة احتياطية: call بسيط (Card, Text) بدون chain
    # ابحث عن أول value_arguments في الأبناء المباشرين
    for child in children:
        if child.type == "value_arguments":
            for va in child.children:
                if va.type == "value_argument":
                    text = source[va.start_byte:va.end_byte].decode("utf-8", errors="replace")
                    return (text, va.start_byte, va.end_byte)

    return None


def find_property_in_node(node: AstNode, source_bytes: bytes, property_name: str) -> Optional[AstNode]:
    """
    يجد خاصية معينة داخل node.
    يعيد أول AstNode يحمل اسم الخاصية.
    """
    calls = find_all_call_expressions_in_node(node, source_bytes, property_name)
    if calls:
        return calls[0]
    return None


def debug_dump_structure(node, source_bytes: bytes, max_depth: int = 5):
    """
    يطبع بنية شجرة AST بشكل مقروء للتشخيص.
    """
    def walk(n, depth):
        if depth > max_depth:
            return
        indent = "  " * depth
        text = source_bytes[n.start_byte:n.end_byte].decode("utf-8", errors="replace")
        short_text = text[:50].replace("\n", "\\n")
        print(f"{indent}<{n.type}> '{short_text}'")
        for child in n.children:
            walk(child, depth + 1)

    walk(node._node, 0)


def surgical_edit(
    file_path: str,
    byte_start: int,
    byte_end: int,
    expected_old_value: str,
    new_value: str,
) -> tuple:
    """
    ينفذ تعديلاً جراحياً على ملف Kotlin.

    الخطوات:
    1. قراءة الملف كـ bytes
    2. التحقق: القيمة الحالية عند byte_start..byte_end == expected_old_value
    3. استبدال فقط هذه البايتات
    4. كتابة ذرية (temp + rename)
    5. إنشاء نسخة احتياطية

    Args:
        file_path: مسار الملف
        byte_start: بداية النطاق
        byte_end: نهاية النطاق
        expected_old_value: القيمة المتوقعة (للتحقق)
        new_value: القيمة الجديدة

    Returns:
        (success: bool, message: str, backup_path: str | None)
    """
    import os
    import shutil
    import tempfile

    path = Path(file_path)
    if not path.exists():
        return (False, f"File not found: {file_path}", None)

    # 1. اقرأ الملف
    with open(path, "rb") as f:
        source = f.read()

    # 2. افحص النطاق
    if not (0 <= byte_start < byte_end <= len(source)):
        return (False, f"Invalid byte range: {byte_start}-{byte_end}", None)

    current_value = source[byte_start:byte_end].decode("utf-8", errors="replace")

    if current_value != expected_old_value:
        return (
            False,
            f"Value mismatch: expected '{expected_old_value}', found '{current_value}'",
            None
        )

    # 3. أنشئ النسخة الاحتياطية
    backup_path = str(path) + ".bridge.bak"
    shutil.copy2(path, backup_path)

    # 4. ابنِ المحتوى الجديد
    new_source = (
        source[:byte_start]
        + new_value.encode("utf-8")
        + source[byte_end:]
    )

    # 5. كتابة ذرية: temp file ثم rename
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            delete=False,
            prefix=path.name + ".tmp_",
        ) as tmp:
            tmp.write(new_source)
            tmp_path = tmp.name

        # rename يضمن atomicity
        os.replace(tmp_path, path)
    except Exception as e:
        # حاول إزالة الـ temp
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except:
            pass
        return (False, f"Write failed: {e}", backup_path)

    return (
        True,
        f"Edited {byte_start}-{byte_end}: '{expected_old_value}' → '{new_value}'",
        backup_path
    )
