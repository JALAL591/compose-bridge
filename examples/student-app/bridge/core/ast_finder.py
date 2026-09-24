"""
AST Finder — Tree-sitter integration for Kotlin parsing.
"""

from pathlib import Path
from typing import Optional, List
from tree_sitter import Language, Parser
import tree_sitter_kotlin


# ============================================================
# Tree-sitter
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
 """ AST."""

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
 Kotlin (tree, source_bytes).

 Args:
 file_path: Path 

 Returns:
 (tree, source_bytes)

 Raises:
 FileNotFoundError: File 
 RuntimeError: Failure Analyze
 """
 path = Path(file_path)
 if not path.exists():
 raise FileNotFoundError(f"File not found: {file_path}")

 with open(path, "rb") as f:
 source_bytes = f.read()

 tree = PARSER.parse(source_bytes)

 if tree.root_node.has_error:
 # 
 print(f"[WARN] Parse errors detected in {file_path}")

 return tree, source_bytes


def find_node_at_byte(tree, source_bytes: bytes, byte_offset: int) -> Optional[AstNode]:
 """
 byte_offset.

 Args:
 tree: tree-sitter
 source_bytes: File
 byte_offset: Location 

 Returns:
 AstNode None 
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
 call_expression .

 :
 1. call_expression → identifier "Card" ← children[0] type == identifier
 2. call_expression → navigation_expression → identifier "padding" ← last identifier
 3. call_expression → call_expression + '.' + identifier "padding" ← middle identifier
 """
 if node.child_count == 0:
 return False

 # 1: children[0] identifier
 first = node.children[0]
 if first.type == "identifier":
 name = source_bytes[first.start_byte:first.end_byte].decode("utf-8", errors="replace")
 if name == target_name:
 return True

 # 2: children[0] navigation_expression
 if first.type == "navigation_expression":
 # identifier navigation
 last_ident = None
 for sub in first.children:
 if sub.type == "identifier":
 last_ident = sub
 if last_ident:
 name = source_bytes[last_ident.start_byte:last_ident.end_byte].decode("utf-8", errors="replace")
 if name == target_name:
 return True

 # 3: Search (method chain)
 # identifier value_arguments 
 children = list(node.children)
 for i, child in enumerate(children):
 if child.type == "identifier":
 name = source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
 if name == target_name:
 # value_arguments
 if i + 1 < len(children) and children[i + 1].type == "value_arguments":
 return True

 return False


def find_all_call_expressions(tree, source_bytes: bytes, function_name: str) -> list:
 """
 .
 :
 - : Card(...)
 - Method chain: Modifier.padding(...)
 - Chain : Modifier.fillMaxWidth().padding(...)
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
 ( ).
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
 composable ( ).

 offset 
 line numbers Compose Tree-sitter.

 Args:
 tree: tree-sitter
 source_bytes: File
 line: (1-based)
 composable_name: ( "Card")
 line_tolerance: 

 Returns:
 AstNode None
 """
 candidates = find_all_call_expressions(tree, source_bytes, composable_name)

 if not candidates:
 return None

 target_line_0 = line - 1 # tree-sitter 0-based

 # 
 best = None
 best_distance = line_tolerance + 1

 for node in candidates:
 node_line = node.start_point[0] # 0-based
 distance = abs(node_line - target_line_0)

 if distance <= line_tolerance and distance < best_distance:
 best = node
 best_distance = distance
 elif distance == best_distance and best is not None:
 # ( column )
 pass

 return best


def find_all_call_expressions_in_node(node, source_bytes: bytes, function_name: str) -> list:
 """
 node ( ).
 find_all_call_expressions .
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
 call_expression.
 (value_text, byte_start, byte_end) None.

 :
 - padding(16.dp) → ("16.dp", start, end)
 - Modifier.fillMaxWidth().padding(16.dp) → ("16.dp", start, end)
 - Card(modifier = Modifier.padding(16.dp)) → 
 """
 ts_node = call_node._node
 source = call_node._source

 children = list(ts_node.children)

 # identifier value_arguments 
 # ( chain)
 for i, child in enumerate(children):
 if child.type == "identifier":
 # value_arguments
 if i + 1 < len(children) and children[i + 1].type == "value_arguments":
 value_args = children[i + 1]

 # value_argument value_arguments
 for va in value_args.children:
 if va.type == "value_argument":
 text = source[va.start_byte:va.end_byte].decode("utf-8", errors="replace")
 return (text, va.start_byte, va.end_byte)

 # : call (Card, Text) chain
 # value_arguments 
 for child in children:
 if child.type == "value_arguments":
 for va in child.children:
 if va.type == "value_argument":
 text = source[va.start_byte:va.end_byte].decode("utf-8", errors="replace")
 return (text, va.start_byte, va.end_byte)

 return None


def find_property_in_node(node: AstNode, source_bytes: bytes, property_name: str) -> Optional[AstNode]:
 """
 node.
 AstNode .
 """
 calls = find_all_call_expressions_in_node(node, source_bytes, property_name)
 if calls:
 return calls[0]
 return None


def debug_dump_structure(node, source_bytes: bytes, max_depth: int = 5):
 """
 AST .
 """
 def walk(n, depth):
 if depth > max_depth:
 return
 indent = " " * depth
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
 Kotlin.

 :
 1. File bytes
 2. : byte_start..byte_end == expected_old_value
 3. 
 4. (temp + rename)
 5. Create 

 Args:
 file_path: File
 byte_start: Start 
 byte_end: End 
 expected_old_value: ( )
 new_value: 

 Returns:
 (success: bool, message: str, backup_path: str | None)
 """
 import os
 import shutil
 import tempfile

 path = Path(file_path)
 if not path.exists():
 return (False, f"File not found: {file_path}", None)

 # 1. File
 with open(path, "rb") as f:
 source = f.read()

 # 2. 
 if not (0 <= byte_start < byte_end <= len(source)):
 return (False, f"Invalid byte range: {byte_start}-{byte_end}", None)

 current_value = source[byte_start:byte_end].decode("utf-8", errors="replace")

 if current_value != expected_old_value:
 return (
 False,
 f"Value mismatch: expected '{expected_old_value}', found '{current_value}'",
 None
 )

 # 3. 
 backup_path = str(path) + ".bridge.bak"
 shutil.copy2(path, backup_path)

 # 4. 
 new_source = (
 source[:byte_start]
 + new_value.encode("utf-8")
 + source[byte_end:]
 )

 # 5. : temp file rename
 try:
 with tempfile.NamedTemporaryFile(
 mode="wb",
 dir=path.parent,
 delete=False,
 prefix=path.name + ".tmp_",
 ) as tmp:
 tmp.write(new_source)
 tmp_path = tmp.name

 # rename atomicity
 os.replace(tmp_path, path)
 except Exception as e:
 # temp
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