"""
Radiology PC Tracker v1 - Telegram Bot & Mini App Controller
Handles Telegram commands (/start, /bos, /durum, /odalar, /takip, /admin),
Telegram Mini App launch buttons, and real-time push notifications.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List
import httpx
from master_mapping import MASTER_PC_MAPPING
from telegram_db import db

logger = logging.getLogger("telegram_bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
MINI_APP_URL = os.getenv("TELEGRAM_MINI_APP_URL", "") # e.g. https://radtracker.koyeb.app/miniapp.html

class TelegramBotController:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.mini_app_url = os.getenv("TELEGRAM_MINI_APP_URL", "")
        self.subscriptions: Dict[str, List[int]] = {} # pc_id -> list of chat_ids

    async def send_message(self, chat_id: int, text: str, reply_markup: Dict = None):
        """Sends a Telegram message with optional inline keyboard."""
        if not self.bot_token:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json=payload)
        except Exception as e:
            logger.error(f"Telegram send_message error: {e}")

    async def handle_update(self, update: Dict[str, Any], state_mgr):
        """Processes an incoming Telegram webhook / polling update."""
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        chat_id = message.get("chat", {}).get("id")
        text = (message.get("text") or "").strip()
        
        if not chat_id or not text:
            return

        # Main Command Handlers
        if text.startswith("/start") or text.startswith("/help"):
            await self.cmd_start(chat_id)
        elif text.startswith("/bos") or text.startswith("/free"):
            await self.cmd_free_pcs(chat_id, state_mgr)
        elif text.startswith("/durum") or text.startswith("/status"):
            await self.cmd_status(chat_id, state_mgr)
        elif text.startswith("/odalar") or text.startswith("/rooms"):
            await self.cmd_rooms(chat_id, state_mgr)
        elif text.startswith("/takip"):
            await self.cmd_subscribe(chat_id, text, state_mgr)
        elif text.startswith("/kod") or text.startswith("/code"):
            await self.cmd_kod(chat_id)
        elif text.startswith("/ekle"):
            await self.cmd_add_email(chat_id, text)
        elif text.startswith("/cikar") or text.startswith("/sil"):
            await self.cmd_remove_email(chat_id, text)
        elif text.startswith("/listele") or text.startswith("/liste"):
            await self.cmd_list_emails(chat_id)
        elif text.startswith("/admin"):
            await self.cmd_admin(chat_id, state_mgr)

    async def cmd_start(self, chat_id: int):
        """Welcome message with Telegram Mini App Launch Button."""
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "📊 Canlı Takip Panelini Aç (Mini App)",
                        "web_app": {"url": self.mini_app_url or "https://radtracker.koyeb.app/miniapp.html"}
                    }
                ],
                [
                    {"text": "🟢 Boş Bilgisayarlar (/bos)", "callback_data": "cmd_free"},
                    {"text": "📌 Odalar (/odalar)", "callback_data": "cmd_rooms"}
                ],
                [
                    {"text": "ℹ️ Genel Durum (/durum)", "callback_data": "cmd_status"}
                ]
            ]
        }
        text = (
            "<b>🏥 Radyoloji PC Takip Botuna Hoş Geldiniz!</b>\n\n"
            "Hastanedeki 45 radyoloji bilgisayarının anlık durumunu (Boş/Dolu) 0 gecikmeyle Telegram'dan takip edebilirsiniz.\n\n"
            "<b>📌 Komutlar:</b>\n"
            "• <b>/bos</b> - Şu an boş olan bilgisayarları listeler\n"
            "• <b>/durum</b> - Tüm bilgisayarların özet durumunu gösterir\n"
            "• <b>/odalar</b> - Odalara (Takımyıldızlara) göre listeler\n"
            "• <b>/takip &lt;PC_ADI&gt;</b> - Bilgisayar boşalınca bildirim gönderir\n"
            "• <b>/admin</b> - Yönetici paneli\n\n"
            "Aşağıdaki butona basarak Telegram içerisinden <b>Canlı Takip Panelini</b> açabilirsiniz!"
        )
        await self.send_message(chat_id, text, keyboard)

    async def cmd_free_pcs(self, chat_id: int, state_mgr):
        """Lists all currently free/idle computers."""
        pcs = state_mgr.get_all_computers()
        free_pcs = [p for p in pcs if p.get("status") in ["idle", "lunch-break"]]
        
        if not free_pcs:
            text = "<b>🔴 Şu an boşta bilgisayar bulunmamaktadır.</b>\n<i>Tüm bilgisayarlar aktif kullanımda veya kapalı.</i>"
        else:
            lines = [f"<b>🟢 ŞU AN BOŞTA OLAN BİLGİSAYARLAR ({len(free_pcs)} Adet):</b>\n"]
            for p in free_pcs:
                fname = p.get("friendlyName") or p.get("hostname")
                room = p.get("room") or "Genel"
                status_str = "🍱 Öğle Arası" if p.get("status") == "lunch-break" else "🟢 Boşta"
                lines.append(f"• <b>{fname}</b> ({room}) — <i>{status_str}</i>")
            text = "\n".join(lines)
            
        await self.send_message(chat_id, text)

    async def cmd_status(self, chat_id: int, state_mgr):
        """Summary of all computers by status."""
        pcs = state_mgr.get_all_computers()
        active_cnt = sum(1 for p in pcs if p.get("status") == "active")
        idle_cnt = sum(1 for p in pcs if p.get("status") in ["idle", "lunch-break", "probably-idle"])
        offline_cnt = sum(1 for p in pcs if p.get("status") == "offline")
        suspicious_cnt = sum(1 for p in pcs if p.get("status") == "suspicious")

        text = (
            f"<b>📊 RADYOLOJİ PC DURUM ÖZETİ (Toplam 45 PC)</b>\n\n"
            f"🟢 <b>Boş / Kullanılabilir:</b> {idle_cnt}\n"
            f"🔴 <b>Dolu / Aktif:</b> {active_cnt}\n"
            f"⚪ <b>Çevrimdışı / Kapalı:</b> {offline_cnt}\n"
            f"⚠️ <b>Şüpheli Aktivite:</b> {suspicious_cnt}\n\n"
            f"<i>Son Güncelleme: Anlık (Real-Time WebSockets)</i>"
        )
        await self.send_message(chat_id, text)

    async def cmd_rooms(self, chat_id: int, state_mgr):
        """Lists PCs grouped by Constellations/Rooms."""
        pcs = state_mgr.get_all_computers()
        rooms: Dict[str, List] = {}
        for p in pcs:
            r = p.get("room") or "Genel"
            rooms.setdefault(r, []).append(p)

        lines = ["<b>🏛️ ODALARA GÖRE BİLGİSAYAR DURUMLARI:</b>\n"]
        status_icons = {
            "active": "🔴 Dolu",
            "idle": "🟢 Boş",
            "probably-idle": "🟡 Muhtemelen Boş",
            "lunch-break": "🍱 Öğle Arası",
            "offline": "⚪ Kapalı",
            "suspicious": "⚠️ Şüpheli"
        }
        
        for room_name, room_pcs in sorted(rooms.items()):
            lines.append(f"\n<b>📍 {room_name}:</b>")
            for p in room_pcs:
                fname = p.get("friendlyName") or p.get("hostname")
                st = p.get("status", "offline")
                icon = status_icons.get(st, "⚪ Kapalı")
                lines.append(f"  • {fname}: {icon}")

        await self.send_message(chat_id, "\n".join(lines))

    async def cmd_subscribe(self, chat_id: int, text: str, state_mgr):
        """Subscribes chat_id to get notified when a target PC becomes free."""
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await self.send_message(chat_id, "<b>Kullanım:</b> <code>/takip Cassiopeia-α</code>")
            return
        target_name = parts[1].strip().lower()
        
        # Match PC by friendlyName or hostname
        pcs = state_mgr.get_all_computers()
        matched_pc = None
        for p in pcs:
            fname = (p.get("friendlyName") or "").lower()
            hname = (p.get("hostname") or "").lower()
            if target_name in fname or target_name in hname:
                matched_pc = p
                break

        if not matched_pc:
            await self.send_message(chat_id, f"❌ <b>'{parts[1]}'</b> adında bir bilgisayar bulunamadı.")
            return

        pc_id = matched_pc["id"]
        self.subscriptions.setdefault(pc_id, []).append(chat_id)
        fname = matched_pc.get("friendlyName") or matched_pc.get("hostname")
        await self.send_message(chat_id, f"✅ <b>{fname}</b> takibe alındı! Bilgisayar boşaldığı an Telegram'dan bildirim alacaksınız.")

    async def cmd_admin(self, chat_id: int, state_mgr):
        """Admin menu for Telegram DB management."""
        from telegram_db import db
        allowed = db.state.get("allowed_emails", [])
        text = (
            "<b>⚙️ TELEGRAM-DB YÖNETİCİ MENÜSÜ</b>\n\n"
            f"• <b>Yetkili Hekim Sayısı:</b> {len(allowed)}\n"
            f"• <b>Toplam Takip Edilen PC:</b> {len(state_mgr.computers)}\n"
            f"• <b>Veritabanı Durumu:</b> Telegram-DB (Bulut Senkronize)\n\n"
            "<b>Komutlar:</b>\n"
            "• <code>/listele</code> : Yetkili e-posta listesini gösterir.\n"
            "• <code>/ekle dr.ahmet@hastane.gov.tr</code> : Yeni hekim ekler.\n"
            "• <code>/cikar dr.ahmet@hastane.gov.tr</code> : Hekim yetkisini kaldırır.\n"
        )
        await self.send_message(chat_id, text)

    async def cmd_add_email(self, chat_id: int, text: str):
        from telegram_db import db
        parts = text.split()
        if len(parts) < 2:
            await self.send_message(chat_id, "❌ Lütfen e-posta yazın.\nKullanım: <code>/ekle dr.ahmet@hastane.gov.tr</code>")
            return
        new_email = parts[1].lower().strip()
        allowed = db.state.setdefault("allowed_emails", [])
        if new_email in [e.lower() for e in allowed]:
            await self.send_message(chat_id, f"⚠️ <code>{new_email}</code> zaten yetkili listede var.")
            return
        allowed.append(new_email)
        await db.sync_to_telegram()
        await self.send_message(chat_id, f"✅ <b>BAŞARILI!</b> <code>{new_email}</code> yetkili asistan hekim listesine eklendi. Artık sisteme kayıt olabilir ve giriş yapabilir.")

    async def cmd_remove_email(self, chat_id: int, text: str):
        from telegram_db import db
        parts = text.split()
        if len(parts) < 2:
            await self.send_message(chat_id, "❌ Lütfen e-posta yazın.\nKullanım: <code>/cikar dr.ahmet@hastane.gov.tr</code>")
            return
        rem_email = parts[1].lower().strip()
        allowed = db.state.setdefault("allowed_emails", [])
        db.state["allowed_emails"] = [e for e in allowed if e.lower() != rem_email]
        await db.sync_to_telegram()
        await self.send_message(chat_id, f"🗑️ <code>{rem_email}</code> yetkili listeden çıkarıldı ve erişimi kısıtlandı.")

    async def cmd_list_emails(self, chat_id: int):
        from telegram_db import db
        allowed = db.state.get("allowed_emails", [])
        if not allowed:
            await self.send_message(chat_id, "📜 Yetkili e-posta listesi şu an boş.")
            return
        email_items = "\n".join([f"• <code>{e}</code>" for e in allowed])
        msg = f"📜 <b>YETKİLİ ASİSTAN HEKİM E-POSTA LİSTESİ ({len(allowed)} Hekim):</b>\n\n{email_items}\n\n<i>Bu listedeki hekimler sisteme kayıt olabilir ve giriş yapabilir.</i>"
        await self.send_message(chat_id, msg)

    async def notify_pc_free(self, pc: Dict[str, Any]):
        """Sends push notification to users subscribed to this PC when it becomes free."""
        pc_id = pc.get("id")
        subscribers = self.subscriptions.get(pc_id, [])
        if not subscribers:
            return
            
        fname = pc.get("friendlyName") or pc.get("hostname")
        room = pc.get("room") or "Genel"
        msg = f"🎉 <b>MÜJDE! {fname} ({room}) ŞU AN BOŞALDI!</b>\n<i>Bilgisayara hemen geçip oturabilirsiniz.</i>"
        
        for cid in list(subscribers):
            await self.send_message(cid, msg)
        
        # Clear subscriptions for this PC after notification
        self.subscriptions[pc_id] = []

    async def cmd_kod(self, chat_id: int):
        """Sends the latest verification code directly to the Telegram chat!"""
        from telegram_db import db
        users = db.state.get("users", {})
        
        # Find unverified users or last registered code
        unverified = [u for u in users.values() if not u.get("is_verified", False)]
        if not unverified:
            all_users = list(users.values())
            if all_users:
                last_u = all_users[-1]
                msg = f"🔑 <b>Son Kayıtlı Doğrulama Kodu:</b>\n\nE-Posta: <code>{last_u.get('email')}</code>\nKod: <b>{last_u.get('verification_code')}</b>\nDurum: {'🟢 Doğrulanmış' if last_u.get('is_verified') else '🟡 Doğrulama Bekliyor'}"
            else:
                msg = "Henüz kayıtlı kullanıcı bulunmuyor."
        else:
            last_unv = unverified[-1]
            msg = f"🔑 <b>Doğrulama Kodunuz:</b>\n\nE-Posta: <code>{last_unv.get('email')}</code>\nKodunuz: <code style='font-size:22px; color:#38bdf8;'>{last_unv.get('verification_code')}</code>\n\n<i>Bu kodu Telegram Mini App ekranındaki kutucuğa girerek onaylayabilirsiniz.</i>"
            
        await self.send_message(chat_id, msg)

    async def start_polling(self, state_mgr):
        """Starts Telegram Bot Long Polling loop for zero-config local testing."""
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set. Telegram Bot Polling disabled.")
            return
            
        logger.info("✅ Telegram Bot Long Polling Loop Active! Listening for Telegram messages...")
        offset = 0
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                try:
                    resp = await client.get(url, params={"offset": offset, "timeout": 20})
                    if resp.status_code == 200:
                        data = resp.json()
                        for update in data.get("result", []):
                            offset = update["update_id"] + 1
                            await self.handle_update(update, state_mgr)
                except Exception as e:
                    logger.error(f"Polling error: {e}")
                    await asyncio.sleep(3)

# Global Singleton Instance
telegram_bot = TelegramBotController()
