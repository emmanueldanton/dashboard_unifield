from __future__ import annotations
import hashlib
import secrets
import time

SESSION_TTL = 86_400  # 24 h

_sessions: dict[str, dict] = {}


def _hash(sid: str) -> str:
    return hashlib.sha256(sid.encode()).hexdigest()


def create_session(email: str, role: str, access_token: str = "", display_name: str = "") -> str:
    sid = secrets.token_urlsafe(32)
    _sessions[_hash(sid)] = {
        "email":        email,
        "display_name": display_name or email,
        "role":         role,
        "access_token": access_token,
        "created_at":   time.time(),
        "expires_at":   time.time() + SESSION_TTL,
    }
    return sid


def get_session(sid: str) -> dict | None:
    if not sid:
        return None
    key  = _hash(sid)
    data = _sessions.get(key)
    if not data:
        return None
    if time.time() > data["expires_at"]:
        _sessions.pop(key, None)
        return None
    return data


def delete_session(sid: str) -> None:
    if sid:
        _sessions.pop(_hash(sid), None)


def cleanup_expired() -> None:
    now     = time.time()
    expired = [k for k, v in _sessions.items() if now > v["expires_at"]]
    for k in expired:
        _sessions.pop(k, None)
