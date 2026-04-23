from __future__ import annotations
import threading
from datetime import datetime
import requests

_load_log: list[str] = []
_load_log_lock = threading.Lock()


def user_headers(email, key):
    return {"Content-type": "application/json",
            "x-user-email": email, "x-user-access-key": key}


def project_headers(pid, key):
    return {"Content-type": "application/json",
            "x-project-id": pid, "x-access-key": key}


def safe_get(url, headers, timeout=(2, 8), **kwargs):
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if not r.ok:
            err = f"HTTP {r.status_code}"
        elif not r.text.strip():
            return None
        else:
            try:
                return r.json()
            except Exception:
                err = "JSON invalide"
    except requests.exceptions.ConnectTimeout:
        err = "ConnectTimeout"
    except requests.exceptions.ReadTimeout:
        err = "ReadTimeout"
    except requests.exceptions.ConnectionError as e:
        err = f"ConnectionError {str(e)[:60]}"
    except Exception as e:
        err = str(e)[:80]

    with _load_log_lock:
        _load_log.append(f"{datetime.now().strftime('%H:%M:%S')} X {url.rsplit('/',1)[-1]} — {err}")
        if len(_load_log) > 100:
            _load_log.pop(0)
    return None