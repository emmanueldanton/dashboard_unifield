from __future__ import annotations
import logging
import threading
import time

from api.mongo_loader import load_all_data as _load_all_data

log = logging.getLogger(__name__)

_CACHE_KEY = "unifield_singleton"

_shared_cache: dict = {}
_cache_lock   = threading.RLock()

_mongo_ok      = True
_last_success  = None


def _state(_email=None, _key=None):  # noqa: ARG001
    with _cache_lock:
        return dict(_shared_cache.get(_CACHE_KEY, {}))


def get_cached_data(_email=None, _key=None):  # noqa: ARG001
    return _state().get("data")


def get_cache_version(_email=None, _key=None):  # noqa: ARG001
    return int(_state().get("cache_version", 0))


def cache_age(_email=None, _key=None):  # noqa: ARG001
    t = _state().get("loaded_at")
    return (time.time() - t) if t else None


def is_mongo_ok() -> bool:
    return _mongo_ok


def last_success_ts() -> float | None:
    return _last_success


def register_creds(_email=None, _key=None):  # noqa: ARG001
    with _cache_lock:
        if _CACHE_KEY not in _shared_cache:
            _shared_cache[_CACHE_KEY] = {
                "data": None, "loading": False, "error": None,
                "loaded_at": None, "cache_version": 0,
            }


def force_refresh(_email=None, _key=None):  # noqa: ARG001
    register_creds()
    if not _state().get("loading"):
        threading.Thread(target=_do_refresh, daemon=True).start()


def invalidate(_email=None, _key=None):  # noqa: ARG001
    with _cache_lock:
        _shared_cache.pop(_CACHE_KEY, None)


def _load_alert_history() -> list[dict]:
    """Charge les 50 dernières entrées alert_history (lecture seule, snapshot).

    Retourne une liste de dicts prêts à afficher dans DataTable.
    Toute erreur est silencieusement loggée — ne doit jamais bloquer le refresh.
    """
    try:
        from api.mongo_client import get_db
        from datetime import timezone as _tz
        db  = get_db()
        raw = list(db["alert_history"].find(
            {}, {"_id": 0, "ts": 1, "subject": 1, "issues_count": 1,
                 "recipients": 1, "mailgun_status": 1}
        ).sort("ts", -1).limit(50))
        rows = []
        for r in raw:
            ts     = r.get("ts")
            ts_str = ts.strftime("%d/%m/%Y %H:%M") if hasattr(ts, "strftime") else str(ts)
            rows.append({
                "Date/Heure":     ts_str,
                "Sujet":          r.get("subject", ""),
                "Nb problèmes":   r.get("issues_count", 0),
                "Destinataires":  ", ".join(r.get("recipients", [])),
                "Statut Mailgun": r.get("mailgun_status", ""),
            })
        return rows
    except Exception as exc:
        log.warning('{"event": "alert_history_load_failed", "detail": "%s"}', str(exc)[:120])
        return []


def _save_snapshot(data: dict) -> None:
    """Write an aggregate snapshot document to MongoDB (one per project + one global).

    Errors are silently logged — a snapshot failure must never crash the refresh.
    """
    try:
        from api.mongo_client import get_db
        from datetime import datetime, timezone
        db  = get_db()
        now = datetime.now(timezone.utc)
        col = db["snapshots"]

        project_data = data.get("project_data", {})
        for pid, pinfo in project_data.items():
            trackers = pinfo.get("trackers", [])
            if not trackers:
                continue
            connected    = sum(1 for t in trackers if t.get("_is_connected"))
            disconnected = len(trackers) - connected
            battery_low  = sum(1 for t in trackers if t.get("_battery_status") == "faible")
            col.insert_one({
                "project_id":   pid,
                "ts":           now,
                "connected":    connected,
                "disconnected": disconnected,
                "battery_low":  battery_low,
            })
    except Exception as exc:
        log.warning('{"event": "snapshot_failed", "detail": "%s"}', str(exc)[:120])


def _do_refresh(_email=None, _key=None):  # noqa: ARG001
    global _mongo_ok, _last_success
    with _cache_lock:
        if _shared_cache.get(_CACHE_KEY, {}).get("loading"):
            return
        _shared_cache.setdefault(_CACHE_KEY, {
            "data": None, "loading": False, "error": None,
            "loaded_at": None, "cache_version": 0,
        })
        _shared_cache[_CACHE_KEY]["loading"] = True
        _shared_cache[_CACHE_KEY]["error"]   = None
    try:
        data = _load_all_data()
        data["alert_history"] = _load_alert_history()

        with _cache_lock:
            _shared_cache[_CACHE_KEY]["data"]          = data
            _shared_cache[_CACHE_KEY]["loaded_at"]     = time.time()
            _shared_cache[_CACHE_KEY]["error"]         = None
            _shared_cache[_CACHE_KEY]["cache_version"] = (
                int(_shared_cache[_CACHE_KEY].get("cache_version", 0)) + 1
            )
        _mongo_ok     = True
        _last_success = time.time()
        _save_snapshot(data)

    except Exception as exc:
        log.error('{"event": "mongo_refresh_failed", "detail": "%s"}', str(exc)[:200])
        _mongo_ok = False
        with _cache_lock:
            _shared_cache[_CACHE_KEY]["error"] = str(exc)
    finally:
        with _cache_lock:
            _shared_cache[_CACHE_KEY]["loading"] = False
