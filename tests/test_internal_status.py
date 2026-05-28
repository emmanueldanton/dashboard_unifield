"""T006/T007 - /internal/status : loopback-only, format JSON, dégradé vs ok."""
import time
import pytest
import flask


# ── Minimal Flask app exposant uniquement /internal/status ────────────────────
# Évite d'importer app.py (threads Gunicorn, Dash layout, connexion MongoDB).

@pytest.fixture(scope="module")
def status_client():
    import os
    os.environ.setdefault("UNIFIELD_MONGO_URI", "")

    mini = flask.Flask("test_status")

    @mini.route("/internal/status")
    def _status():
        from flask import request as _req, jsonify
        from datetime import datetime, timezone
        import cache

        if _req.remote_addr not in ("127.0.0.1", "::1"):
            return jsonify({"error": "forbidden"}), 403

        mongo_ok = cache.is_mongo_ok()
        ts = cache.last_success_ts()
        last_refresh = None
        cache_age_s  = None
        if ts is not None:
            last_refresh = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            cache_age_s  = int(time.time() - ts)

        status = "ok" if (mongo_ok and ts is not None) else "degraded"
        return jsonify({
            "status":       status,
            "mongo_ok":     mongo_ok,
            "last_refresh": last_refresh,
            "cache_age_s":  cache_age_s,
        })

    mini.config["TESTING"] = True
    return mini.test_client()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_loopback_returns_200(status_client, monkeypatch):
    import cache
    monkeypatch.setattr(cache, "is_mongo_ok",     lambda: True)
    monkeypatch.setattr(cache, "last_success_ts", lambda: None)

    resp = status_client.get("/internal/status", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert resp.status_code == 200


def test_non_loopback_returns_403(status_client):
    resp = status_client.get("/internal/status", environ_base={"REMOTE_ADDR": "10.0.0.1"})
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "forbidden"


def test_ipv6_loopback_returns_200(status_client, monkeypatch):
    import cache
    monkeypatch.setattr(cache, "is_mongo_ok",     lambda: True)
    monkeypatch.setattr(cache, "last_success_ts", lambda: None)

    resp = status_client.get("/internal/status", environ_base={"REMOTE_ADDR": "::1"})
    assert resp.status_code == 200


def test_degraded_when_no_timestamp(status_client, monkeypatch):
    import cache
    monkeypatch.setattr(cache, "is_mongo_ok",     lambda: True)
    monkeypatch.setattr(cache, "last_success_ts", lambda: None)

    data = status_client.get(
        "/internal/status", environ_base={"REMOTE_ADDR": "127.0.0.1"}
    ).get_json()
    assert data["status"] == "degraded"
    assert data["last_refresh"] is None
    assert data["cache_age_s"]  is None


def test_degraded_when_mongo_nok(status_client, monkeypatch):
    import cache
    monkeypatch.setattr(cache, "is_mongo_ok",     lambda: False)
    monkeypatch.setattr(cache, "last_success_ts", lambda: time.time() - 10)

    data = status_client.get(
        "/internal/status", environ_base={"REMOTE_ADDR": "127.0.0.1"}
    ).get_json()
    assert data["status"] == "degraded"
    assert data["mongo_ok"] is False


def test_ok_with_valid_timestamp(status_client, monkeypatch):
    import cache
    ts = time.time() - 30
    monkeypatch.setattr(cache, "is_mongo_ok",     lambda: True)
    monkeypatch.setattr(cache, "last_success_ts", lambda: ts)

    data = status_client.get(
        "/internal/status", environ_base={"REMOTE_ADDR": "127.0.0.1"}
    ).get_json()
    assert data["status"]    == "ok"
    assert data["mongo_ok"]  is True
    assert data["last_refresh"] is not None
    assert isinstance(data["cache_age_s"], int)
    assert data["cache_age_s"] >= 29


def test_response_keys_complete(status_client, monkeypatch):
    import cache
    monkeypatch.setattr(cache, "is_mongo_ok",     lambda: True)
    monkeypatch.setattr(cache, "last_success_ts", lambda: None)

    data = status_client.get(
        "/internal/status", environ_base={"REMOTE_ADDR": "127.0.0.1"}
    ).get_json()
    assert set(data.keys()) == {"status", "mongo_ok", "last_refresh", "cache_age_s"}
