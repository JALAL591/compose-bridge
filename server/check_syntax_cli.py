# -*- coding: utf-8 -*-
"""
Lightweight, ultra-fast Kotlin syntax checker CLI for real-time IDE plugin feedback.
Forwarder to cli.check_syntax_cli.
"""
import sys
from pathlib import Path

server_dir = Path(__file__).resolve().parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from cli.check_syntax_cli import main, check_kotlin_syntax

if __name__ == "__main__":
    main()
