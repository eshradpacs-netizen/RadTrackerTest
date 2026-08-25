"""
Radiology PC Tracker v1 - Secure Telegram Bot Gateway
Enforces zero-data-leak privacy: No hospital telemetry is exposed in public chat.
Strictly routes doctors to the email-verified WebApp and handles private notifications.
"""

import os
import re
import json
import random
import asyncio
import logging
from typing import Dict, Any, List
import httpx
from telegram_db import db

logger = logging.getLogger("telegram_bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
MINI_APP_URL = os.getenv("TELEGRAM_MINI_APP_URL", "")

class TelegramBotController:
    def is_admin_chat(self, chat_id: int) -> bool:
        for uid, udata in db.state.get("users", {}).items():
            if str(udata.get("chat_id")) == str(chat_id) or str(udata.get("telegram_id")) == str(chat_id):
                u_email = udata.get("email", "").lower()
                if u_email in ["gulderenabdullah@gmail.com", "eshradpacs@gmail.com"]:
                    return True
        admin_chats = db.state.get("admin_chat_ids", [])
        return chat_id in admin_chats

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.mini_app_url = os.getenv("TELEGRAM_MINI_APP_URL", "")

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
        
        # 1. Handle Inline Button Clicks
        callback_query = update.get("callback_query")
        if callback_query:
            cb_id = callback_query.get("id")
            cb_data = callback_query.get("data")
            cb_chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
            
            await self.answer_callback_query(cb_id)
            
            if cb_data == "cmd_start":
                await self.cmd_start(cb_chat_id)
            elif cb_data == "cmd_kod":
                await self.cmd_kod(cb_chat_id)
            elif cb_data in ["cmd_bos", "cmd_durum", "cmd_odalar"]:
                await self.cmd_redirect_to_web(cb_chat_id)
            return

        # 2. Handle Text Messages
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        chat_id = message.get("chat", {}).get("id")
        text = (message.get("text") or "").strip()
        
        if not chat_id or not text:
            return

        # Check if doctor sent an email to bind their Telegram account
        email_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text)
        if email_match:
            email_found = email_match.group(1).lower().strip()
            from doctors_registry import is_doctor_allowed, get_doctor_name
            
            if is_doctor_allowed(email_found) or email_found in [e.lower() for e in db.state.get("allowed_emails", [])]:
                doc_name = get_doctor_name(email_found)
                # Bind telegram account
                db.state.setdefault("users", {})[email_found] = {
                    "email": email_found,
                    "name": doc_name,
                    "telegram_id": str(chat_id),
                    "chat_id": chat_id,
                    "telegram_username": message.get("from", {}).get("username", "")
                }
                asyncio.create_task(db.sync_to_telegram())
                
                # Generate active verification code
                from main import VERIFICATION_CODES
                import time
                code = f"{random.randint(100000, 999999)}"
                VERIFICATION_CODES[email_found] = {
                    "code": code,
                    "expires_at": time.time() + 900,
                    "telegram_id": str(chat_id),
                    "telegram_username": message.get("from", {}).get("username", "")
                }
                
                app_url = self.mini_app_url or "https://esh-radtracker.onrender.com/miniapp.html"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🚀 Canlı Haritayı Aç & Giriş Yap", "web_app": {"url": app_url}}]
                    ]
                }
                
                msg = (
                    f"✅ <b>Hoş Geldiniz, {doc_name}!</b>\n"
                    "━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📧 <b>Eşleşen Mail:</b> <code>{email_found}</code>\n"
                    f"🔑 <b>Tek Kullanımlık Kodunuz:</b> <code>{code}</code>\n\n"
                    "🔒 <i>Bu kod ile canlı panele giriş yapabilir veya doğrudan aşağıdaki butona basarak açabilirsiniz.</i>"
                )
                await self.send_message(chat_id, msg, keyboard)
                return
            else:
                msg = (
                    "⛔ <b>Yetkisiz E-Posta Adresi</b>\n\n"
                    f"<code>{email_found}</code> adresi Etlik Şehir Hastanesi Radyoloji Kliniği kayıtlı hekim listesinde bulunamadı.\n\n"
                    "<i>Lütfen kliniğimize kayıtlı resmi mail adresinizi giriniz.</i>"
                )
                await self.send_message(chat_id, msg)
                return

        # Main Command Handlers
        if text.startswith("/start") or text.startswith("/help") or text.startswith("/menu"):
            await self.cmd_start(chat_id)
        elif text.startswith("/kod") or text.startswith("/code") or "Giriş Kodu" in text:
            await self.cmd_kod(chat_id)
        elif text.startswith("/admin"):
            await self.cmd_admin(chat_id, state_mgr)
        else:
            # All other queries safely redirect to the secure mail-authenticated web portal
            await self.cmd_redirect_to_web(chat_id)

    async def cmd_start(self, chat_id: int):
        """Secure, zero-leak welcome screen prompting doctors to launch verified WebApp."""
        app_url = self.mini_app_url or "https://esh-radtracker.onrender.com/miniapp.html"

        inline_keyboard = {
            "inline_keyboard": [
                [{"text": "🗺️ 🚀 CANLI PACS HARİTASINI AÇ", "web_app": {"url": app_url}}],
                [{"text": "🔑 Giriş Kodu & E-Posta Doğrulama", "callback_data": "cmd_kod"}]
            ]
        }

        reply_keyboard = {
            "keyboard": [
                [{"text": "🗺️ Canlı Harita & Kroki", "web_app": {"url": app_url}}],
                [{"text": "🔑 Giriş Kodu Al"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }

        text = (
            "🏥 <b>ETLİK ŞEHİR HASTANESİ</b>\n"
            "🩺 <b>Radyoloji PACS Takip Sistemi</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "🔒 <b>Hekim Güvenlik Protokolü:</b>\n"
            "Hastane çalışma istasyonlarının anlık durumları ve masa notları yalnızca <b>yetkili radyoloji hekimlerimize özeldir</b>.\n\n"
            "📱 <b>Canlı Takip Paneli:</b>\n"
            "Tüm odaların anlık doluluk durumunu, boş masaları ve interaktif kat krokisini görmek için <b>aşağıdaki butona dokunarak güvenli paneli açınız</b>.\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>Giriş yaptıktan sonra sistem sizi 30 gün boyunca hatırlar.</i>"
        )
        
        await self.send_message(chat_id, text, inline_keyboard)

    async def cmd_redirect_to_web(self, chat_id: int):
        """Redirects any generic query to the secure web app."""
        app_url = self.mini_app_url or "https://esh-radtracker.onrender.com/miniapp.html"
        keyboard = {
            "inline_keyboard": [
                [{"text": "🗺️ 🚀 Canlı Haritayı Aç", "web_app": {"url": app_url}}],
                [{"text": "🔑 Giriş Kodu Al", "callback_data": "cmd_kod"}]
            ]
        }
        msg = (
            "🔒 <b>Güvenlik Uyarısı:</b>\n\n"
            "Hastane PACS istasyonları ve doluluk verileri gizlilik gereği doğrudan sohbet ekranında paylaşılmamaktadır.\n\n"
            "👉 Lütfen <b>Doğrulanmış Canlı Haritayı</b> açarak anlık durumu inceleyiniz."
        )
        await self.send_message(chat_id, msg, keyboard)

    async def cmd_kod(self, chat_id: int):
        """Help instructions for getting login code / email pairing."""
        app_url = self.mini_app_url or "https://esh-radtracker.onrender.com/miniapp.html"
        keyboard = {
            "inline_keyboard": [
                [{"text": "🚀 Canlı Giriş Panelini Aç", "web_app": {"url": app_url}}]
            ]
        }
        msg = (
            "🔑 <b>HEKİM DOĞRULAMA & GİRİŞ:</b>\n\n"
            "1. Kayıtlı e-posta adresinizi bu sohbete yazarak gönderdiğinizde, tek tıkla giriş kodunuz üretilir.\n"
            "2. Veya doğrudan aşağıdaki <b>Canlı Giriş Panelini Aç</b> butonuna tıklayıp mailinizi girerek oturum açabilirsiniz.\n\n"
            "<i>(Oturumunuz 30 gün boyunca cihazınızda kalıcı olarak saklanır.)</i>"
        )
        await self.send_message(chat_id, msg, keyboard)

    async def cmd_admin(self, chat_id: int, state_mgr):
        if not self.is_admin_chat(chat_id):
            await self.send_message(chat_id, "⛔ Bu komutu kullanma yetkiniz yok.")
            return
        pcs = state_mgr.get_all_computers()
        text = (
            "🛠️ <b>YÖNETİCİ KONTROL PANELİ</b>\n\n"
            f"📌 Toplam Bilgisayar: <b>{len(pcs)}</b>\n"
            f"👥 Kayıtlı Kullanıcı: <b>{len(db.state.get('users', {}))}</b>\n"
            f"🔐 İzinli Hekim Sayısı: <b>{len(db.state.get('allowed_emails', []))}</b>\n"
        )
        await self.send_message(chat_id, text)

# Global Instance
telegram_bot = TelegramBotController()
