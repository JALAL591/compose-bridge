import os
# -*- coding: utf-8 -*-
from pathlib import Path
import sys
_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

from core.state_manager import StateManager

# Test

if __name__ == '__main__':
    project_root = Path(os.environ.get("COMPOSEBRIDGE_ROOT", "."))
    sm = StateManager(project_root)
    
    print("1. Init...")
    sm.init()
    print(f"   Snapshot version: {sm.snapshot.version}")
    print(f"   Tokens: {len(sm.snapshot.tokens)}")
    print()
    
    print("2. Queue test...")
    sm.queue.add("welcomeCardHeight", "500")
    print(f"   Queue count: {sm.queue.count()}")
    print()
    
    print("3. History test...")
    sm.history.record_value("welcomeCardHeight", "240", "500", "user")
    sm.history.record_location(
        "welcomeCardHeight",
        "AppDimens.kt:70",
        "AppDimens.kt:160",
        "agent",
    )
    print(f"   Current value: {sm.history.get_current_value('welcomeCardHeight')}")
    print(f"   Current location: {sm.history.get_current_location('welcomeCardHeight')}")
    print()
    
    print("4. Events test...")
    sm.events.log("test_event", {"foo": "bar"})
    print(f"   Events count: {len(sm.events.read_all())}")
    print()
    
    print("5. Failures test...")
    sm.failures.record(
        operation="move_token",
        token="welcomeCardHeight",
        location="AppDimens.kt:160",
        error="AST parse failed",
    )
    print(f"   Unresolved failures: {len(sm.failures.get_unresolved())}")
    print()
    
    print("6. Save all...")
    sm.save_all()
    print(f"   State dir: {sm.state_dir}")
    print()
    
    print("=" * 50)
    print("✅ ALL TESTS PASSED")
    print("=" * 50)
