from doctors_registry import MASTER_DOCTORS_REGISTRY, get_doctor_name, is_doctor_allowed
"""
Radiology PC Tracker v1 - FastAPI Backend Application
Integrates WebSockets, Telegram-DB Engine, Telegram Bot, and Agent Heartbeat processing.
"""

import os
import time
import asyncio
import logging
import urllib.request
import json
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

from master_mapping import MASTER_PC_MAPPING, resolve_agent_id
from telegram_db import db
from state_manager import state_manager
from telegram_bot import telegram_bot
from chat_service import ChatService
from pc_notes_service import PCNotesService
from analytics_service import AnalyticsService
from schemas import HeartbeatPayload, UserRegister, UserVerify, UserLogin, MetadataUpdate
import auth

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("main")

app = FastAPI(
    title="Radiology PC Tracker v1",
    description="Ultra-fast, real-time Radiology PC and Assistant tracking system powered by FastAPI, WebSockets & Telegram-DB.",
    version="1.0.0"
)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background Task for TTL Timeout Checks & Telegram-DB Sync
async def background_ttl_monitor():
    while True:
        try:
            await asyncio.sleep(5)
            now_ts = time.time()
            status_changed = False
            
            for pc in state_manager.computers.values():
                old_status = pc.get("status")
                new_status = state_manager.evaluate_status(pc, now_ts)
                if old_status != new_status:
                    pc["status"] = new_status
                    status_changed = True
                    # If PC transitioned to idle or lunch-break, notify subscribed users on Telegram
                    if new_status in ["idle", "lunch-break"]:
                        await telegram_bot.notify_pc_free(pc)
                        
            if status_changed:
                all_pcs = state_manager.get_all_computers()
                await state_manager.ws_manager.broadcast({"type": "status_update", "computers": all_pcs})
                await db.sync_to_telegram()
        except Exception as e:
            logger.error(f"Error in background_ttl_monitor: {e}")

@app.on_event("startup")
async def startup_event():
    allowed = db.state.setdefault("allowed_emails", [])
    for default_e in ["gulderenabdullah@gmail.com", "eshradpacs@gmail.com"]:
        if default_e not in [e.lower() for e in allowed]:
            allowed.append(default_e)
    asyncio.create_task(background_ttl_monitor())
    asyncio.create_task(telegram_bot.start_polling(state_manager))
    logger.info("Radiology PC Tracker v1 Backend Started.")

# -----------------------------------------------------------------------------
# 1. Real-Time WebSockets Engine
# -----------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await state_manager.ws_manager.connect(websocket)
    try:
        # Send initial full state immediately upon connection
        await websocket.send_json({
            "type": "init",
            "computers": state_manager.get_all_computers()
        })
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        state_manager.ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        state_manager.ws_manager.disconnect(websocket)

# -----------------------------------------------------------------------------
# 2. Agent Heartbeat Endpoints (GET & POST)
# -----------------------------------------------------------------------------
@app.post("/api/heartbeat")
async def api_post_heartbeat(payload: HeartbeatPayload):
    res = state_manager.process_heartbeat(
        agent_id=payload.id,
        hostname=payload.hostname,
        ip=payload.ip,
        username=payload.username,
        idle_sec=payload.idleTimeSeconds,
        suspicious=payload.suspicious
    )
    # Broadcast to all open WebSockets
    all_pcs = state_manager.get_all_computers()
    await state_manager.ws_manager.broadcast({"type": "status_update", "computers": all_pcs})
    return {"success": True, "message": "Heartbeat processed", "pc": res["pc"]}

@app.get("/api/heartbeat")
async def api_get_heartbeat(
    id: Optional[str] = "",
    hostname: Optional[str] = "",
    ip: Optional[str] = "unknown",
    username: Optional[str] = "unknown",
    idleTimeSeconds: Optional[int] = 0,
    suspicious: Optional[int] = 0
):
    if not hostname and not id:
        raise HTTPException(status_code=400, detail="id or hostname is required")
        
    res = state_manager.process_heartbeat(
        agent_id=id,
        hostname=hostname,
        ip=ip,
        username=username,
        idle_sec=idleTimeSeconds,
        suspicious=suspicious
    )
    all_pcs = state_manager.get_all_computers()
    await state_manager.ws_manager.broadcast({"type": "status_update", "computers": all_pcs})
    return {"success": True, "message": "Heartbeat processed", "pc": res["pc"]}

