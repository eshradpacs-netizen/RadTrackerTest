"""
Radiology PC Tracker v1 - PACS PC Notes & Threaded Asistan Chat Service
Supports threaded sticky notes on workstations with author-only deletion and smart Telegram notifications.
"""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("pc_notes_service")

class PCNotesService:
    def __init__(self, db_instance, ws_manager_instance, bot_instance=None):
        self.db = db_instance
        self.ws_manager = ws_manager_instance
        self.bot = bot_instance

    def set_bot(self, bot_instance):
        self.bot = bot_instance

    def get_all_notes(self) -> Dict[str, Any]:
        """Returns all PC metadata notes."""
        return self.db.state.setdefault("pc_metadata", {})

    def get_pc_entry(self, pc_id: str) -> Dict[str, Any]:
        metadata = self.get_all_notes()
        return metadata.setdefault(pc_id.strip(), {
            "notes": "",
            "messages": [],
            "last_updated_at": 0,
            "last_updated_by": ""
        })

    async def add_message(self, pc_id: str, author_email: str, text: str, author_name: Optional[str] = None, pc_friendly_name: Optional[str] = None) -> Dict[str, Any]:
        """Adds a new message/note to a PC thread and triggers smart Telegram reply notifications."""
        pc_id = pc_id.strip()
        text = text.strip()
        author_email = author_email.strip().lower()
        if not text or not author_email:
            return {}

        pc_entry = self.get_pc_entry(pc_id)
        messages: List[Dict[str, Any]] = pc_entry.setdefault("messages", [])

        # Display name extraction (e.g. Dr. Ahmet or username part of email)
        if not author_name:
            author_name = "Dr. " + author_email.split("@")[0].capitalize()

        msg_id = f"msg_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
        now = time.time()
        time_str = time.strftime("%H:%M", time.localtime(now))

        new_msg = {
            "id": msg_id,
            "author_email": author_email,
            "author_name": author_name,
            "text": text,
            "timestamp": now,
            "time_str": time_str
        }

        # Check if this is a reply to an existing note (i.e. Dr. B replying to Dr. A)
        is_reply = len(messages) >= 1
        previous_authors = list(set([m["author_email"] for m in messages if m.get("author_email") and m["author_email"] != author_email]))

        messages.append(new_msg)
        pc_entry["notes"] = text # Keep last message as short preview
        pc_entry["last_updated_by"] = author_name
        pc_entry["last_updated_at"] = now

        await self.db.sync_to_telegram()

        # Broadcast over WebSocket in real time
        await self.ws_manager.broadcast({
            "type": "pc_note_update",
            "pc_id": pc_id,
            "messages": messages,
            "last_updated_by": author_name
        })

        # Smart Telegram Notification: Send notification to previous authors (e.g., Dr. A) when replied!
        if is_reply and previous_authors and self.bot:
            users = self.db.state.get("users", {})
            desk_name = pc_friendly_name or pc_id
            tg_text = (
                f"💬 <b>Masa Notunuza Yanıt Geldi!</b>\n\n"
                f"📍 <b>{desk_name}</b>\n"
                f"👤 <b>{author_name}</b>: <i>\"{text}\"</i>\n\n"
                f"🔗 <a href='https://esh-radtracker.onrender.com/miniapp.html'>RadTracker Canlı Paneli Aç</a>"
            )
            for prev_email in previous_authors:
                u = users.get(prev_email)
                if u and (u.get("chat_id") or u.get("telegram_id")):
                    try:
                        cid = int(u.get("chat_id") or u.get("telegram_id"))
                        await self.bot.send_message(cid, tg_text)
                        logger.info(f"Sent reply notification to {prev_email} ({cid})")
                    except Exception as e:
                        logger.warning(f"Could not send Telegram reply note alert to {prev_email}: {e}")

        return pc_entry

    async def delete_message(self, pc_id: str, message_id: str, requesting_email: str, is_admin: bool = False) -> bool:
        """Deletes a message if requested by its original author or an admin."""
        pc_id = pc_id.strip()
        requesting_email = requesting_email.strip().lower()
        pc_entry = self.get_pc_entry(pc_id)
        messages: List[Dict[str, Any]] = pc_entry.get("messages", [])

        target_idx = None
        for i, m in enumerate(messages):
            if m["id"] == message_id:
                if is_admin or m["author_email"] == requesting_email:
                    target_idx = i
                    break
                else:
                    return False # Unauthorized

        if target_idx is not None:
            messages.pop(target_idx)
            pc_entry["notes"] = messages[-1]["text"] if messages else ""
            await self.db.sync_to_telegram()
            await self.ws_manager.broadcast({
                "type": "pc_note_update",
                "pc_id": pc_id,
                "messages": messages
            })
            return True

        return False
