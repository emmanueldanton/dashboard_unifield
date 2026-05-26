import time
import pytest
from auth.session_store import (
    create_session, get_session, delete_session, cleanup_expired, _sessions,
)


def setup_function():
    _sessions.clear()


def test_create_session_returns_string():
    sid = create_session("user@test.com", "app:unifield:read")
    assert isinstance(sid, str)
    assert len(sid) > 0


def test_get_session_returns_data():
    sid  = create_session("user@test.com", "app:unifield:read")
    data = get_session(sid)
    assert data is not None
    assert data["email"] == "user@test.com"
    assert data["role"]  == "app:unifield:read"


def test_get_session_unknown_returns_none():
    assert get_session("unknown-sid-xyz") is None


def test_delete_session():
    sid = create_session("user@test.com", "app:unifield:read")
    delete_session(sid)
    assert get_session(sid) is None


def test_cleanup_expired():
    sid = create_session("user@test.com", "app:unifield:read")
    from auth.session_store import _hash
    _sessions[_hash(sid)]["expires_at"] = time.time() - 1
    cleanup_expired()
    assert get_session(sid) is None


def test_get_session_expired_returns_none():
    sid = create_session("user@test.com", "app:unifield:read")
    from auth.session_store import _hash
    _sessions[_hash(sid)]["expires_at"] = time.time() - 1
    assert get_session(sid) is None
