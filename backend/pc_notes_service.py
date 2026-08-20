"""
Radiology PC Tracker v1 - PACS PC Notes & Tags Service
Manages doctor notes, tags, and status metadata for workstations.
"""

import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("pc_notes_service")

class PCNotesService:
    def __init__(self, db_instance, ws_manager_instance):
        self.db = db_instance
        self.ws_manager = ws_manager_instance

    def get_all_notes(self) -> Dict[str, Any]:
        """Returns all PC metadata notes."""
        return self.db.state.setdefault("pc_metadata", {})

    async def update_pc_note(self, pc_id: str, notes: str, friendly_name: Optional[str] = None, room: Optional[str] = None, author: str = "Hekim") -> Dict[str, Any]:
        """Updates note, friendlyName, or room for a specific PC."""
        pc_id = pc_id.strip()
        metadata = self.get_all_notes()
        
        pc_entry = metadata.setdefault(pc_id, {})
        if notes is not None:
            pc_entry["notes"] = notes.strip()
        if friendly_name:
            pc_entry["friendlyName"] = friendly_name.strip()
        if room:
            pc_entry["room"] = room.strip()
            
        pc_entry["last_updated_by"] = author
        pc_entry["last_updated_at"] = time.time()

        await self.db.sync_to_telegram()

        # Broadcast update over WebSockets
        await self.ws_manager.broadcast({
            "type": "pc_note_update",
            "pc_id": pc_id,
            "metadata": pc_entry
        })

        return pc_entry
