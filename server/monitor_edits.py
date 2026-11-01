# -*- coding: utf-8 -*-
"""
ComposeBridge Live Audit & Monitor CLI
Forwarder to cli.monitor_edits.
"""
import sys
from pathlib import Path

server_dir = Path(__file__).resolve().parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from cli.monitor_edits import main, RealtimeMonitor

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
