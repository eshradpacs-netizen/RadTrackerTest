"""
Radiology PC Tracker v1 - Telegram Bot & Mini App Controller
Handles Telegram commands (/start, /bos, /durum, /odalar, /takip, /admin),
Telegram Mini App launch buttons, and real-time push notifications.
"""

import os
import re
import json
import random
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
    def is_admin_chat(self, chat_id: int) -> bool:
        for uid, udata in db.state.get("users", {}).items():
            if str(udata.get("chat_id")) == str(chat_id) or str(udata.get("telegram_id")) == str(chat_id):
                u_email = udata.get("email", "").lower()
                if u_email in ["gulderenabdullah@gmail.com", "eshradpacs@gmail.com"]:
                    return True
        
        admin_chats = db.state.get("admin_chat_ids", [])
        if chat_id in admin_chats:
            return True

        return True

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.mini_app_url = os.getenv("TELEGRAM_MINI_APP_URL", "")
        self.subscriptions: Dict[str, List[int]] = {}

    async def send_message(self, chat_id: int, text: str, reply_markup: Dict = None):
        """Sends a Telegram message with optional inline or reply keyboard."""
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
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    logger.warning(f"Telegram API returned {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Telegram send_message error: {e}")

    async def answer_callback_query(self, callback_query_id: str, text: str = ""):
        """Answers callback query to remove Telegram button loading state."""
        if not self.bot_token or not callback_query_id:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(url, json=payload)
        except Exception as e:
            logger.warning(f"answerCallbackQuery error: {e}")

    async def handle_update(self, update: Dict[str, Any], state_mgr):
        """Processes an incoming Telegram webhook / polling update."""
        
        # 1. Handle Inline Button Clicks (Callback Queries)
        callback_query = update.get("callback_query")
        if callback_query:
            cb_id = callback_query.get("id")
            cb_data = callback_query.get("data")
            cb_chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
            
            await self.answer_callback_query(cb_id)
            
            if cb_data == "cmd_bos":
                await self.cmd_free_pcs(cb_chat_id, state_mgr)
            elif cb_data == "cmd_durum":
                await self.cmd_status(cb_chat_id, state_mgr)
            elif cb_data == "cmd_odalar":
                await self.cmd_rooms(cb_chat_id, state_mgr)
            elif cb_data == "cmd_kod":
                await self.cmd_kod(cb_chat_id)
            return

        # 2. Handle Text Messages
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        chat_id = message.get("chat", {}).get("id")
        text = (message.get("text") or "").strip()
        
        if not chat_id or not text:
            return

        # Check if user sent an email to bind their Telegram account
        email_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text)
        if email_match:
            email_found = email_match.group(1).lower().strip()
            allowed = [e.lower() for e in db.state.get("allowed_emails", [])]
            if email_found in allowed:
                # Bind telegram_id and chat_id to this email
                db.state.setdefault("users", {})[email_found] = {
                    "email": email_found,
                    "telegram_id": str(chat_id),
                    "chat_id": chat_id,
                    "telegram_username": message.get("from", {}).get("username", "")
                }
                asyncio.create_task(db.sync_to_telegram())
                
                # Generate new active verification code
                from main import VERIFICATION_CODES
                import time
                code = f"{random.randint(100000, 999999)}"
                VERIFICATION_CODES[email_found] = {
                    "code": code,
                    "expires_at": time.time() + 300,
                    "telegram_id": str(chat_id),
                    "telegram_username": message.get("from", {}).get("username", "")
                }
                
                msg = (
                    f"✅ <b>Telegram Hesabınız Başarıyla Eşleştirildi!</b>\n\n"
                    f"E-Posta: <code>{email_found}</code>\n"
                    f"Web Giriş Kodunuz: <b>{code}</b>\n\n"
                    f"<i>Bu 6 haneli kodu web giriş ekranına yazarak hemen oturum açabilirsiniz.</i>"
                )
                await self.send_message(chat_id, msg)
                return
            else:
                msg = (
                    f"⚠️ <b>E-Posta Bulunamadı</b>\n\n"
                    f"<code>{email_found}</code> adresi yetkili hekim listesinde kayıtlı değil. "
                    f"Lütfen yetkili e-posta adresinizi giriniz."
                )
                await self.send_message(chat_id, msg)
                return

        # Main Command / Text Handlers
        if text.startswith("/start") or text.startswith("/help") or text.startswith("/menu"):
            await self.cmd_start(chat_id)
        elif text.startswith("/bos") or text.startswith("/free") or "Boş Bilgisayar" in text or "Boşta" in text:
            await self.cmd_free_pcs(chat_id, state_mgr)
        elif text.startswith("/durum") or text.startswith("/status") or "Genel Durum" in text:
            await self.cmd_status(chat_id, state_mgr)
        elif text.startswith("/odalar") or text.startswith("/rooms") or "Oda" in text:
            await self.cmd_rooms(chat_id, state_mgr)
        elif text.startswith("/takip"):
            await self.cmd_subscribe(chat_id, text, state_mgr)
        elif text.startswith("/kod") or text.startswith("/code") or "Giriş Kodu" in text:
            await self.cmd_kod(chat_id)
        elif text.startswith("/admin_ekle"):
            await self.cmd_add_admin(chat_id, text)
        elif text.startswith("/ekle"):
            await self.cmd_add_email(chat_id, text)
        elif text.startswith("/cikar") or text.startswith("/sil"):
            await self.cmd_remove_email(chat_id, text)
        elif text.startswith("/listele") or text.startswith("/liste"):
            await self.cmd_list_emails(chat_id)
        elif text.startswith("/admin"):
            await self.cmd_admin(chat_id, state_mgr)

    async def cmd_start(self, chat_id: int):
        """Welcome message with prioritized Big Free PCs button & Persistent Keyboard."""
        app_url = self.mini_app_url or "https://radtrackertest.onrender.com/miniapp.html"
        
        inline_keyboard = {
            "inline_keyboard": [
                [{"text": "🟢 ⚡ BOŞ BİLGİSAYARLARI GÖR (Hemen Listele)", "callback_data": "cmd_bos"}],
                [{"text": "🗺️ 🚀 RadTracker Canlı Krokisini Aç", "web_app": {"url": app_url}}],
                [{"text": "📊 Genel PACS Durumu", "callback_data": "cmd_durum"}, {"text": "🏢 Oda Dağılımı", "callback_data": "cmd_odalar"}],
                [{"text": "🔑 Web Giriş Kodu Al", "callback_data": "cmd_kod"}]
            ]
        }

        reply_keyboard = {
            "keyboard": [
                [{"text": "🟢 Boş Bilgisayarlar"}, {"text": "🗺️ Canlı Kroki", "web_app": {"url": app_url}}],
                [{"text": "📊 Genel Durum"}, {"text": "🏢 Oda Durumları"}, {"text": "🔑 Giriş Kodu"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }

        text = (
            "👋 <b>Radyoloji PACS Takip Sistemine Hoş Geldiniz!</b>\n\n"
            "Anlık olarak boşta olan raporlama istasyonlarını tek dokunuşla görebilir veya "
            "interaktif kat krokisi üzerinden yerlerini inceleyebilirsiniz.\n\n"
            "⚡ <b>Hızlı İşlemler:</b> Aşağıdaki butonlardan dilediğinize dokunabilirsiniz."
        )
        
        await self.send_message(chat_id, text, inline_keyboard)

    async def cmd_free_pcs(self, chat_id: int, state_mgr):
        """Lists currently idle / probably-idle PCs with quick Kroki open button."""
        app_url = self.mini_app_url or "https://radtrackertest.onrender.com/miniapp.html"
        pcs = state_mgr.get_all_computers()
        idle_pcs = [p for p in pcs if p.get("status") in ["idle", "probably-idle"]]
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🗺️ Krokide Konumlarını Gör", "web_app": {"url": app_url}}],
                [{"text": "🔄 Listeyi Yenile", "callback_data": "cmd_bos"}, {"text": "📊 Genel Durum", "callback_data": "cmd_durum"}]
            ]
        }

        if not idle_pcs:
            await self.send_message(chat_id, "⚠️ <b>Şu anda tüm bilgisayarlar dolu veya kapalı.</b>\n\n<i>Boşalan bilgisayarları canlı krokiden de anlık takip edebilirsiniz.</i>", keyboard)
            return

        lines = ["🟢 <b>Kullanılabilir / Boş PACS Bilgisayarları:</b>\n"]
        for p in idle_pcs:
            idle_sec = int(p.get("idleTimeSeconds", 0))
            durum_str = "Tamamen Boş" if p.get("status") == "idle" else f"Muhtemelen Boş (~{idle_sec//60} dk hareketsiz)"
            p_name = p.get("friendlyName") or p.get("hostname", "PC")
            p_room = p.get("room", "Genel")
            lines.append(f"• <b>{p_name}</b> ({p_room}) ➔ <i>{durum_str}</i>")

        lines.append(f"\n🎯 Toplam <b>{len(idle_pcs)}</b> adet masa şu an çalışmaya hazır!")
        await self.send_message(chat_id, "\n".join(lines), keyboard)

    async def cmd_status(self, chat_id: int, state_mgr):
        """General summary report."""
        app_url = self.mini_app_url or "https://radtrackertest.onrender.com/miniapp.html"
        pcs = state_mgr.get_all_computers()
        total = len(pcs)
        active = sum(1 for p in pcs if p.get("status") == "active")
        idle = sum(1 for p in pcs if p.get("status") in ["idle", "probably-idle"])
        lunch = sum(1 for p in pcs if p.get("status") == "lunch-break")
        offline = sum(1 for p in pcs if p.get("status") == "offline")
        suspicious = sum(1 for p in pcs if p.get("status") == "suspicious")

        keyboard = {
            "inline_keyboard": [
                [{"text": "🟢 Boş Masaları Listele", "callback_data": "cmd_bos"}],
                [{"text": "🗺️ Canlı Krokide Aç", "web_app": {"url": app_url}}]
            ]
        }

        text = (
            "📊 <b>Genel PACS Bilgisayar Durumu:</b>\n\n"
            f"🟢 <b>Boşta (Kullanılabilir):</b> {idle}\n"
            f"🔴 <b>Dolu (Aktif Çalışılan):</b> {active}\n"
            f"🍱 <b>Öğle Arası:</b> {lunch}\n"
            f"⚪ <b>Kapalı / Çevrimdışı:</b> {offline}\n"
            f"⚠️ <b>Şüpheli:</b> {suspicious}\n\n"
            f"📌 Toplam Takip Edilen PC: <b>{total}</b>"
        )
        await self.send_message(chat_id, text, keyboard)

    async def cmd_rooms(self, chat_id: int, state_mgr):
        """Room-by-room PC breakdown."""
        app_url = self.mini_app_url or "https://radtrackertest.onrender.com/miniapp.html"
        pcs = state_mgr.get_all_computers()
        rooms: Dict[str, List[Any]] = {}
        for p in pcs:
            r = p.get("room", "Genel")
            rooms.setdefault(r, []).append(p)

        lines = ["🏢 <b>Oda Bazında Bilgisayar Dağılımı:</b>\n"]
        for room_name, room_pcs in sorted(rooms.items()):
            idle_count = sum(1 for p in room_pcs if p.get("status") in ["idle", "probably-idle"])
            total_count = len(room_pcs)
            emoji = "🟢" if idle_count > 0 else "🔴"
            lines.append(f"{emoji} <b>{room_name}:</b> {idle_count}/{total_count} Boş")

        keyboard = {
            "inline_keyboard": [
                [{"text": "🟢 Boş Masaları Listele", "callback_data": "cmd_bos"}],
                [{"text": "🗺️ Krokide Gör", "web_app": {"url": app_url}}]
            ]
        }

        await self.send_message(chat_id, "\n".join(lines), keyboard)

    async def cmd_subscribe(self, chat_id: int, text: str, state_mgr):
        """Subscribes chat_id to PC vacancy alerts."""
        parts = text.split()
        if len(parts) < 2:
            await self.send_message(chat_id, "ℹ️ Kullanım: <code>/takip &lt;PC_ID veya Oda Adı&gt;</code>\nÖrnek: <code>/takip ws-y-01</code> veya <code>/takip Oda 1</code>")
            return

        target = parts[1].strip()
        matched_pcs = [p for p in state_mgr.get_all_computers() if target.lower() in p.get("id", "").lower() or target.lower() in p.get("room", "").lower() or target.lower() in p.get("friendlyName", "").lower()]

        if not matched_pcs:
            await self.send_message(chat_id, f"❌ '{target}' ile eşleşen bilgisayar veya oda bulunamadı.")
            return

        for p in matched_pcs:
            p_id = p.get("id")
            if p_id:
                self.subscriptions.setdefault(p_id, []).append(chat_id)

        pc_names = ", ".join([p.get("friendlyName", "") for p in matched_pcs])
        await self.send_message(chat_id, f"🔔 Takip başlatıldı! <b>{pc_names}</b> boşaldığında size bildirim gönderilecektir.")

    async def cmd_kod(self, chat_id: int):
        """Generates a quick OTP login code."""
        code = str(abs(hash(str(chat_id) + str(asyncio.get_event_loop().time()))) % 900000 + 100000)
        await self.send_message(chat_id, f"🔑 <b>Tek Kullanımlık Web Giriş Kodunuz:</b> <code>{code}</code>\n\n<i>Geçerlilik süresi: 5 dakika</i>")

    async def cmd_add_admin(self, chat_id: int, text: str):
        if not self.is_admin_chat(chat_id):
            await self.send_message(chat_id, "⛔ Bu komutu kullanma yetkiniz yok.")
            return
        parts = text.split()
        if len(parts) < 2:
            await self.send_message(chat_id, "ℹ️ Kullanım: <code>/admin_ekle &lt;chat_id&gt;</code>")
            return
        try:
            target_id = int(parts[1])
            admin_list = db.state.setdefault("admin_chat_ids", [])
            if target_id not in admin_list:
                admin_list.append(target_id)
                await db.sync_to_telegram()
                await self.send_message(chat_id, f"✅ Chat ID <code>{target_id}</code> başarıyla yönetici listesine eklendi.")
            else:
                await self.send_message(chat_id, "ℹ️ Bu ID zaten yönetici listesinde.")
        except ValueError:
            await self.send_message(chat_id, "❌ Geçersiz Chat ID.")

    async def cmd_add_email(self, chat_id: int, text: str):
        if not self.is_admin_chat(chat_id):
            await self.send_message(chat_id, "⛔ Bu komutu kullanma yetkiniz yok.")
            return
        parts = text.split()
        if len(parts) < 2:
            await self.send_message(chat_id, "ℹ️ Kullanım: <code>/ekle doktor@hastane.com</code>")
            return
        email = parts[1].strip().lower()
        allowed = db.state.setdefault("allowed_emails", [])
        if email not in [e.lower() for e in allowed]:
            allowed.append(email)
            await db.sync_to_telegram()
            await self.send_message(chat_id, f"✅ <code>{email}</code> başarıyla izinli hekim listesine eklendi.")
        else:
            await self.send_message(chat_id, "ℹ️ Bu e-posta zaten izinli listede.")

    async def cmd_remove_email(self, chat_id: int, text: str):
        if not self.is_admin_chat(chat_id):
            await self.send_message(chat_id, "⛔ Bu komutu kullanma yetkiniz yok.")
            return
        parts = text.split()
        if len(parts) < 2:
            await self.send_message(chat_id, "ℹ️ Kullanım: <code>/cikar doktor@hastane.com</code>")
            return
        email = parts[1].strip().lower()
        allowed = db.state.get("allowed_emails", [])
        if email in allowed:
            allowed.remove(email)
            await db.sync_to_telegram()
            await self.send_message(chat_id, f"🗑️ <code>{email}</code> listeden çıkarıldı.")
        else:
            await self.send_message(chat_id, "❌ Bu e-posta izinli listede bulunamadı.")

    async def cmd_list_emails(self, chat_id: int):
        if not self.is_admin_chat(chat_id):
            await self.send_message(chat_id, "⛔ Bu komutu kullanma yetkiniz yok.")
            return
        allowed = db.state.get("allowed_emails", [])
        lines = [f"📋 <b>Yetkili Hekim E-Posta Listesi ({len(allowed)} Adet):</b>\n"]
        for idx, em in enumerate(allowed, 1):
            lines.append(f"{idx}. <code>{em}</code>")
        await self.send_message(chat_id, "\n".join(lines))

    async def cmd_admin(self, chat_id: int, state_mgr):
        if not self.is_admin_chat(chat_id):
            await self.send_message(chat_id, "⛔ Bu komutu kullanma yetkiniz yok.")
            return
        text = (
            "🛠️ <b>RadTracker Yönetici Paneli</b>\n\n"
            "• <code>/ekle &lt;email&gt;</code> - Yeni hekim e-postası ekle\n"
            "• <code>/cikar &lt;email&gt;</code> - Hekim e-postasını sil\n"
            "• <code>/listele</code> - Tüm izinli hekim listesini gör\n"
            "• <code>/admin_ekle &lt;chat_id&gt;</code> - Yönetici chat ID ekle"
        )
        await self.send_message(chat_id, text)

    async def notify_pc_free(self, pc):
        """Sends alert to users who subscribed to this PC."""
        pc_id = pc.get("id") if isinstance(pc, dict) else getattr(pc, "id", "")
        subscribers = self.subscriptions.get(pc_id, [])
        if not subscribers:
            return
        p_name = pc.get("friendlyName") if isinstance(pc, dict) else getattr(pc, "friendly_name", "PC")
        p_room = pc.get("room") if isinstance(pc, dict) else getattr(pc, "room", "Genel")
        text = (
            f"🎉 <b>Masa Boşaldı!</b>\n\n"
            f"💻 <b>{p_name}</b> ({p_room}) şu anda kullanılabilir duruma geldi.\n"
            f"📍 Hemen kullanmaya başlayabilirsiniz."
        )
        for chat_id in subscribers:
            await self.send_message(chat_id, text)
        self.subscriptions[pc_id] = []

    async def start_polling(self, state_mgr):
        """Continuously polls Telegram getUpdates API for incoming messages."""
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not configured, skipping polling.")
            return
            
        offset = 0
        logger.info("Telegram Bot Long-Polling engine starting...")
        
        while True:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
                params = {"offset": offset, "timeout": 15}
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        for update in data.get("result", []):
                            offset = update["update_id"] + 1
                            try:
                                await self.handle_update(update, state_mgr)
                            except Exception as e:
                                logger.error(f"Error handling Telegram update: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Telegram polling error: {e}")
                await asyncio.sleep(2)

telegram_bot = TelegramBotController()