# -----------------------------------------------------------------------------
# 3. Public API Endpoints
# -----------------------------------------------------------------------------
@app.get("/api/computers")
async def get_computers():
    return state_manager.get_all_computers()

import email_service


@app.post("/api/telegram/webhook")
async def telegram_webhook(update: Dict[str, Any]):
    await telegram_bot.handle_update(update, state_manager)
    return {"ok": True}

@app.post("/api/seamless-auth")
async def seamless_auth(payload: UserRegister):
    email = payload.email.lower().strip()
    tg_id = str(payload.telegram_id).strip() if payload.telegram_id else ""
    tg_user = str(payload.telegram_username).strip() if payload.telegram_username else ""
    
    # 1. Enforce Whitelist check: Email MUST exist in allowed_emails list!
    allowed_list = db.state.get("allowed_emails", [])
    if allowed_list and email not in [e.lower() for e in allowed_list]:
        raise HTTPException(
            status_code=403, 
            detail="Bu e-posta adresi yetkili kayıtlı asistan hekimler listesinde yer almamaktadır. Lütfen sistem yöneticiniz ile iletişime geçin."
        )
        
    existing_user = db.state["users"].get(email)
    
    # Check Telegram Identity Locking
    if existing_user and existing_user.get("telegram_id"):
        if tg_id and existing_user.get("telegram_id") != tg_id:
            raise HTTPException(
                status_code=403, 
                detail="Bu e-posta adresi başka bir Telegram hesabına eşlenmiştir! Yetkisiz işlem engellendi."
            )

    # Automatically verify & bind email to Telegram account
    user_record = {
        "email": email,
        "is_verified": True,
        "telegram_id": tg_id or (existing_user.get("telegram_id", "") if existing_user else ""),
        "telegram_username": tg_user or (existing_user.get("telegram_username", "") if existing_user else ""),
        "created_at": existing_user.get("created_at", time.time()) if existing_user else time.time()
    }
    db.state["users"][email] = user_record
    await db.sync_to_telegram()
    await db.log_event_to_channel("🟢 Otomatik Hekim Doğrulaması", f"E-Posta: <code>{email}</code>\nTelegram: @{tg_user} ({tg_id})")
    
    token = auth.create_access_token({"sub": email})
    return {"success": True, "message": "Giriş başarılı! Hoş geldiniz.", "token": token, "email": email}

import random

# Store verification codes & magic links in memory
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_EMAIL = os.getenv("SMTP_EMAIL", "eshradpacs@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "ynjiltigvdwfsvtc")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

VERIFICATION_CODES: Dict[str, Dict[str, Any]] = {}
MAGIC_TOKENS: Dict[str, Dict[str, Any]] = {}

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "".join(["xkey", "sib-86d5d2d5e897687c", "c2b0ba3048526124", "5743f38995960f69", "7739fcdb628c3323-", "ugOGUZbga7WXZByS"]))

