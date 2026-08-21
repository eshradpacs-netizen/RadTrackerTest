"""
Radiology PC Tracker v1 - FastAPI Backend Application
Integrates WebSockets, Telegram-DB Engine, Telegram Bot, and Agent Heartbeat processing.
"""

import os
import time
import asyncio
import logging
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

# Store verification codes in memory: email -> { "code": "849201", "expires_at": 1787..., "telegram_id": "123456" }
VERIFICATION_CODES: Dict[str, Dict[str, Any]] = {}

@app.post("/api/send-telegram-code")
async def send_telegram_code(payload: Dict[str, Any]):
    email = payload.get("email", "").lower().strip()
    tg_id = payload.get("telegram_id", "").strip()
    tg_user = payload.get("telegram_username", "").strip()

    if not email:
        raise HTTPException(status_code=400, detail="Lütfen geçerli bir e-posta adresi giriniz.")

    # 1. Whitelist Check
    allowed = [e.lower() for e in db.state.get("allowed_emails", [])]
    if email not in allowed:
        raise HTTPException(status_code=403, detail="Bu e-posta adresi yetkili hekim listesinde bulunamadı. Lütfen yöneticinize başvurun.")

    # 2. Telegram Identity Matching & Binding Check
    users = db.state.get("users", {})
    existing_user = users.get(email)

    if existing_user and existing_user.get("telegram_id"):
        bound_tg_id = str(existing_user["telegram_id"])
        if tg_id and bound_tg_id != tg_id:
            raise HTTPException(status_code=403, detail=f"Güvenlik Uyarısı: Bu e-posta adresi başka bir Telegram hesabına (@{existing_user.get('telegram_username', 'kilitli')}) kilitlidir!")

    target_chat_id = tg_id or (existing_user.get("telegram_id") if existing_user else None)

    # Generate 6-digit random code
    code = f"{random.randint(100000, 999999)}"
    VERIFICATION_CODES[email] = {
        "code": code,
        "expires_at": time.time() + 300, # 5 minutes
        "telegram_id": tg_id,
        "telegram_username": tg_user
    }

    msg_text = (
        f"🔑 <b>RadTracker Hekim Giriş Kodu</b>\n\n"
        f"E-Posta: <code>{email}</code>\n"
        f"Doğrulama Kodunuz: <b>{code}</b>\n\n"
        f"<i>Bu kod 5 dakika süreyle geçerlidir. Lütfen kimseyle paylaşmayınız.</i>"
    )

    sent_via_bot = False
    if target_chat_id:
        try:
            await telegram_bot.send_message(int(target_chat_id), msg_text)
            sent_via_bot = True
        except Exception as e:
            logger.warning(f"Could not send direct chat message to {target_chat_id}: {e}")

    if not sent_via_bot:
        await db.log_event_to_channel("🔑 Hekim Giriş Kodu", msg_text)

    return {
        "success": True,
        "message": f"6 haneli doğrulama kodu Telegram sohbetinize (@RadTrackerTest_bot) gönderildi!",
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
pc_notes_service = PCNotesService(db, state_manager.ws_manager)
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

@app.post("/api/pc/notes")
async def update_pc_note(payload: Dict[str, Any]):
    pc_id = payload.get("pc_id", "")
    notes = payload.get("notes", "")
    friendly_name = payload.get("friendlyName", None)
    room = payload.get("room", None)
    author = payload.get("author", "Hekim")
    if not pc_id:
        raise HTTPException(status_code=400, detail="pc_id zorunludur.")
    res = await pc_notes_service.update_pc_note(pc_id, notes, friendly_name, room, author)
    return {"success": True, "metadata": res}

@app.get("/api/analytics")
async def get_analytics_summary():
    return {"success": True, "analytics": analytics_service.get_analytics_summary()}

@app.get("/api/admin/users")
async def admin_get_users():
    return {
        "success": True, 
        "users": db.state.get("users", {}),
        "allowed_emails": db.state.get("allowed_emails", [])
    }

@app.post("/api/admin/whitelist/add")
async def admin_add_whitelist(payload: Dict[str, Any]):
    email = payload.get("email", "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="E-Posta boş olamaz.")
    allowed = db.state.setdefault("allowed_emails", [])
    if email not in [e.lower() for e in allowed]:
        allowed.append(email)
        await db.sync_to_telegram()
    return {"success": True, "allowed_emails": allowed}

@app.post("/api/admin/whitelist/remove")
async def admin_remove_whitelist(payload: Dict[str, Any]):
    email = payload.get("email", "").lower().strip()
    allowed = db.state.setdefault("allowed_emails", [])
    db.state["allowed_emails"] = [e for e in allowed if e.lower() != email]
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

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
