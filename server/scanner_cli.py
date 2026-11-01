# -*- coding: utf-8 -*-
"""
Scanner CLI — Run from terminal.
Forwarder to cli.scanner_cli.
"""
import sys
from pathlib import Path

server_dir = Path(__file__).resolve().parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from cli.scanner_cli import main

if __name__ == "__main__":
    main()
