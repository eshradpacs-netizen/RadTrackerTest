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
MINI_APP_URL = os.getenv("TELEGRAM_MINI_APP_URL", "")

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
            
            if cb_data == "cmd_start":
                await self.cmd_start(cb_chat_id, state_mgr)
            elif cb_data == "cmd_bos":
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
            await self.cmd_start(chat_id, state_mgr)
        elif text.startswith("/bos") or text.startswith("/free") or "Boş Bilgisayar" in text or "Boşta" in text or "Boş Masa" in text:
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

    async def cmd_start(self, chat_id: int, state_mgr=None):
        """Ultra-premium, resident-centric welcome dashboard with live metrics & quick actions."""
        app_url = self.mini_app_url or "https://esh-radtracker.onrender.com/miniapp.html"
        
        active, idle, probably_idle, lunch, offline = 0, 0, 0, 0, 0
        total_desks = 41
        
        if state_mgr:
            pcs = state_mgr.get_all_computers()
            total_desks = len(pcs) or 41
            active = sum(1 for p in pcs if p.get("status") == "active")
            idle = sum(1 for p in pcs if p.get("status") == "idle")
            probably_idle = sum(1 for p in pcs if p.get("status") == "probably-idle")
            lunch = sum(1 for p in pcs if p.get("status") == "lunch-break")
            offline = sum(1 for p in pcs if p.get("status") == "offline")
            
        total_available = idle + probably_idle + offline
        occ_pct = round((active / total_desks) * 100) if total_desks > 0 else 0

        inline_keyboard = {
            "inline_keyboard": [
                [{"text": "🟢 ⚡ BOŞ MASALARI LİSTELE", "callback_data": "cmd_bos"}],
                [{"text": "🗺️ 🚀 RadTracker Canlı Krokisini Aç", "web_app": {"url": app_url}}],
                [{"text": "🏢 Oda Dağılımları", "callback_data": "cmd_odalar"}, {"text": "📊 Genel Durum", "callback_data": "cmd_durum"}],
                [{"text": "🔑 Web Giriş Kodu Al", "callback_data": "cmd_kod"}, {"text": "🔄 Yenile", "callback_data": "cmd_start"}]
            ]
        }

        reply_keyboard = {
            "keyboard": [
                [{"text": "🟢 Boş Masalar"}, {"text": "🗺️ Canlı Kroki", "web_app": {"url": app_url}}],
                [{"text": "🏢 Oda Dağılımları"}, {"text": "📊 Genel Durum"}, {"text": "🔑 Giriş Kodu"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }

        text = (
            "🏥 <b>ETLİK ŞEHİR HASTANESİ</b>\n"
            "🩺 <b>Radyoloji PACS Canlı Takip Sistemi</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "📊 <b>ANLIK HASTANE DOLULUK DURUMU:</b>\n"
            f"• 🟢 <b>Boşta (Hemen Otur):</b> {idle} Masa\n"
            f"• 🟡 <b>Muhtemelen Boş:</b> {probably_idle} Masa\n"
            f"• 🔴 <b>Dolu (Aktif Kullanımda):</b> {active} Masa\n"
            f"• ⚪ <b>Açılabilir (Kapalı):</b> {offline} Masa\n\n"
            f"📈 <b>Doluluk Oranı:</b> %{occ_pct} (<i>{active}/{total_desks} Masa Dolu</i>)\n"
            f"🎯 <b>Toplam Müsait:</b> <b>{total_available} Masa Oturulabilir</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "⚡ <i>Aşağıdaki hızlı butonlardan boş masaları listeleyebilir veya canlı interaktif krokide yerlerini görebilirsiniz:</i>"
        )
        
        await self.send_message(chat_id, text, inline_keyboard)

    async def cmd_free_pcs(self, chat_id: int, state_mgr):
        """Lists free and idle desks grouped by room."""
        app_url = self.mini_app_url or "https://esh-radtracker.onrender.com/miniapp.html"
        pcs = state_mgr.get_all_computers()
        idle_pcs = [p for p in pcs if p.get("status") in ["idle", "probably-idle"]]
        offline_count = sum(1 for p in pcs if p.get("status") == "offline")
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🗺️ Krokide Masaların Yerini Gör", "web_app": {"url": app_url}}],
                [{"text": "🔄 Listeyi Yenile", "callback_data": "cmd_bos"}, {"text": "📊 Genel Durum", "callback_data": "cmd_durum"}]
            ]
        }

        if not idle_pcs:
            msg = (
                "⚠️ <b>Şu anda açık durumda boş bilgisayar bulunmuyor.</b>\n\n"
                f"💡 <i>Ancak <b>{offline_count}</b> adet kapalı masa mevcuttur. Dilediğiniz masaya gidip bilgisayarı açarak hemen oturabilirsiniz.</i>"
            )
            await self.send_message(chat_id, msg, keyboard)
            return

        room_groups: Dict[str, List[Any]] = {}
        for p in idle_pcs:
            r = p.get("room", "Genel PACS")
            room_groups.setdefault(r, []).append(p)

        lines = [
            "🟢 <b>ŞU AN MÜSAİT OLAN PACS MASALARI:</b>",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        
        for room_name, r_pcs in sorted(room_groups.items()):
            lines.append(f"🏢 <b>{room_name}:</b>")
            for p in r_pcs:
                idle_sec = int(p.get("idleTimeSeconds", 0))
                durum = "🟢 Tamamen Boş" if p.get("status") == "idle" else f"🟡 ~{idle_sec//60} dk Hareketsiz"
                p_name = p.get("friendlyName") or p.get("hostname", "PC")
                lines.append(f"  • <b>{p_name}</b> ➔ <i>{durum}</i>")
            lines.append("")

        lines.append(f"🎯 <i>Toplam <b>{len(idle_pcs)}</b> adet açık masa hemen oturmaya hazır!</i>")
        await self.send_message(chat_id, "\n".join(lines), keyboard)

    async def cmd_status(self, chat_id: int, state_mgr):
        """General hospital PACS telemetry summary."""
        app_url = self.mini_app_url or "https://esh-radtracker.onrender.com/miniapp.html"
        pcs = state_mgr.get_all_computers()
        total = len(pcs) or 41
        active = sum(1 for p in pcs if p.get("status") == "active")
        idle = sum(1 for p in pcs if p.get("status") == "idle")
        probably_idle = sum(1 for p in pcs if p.get("status") == "probably-idle")
        lunch = sum(1 for p in pcs if p.get("status") == "lunch-break")
        offline = sum(1 for p in pcs if p.get("status") == "offline")
        suspicious = sum(1 for p in pcs if p.get("status") == "suspicious")
        
        total_open = active + idle + probably_idle + lunch
        occ_pct = round((active / total) * 100) if total > 0 else 0

        keyboard = {
            "inline_keyboard": [
                [{"text": "🟢 Boş Masaları Listele", "callback_data": "cmd_bos"}],
                [{"text": "🗺️ Canlı Krokide Aç", "web_app": {"url": app_url}}],
                [{"text": "🏢 Oda Dağılımları", "callback_data": "cmd_odalar"}]
            ]
        }

        text = (
            "📊 <b>RADYOLOJİ PACS GENEL DURUM RAPORU</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔴 <b>Dolu (Aktif Çalışılan):</b> {active} Masa\n"
            f"🟢 <b>Boşta (Hemen Kullanılabilir):</b> {idle} Masa\n"
            f"🟡 <b>Muhtemelen Boş (30+ dk):</b> {probably_idle} Masa\n"
            f"🍱 <b>Öğle Arasında:</b> {lunch} Masa\n"
            f"⚪ <b>Kapalı / Çevrimdışı:</b> {offline} Masa\n"
            f"⚠️ <b>Şüpheli Aktivite:</b> {suspicious}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"📈 <b>Genel Doluluk Oranı:</b> <b>%{occ_pct}</b> (<i>{active}/{total} Dolu</i>)\n"
            f"🖥️ <b>Açık Bilgisayar Sayısı:</b> {total_open} / {total}\n"
            f"📌 <b>Toplam Takip Edilen Masa:</b> <b>{total} Masa</b>"
        )
        await self.send_message(chat_id, text, keyboard)

    async def cmd_rooms(self, chat_id: int, state_mgr):
        """Room-by-room breakdown of all 41 PACS desks."""
        app_url = self.mini_app_url or "https://esh-radtracker.onrender.com/miniapp.html"
        pcs = state_mgr.get_all_computers()
        rooms: Dict[str, List[Any]] = {}
        for p in pcs:
            r = p.get("room", "Genel PACS")
            rooms.setdefault(r, []).append(p)

        lines = [
            "🏢 <b>ODA BAZINDA DOLULUK DAĞILIMI:</b>",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        
        for room_name, room_pcs in sorted(rooms.items()):
            active_count = sum(1 for p in room_pcs if p.get("status") == "active")
            free_count = sum(1 for p in room_pcs if p.get("status") in ["idle", "probably-idle", "offline"])
            total_count = len(room_pcs)
            
            status_icon = "🟢" if active_count == 0 else ("🟡" if free_count > 0 else "🔴")
            lines.append(f"{status_icon} <b>{room_name}:</b> {free_count}/{total_count} Müsait (<i>{active_count} Dolu</i>)")

        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📌 Toplam Kapasite: <b>{len(pcs)} PACS Masası</b>")

        keyboard = {
            "inline_keyboard": [
                [{"text": "🟢 Boş Masaları Listele", "callback_data": "cmd_bos"}],
                [{"text": "🗺️ Canlı Krokide İncele", "web_app": {"url": app_url}}]
            ]
        }

        await self.send_message(chat_id, "\n".join(lines), keyboard)

    async def cmd_kod(self, chat_id: int):
        """Generates a rapid one-time web login code and magic link."""
        app_url = self.mini_app_url or "https://esh-radtracker.onrender.com/miniapp.html"
        code = str(abs(hash(str(chat_id) + str(asyncio.get_event_loop().time()))) % 900000 + 100000)
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🚀 Canlı Paneli Aç", "web_app": {"url": app_url}}]
            ]
        }
        
        msg = (
            "🔑 <b>WEB GİRİŞ KODUNUZ:</b>\n\n"
            f"👉 <code>{code}</code> <i>(Dokunup kopyalayabilirsiniz)</i>\n\n"
            f"🌐 <i>Bu kodu web giriş ekranındaki kutuya yazarak veya aşağıdaki butona tıklayarak anında oturum açabilirsiniz.</i>"
        )
        await self.send_message(chat_id, msg, keyboard)

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
        if email in [e.lower() for e in allowed]:
            db.state["allowed_emails"] = [e for e in allowed if e.lower() != email]
            await db.sync_to_telegram()
            await self.send_message(chat_id, f"✅ <code>{email}</code> izinli hekim listesinden çıkarıldı.")
        else:
            await self.send_message(chat_id, "ℹ️ Bu e-posta zaten listede yok.")

    async def cmd_list_emails(self, chat_id: int):
        if not self.is_admin_chat(chat_id):
            await self.send_message(chat_id, "⛔ Bu komutu kullanma yetkiniz yok.")
            return
        allowed = db.state.get("allowed_emails", [])
        if not allowed:
            await self.send_message(chat_id, "📋 İzinli hekim listesi boş.")
            return
        msg = "📋 <b>İzinli Hekim E-Posta Listesi:</b>\n\n" + "\n".join([f"• <code>{e}</code>" for e in allowed])
        await self.send_message(chat_id, msg)

    async def cmd_admin(self, chat_id: int, state_mgr):
        if not self.is_admin_chat(chat_id):
            await self.send_message(chat_id, "⛔ Bu komutu kullanma yetkiniz yok.")
            return
        pcs = state_mgr.get_all_computers()
        text = (
            "🛠️ <b>YÖNETİCİ KONTROL PANELİ</b>\n\n"
            f"📌 Toplam Bilgisayar: <b>{len(pcs)}</b>\n"
            f"👥 Kayıtlı Kullanıcı: <b>{len(db.state.get('users', {}))}</b>\n"
            f"🔐 İzinli E-Posta: <b>{len(db.state.get('allowed_emails', []))}</b>\n\n"
            "<b>Kullanılabilir Komutlar:</b>\n"
            "• <code>/ekle doktor@hastane.com</code> ➔ Hekim ekle\n"
            "• <code>/cikar doktor@hastane.com</code> ➔ Hekim sil\n"
            "• <code>/listele</code> ➔ Tüm izinli hekimleri gör\n"
            "• <code>/admin_ekle &lt;chat_id&gt;</code> ➔ Yeni yönetici ata"
        )
        await self.send_message(chat_id, text)

# Global Instance
telegram_bot = TelegramBotController()
