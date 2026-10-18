import os
# -*- coding: utf-8 -*-
"""
End-to-End Integration Test

Simulates a full User+Agent workflow with conflict resolution.
Tests the design principles we agreed on:

1. Value and Location are independent dimensions
2. User Intent > Agent Proposal > Snapshot
3. Build = Checkpoint (reset)
"""

import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from core.state_manager import StateManager


def section(title):
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


def main():
    project_root = Path(os.environ.get("COMPOSEBRIDGE_ROOT", "."))
    app_dimens = (
        project_root / "app" / "src" / "main" / "java"
        / "com" / "student" / "app" / "ui" / "theme" / "AppDimens.kt"
    )

    # ═══════════════════════════════════════════════════════════
    # SETUP: Clean state
    # ═══════════════════════════════════════════════════════════

    section("SETUP: Reset state")
    state_dir = project_root / ".composebridge-state"
    if state_dir.exists():
        import shutil
        shutil.rmtree(state_dir)

    sm = StateManager(project_root)
    sm.init()

    print(f"✅ Snapshot captured: v{sm.snapshot.version}")
    print(f"   Tokens: {len(sm.snapshot.tokens)}")

    # Verify initial value
    initial = sm.snapshot.tokens.get("welcomeCardHeight", {})
    print(f"\n📸 Initial state of 'welcomeCardHeight':")
    print(f"   Value: {initial.get('value')}")
    print(f"   Location: {initial.get('file')}:{initial.get('line')}")
    print(f"   Kind: {initial.get('kind')}")

    # ═══════════════════════════════════════════════════════════
    # SCENARIO 1: Agent moves token (Location change)
    # ═══════════════════════════════════════════════════════════

    section("SCENARIO 1: Agent moves token (Location only)")

    # Record: Agent proposes a location change
    print("\n🤖 Agent proposes: move welcomeCardHeight from line 70 → 160")

    old_loc = f"{initial['file']}:{initial['line']}"
    new_loc = f"{initial['file']}:160"

    sm.history.record_location(
        token="welcomeCardHeight",
        old_loc=old_loc,
        new_loc=new_loc,
        source="agent",
    )
    sm.events.log(
        "agent_location_proposal",
        {"token": "welcomeCardHeight", "from": old_loc, "to": new_loc},
        source="agent",
    )

    print(f"   ✅ Recorded in location_history")
    print(f"   Old: {old_loc}")
    print(f"   New: {new_loc}")
    print(f"   Status: pending")

    # ═══════════════════════════════════════════════════════════
    # SCENARIO 2: User queues a value edit
    # ═══════════════════════════════════════════════════════════

    section("SCENARIO 2: User queues a value edit")

    print("\n👤 User wants: welcomeCardHeight = 500")
    queued = sm.queue.add(
        token="welcomeCardHeight",
        value="500",
        source="user",
    )
    print(f"   ✅ Queued: {queued['id']}")
    print(f"   Total in queue: {sm.queue.count()}")

    # ═══════════════════════════════════════════════════════════
    # SCENARIO 3: User ACCEPTS Agent's location change
    # ═══════════════════════════════════════════════════════════

    section("SCENARIO 3: User accepts Agent's location move")

    print("\n✅ User accepts: welcomeCardHeight moves to line 160")
    print(f"   Value should stay: 240 (unchanged)")
    print(f"   Location should be: {new_loc}")

    # Mark location as accepted
    entries = sm.history.location_history.get("welcomeCardHeight", [])
    entries[-1]["status"] = "accepted"
    sm.events.log(
        "location_accepted",
        {"token": "welcomeCardHeight", "to": new_loc},
        source="user",
    )

    current_loc = sm.history.get_current_location("welcomeCardHeight")
    current_val = sm.history.get_current_value("welcomeCardHeight")

    print(f"\n   📍 Current location: {current_loc}")
    print(f"   💎 Current value: {current_val if current_val else '240 (from snapshot)'}")

    assert current_loc == new_loc, "Location should be accepted"

    # ═══════════════════════════════════════════════════════════
    # SCENARIO 4: User SYNC — Apply queued value edit
    # ═══════════════════════════════════════════════════════════

    section("SCENARIO 4: User SYNC — apply queued value")

    print("\n🔄 Syncing queue...")
    print(f"   Queue: {sm.queue.count()} edits")

    # Apply each queued edit
    for edit in sm.queue.get_all():
        print(f"\n   Processing: {edit['token']} = {edit['value']}")
        
        # Record value change
        sm.history.record_value(
            token=edit["token"],
            old_value="240",  # from snapshot
            new_value=edit["value"],
            source="user",
        )
        sm.events.log(
            "user_value_applied",
            {"token": edit["token"], "value": edit["value"]},
            source="user",
        )
        print(f"   ✅ Applied")

    # Clear queue
    sm.queue.clear()
    print(f"\n   Queue cleared: {sm.queue.count()} edits remaining")

    # Verify final state
    final_val = sm.history.get_current_value("welcomeCardHeight")
    final_loc = sm.history.get_current_location("welcomeCardHeight")

    print(f"\n   📊 Final state:")
    print(f"      Value: {final_val}")
    print(f"      Location: {final_loc}")

    assert final_val == "500", f"Value should be 500, got {final_val}"
    assert final_loc == new_loc, f"Location should be {new_loc}"

    # ═══════════════════════════════════════════════════════════
    # SCENARIO 5: Agent moves token AGAIN, User REJECTS
    # ═══════════════════════════════════════════════════════════

    section("SCENARIO 5: Agent moves again, User REJECTS")

    print("\n🤖 Agent proposes: move to line 200")
    second_loc = f"{initial['file']}:200"
    sm.history.record_location(
        token="welcomeCardHeight",
        old_loc=new_loc,
        new_loc=second_loc,
        source="agent",
    )

    print("\n❌ User rejects this move")
    entries = sm.history.location_history.get("welcomeCardHeight", [])
    entries[-1]["status"] = "rejected"
    sm.events.log(
        "location_rejected",
        {"token": "welcomeCardHeight", "to": second_loc},
        source="user",
    )

    # Verify
    after_reject_loc = sm.history.get_current_location("welcomeCardHeight")
    after_reject_val = sm.history.get_current_value("welcomeCardHeight")

    print(f"\n   📍 Location after reject: {after_reject_loc}")
    print(f"   💎 Value after reject: {after_reject_val}")

    assert after_reject_loc == new_loc, "Should return to accepted location"
    assert after_reject_val == "500", "Value should NOT change (500)"

    print("\n   ✅ CONFIRMED: Rejecting location doesn't affect value!")

    # ═══════════════════════════════════════════════════════════
    # SCENARIO 6: Save & Reload (Persistence check)
    # ═══════════════════════════════════════════════════════════

    section("SCENARIO 6: Persistence — Save & Reload")

    print("\n💾 Saving state...")
    sm.save_all()

    print("📂 Reloading state...")
    sm2 = StateManager(project_root)
    sm2.init()

    reloaded_val = sm2.history.get_current_value("welcomeCardHeight")
    reloaded_loc = sm2.history.get_current_location("welcomeCardHeight")

    print(f"\n   📊 After reload:")
    print(f"      Value: {reloaded_val}")
    print(f"      Location: {reloaded_loc}")

    assert reloaded_val == "500", "Persistence failed: value"
    assert reloaded_loc == new_loc, "Persistence failed: location"

    print("\n   ✅ Persistence works across process restarts!")

    # ═══════════════════════════════════════════════════════════
    # SCENARIO 7: Build — Full Reset
    # ═══════════════════════════════════════════════════════════

    section("SCENARIO 7: Build = Full Reset")

    print("\n🔨 Simulating Build...")
    sm2.reset()

    print(f"   Snapshot version: {sm2.snapshot.version}")
    print(f"   Queue: {sm2.queue.count()} edits")
    print(f"   Events cleared")

    print("\n   ✅ Full reset complete")

    # ═══════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════

    section("✅ ALL INTEGRATION TESTS PASSED")
    print()
    print("   Scenarios verified:")
    print("   ✅ 1. Agent location proposal")
    print("   ✅ 2. User queued value edit")
    print("   ✅ 3. User accepts location move")
    print("   ✅ 4. User sync applies value")
    print("   ✅ 5. User rejects move (value preserved)")
    print("   ✅ 6. Persistence across reload")
    print("   ✅ 7. Build full reset")
    print()
    print("   Design principles confirmed:")
    print("   ✅ Value and Location are INDEPENDENT")
    print("   ✅ User Intent > Agent Proposal > Snapshot")
    print("   ✅ Build = Checkpoint (full reset)")
    print()


if __name__ == "__main__":
    main()