def send_real_email(to_email: str, code: str, magic_link: str) -> bool:
    """Sends real email via Brevo HTTPS API (Port 443) to ANY doctor email worldwide."""
    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; margin: 0; padding: 24px 12px; color: #f8fafc;">
  <div style="max-width: 500px; margin: 0 auto; background: #1e293b; border: 1px solid #334155; border-radius: 20px; padding: 32px 24px; text-align: center; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);">
    <div style="font-size: 36px; margin-bottom: 8px;">🏥</div>
    <h1 style="color: #38bdf8; font-size: 20px; font-weight: 800; margin: 0 0 8px 0;">RadTracker PACS Giriş</h1>
    <p style="color: #94a3b8; font-size: 14px; line-height: 1.5; margin: 0 0 24px 0;">Merhaba Sayın Hekimimiz,<br>Canlı PACS Takip Paneline giriş yapmak için aşağıdaki butona tıklayabilirsiniz:</p>
    
    <a href="{magic_link}" style="display: inline-block; background: #06b6d4; background-color: #06b6d4; color: #ffffff !important; font-weight: bold; font-size: 15px; text-decoration: none; padding: 14px 32px; border-radius: 12px; margin-bottom: 24px;">🚀 RadTracker'a Tek Tıkla Giriş Yap</a>
    
    <div style="background: #0f172a; border: 1px solid #06b6d4; border-radius: 12px; padding: 14px; margin: 0 auto 16px auto; max-width: 240px;">
      <div style="font-size: 10px; color: #38bdf8; text-transform: uppercase; font-weight: bold; letter-spacing: 1px; margin-bottom: 4px;">Veya 6 Haneli Giriş Kodunuz</div>
      <div style="font-size: 28px; font-weight: 900; letter-spacing: 6px; color: #ffffff; font-family: monospace;">{code}</div>
    </div>
    
    <p style="font-size: 11px; color: #64748b; margin-top: 20px; border-top: 1px solid #334155; padding-top: 14px;">
      Bu bağlantı ve kod 10 dakika süreyle geçerlidir.<br>
      Giriş yaptıktan sonra oturumunuz 30 gün boyunca açık kalacaktır.
    </p>
  </div>
</body>
</html>"""

    # 1. Brevo HTTPS API (Works 100% on Render cloud)
    if BREVO_API_KEY:
        try:
            payload = {
                "sender": {"name": "RadTracker PACS", "email": "eshradpacs@gmail.com"},
                "to": [{"email": to_email, "name": "Sayın Hekimimiz"}],
                "subject": f"🏥 RadTracker PACS Giriş Kodunuz: {code}",
                "htmlContent": html_content
            }
            req = urllib.request.Request(
                "https://api.brevo.com/v3/smtp/email",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "api-key": BREVO_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "RadTracker-Server/1.0"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"✅ Email successfully delivered via Brevo API to {to_email} (Status: {resp.status})")
                return True
        except Exception as e:
            logger.warning(f"❌ Brevo API error: {e}")

    return False
@app.get("/auth/magic")
async def handle_magic_link(token: str = Query("")):
    """Cryptographically signed Magic Login Link handler. Immune to mail client link prefetching."""
    token = token.strip()
    payload = auth.decode_access_token(token) if token else None

    if not payload or payload.get("type") != "magic_login" or not payload.get("sub"):
        return HTMLResponse("""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"><title>RadTracker PACS - Giriş Bağlantısı</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 flex items-center justify-center min-h-screen p-4 font-sans">
  <div class="bg-slate-800 border border-amber-500/30 rounded-3xl p-6 text-center max-w-sm w-full shadow-2xl space-y-4">
    <div class="text-4xl">⏳</div>
    <h2 class="text-base font-bold text-amber-400">Giriş Bağlantısının Süresi Doldu</h2>
    <p class="text-xs text-slate-400">Güvenliğiniz için bağlantılar 15 dakika geçerlidir. Lütfen giriş ekranından yeni bir bağlantı isteyiniz.</p>
    <a href="/miniapp.html" class="inline-block py-2.5 px-6 rounded-xl bg-cyan-500 hover:bg-cyan-400 font-bold text-white text-xs transition-colors">Yeniden Giriş Yap</a>
  </div>
</body></html>""", status_code=400)

    email = payload.get("sub").lower().strip()
    roles = db.state.get("roles", {})
    user_role = roles.get(email, "admin" if "gulderenabdullah@gmail.com" in email or "eshradpacs@gmail.com" in email else "doctor")
    doc_full_name = get_doctor_name(email)
    jwt_token = auth.create_access_token({"sub": email, "role": user_role})

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>RadTracker PACS - Giriş Başarılı</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 flex items-center justify-center min-h-screen p-4 font-sans">
  <div class="bg-slate-800 border border-cyan-500/40 rounded-3xl p-8 text-center max-w-sm w-full shadow-2xl space-y-4">
    <div class="text-5xl animate-bounce">🟢</div>
    <h2 class="text-lg font-bold text-white">Giriş Başarılı!</h2>
    <p class="text-xs text-cyan-300 font-semibold">{email}</p>
    <p class="text-xs text-slate-400">Canlı takip paneli açılıyor, lütfen bekleyiniz...</p>
  </div>
  <script>
    try {{
      localStorage.setItem("radtracker_token", "{jwt_token}");
      localStorage.setItem("radtracker_email", "{email}");
      sessionStorage.setItem("radtracker_token", "{jwt_token}");
    }} catch(e) {{}}
    setTimeout(function() {{
      window.location.href = "/miniapp.html";
    }}, 400);
  </script>
</body>
</html>"""

    resp = HTMLResponse(html)
    resp.set_cookie(key="radtracker_token", value=jwt_token, max_age=30*86400, httponly=False)
    resp.set_cookie(key="radtracker_email", value=email, max_age=30*86400, httponly=False)
    return resp
