from __future__ import annotations
import hashlib
import threading
import time

from api.loader import load_all_data

_shared_cache = {}
_cache_lock   = threading.RLock()


def _cache_key(email, key):
    return hashlib.md5(f"{email}:{key}".encode()).hexdigest()


def _state(email, key):
    with _cache_lock:
        return dict(_shared_cache.get(_cache_key(email, key), {}))


def get_cached_data(email, key):
    return _state(email, key).get("data")


def get_cache_version(email, key):
    return int(_state(email, key).get("cache_version", 0))


def cache_age(email, key):
    t = _state(email, key).get("loaded_at")
    return (time.time() - t) if t else None


def register_creds(email, key):
    k = _cache_key(email, key)
    with _cache_lock:
        if k not in _shared_cache:
            _shared_cache[k] = {"data":None,"loading":False,"error":None,
                                "loaded_at":None,"cache_version":0}


def force_refresh(email, key):
    register_creds(email, key)
    if not _state(email, key).get("loading"):
        threading.Thread(target=_do_refresh, args=(email, key), daemon=True).start()


def invalidate(email, key):
    with _cache_lock:
        _shared_cache.pop(_cache_key(email, key), None)


def _do_refresh(email, key):
    k = _cache_key(email, key)
    with _cache_lock:
        if _shared_cache.get(k, {}).get("loading"): return
        _shared_cache[k]["loading"] = True
        _shared_cache[k]["error"]   = None
    try:
        data = load_all_data(email, key)
        with _cache_lock:
            _shared_cache[k]["data"]          = data
            _shared_cache[k]["loaded_at"]     = time.time()
            _shared_cache[k]["error"]         = None
            _shared_cache[k]["cache_version"] = int(_shared_cache[k].get("cache_version",0)) + 1
    except Exception as e:
        with _cache_lock:
            _shared_cache[k]["error"] = str(e)
    finally:
        with _cache_lock:
            _shared_cache[k]["loading"] = False
