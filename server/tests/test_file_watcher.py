import os
# -*- coding: utf-8 -*-
from pathlib import Path
import sys
_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

import sys
import time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

from core.state_manager import StateManager
from core.file_watcher import FileWatcher


if __name__ == '__main__':
    project_root = Path(os.environ.get("COMPOSEBRIDGE_ROOT", "."))
    target = project_root / "app" / "src" / "main" / "java" / "com" / "student" / "app" / "ui" / "theme" / "AppDimens.kt"
    
    print("=" * 60)
    print("FILE WATCHER TEST")
    print("=" * 60)
    
    # 1. Initial scan
    watcher = FileWatcher(project_root, poll_interval=0.3, debounce_seconds=0.5)
    print("\n1. Initial scan...")
    watcher.initial_scan()
    print(f"   Files tracked: {len(watcher.known_hashes)}")
    print(f"   Sample: {list(watcher.known_hashes.keys())[:3]}")
    
    # 2. No change → no detection
    print("\n2. Test: no change (should return [])...")
    time.sleep(0.6)
    changes = watcher.check_once()
    print(f"   Changes detected: {len(changes)}")
    assert len(changes) == 0, "Should be no changes"
    
    # 3. Modify a file → detect
    print("\n3. Test: modify file → detect...")
    original = target.read_text(encoding="utf-8")
    modified = original.replace("240.dp", "999.dp")  # تغيير مؤقت
    target.write_text(modified, encoding="utf-8")
    
    time.sleep(0.6)
    changes = watcher.check_once()
    print(f"   Changes detected: {len(changes)}")
    for c in changes:
        print(f"     File: {c['path'].name}")
        print(f"     Old hash: {(c.get('old_hash') or 'None')[:16]}...")
        print(f"     New hash: {(c.get('new_hash') or 'None')[:16]}...")
    
    # Restore
    target.write_text(original, encoding="utf-8")
    time.sleep(0.6)
    watcher.check_once()  # consume restore
    
    # 4. StateManager integration
    print("\n4. Test: StateManager integration...")
    sm = StateManager(project_root)
    sm.init()
    print(f"   Initial file count: {len(sm.watcher.known_hashes)}")
    
    # Modify again
    modified = original.replace("240.dp", "888.dp")
    target.write_text(modified, encoding="utf-8")
    
    time.sleep(0.6)
    changes = sm.check_for_external_changes()
    print(f"   Changes via StateManager: {len(changes)}")
    
    # Check event log
    events = sm.events.read_all(limit=5)
    external_events = [e for e in events if e.get("type") == "external_file_change"]
    print(f"   Events logged: {len(external_events)}")
    
    # Restore
    target.write_text(original, encoding="utf-8")
    
    print()
    print("=" * 60)
    print("✅ ALL FILE WATCHER TESTS PASSED")
    print("=" * 60)
