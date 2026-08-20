"""
Radiology PC Tracker v1 - Live Chat & Inter-Physician Messaging Service
Manages public room chat and 1-on-1 private messaging between resident doctors.
"""

import time
import uuid
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("chat_service")

class ChatService:
    def __init__(self, db_instance, ws_manager_instance):
        self.db = db_instance
        self.ws_manager = ws_manager_instance

    def _get_public_messages(self) -> List[Dict[str, Any]]:
        return self.db.state.setdefault("chat_messages", [])

    def _get_private_messages(self) -> List[Dict[str, Any]]:
        return self.db.state.setdefault("private_chat_messages", [])

    async def send_public_message(self, sender_email: str, text: str) -> Dict[str, Any]:
        """Sends a message to the general physician room chat."""
        msg_id = str(uuid.uuid4())
        sender_name = sender_email.split("@")[0]
        timestamp = time.time()

        msg = {
            "id": msg_id,
            "sender_email": sender_email,
            "sender_name": sender_name,
            "text": text.strip(),
            "timestamp": timestamp,
            "type": "public"
        }

        messages = self._get_public_messages()
        messages.append(msg)
        # Keep last 200 public messages
        if len(messages) > 200:
            self.db.state["chat_messages"] = messages[-200:]

        await self.db.sync_to_telegram()

        # Broadcast real-time WebSocket update
        await self.ws_manager.broadcast({
            "type": "chat_message",
            "message": msg
        })

        return msg

    async def send_private_message(self, sender_email: str, recipient_email: str, text: str) -> Dict[str, Any]:
        """Sends a 1-on-1 private message to another physician."""
        msg_id = str(uuid.uuid4())
        sender_name = sender_email.split("@")[0]
        timestamp = time.time()

        msg = {
            "id": msg_id,
            "sender_email": sender_email,
            "sender_name": sender_name,
            "recipient_email": recipient_email.lower().strip(),
            "text": text.strip(),
            "timestamp": timestamp,
            "is_read": False,
            "type": "private"
        }

        private_msgs = self._get_private_messages()
        private_msgs.append(msg)
        # Keep last 500 private messages
        if len(private_msgs) > 500:
            self.db.state["private_chat_messages"] = private_msgs[-500:]

        await self.db.sync_to_telegram()

        # Broadcast real-time WebSocket update
        await self.ws_manager.broadcast({
            "type": "private_chat_message",
            "message": msg
        })

        return msg

    def get_public_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns public chat history."""
        messages = self._get_public_messages()
        return messages[-limit:]

    def get_private_history(self, email1: str, email2: str) -> List[Dict[str, Any]]:
        """Returns 1-on-1 private chat history between two physicians."""
        e1, e2 = email1.lower().strip(), email2.lower().strip()
        private_msgs = self._get_private_messages()

        res = [
            m for m in private_msgs
            if (m.get("sender_email") == e1 and m.get("recipient_email") == e2) or
               (m.get("sender_email") == e2 and m.get("recipient_email") == e1)
        ]
        return res[-50:]

    def mark_private_as_read(self, user_email: str, sender_email: str):
        """Marks private messages sent from sender_email to user_email as read."""
        u_email = user_email.lower().strip()
        s_email = sender_email.lower().strip()

        private_msgs = self._get_private_messages()
        for m in private_msgs:
            if m.get("recipient_email") == u_email and m.get("sender_email") == s_email:
                m["is_read"] = True
