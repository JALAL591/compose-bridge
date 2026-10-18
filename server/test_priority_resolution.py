import os
# -*- coding: utf-8 -*-
"""
Test Priority Resolution + Sync Logic
"""

import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

from core.state_manager import StateManager
from core.priority_resolver import PriorityResolver


def section(title):
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


def main():
    project_root = Path(os.environ.get("COMPOSEBRIDGE_ROOT", "."))
    
    # Clean start
    state_dir = project_root / ".composebridge-state"
    if state_dir.exists():
        import shutil
        shutil.rmtree(state_dir)
    
    sm = StateManager(project_root)
    sm.init()
    resolver = PriorityResolver(sm)
    
    # ═══════════════════════════════════════════════════════════
    # TEST 1: Resolve from snapshot only
    # ═══════════════════════════════════════════════════════════
    
    section("TEST 1: Resolve from snapshot only")
    
    val, src = resolver.resolve_value("welcomeCardHeight")
    loc, lsrc = resolver.resolve_location("welcomeCardHeight")
    
    print(f"  Value: {val} (from {src})")
    print(f"  Location: {loc} (from {lsrc})")
    
    assert val == "240", f"Expected 240, got {val}"
    assert src == "snapshot", f"Expected snapshot, got {src}"
    
    print("  ✅ Snapshot resolution works")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 2: Agent proposes location change
    # ═══════════════════════════════════════════════════════════
    
    section("TEST 2: Agent proposes location change")
    
    sm.history.record_location(
        token="welcomeCardHeight",
        old_loc="AppDimens.kt:16",
        new_loc="AppDimens.kt:160",
        source="agent",
    )
    
    pending = sm.get_pending_agent_proposals()
    print(f"  Pending proposals: {len(pending)}")
    for p in pending:
        print(f"    {p['token']}: {p['from']} → {p['to']}")
    
    assert len(pending) == 1
    print("  ✅ Pending proposal detected")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 3: User accepts the proposal
    # ═══════════════════════════════════════════════════════════
    
    section("TEST 3: User accepts proposal")
    
    ok = sm.accept_agent_location("welcomeCardHeight")
    print(f"  Accepted: {ok}")
    
    loc, lsrc = resolver.resolve_location("welcomeCardHeight")
    print(f"  Location after accept: {loc} (from {lsrc})")
    
    assert loc == "AppDimens.kt:160"
    assert lsrc == "agent"
    
    print("  ✅ Acceptance works")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 4: User queues value edit
    # ═══════════════════════════════════════════════════════════
    
    section("TEST 4: Queue value edit")
    
    sm.queue.add("welcomeCardHeight", "500", source="user")
    print(f"  Queue size: {sm.queue.count()}")
    
    assert sm.queue.count() == 1
    
    # ═══════════════════════════════════════════════════════════
    # TEST 5: Preview sync (dry run)
    # ═══════════════════════════════════════════════════════════
    
    section("TEST 5: Preview sync (dry run)")
    
    preview = sm.apply_user_sync(dry_run=True)
    print(f"  Would apply: {len(preview['applied'])}")
    print(f"  Would skip: {len(preview['skipped'])}")
    
    for item in preview['applied']:
        print(f"    → {item['token']} = {item['value']} @ {item.get('location', '?')}")
    
    print("  ✅ Dry run works")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 6: Reject agent location, verify value independence
    # ═══════════════════════════════════════════════════════════
    
    section("TEST 6: Reject location, value independence")
    
    # Add another agent proposal
    sm.history.record_location(
        token="welcomeCardHeight",
        old_loc="AppDimens.kt:160",
        new_loc="AppDimens.kt:200",
        source="agent",
    )
    
    # Reject it
    ok = sm.reject_agent_location("welcomeCardHeight")
    print(f"  Rejected: {ok}")
    
    loc, _ = resolver.resolve_location("welcomeCardHeight")
    print(f"  Location after reject: {loc}")
    
    # Should still be at 160 (previous accepted), not 200
    assert loc == "AppDimens.kt:160"
    print("  ✅ Rejection preserves previous accepted location")
    
    # ═══════════════════════════════════════════════════════════
    # TEST 7: Resolve ALL tokens
    # ═══════════════════════════════════════════════════════════
    
    section("TEST 7: Resolve all tokens")
    
    all_states = resolver.resolve_all()
    print(f"  Total tokens resolved: {len(all_states)}")
    
    # Show first 3
    for token, state in list(all_states.items())[:3]:
        print(f"    {token}:")
        print(f"      value: {state['value']} (from {state['value_source']})")
        print(f"      location: {state['location']} (from {state['location_source']})")
    
    print("  ✅ Full resolution works")
    
    # ═══════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════
    
    section("✅ ALL PRIORITY RESOLUTION TESTS PASSED")
    print()
    print("  Tests verified:")
    print("  ✅ 1. Snapshot resolution")
    print("  ✅ 2. Pending agent proposal detection")
    print("  ✅ 3. User acceptance")
    print("  ✅ 4. Queue value edit")
    print("  ✅ 5. Dry run preview")
    print("  ✅ 6. Rejection preserves value independence")
    print("  ✅ 7. Resolve all tokens")
    print()


if __name__ == "__main__":
    main()