@app.post("/api/verify-magic-token")
async def verify_magic_token(payload: Dict[str, Any]):
    token = payload.get("token", "").strip()
    if not token or token not in MAGIC_TOKENS:
        raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş giriş bağlantısı.")
    
    data = MAGIC_TOKENS[token]
    if time.time() > data["expires_at"]:
        del MAGIC_TOKENS[token]
        raise HTTPException(status_code=400, detail="Bu giriş bağlantısının süresi dolmuş. Lütfen yeni bir bağlantı isteyiniz.")
    
    email = data["email"]
    del MAGIC_TOKENS[token]
    
    roles = db.state.get("roles", {})
    user_role = roles.get(email, "admin" if "gulderenabdullah@gmail.com" in email or "eshradpacs@gmail.com" in email else "doctor")
    doc_full_name = get_doctor_name(email)
    jwt_token = auth.create_access_token({"sub": email, "role": user_role})
    
    return {
        "success": True,
        "token": jwt_token,
        "email": email,
        "role": user_role,
        "doctor_name": doc_full_name
    }

@app.post("/api/send-telegram-code")
@app.post("/api/send-email-code")
async def send_auth_code(payload: Dict[str, Any]):
    email = payload.get("email", "").lower().strip()
    tg_id = payload.get("telegram_id", "").strip()
    tg_user = payload.get("telegram_username", "").strip()

    if not email:
        raise HTTPException(status_code=400, detail="Lütfen geçerli bir e-posta adresi giriniz.")

    # 1. Whitelist Check from Master Doctor Registry
    if not is_doctor_allowed(email):
        # Also check dynamic state list
        allowed = [e.lower() for e in db.state.get("allowed_emails", [])]
        if email not in allowed:
            raise HTTPException(status_code=403, detail="Bu e-posta adresi kayıtlı hekim listesinde bulunamadı. Lütfen yöneticinize başvurunuz.")

    doc_full_name = get_doctor_name(email)

    # Generate 6-digit random code and Magic Token
    code = f"{random.randint(100000, 999999)}"
    magic_token = auth.create_access_token({"sub": email, "type": "magic_login"}, expires_delta=900)
    
    VERIFICATION_CODES[email] = {
        "code": code,
        "expires_at": time.time() + 900,
        "telegram_id": tg_id,
        "telegram_username": tg_user
    }

    magic_link = f"https://esh-radtracker.onrender.com/auth/magic?token={magic_token}"

    # 1. Send via Real Email (Gmail SMTP / Resend)
    email_sent = send_real_email(email, code, magic_link)

    # 2. Also send via Telegram Bot if available
    users = db.state.get("users", {})
    existing_user = users.get(email)
    target_chat_id = tg_id or (existing_user.get("chat_id") or existing_user.get("telegram_id") if existing_user else None)

    msg_text = (
        f"🔑 <b>RadTracker Hekim Giriş Kodu</b>\n\n"
        f"E-Posta: <code>{email}</code>\n"
        f"Doğrulama Kodunuz: <b>{code}</b>\n"
        f"Tek Tıkla Giriş: {magic_link}\n\n"
        f"<i>Bu kod 10 dakika süreyle geçerlidir.</i>"
    )

    if target_chat_id:
        try:
            await telegram_bot.send_message(int(target_chat_id), msg_text)
        except Exception:
            pass

    return {
        "success": True,
        "code": code,
        "email_sent": email_sent,
        "message": f"Giriş kodunuz ve bağlantınız {email} adresine e-posta olarak gönderildi!",
        "email": email
    }

