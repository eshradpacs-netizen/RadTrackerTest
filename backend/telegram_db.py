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
            "allowed_emails": [
    "ozyozcn7106@gmail.com",
    "aybukeucgun@gmail.com",
    "ibrahimekinci172@gmail.com",
    "ekindenizcigil@gmail.com",
    "aytenaksoy3@gmail.com",
    "ersnyvz11@gmail.com",
    "drugurgokayk@gmail.com",
    "enesozsozgun@gmail.com",
    "drmelikedogan1@gmail.com",
    "furkaneren653@gmail.com",
    "demirbilekzelal@gmail.com",
    "kzbndktr@gmail.com",
    "ozgediraman@gmail.com",
    "tgce40.66@gmail.com",
    "zeynepsorucu123@gmail.com",
    "msamibircan40@gmail.com",
    "babursah97@gmail.com",
    "gizem9775@gmail.com",
    "candantuncel@gmail.com",
    "zehrakostu@gmail.com",
    "elifkirpar@gmail.com",
    "aeg2346@gmail.com",
    "burhan.vrl.71@gmail.com",
    "ahmetkoroglu1996@gmail.com",
    "senaerden64@gmail.com",
    "canibegokcenaydin@gmail.com",
    "zehranursonkaya@gmail.com",
    "aysenur9583@gmail.com",
    "95eliferen@gmail.com",
    "erdinc1duru@gmail.com",
    "ersindeniz7@gmail.com",
    "sumeyyeakturk3@gmail.com",
    "cihanpolat1992@gmail.com",
    "bugrahankalkandelen@gmail.com",
    "anesnesa97@gmail.com",
    "farukylmz978@gmail.com",
    "e.ekintunc95@gmail.com",
    "ayhanyalcin97@gmail.com",
    "drbedirkaya@gmail.com",
    "sarper.sahin18@gmail.com",
    "sercanaltioglu@gmail.com",
    "draybukesshnn@gmail.com",
    "hhzontur19@gmail.com",
    "dr.eneskocyigit@gmail.com",
    "drtuncerozlem@gmail.com",
    "ozkanmelike222@gmail.com",
    "scdemirtas193@gmail.com",
    "uipsuz@gmail.com",
    "beyzaa.basaran@gmail.com",
    "gulderenabdullah@gmail.com",
    "dralp.1919@gmail.com",
    "sevval.dograr@gmail.com",
    "akkamaneceesra@gmail.com",
    "mr.atakaraman@gmail.com",
    "merverencber98@gmail.com",
    "muhammedcakmak3306@gmail.com",
    "burakyucetepe52@gmail.com",
    "akkcahmt@gmail.com",
    "furkangoktugkucuk@gmail.com",
    "utkukara10@gmail.com",
    "karademirhsyn17@gmail.com",
    "senatoryumm@gmail.com",
    "mcatalbas22@gmail.com",
    "furkanvardar15@gmail.com",
    "omurkaplan986@gmail.com",
    "anuluturk@gmail.com",
    "gulpinar.gungor62@gmail.com",
    "silakambur8@gmail.com",
    "tolgal1996@gmail.com",
    "aktas.buse1998@gmail.com",
    "eniserenn@gmail.com",
    "ustun.ceyhun@gmail.com",
    "stkguclu@gmail.com",
    "atesbasakece@gmail.com",
    "cerenaaydaar@gmail.com",
    "mecelik1994@gmail.com",
    "salihyilmazmd@gmail.com",
    "cemal.chopanci@gmail.com",
    "ertuncerenoglu@gmail.com",
    "semaekinci02@gmail.com",
    "ozturkrana97@gmail.com",
    "sulesyd12@gmail.com",
    "omrfarukduzenli@gmail.com",
    "1.hakanarslan@gmail.com",
    "nurkoksalmd@gmail.com",
    "drokayhan@gmail.com",
    "mehmet317985@gmail.com",
    "esingumusay97@gmail.com",
    "hulyakutar@gmail.com",
    "tahsinerdem71@gmail.com",
    "kibrisselin@gmail.com",
    "mdaliyilmaz@gmail.com",
    "ali.49tekce@gmail.com",
    "ismetaydin666@gmail.com",
    "atokpunar@gmail.com",
    "onurkosaaa@gmail.com",
    "ozkayaselen94@gmail.com",
    "yvzslm1516@gmail.com",
    "habibeserr@gmail.com",
    "ayangonul2@gmail.com",
    "aysenurgunay06@gmail.com",
    "a.kadirbalikci@gmail.com",
    "sefamerve043@gmail.com",
    "enanur95@gmail.com",
    "salihozayasliol@gmail.com",
    "ezginisan20@gmail.com",
    "baranburakaslan434@gmail.com",
    "r.furkan06@gmail.com",
    "iremayd13@gmail.com",
    "aysemervegolcuk@gmail.com",
    "sefiknamik@gmail.com",
    "nurettinkara.2611@gmail.com",
    "gokseninkav@gmail.com",
    "selguven07@gmail.com",
    "karakoczehra56@gmail.com",
    "irem.g418@gmail.com",
    "hrngonen@gmail.com",
    "slyldrm98@gmail.com",
    "kaan.bulbul.13@gmail.com",
    "sbsaatci@gmail.com",
    "dremreguner@gmail.com",
    "ebrarsuaradabak@gmail.com",
    "dilaytac@gmail.com",
    "ufukseda00@gmail.com",
    "mahmutuluturk94@gmail.com",
    "sgunesgunay@gmail.com",
    "dilayilmaz8@gmail.com",
    "ftmnrztprk1@gmail.com",
    "rab195yal@gmail.com",
    "aleynakaykc02@gmail.com",
    "eceeterzier@gmail.com",
    "defneaksu5@gmail.com",
    "esilanurerol@gmail.com",
    "neziheozkiran@gmail.com",
    "byznrsln11795@gmail.com",
    "omerfurkancirik@gmail.com",
    "aysekepenek0606@gmail.com",
    "ezgimert.21@gmail.com",
    "aysegulbaki88@gmail.com",
    "muhammetomerguney@gmail.com",
    "cgdm102@gmail.com",
    "drmustafagoktugaygar@gmail.com",
    "aliturk199827@gmail.com",
    "enezmusa@gmail.com",
    "huseyincem.ucar@gmail.com",
    "senagozen00@gmail.com",
    "esraersans@gmail.com",
    "eshradpacs@gmail.com",
    "selmauysalramadan@gmail.com"
], # whitelisted emails for resident doctors
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

        # Ensure default whitelisted emails exist
        allowed = self.state.setdefault("allowed_emails", [])
        for default_e in ["gulderenabdullah@gmail.com", "eshradpacs@gmail.com"]:
            if default_e not in [e.lower() for e in allowed]:
                allowed.append(default_e)

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
