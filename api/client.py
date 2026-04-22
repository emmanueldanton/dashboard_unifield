from __future__ import annotations
import threading
import time
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


def safe_get(url, headers, retries=2, timeout=(2, 8)):
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if not r.ok:
                last_err = f"HTTP {r.status_code}"
            elif not r.text.strip():
                return None
            else:
                try:
                    return r.json()
                except Exception:
                    last_err = "JSON invalide"
        except requests.exceptions.ConnectTimeout:
            last_err = "ConnectTimeout"
        except requests.exceptions.ReadTimeout:
            last_err = "ReadTimeout"
        except requests.exceptions.ConnectionError as e:
            last_err = f"ConnectionError {str(e)[:60]}"
        except Exception as e:
            last_err = str(e)[:80]
        if attempt < retries:
            time.sleep(0.4 * (attempt + 1))
    with _load_log_lock:
        _load_log.append(f"{datetime.now().strftime('%H:%M:%S')} X {url.rsplit('/',1)[-1]} — {last_err}")
        if len(_load_log) > 100:
            _load_log.pop(0)
    return None
