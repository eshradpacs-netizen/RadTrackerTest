"""
Radiology PC Tracker v1 - Pydantic Validation Schemas
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any

class HeartbeatPayload(BaseModel):
    id: Optional[str] = ""
    hostname: str
    ip: Optional[str] = "unknown"
    username: Optional[str] = "unknown"
    idleTimeSeconds: Optional[int] = 0
    suspicious: Optional[int] = 0

class UserRegister(BaseModel):
    email: str
    password: str
    telegram_id: Optional[str] = ""
    telegram_username: Optional[str] = ""

class UserVerify(BaseModel):
    email: str
    code: str
    telegram_id: Optional[str] = ""

class UserLogin(BaseModel):
    email: str
    password: str
    telegram_id: Optional[str] = ""
    telegram_username: Optional[str] = ""

class MetadataUpdate(BaseModel):
    id: Optional[str] = ""
    hostname: Optional[str] = ""
    friendlyName: Optional[str] = ""
    room: Optional[str] = ""
    notes: Optional[str] = ""