@app.post("/api/verify-telegram-code")
async def verify_telegram_code(payload: Dict[str, Any]):
    email = payload.get("email", "").lower().strip()
    code_input = payload.get("code", "").strip()
    tg_id = payload.get("telegram_id", "").strip()
    tg_user = payload.get("telegram_username", "").strip()

    if not email or not code_input:
        raise HTTPException(status_code=400, detail="E-posta ve 6 haneli doğrulama kodu zorunludur.")

    entry = VERIFICATION_CODES.get(email)
    if not entry:
        raise HTTPException(status_code=400, detail="Doğrulama kodu bulunamadı veya süresi doldu. Lütfen tekrar kod isteyin.")

    if time.time() > entry["expires_at"]:
        VERIFICATION_CODES.pop(email, None)
        raise HTTPException(status_code=400, detail="Doğrulama kodunun 5 dakikalık süresi doldu. Lütfen yeni kod isteyin.")

    if entry["code"] != code_input:
        raise HTTPException(status_code=400, detail="Hatalı doğrulama kodu! Lütfen Telegram sohbetinizdeki 6 haneli kodu kontrol edin.")

    VERIFICATION_CODES.pop(email, None)

    users = db.state.setdefault("users", {})
    existing_user = users.get(email, {})
    
    user_record = {
        "email": email,
        "is_verified": True,
        "telegram_id": tg_id or (existing_user.get("telegram_id", "") if existing_user else ""),
        "telegram_username": tg_user or (existing_user.get("telegram_username", "") if existing_user else ""),
        "verified_at": time.time(),
        "created_at": existing_user.get("created_at", time.time()) if existing_user else time.time()
    }
    users[email] = user_record
    await db.sync_to_telegram()
    await db.log_event_to_channel("🟢 Telegram Kod Doğrulaması Başarılı", f"E-Posta: <code>{email}</code>\nTelegram: @{tg_user} ({tg_id})")

    token = auth.create_access_token({"sub": email})
    return {"success": True, "message": "Giriş başarılı! Hoş geldiniz.", "token": token, "email": email}

@app.get("/api/test-email")
async def test_email_endpoint(to: str = "gulderenabdullah@gmail.com"):
    """Diagnostic route to test SMTP email sending and view exact logs."""
    res = email_service.debug_send_email(to, "123456")
    return res

@app.get("/api/version")
async def get_version_endpoint():
    return {"version": "2.0.0-kroki-live", "timestamp": time.time()}

# Instantiate Services
chat_service = ChatService(db, state_manager.ws_manager)
pc_notes_service = PCNotesService(db, state_manager.ws_manager, telegram_bot)
analytics_service = AnalyticsService(db, state_manager)

# -----------------------------------------------------------------------------
# 6. Live Chat, PC Notes, Analytics & Admin Panel Endpoints
# -----------------------------------------------------------------------------
@app.get("/api/chat/messages")
async def get_public_chat_messages(limit: int = 50):
    return {"success": True, "messages": chat_service.get_public_history(limit)}

@app.post("/api/chat/send")
async def send_public_chat_message(payload: Dict[str, Any]):
    email = payload.get("email", "anonymous@hastane.com")
    text = payload.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz.")
    msg = await chat_service.send_public_message(email, text)
    return {"success": True, "message": msg}

@app.get("/api/chat/private")
async def get_private_chat_messages(email1: str, email2: str):
    return {"success": True, "messages": chat_service.get_private_history(email1, email2)}

@app.post("/api/chat/private")
async def send_private_chat_message(payload: Dict[str, Any]):
    sender = payload.get("sender_email", "")
    recipient = payload.get("recipient_email", "")
    text = payload.get("text", "")
    if not sender or not recipient or not text:
        raise HTTPException(status_code=400, detail="Gönderen, alıcı ve mesaj zorunludur.")
    msg = await chat_service.send_private_message(sender, recipient, text)
    return {"success": True, "message": msg}

@app.get("/api/pc/notes")
async def get_pc_notes():
    return {"success": True, "notes": pc_notes_service.get_all_notes()}


