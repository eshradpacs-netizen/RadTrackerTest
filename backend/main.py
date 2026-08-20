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

@app.post("/api/register")
async def register(payload: UserRegister):
    email = payload.email.lower().strip()
    if email in db.state["users"]:
        raise HTTPException(status_code=400, detail="Bu e-posta adresi zaten kayıtlı.")
        
    code = auth.generate_verification_code()
    pwd_hash = auth.hash_password(payload.password)
    
    user_record = {
        "email": email,
        "password_hash": pwd_hash,
        "is_verified": False,
        "verification_code": code,
        "created_at": time.time()
    }
    db.state["users"][email] = user_record
    await db.sync_to_telegram()
    await db.log_event_to_channel("👤 Yeni Kullanıcı Kaydı", f"E-Posta: <code>{email}</code>\nDoğrulama Kodu: <b>{code}</b>")
    
    return {"success": True, "message": "Kayıt başarılı. Lütfen doğrulama kodunu girin.", "verification_code_demo": code}

@app.post("/api/verify")
async def verify_code(payload: UserVerify):
    email = payload.email.lower().strip()
    user = db.state["users"].get(email)
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    if user.get("verification_code") != payload.code.strip():
        raise HTTPException(status_code=400, detail="Geçersiz doğrulama kodu.")
        
    user["is_verified"] = True
    await db.sync_to_telegram()
    
    token = auth.create_access_token({"sub": email})
    return {"success": True, "message": "E-posta başarıyla doğrulandı.", "token": token, "email": email}

@app.post("/api/login")
async def login(payload: UserLogin):
    email = payload.email.lower().strip()
    user = db.state["users"].get(email)
    if not user or not auth.verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Hatalı e-posta veya şifre.")
    if not user.get("is_verified", False):
        raise HTTPException(status_code=403, detail="E-posta henüz doğrulanmamış.")
        
    token = auth.create_access_token({"sub": email})
    return {"success": True, "token": token, "email": email}

# -----------------------------------------------------------------------------
# 4. Telegram Webhook Endpoint
# -----------------------------------------------------------------------------
@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    try:
        update = await request.json()
        await telegram_bot.handle_update(update, state_manager)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error handling Telegram update: {e}")
        return {"ok": False}

# -----------------------------------------------------------------------------
# 5. Serve Frontend & Telegram Mini App Static Files
# -----------------------------------------------------------------------------
from fastapi.responses import FileResponse

frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")

@app.get("/")
@app.get("/index.html")
@app.get("/miniapp.html")
async def serve_index():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found")

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
