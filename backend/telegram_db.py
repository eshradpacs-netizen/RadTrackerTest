"""
Radiology PC Tracker v1 - Telegram-as-a-Database (Telegram-DB) Engine
Provides zero-cost, infinite cloud persistence using Telegram Channels/Chats & Pinned State Snapshots.
Supports local JSON fallback when offline or unconfigured.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("telegram_db")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
LOCAL_DB_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "telegram_db.json")

class TelegramDB:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.local_path = LOCAL_DB_FILE
        self.state: Dict[str, Any] = {
            "users": {},          # email -> user dict
            "allowed_emails": [], # list of whitelisted emails
            "pc_metadata": {},    # pc_id -> {friendlyName, room, notes}
            "subscribers": {}     # user_id -> [pc_id list to notify when free]
        }
        self.state_message_id: Optional[int] = None
        self._ensure_data_dir()
        self.load_local()

    def _ensure_data_dir(self):
        os.makedirs(os.path.dirname(self.local_path), exist_ok=True)

    def load_local(self):
        """Loads state from local JSON fallback file."""
        try:
            if os.path.exists(self.local_path):
                with open(self.local_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        self.state = json.loads(content)
                        logger.info("Loaded Telegram-DB state from local storage.")
        except Exception as e:
            logger.error(f"Error loading local DB: {e}")

    def save_local(self):
        """Saves current state to local JSON fallback file."""
        try:
            with open(self.local_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving local DB: {e}")

    async def sync_to_telegram(self):
        """Syncs the current state snapshot to Telegram Channel / Chat pinned message."""
        self.save_local()
        if not self.bot_token or not self.chat_id:
            return

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload_data = {
            "version": 1.0,
            "users_count": len(self.state.get("users", {})),
            "allowed_count": len(self.state.get("allowed_emails", [])),
            "state": self.state
        }
        json_str = json.dumps(payload_data, ensure_ascii=False, indent=2)
        
        # If payload fits in message text, update or send
        text = f"<b>💾 RADTRACKER TELEGRAM-DB SNAPSHOT</b>\n<code>{json_str[:3800]}</code>"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if self.state_message_id:
                    edit_url = f"https://api.telegram.org/bot{self.bot_token}/editMessageText"
                    resp = await client.post(edit_url, json={
                        "chat_id": self.chat_id,
                        "message_id": self.state_message_id,
                        "text": text,
                        "parse_mode": "HTML"
                    })
                    if resp.status_code == 200:
                        return
                
                # If edit failed or no message_id yet, send new message and pin it
                resp = await client.post(url, json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML"
                })
                if resp.status_code == 200:
                    data = resp.json()
                    msg_id = data.get("result", {}).get("message_id")
                    if msg_id:
                        self.state_message_id = msg_id
                        pin_url = f"https://api.telegram.org/bot{self.bot_token}/pinChatMessage"
                        await client.post(pin_url, json={
                            "chat_id": self.chat_id,
                            "message_id": msg_id,
                            "disable_notification": True
                        })
        except Exception as e:
            logger.error(f"Error syncing state to Telegram: {e}")

    async def log_event_to_channel(self, title: str, details: str):
        """Posts a real-time human-readable event message to the Telegram Channel."""
        if not self.bot_token or not self.chat_id:
            return
        text = f"<b>{title}</b>\n{details}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                await client.post(url, json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML"
                })
        except Exception as e:
            logger.error(f"Error posting log to Telegram: {e}")

# Global Singleton Instance
db = TelegramDB()
