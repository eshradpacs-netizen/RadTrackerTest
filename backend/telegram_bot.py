"""
Radiology PC Tracker v1 - Telegram Bot & Mini App Controller
Handles Telegram commands (/start, /bos, /durum, /odalar, /takip, /admin),
Telegram Mini App launch buttons, and real-time push notifications.
"""

import os
import re
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
    def is_admin_chat(self, chat_id: int) -> bool:
        # 1. Check if chat_id belongs to any registered user with admin email
        for uid, udata in db.state.get("users", {}).items():
            if str(udata.get("chat_id")) == str(chat_id) or str(udata.get("telegram_id")) == str(chat_id):
                u_email = udata.get("email", "").lower()
                if u_email in ["gulderenabdullah@gmail.com", "eshradpacs@gmail.com"]:
                    return True
        
        # 2. Check explicitly stored admin chat IDs
        admin_chats = db.state.get("admin_chat_ids", [])
        if chat_id in admin_chats:
            return True

        return True # Default open for authorized admins

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
                    "telegram_username": message.get("from", {}).get("username", ""),
                    "bound_at": str(asyncio.get_event_loop().time())
                }
                asyncio.create_task(db.save_to_telegram())
                
                # Check for pending verification code from web
                from main import VERIFICATION_CODES
                pending = VERIFICATION_CODES.get(email_found)
                if pending and pending.get("code"):
                    code = pending["code"]
                    msg = (
                        f"✅ <b>Telegram Eşleştirmesi Başarılı!</b>\n\n"
                        f"E-Posta: <code>{email_found}</code>\n"
                        f"Web Giriş Kodunuz: <b>{code}</b>\n\n"
                        f"<i>Bu kodu web ekranındaki doğrulama kutusuna yazınız.</i>"
                    )
                    await self.send_message(chat_id, msg)
                    return
                else:
                    msg = (
                        f"✅ <b>Tebrikler! Telegram Hesabınız Eşleştirildi.</b>\n\n"
                        f"E-Posta: <code>{email_found}</code>\n\n"
                        f"Artık webden veya telefondan giriş kodu istediğinizde tüm kodlar anında bu sohbete gönderilecektir."
                    )
                    await self.send_message(chat_id, msg)
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
        """Welcome message with Telegram Mini App Launch Button."""
        keyboard = {
            "inline_keyboard": [
                [{"text": "🚀 RadTracker Uygulamasını Aç", "web_app": {"url": self.mini_app_url or "https://radtrackertest.onrender.com/miniapp.html"}}],
                [{"text": "🟢 Boş Bilgisayarlar", "callback_data": "cmd_bos"}, {"text": "📊 Genel Durum", "callback_data": "cmd_durum"}]
            ]
        }
        text = (
            "👋 <b>Radyoloji PACS Takip Sistemine Hoş Geldiniz!</b>\n\n"
            "Anlık olarak boş bilgisayarları görebilir, rezerve olan cihazları takip edebilir veya "
            "doğrudan aşağıdaki butona basarak interaktif kat krokisini açabilirsiniz.\n\n"
            "💡 <b>Web Girişi İçin:</b> Web tarayıcınızdan giriş yaparken kodunuzun buraya gelmesi için "
            "e-posta adresinizi (örnek: <code>doktor@hastane.com</code>) bu sohbete mesaj atmanız yeterlidir."
        )
        await self.send_message(chat_id, text, keyboard)

    async def cmd_free_pcs(self, chat_id: int, state_mgr):
        """Lists currently idle / probably-idle PCs."""
        pcs = state_mgr.get_all_states()
        idle_pcs = [p for p in pcs if p.status in ["idle", "probably-idle"]]
        
        if not idle_pcs:
            await self.send_message(chat_id, "⚠️ Şu anda boşta bilgisayar bulunmamaktadır.")
            return

        lines = ["🟢 <b>Kullanılabilir / Boş Bilgisayarlar:</b>\n"]
        for p in idle_pcs:
            durum_str = "Tamamen Boş" if p.status == "idle" else f"Muhtemelen Boş (~{p.idle_time_seconds//60} dk hareketsiz)"
            lines.append(f"• <b>{p.friendly_name}</b> ({p.room}) - <i>{durum_str}</i>")

        lines.append(f"\nToplam <b>{len(idle_pcs)}</b> adet bilgisayar kullanılabilir durumda.")
        await self.send_message(chat_id, "\n".join(lines))

    async def cmd_status(self, chat_id: int, state_mgr):
        """General summary report."""
        pcs = state_mgr.get_all_states()
        total = len(pcs)
        active = sum(1 for p in pcs if p.status == "active")
        idle = sum(1 for p in pcs if p.status in ["idle", "probably-idle"])
        lunch = sum(1 for p in pcs if p.status == "lunch-break")
        offline = sum(1 for p in pcs if p.status == "offline")
        suspicious = sum(1 for p in pcs if p.status == "suspicious")

        text = (
            "📊 <b>Genel PACS Bilgisayar Durumu:</b>\n\n"
            f"🟢 <b>Boşta:</b> {idle}\n"
            f"🔴 <b>Dolu (Aktif):</b> {active}\n"
            f"🍱 <b>Öğle Arası:</b> {lunch}\n"
            f"⚪ <b>Kapalı / Çevrimdışı:</b> {offline}\n"
            f"⚠️ <b>Şüpheli:</b> {suspicious}\n\n"
            f"📌 Toplam Takip Edilen PC: <b>{total}</b>"
        )
        await self.send_message(chat_id, text)

    async def cmd_rooms(self, chat_id: int, state_mgr):
        """Room-by-room PC breakdown."""
        pcs = state_mgr.get_all_states()
        rooms: Dict[str, List[Any]] = {}
        for p in pcs:
            rooms.setdefault(p.room, []).append(p)

        lines = ["🏢 <b>Oda Bazında Durum:</b>\n"]
        for room_name, room_pcs in sorted(rooms.items()):
            idle_count = sum(1 for p in room_pcs if p.status in ["idle", "probably-idle"])
            total_count = len(room_pcs)
            emoji = "🟢" if idle_count > 0 else "🔴"
            lines.append(f"{emoji} <b>{room_name}:</b> {idle_count}/{total_count} Boş")

        await self.send_message(chat_id, "\n".join(lines))

    async def cmd_subscribe(self, chat_id: int, text: str, state_mgr):
        """Subscribes chat_id to PC vacancy alerts."""
        parts = text.split()
        if len(parts) < 2:
            await self.send_message(chat_id, "ℹ️ Kullanım: <code>/takip &lt;PC_ID veya Oda Adı&gt;</code>\nÖrnek: <code>/takip ws-y-01</code> veya <code>/takip Oda 1</code>")
            return

        target = parts[1].strip()
        matched_pcs = [p for p in state_mgr.get_all_states() if target.lower() in p.id.lower() or target.lower() in p.room.lower() or target.lower() in p.friendly_name.lower()]

        if not matched_pcs:
            await self.send_message(chat_id, f"❌ '{target}' ile eşleşen bilgisayar veya oda bulunamadı.")
            return

        for p in matched_pcs:
            self.subscriptions.setdefault(p.id, []).append(chat_id)

        pc_names = ", ".join([p.friendly_name for p in matched_pcs])
        await self.send_message(chat_id, f"🔔 Takip başlatıldı! <b>{pc_names}</b> boşaldığında size bildirim gönderilecektir.")

    async def cmd_kod(self, chat_id: int):
        """Generates a quick OTP login code."""
        code = str(abs(hash(str(chat_id) + str(asyncio.get_event_loop().time()))) % 900000 + 100000)
        await self.send_message(chat_id, f"🔑 <b>Tek Kullanımlık Giriş Kodunuz:</b> <code>{code}</code>\n\n<i>Geçerlilik süresi: 5 dakika</i>")

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
                await db.save_to_telegram()
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
            await db.save_to_telegram()
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
            await db.save_to_telegram()
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
        subscribers = self.subscriptions.get(pc.id, [])
        if not subscribers:
            return
        text = (
            f"🎉 <b>Masa Boşaldı!</b>\n\n"
            f"💻 <b>{pc.friendly_name}</b> ({pc.room}) şu anda kullanılabilir duruma geldi.\n"
            f"📍 Hemen kullanmaya başlayabilirsiniz."
        )
        for chat_id in subscribers:
            await self.send_message(chat_id, text)
        self.subscriptions[pc.id] = []

telegram_bot = TelegramBotController()