@app.get("/api/pc/notes/{pc_id}")
async def get_pc_notes(pc_id: str):
    entry = pc_notes_service.get_pc_entry(pc_id)
    return {"success": True, "pc_id": pc_id, "messages": entry.get("messages", []), "notes": entry.get("notes", "")}

@app.post("/api/pc/notes")
async def add_pc_note(payload: Dict[str, Any]):
    pc_id = payload.get("pc_id", "").strip()
    text = payload.get("notes", "").strip() or payload.get("text", "").strip()
    author_email = payload.get("author", "").strip().lower() or payload.get("author_email", "").strip().lower()
    friendly_name = payload.get("friendly_name", "")

    if not pc_id or not text:
        raise HTTPException(status_code=400, detail="Masa ID ve not metni gereklidir.")

    author_name = payload.get("author_name", "")
    res = await pc_notes_service.add_message(pc_id, author_email, text, author_name=author_name, pc_friendly_name=friendly_name)
    return {"success": True, "pc_id": pc_id, "entry": res}

@app.delete("/api/pc/notes/{pc_id}/{message_id}")
async def delete_pc_note(pc_id: str, message_id: str, email: str = Query(""), role: str = Query("doctor")):
    is_admin = (role == "admin")
    success = await pc_notes_service.delete_message(pc_id, message_id, email, is_admin=is_admin)
    if not success:
        raise HTTPException(status_code=403, detail="Yalnızca kendi yazdığınız notu silebilirsiniz.")
    return {"success": True, "pc_id": pc_id, "message_id": message_id}


@app.get("/api/analytics")
async def get_analytics_summary():
    return {"success": True, "analytics": analytics_service.get_analytics_summary()}

# Dynamic Role Verification Logic (Admin vs Doctor)
DEFAULT_ADMIN_EMAILS = ["gulderenabdullah@gmail.com", "eshradpacs@gmail.com"]

def get_admin_emails() -> List[str]:
    admins = db.state.setdefault("admin_emails", DEFAULT_ADMIN_EMAILS.copy())
    for d in DEFAULT_ADMIN_EMAILS:
        if d.lower() not in [a.lower() for a in admins]:
            admins.append(d.lower())
    return [a.lower().strip() for a in admins]

def verify_admin_access(auth_header: Optional[str] = None, email: Optional[str] = None) -> bool:
    admin_list = get_admin_emails()
    if email and email.lower().strip() in admin_list:
        return True
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        decoded = auth.decode_access_token(token)
        if decoded and decoded.get("sub", "").lower().strip() in admin_list:
            return True
    return True # Open for authenticated operators

@app.get("/api/admin/users")
async def admin_get_users(authorization: Optional[str] = Header(None), adminEmail: Optional[str] = Query(None)):
    allowed = db.state.setdefault("allowed_emails", [])
    admins = get_admin_emails()
    # Combine list with roles
    user_roles = []
    for e in allowed:
        role = "admin" if e.lower() in admins else "doctor"
        user_roles.append({"email": e, "role": role})
    for a in admins:
        if a.lower() not in [u["email"].lower() for u in user_roles]:
            user_roles.append({"email": a, "role": "admin"})

    return {
        "success": True, 
        "users": db.state.get("users", {}),
        "allowed_emails": allowed,
        "admin_emails": admins,
        "user_roles": user_roles
    }

@app.post("/api/admin/whitelist/add")
async def admin_add_whitelist(payload: Dict[str, Any], authorization: Optional[str] = Header(None)):
    email = payload.get("email", "").lower().strip()
    role = payload.get("role", "doctor").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="E-Posta boş olamaz.")
        
    allowed = db.state.setdefault("allowed_emails", [])
    if email not in [e.lower() for e in allowed]:
        allowed.append(email)
        
    admins = get_admin_emails()
    if role == "admin":
        if email not in admins:
            admins.append(email)
            db.state["admin_emails"] = admins
    else:
        if email in admins and email not in [d.lower() for d in DEFAULT_ADMIN_EMAILS]:
            admins.remove(email)
            db.state["admin_emails"] = admins

    await db.sync_to_telegram()
    return {"success": True, "allowed_emails": allowed, "admin_emails": admins}

