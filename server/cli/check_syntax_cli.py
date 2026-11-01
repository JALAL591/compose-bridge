# -*- coding: utf-8 -*-
"""
Lightweight, ultra-fast Kotlin syntax checker CLI for real-time IDE plugin feedback.
Execution time: ~200ms (avoids loading heavy project scanner models).
"""
import sys
import json
from pathlib import Path

server_dir = Path(__file__).resolve().parent.parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from core.ast_finder import check_kotlin_syntax


def main():
    if len(sys.argv) > 1:
        target = sys.argv[1]
        path = Path(target)
        if path.exists():
            res = check_kotlin_syntax(path)
            res["file"] = path.name
            res["full_path"] = str(path.resolve())
            print(json.dumps(res, ensure_ascii=False))
            return
        else:
            print(json.dumps({"is_valid": False, "error": f"File not found: {target}", "line": 1, "column": 1}))
            return

    # Fallback to stdin
    try:
        content = sys.stdin.read()
        res = check_kotlin_syntax(content)
        print(json.dumps(res, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"is_valid": False, "error": str(e), "line": 1, "column": 1}))


if __name__ == "__main__":
    main()
