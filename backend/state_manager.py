"""
Radiology PC Tracker v1 - State Manager & Real-Time WebSocket Engine
Manages in-memory PC state, 20s TTL timeout monitoring, status calculations,
and broadcasts real-time updates over WebSockets.
"""

import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Set
from fastapi import WebSocket
from master_mapping import MASTER_PC_MAPPING, resolve_agent_id, match_master_pc

# Turkey Timezone GMT+3
TR_TZ = timezone(timedelta(hours=3))

class WebSocketConnectionManager:
    """Manages active WebSocket connections from browsers and Telegram Mini Apps."""
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcasts JSON payload to all connected clients."""
        dead_sockets = set()
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead_sockets.add(ws)
        for ws in dead_sockets:
            self.active_connections.discard(ws)

class PCStateManager:
    """Manages real-time computer states, status evaluation, and TTL timeouts."""
    def __init__(self):
        self.computers: Dict[str, Dict[str, Any]] = {}
        self.ws_manager = WebSocketConnectionManager()
        self._init_all_master_pcs()

    def _init_all_master_pcs(self):
        """Initializes all 45 Radiology PCs from Master Mapping so all PCs exist out-of-the-box."""
        now_iso = datetime.now(TR_TZ).isoformat()
        for pc_id, info in MASTER_PC_MAPPING.items():
            if pc_id not in self.computers:
                self.computers[pc_id] = {
                    "id": pc_id,
                    "hostname": info.get("hostname", ""),
                    "ip": info.get("ip", ""),
                    "username": "unknown",
                    "friendlyName": info.get("friendlyName", ""),
                    "room": info.get("room", ""),
                    "idleTimeSeconds": 0,
                    "suspicious": 0,
                    "lastSeen": now_iso,
                    "lastSeenTimestamp": 0.0, # 0 means never seen live yet
                    "status": "offline",
                    "notes": ""
                }

    def evaluate_status(self, pc: Dict[str, Any], now_ts: float) -> str:
        """Evaluates PC status based on idle time, lastSeen timestamp, and lunch break."""
        last_seen_diff = now_ts - pc.get("lastSeenTimestamp", 0.0)
        
        # If no heartbeat in last 25 seconds, mark offline
        if last_seen_diff >= 25.0:
            return "offline"
            
        idle_sec = int(pc.get("idleTimeSeconds", 0))
        suspicious = int(pc.get("suspicious", 0))
        
        # Check lunch break (12:00 - 13:30 TR time)
        tr_now = datetime.now(TR_TZ)
        time_str = tr_now.strftime("%H:%M")
        is_lunch = ("12:00" <= time_str <= "13:30")
        
        if suspicious == 1:
            return "suspicious"
        if idle_sec >= 2700: # 45 minutes
            return "lunch-break" if is_lunch else "idle"
        if idle_sec >= 1800: # 30 minutes
            return "lunch-break" if is_lunch else "probably-idle"
            
        return "active"

    def process_heartbeat(self, agent_id: str, hostname: str, ip: str, username: str, idle_sec: int, suspicious: int) -> Dict[str, Any]:
        """Processes an incoming heartbeat signal from a client agent."""
        now_dt = datetime.now(TR_TZ)
        now_ts = now_dt.timestamp()
        
        resolved_id = resolve_agent_id(agent_id, hostname, ip)
        if not resolved_id:
            resolved_id = f"custom-{hostname.lower()}"
            
        pc = self.computers.get(resolved_id)
        if not pc:
            master = match_master_pc(resolved_id)
            pc = {
                "id": resolved_id,
                "hostname": hostname,
                "ip": ip,
                "username": username or "unknown",
                "friendlyName": master["friendlyName"] if master else hostname,
                "room": master["room"] if master else "General",
                "idleTimeSeconds": idle_sec,
                "suspicious": suspicious,
                "lastSeen": now_dt.isoformat(),
                "lastSeenTimestamp": now_ts,
                "status": "active",
                "notes": ""
            }
            self.computers[resolved_id] = pc
        else:
            pc["hostname"] = hostname or pc["hostname"]
            pc["ip"] = ip or pc["ip"]
            if username and username.lower() not in ["pc", "admin", "administrator", "user", "default", "unknown"]:
                pc["username"] = username
            pc["idleTimeSeconds"] = idle_sec
            pc["suspicious"] = suspicious
            pc["lastSeen"] = now_dt.isoformat()
            pc["lastSeenTimestamp"] = now_ts
            
            # Ensure master friendlyName and room are populated
            master = match_master_pc(resolved_id)
            if master:
                if not pc.get("friendlyName"): pc["friendlyName"] = master["friendlyName"]
                if not pc.get("room"): pc["room"] = master["room"]

        old_status = pc.get("status", "offline")
        new_status = self.evaluate_status(pc, now_ts)
        pc["status"] = new_status
        
        return {
            "pc": pc,
            "status_changed": (old_status != new_status),
            "old_status": old_status,
            "new_status": new_status
        }

    def get_all_states(self) -> List[Dict[str, Any]]:
        return self.get_all_computers()

    def get_all_computers(self) -> List[Dict[str, Any]]:
        """Returns the evaluated list of all 45 Radiology PCs."""
        now_ts = datetime.now(TR_TZ).timestamp()
        result = []
        for pc in self.computers.values():
            pc["status"] = self.evaluate_status(pc, now_ts)
            result.append(pc)
        return result

# Global Singleton Instance
state_manager = PCStateManager()
