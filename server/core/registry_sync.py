# -*- coding: utf-8 -*-
"""
Registry ↔ Source Synchronization.
Ensures both sides stay in sync — one source of truth.
"""

import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Set


class RegistrySyncManager:
    """
    Manages bidirectional sync between:
    - Source files (.kt on disk)
    - Registry state (BridgeDimensionRegistry, BridgeThemeRegistry in-app)
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.clients: Set = set()
        self._watcher_task: Optional[asyncio.Task] = None
        self._last_state: Dict[str, str] = {}

    def register_client(self, websocket):
        """Register a connected client."""
        self.clients.add(websocket)

    def unregister_client(self, websocket):
        """Unregister a client."""
        self.clients.discard(websocket)

    async def broadcast_to_clients(self, message: dict):
        """Send state update to all connected clients."""
        dead = []
        payload = json.dumps(message)
        for client in list(self.clients):
            try:
                await client.send(payload)
            except Exception:
                dead.append(client)
        for client in dead:
            self.clients.discard(client)

    def notify_source_changed(self, file_path: str, property_name: str, new_value: str):
        """
        Called when source file changes.
        Schedules a registry update on all connected clients.
        """
        asyncio.create_task(self.broadcast_to_clients({
            "type": "source_changed",
            "file": file_path,
            "property": property_name,
            "value": new_value,
        }))

    def notify_registry_changed(self, property_name: str, new_value: str):
        """Called when registry changes."""
        pass


_sync_manager: Optional[RegistrySyncManager] = None


def get_sync_manager(project_root: Path) -> RegistrySyncManager:
    """Get or create sync manager."""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = RegistrySyncManager(project_root)
    return _sync_manager