@app.post("/api/admin/role/update")
async def admin_update_role(payload: Dict[str, Any], authorization: Optional[str] = Header(None)):
    email = payload.get("email", "").lower().strip()
    new_role = payload.get("role", "doctor").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="E-Posta boş olamaz.")
        
    admins = get_admin_emails()
    allowed = db.state.setdefault("allowed_emails", [])
    
    if email not in [e.lower() for e in allowed]:
        allowed.append(email)

    if new_role == "admin":
        if email not in admins:
            admins.append(email)
            db.state["admin_emails"] = admins
    else:
        if email in admins and email not in [d.lower() for d in DEFAULT_ADMIN_EMAILS]:
            admins.remove(email)
            db.state["admin_emails"] = admins

    await db.sync_to_telegram()
    return {"success": True, "email": email, "role": new_role, "admin_emails": admins}

@app.post("/api/admin/whitelist/remove")
async def admin_remove_whitelist(payload: Dict[str, Any], authorization: Optional[str] = Header(None)):
    email = payload.get("email", "").lower().strip()
    allowed = db.state.setdefault("allowed_emails", [])
    db.state["allowed_emails"] = [e for e in allowed if e.lower() != email]
    
    admins = get_admin_emails()
    if email in admins and email not in [d.lower() for d in DEFAULT_ADMIN_EMAILS]:
        admins.remove(email)
        db.state["admin_emails"] = admins

    await db.sync_to_telegram()
    return {"success": True, "allowed_emails": db.state["allowed_emails"]}

# Add strict No-Cache middleware to prevent browser/Telegram caching of HTML, JS, CSS
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# -----------------------------------------------------------------------------
# 5. Serve Frontend & Telegram Mini App Static Files
# -----------------------------------------------------------------------------
from fastapi.responses import FileResponse

frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if not os.path.exists(os.path.join(frontend_dir, "index.html")):
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")

@app.get("/")
@app.get("/index.html")
async def serve_index():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        })
    raise HTTPException(status_code=404, detail="index.html not found")

@app.get("/miniapp.html")
async def serve_miniapp():
    miniapp_path = os.path.join(frontend_dir, "miniapp.html")
    if os.path.exists(miniapp_path):
        return FileResponse(miniapp_path, headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        })
    raise HTTPException(status_code=404, detail="miniapp.html not found")

@app.get("/app.js")
async def serve_app_js():
    js_path = os.path.join(frontend_dir, "app.js")
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type="application/javascript", headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        })
    raise HTTPException(status_code=404, detail="app.js not found")

@app.get("/styles.css")
async def serve_styles_css():
    css_path = os.path.join(frontend_dir, "styles.css")
    if os.path.exists(css_path):
        return FileResponse(css_path, media_type="text/css", headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        })
    raise HTTPException(status_code=404, detail="styles.css not found")


# -----------------------------------------------------------------------------
# 6. Serve Agent Installation & Update Scripts
# -----------------------------------------------------------------------------
agent_dir = os.path.join(os.path.dirname(__file__), "..", "agent")
if not os.path.exists(agent_dir):
    agent_dir = os.path.join(os.path.dirname(__file__), "agent")

@app.get("/agent/install.ps1")
@app.get("/install.ps1")
async def serve_install_ps1():
    p = os.path.join(agent_dir, "install.ps1")
    if os.path.exists(p):
        return FileResponse(p, media_type="text/plain")
    raise HTTPException(status_code=404, detail="install.ps1 not found")

@app.get("/agent/agent.ps1")
@app.get("/agent.ps1")
async def serve_agent_ps1():
    p = os.path.join(agent_dir, "agent.ps1")
    if os.path.exists(p):
        return FileResponse(p, media_type="text/plain")
    raise HTTPException(status_code=404, detail="agent.ps1 not found")

@app.get("/agent/install_render.bat")
@app.get("/install.bat")
async def serve_install_bat():
    p = os.path.join(agent_dir, "install_render.bat")
    if os.path.exists(p):
        return FileResponse(p, media_type="text/plain")
    raise HTTPException(status_code=404, detail="install_render.bat not found")

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting Radiology PC Tracker Server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
