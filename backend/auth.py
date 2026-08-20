"""
Radiology PC Tracker v1 - Authentication & Security Module
Provides password hashing, 6-digit email verification codes, and JWT tokens.
"""

import os
import secrets
import hashlib
import time
from typing import Optional, Dict, Any
import jwt

SECRET_KEY = os.getenv("JWT_SECRET", "radtracker_super_secret_jwt_key_2026")
ALGORITHM = "HS256"
TOKEN_EXPIRE_SECONDS = 86400 * 30  # 30 days session expiry

def hash_password(password: str) -> str:
    """Hashes a password with SHA256 and a random salt."""
    salt = secrets.token_hex(16)
    salted = f"{salt}:{password}".encode("utf-8")
    pwd_hash = hashlib.sha256(salted).hexdigest()
    return f"{salt}${pwd_hash}"

def verify_password(password: str, hashed: str) -> bool:
    """Verifies a password against a stored salt$hash string."""
    try:
        salt, pwd_hash = hashed.split("$")
        salted = f"{salt}:{password}".encode("utf-8")
        calc_hash = hashlib.sha256(salted).hexdigest()
        return secrets.compare_digest(calc_hash, pwd_hash)
    except Exception:
        return False

def generate_verification_code() -> str:
    """Generates a 6-digit verification code."""
    return str(secrets.randbelow(900000) + 100000)

def create_access_token(data: dict, expires_delta: Optional[int] = None) -> str:
    """Creates a JWT access token for a user."""
    to_encode = data.copy()
    expire = time.time() + (expires_delta or TOKEN_EXPIRE_SECONDS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
