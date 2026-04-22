"""
DASHBOARD UNIFIELD - CAD.42 (Dash)
Lancement : python dashboard.py -> http://127.0.0.1:8060
"""

from __future__ import annotations
import hashlib, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import dash
from dash import dcc, html, dash_table, Input, Output, State, ctx
import requests

try:
    from timezonefinder import TimezoneFinder
    _tf = TimezoneFinder()
except Exception:
    _tf = None


# ════════════════════════════════════════════════════════════
# SECTION 1 — CONFIGURATION
# ════════════════════════════════════════════════════════════

API_BASE                  = "https://api.cad42.com"
BATTERY_WARNING_THRESHOLD = 3.5
ENDING_SOON_DAYS          = 30
PAST_DAYS                 = 10
MAX_WORKERS               = 10

PARASITE_KEYWORDS = {"atelier", "stock", "test", "dev"}

def filter_data(data):
    """Exclut les projets parasites et les capteurs sans lastTrack."""
    bad = {p["id"] for p in data["projects"]
           if any(kw in p.get("name","").lower() for kw in PARASITE_KEYWORDS)}

    def has_data(t):
        lt = t.get("lastTrack") or {}
        return bool(lt.get("message"))

    filtered_pd = {
        pid: {**pinfo, "trackers": [t for t in pinfo.get("trackers", []) if has_data(t)]}
        for pid, pinfo in data.get("project_data", {}).items()
        if pid not in bad
    }

    return {
        **data,
        "projects":     [p for p in data["projects"] if p["id"] not in bad],
        "all_trackers": [t for t in data["all_trackers"]
                         if t.get("_project_id") not in bad and has_data(t)],
        "project_data": filtered_pd,
    }

C = {
    "accent":     "#5D9050", "accent_bg":  "#F0F5EF",
    "bg":         "#F8FAFB", "surface":    "#FFFFFF", "border":    "#E2E8F0",
    "text":       "#1E293B", "text_muted": "#64748B", "text_light":"#94A3B8",
    "red":        "#DC2626", "red_bg":     "#FEF2F2", "red_border":"#FECACA",
    "orange":     "#D97706", "orange_bg":  "#FFFBEB", "orange_bdr":"#FDE68A",
    "green":      "#16A34A", "green_bg":   "#F0FDF4", "green_bdr": "#BBF7D0",
}


# ════════════════════════════════════════════════════════════
# SECTION 2 — HELPERS API
# ════════════════════════════════════════════════════════════

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

PARIS_TZ = ZoneInfo("Europe/Paris")

def fmt_paris(date_str):
    """Convertit une date ISO UTC en heure Europe/Paris, format dd/mm/yyyy HH:MM."""
    if not date_str:
        return "Jamais"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.astimezone(PARIS_TZ).strftime("%d/%m/%Y %H:%M")
    except:
        return "?"
    
# ════════════════════════════════════════════════════════════
# SECTION 3 — HELPERS MÉTIER
# ════════════════════════════════════════════════════════════

def _msg(t):
    lt = t.get("lastTrack") or {}
    msg = lt.get("message") or {}
    return msg if isinstance(msg, dict) else {}

def is_connected(t, offline_delay=60):
    last = t.get("lastUpdate")
    if not last: return False
    try:
        dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() < offline_delay
    except: return False

def battery_volt(t):
    v = _msg(t).get("battery_volt") or t.get("_battery_volt") or -1
    try: return float(v)
    except: return -1.0

def battery_status(t, threshold=BATTERY_WARNING_THRESHOLD):
    v = battery_volt(t)
    if v < 0: return "inconnu"
    if v < threshold: return "faible"
    return "ok"

def weight_status(t):
    w = _msg(t).get("weight", -1)
    return "inconnu" if (w is None or w < 0) else "ok"

def last_seen_seconds(t):
    last = t.get("lastUpdate")
    if not last: return -1
    try:
        dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        return int((datetime.now(timezone.utc) - dt).total_seconds())
    except: return -1

def age_full(date_str):
    if not date_str: return "—"
    try:
        dt   = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        diff = int((datetime.now(timezone.utc) - dt).total_seconds())
        if diff < 0: return "—"
        j, h = diff // 86400, (diff % 86400) // 3600
        m, s = (diff % 3600) // 60, diff % 60
        parts = []
        if j: parts.append(f"{j}j")
        if h: parts.append(f"{h}h")
        if m: parts.append(f"{m}min")
        parts.append(f"{s}s")
        return " ".join(parts)
    except: return "?"

def health_score(trackers, offline_delay=60, threshold=BATTERY_WARNING_THRESHOLD):
    if not trackers: return 0
    total = sum(
        (50 if is_connected(t, offline_delay) else 0)
        + (30 if battery_status(t, threshold) == "ok" else 0)
        + (20 if weight_status(t) == "ok" else 0)
        for t in trackers
    )
    return round(total / len(trackers))

def score_class(score):
    if score >= 80: return "excellent"
    if score >= 55: return "good"
    if score >= 30: return "medium"
    if score >  0: return "bad"
    return "empty"

def score_label(score):
    return {"excellent":"Excellent","good":"Bon","medium":"Moyen",
            "bad":"Critique","empty":"Aucune donnée"}[score_class(score)]

def fmt_date(d):
    try: return datetime.fromisoformat(d.replace("Z","+00:00")).strftime("%d/%m/%Y") if d else "—"
    except: return "—"

def fmt_tz(tz_raw):
    try:
        offset = int(datetime.now(ZoneInfo(tz_raw)).utcoffset().total_seconds() / 3600)
        return f"UTC{offset:+d} ({tz_raw})" if tz_raw != "UTC" else "UTC"
    except: return tz_raw

def parse_schedule(schedule):
    """
    Normalise le schedule projet en format interne unifié.
    Supporte V1 (liste) et V2 (dict avec enable/times).
    Retourne None si pas de schedule réel (H24 ou vide).
    """
    if not schedule:
        return None

    days_order = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    result = {}
    has_real_schedule = False

    for day in days_order:
        cfg = schedule.get(day, {})

        # V2 : {"enable": True, "times": [["07:00", "17:00"]]}
        if isinstance(cfg, dict):
            enable = cfg.get("enable", False)
            times  = cfg.get("times", [])
            is_h24 = any(
                slot[0] == "00:00" and slot[1] in ("23:59", "24:00")
                for slot in times
                if isinstance(slot, (list, tuple)) and len(slot) >= 2
            )
            if enable and times and not is_h24:
                has_real_schedule = True
            result[day] = {"enable": enable, "times": times, "h24": is_h24}

        # V1 : ["07:00", "17:00", "true"]
        elif isinstance(cfg, list) and len(cfg) >= 2:
            enable = str(cfg[2]).lower() == "true" if len(cfg) > 2 else True
            times  = [[cfg[0], cfg[1]]] if cfg[0] and cfg[1] else []
            is_h24 = len(cfg) >= 2 and cfg[0] == "00:00" and cfg[1] in ("23:59", "24:00")
            if enable and times and not is_h24:
                has_real_schedule = True
            result[day] = {"enable": enable, "times": times, "h24": is_h24}

        # Vide ou inconnu
        else:
            result[day] = {"enable": False, "times": [], "h24": False}

    return result if has_real_schedule else None


def is_time_in_schedule(dt_paris, parsed_schedule):
    """
    Vérifie si un datetime Paris est dans les plages du schedule parsé.
    Retourne True si dans le schedule, False sinon.
    Si parsed_schedule est None → H24 → toujours True.
    """
    if parsed_schedule is None:
        return True

    days_order = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    day_key    = days_order[dt_paris.weekday()]
    day_cfg    = parsed_schedule.get(day_key, {})

    if day_cfg.get("h24"):
        return True
    if not day_cfg.get("enable"):
        return False

    current = dt_paris.strftime("%H:%M")
    for slot in day_cfg.get("times", []):
        if isinstance(slot, (list, tuple)) and len(slot) >= 2:
            if slot[0] <= current <= slot[1]:
                return True
    return False

def check_schedule_anomalies(trackers, schedule, now):
    """
    Retourne deux listes :
    - hors_schedule : trackers actifs EN DEHORS des heures prévues
    - manquants     : trackers INACTIFS alors qu'ils devraient être actifs
    Ne génère des anomalies que si le projet a un schedule réel configuré.
    """
    parsed = parse_schedule(schedule)
    if parsed is None:
        return [], []  # H24 ou pas de schedule → aucune anomalie schedule

    paris_now       = now.astimezone(PARIS_TZ)
    in_schedule_now = is_time_in_schedule(paris_now, parsed)

    hors_schedule = []
    manquants     = []

    for t in trackers:
        connected = t.get("_is_connected", False)
        last_sec  = t.get("_last_seen_seconds", -1)

        if in_schedule_now:
            if not connected:
                manquants.append(t)
        else:
            # Hors heures → anomalie si actif récemment (< 1h)
            if connected or (0 <= last_sec < 3600):
                hors_schedule.append(t)

    return hors_schedule, manquants

def compute_project_flags(p, trkrs, now, bt):
    """
    Calcule les 3 flags pour un projet et retourne leurs détails.
    """
    schedule = p.get("schedule", {})
    parsed   = parse_schedule(schedule)
    paris_now = now.astimezone(PARIS_TZ)

    # ── Flag 1 : Capteur KO (déconnecté ou batterie faible)
    ko_details = []
    for t in trkrs:
        reasons = []
        if not t.get("_is_connected", False):
            reasons.append(f"déco. depuis {age_full(t.get('lastUpdate',''))}")
        if battery_status(t, bt) == "faible":
            v = t.get("_battery_volt", -1)
            reasons.append(f"batt. {v:.2f}V")
        if reasons:
            ko_details.append(f"{t.get('name','?')} — {', '.join(reasons)}")

    # ── Flag 2 & 3 : Schedule (uniquement si schedule réel configuré)
    hors_details    = []
    inactif_details = []

    if parsed is not None:
        in_schedule_now = is_time_in_schedule(paris_now, parsed)

        # Trouver la plage courante pour le message
        days_order = ["mon","tue","wed","thu","fri","sat","sun"]
        day_key    = days_order[paris_now.weekday()]
        day_cfg    = parsed.get(day_key, {})
        times     = day_cfg.get("times", [])
        plage_str = (" / ".join(f"{s[0]}-{s[1]}" for s in times if len(s) >= 2)
                     if times else "?")

        for t in trkrs:
            connected = t.get("_is_connected", False)
            last_sec  = t.get("_last_seen_seconds", -1)
            name      = t.get("name", "?")

            if in_schedule_now:
                # Dans les heures → anomalie si inactif
                if not connected:
                    duree = age_full(t.get("lastUpdate", ""))
                    inactif_details.append(
                        f"{name} — absent depuis {duree} (plage {plage_str})"
                    )
            else:
                # Hors heures → anomalie si actif récemment (< 1h)
                if connected or (0 <= last_sec < 3600):
                    duree = age_full(t.get("lastUpdate", ""))
                    hors_details.append(
                        f"{name} — actif depuis {duree} hors plage {plage_str}"
                    )

    return {
        "capteur_ko":       len(ko_details) > 0,
        "hors_schedule":    len(hors_details) > 0,
        "inactif_schedule": len(inactif_details) > 0,
        "details": {
            "ko_count":       len(ko_details),
            "ko_list":        ko_details,
            "hors_count":     len(hors_details),
            "hors_list":      hors_details,
            "inactif_count":  len(inactif_details),
            "inactif_list":   inactif_details,
        }
    }


def flag_badge(label, count, anchor, color, text_color="#fff"):
    """
    Badge cliquable qui switche vers Urgences et scrolle vers l'ancre.
    """
    if count == 0:
        return html.Span()
    return html.Span(
        f"{label} {count}",
        id={"type": "flag-badge", "anchor": anchor},
        n_clicks=0,
        style={
            "background":    color,
            "color":         text_color,
            "fontSize":      "0.68rem",
            "fontWeight":    "700",
            "padding":       "3px 9px",
            "borderRadius":  "20px",
            "cursor":        "pointer",
            "marginRight":   "4px",
            "display":       "inline-block",
            "letterSpacing": "0.02em",
            "userSelect":    "none",
        }
    )

# ════════════════════════════════════════════════════════════
# SECTION 4 — CACHE SERVEUR (thread-safe, refresh manuel)
# ════════════════════════════════════════════════════════════

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


# ════════════════════════════════════════════════════════════
# SECTION 5 — CHARGEMENT DES DONNEES (parallele par projet)
# ════════════════════════════════════════════════════════════

def _load_one_project(p, u_hdrs, now, lock, qc):
    pid  = p.get("id","")
    name = p.get("name","?")

    detail   = safe_get(f"{API_BASE}/projects/{pid}", u_hdrs, retries=2)
    proj_key = (detail or {}).get("accessKey")
    if not detail or not proj_key:
        with lock:
            qc["projects_no_key"] += 1
            qc["issues"].append(f"[{name}] accessKey inaccessible.")
        return pid, None

    p.update({
        "accessKey":    proj_key,
        "offlineDelay": detail.get("offlineDelay", p.get("offlineDelay", 60)),
        "endDate":      detail.get("endDate",      p.get("endDate")),
        "startDate":    detail.get("startDate",    p.get("startDate")),
        "archived":     detail.get("archived",     p.get("archived", False)),
        "type":         detail.get("type",         p.get("type", "?")),
        "city":         detail.get("city",         p.get("city", "")),
        "schedule":     detail.get("schedule",     {}),
        "database":     detail.get("database",     ""),
        "description":  detail.get("description",  ""),
    })

    if p.get("archived"):
        with lock: qc["projects_loaded"] += 1
        return pid, {"units":[],"trackers":[],"events":[],"timezone":"UTC","qc_local":{"archived":True}}

    p_hdrs        = project_headers(pid, proj_key)
    offline_delay = p.get("offlineDelay", 60)

    units_raw = safe_get(f"{API_BASE}/units", p_hdrs, retries=2, timeout=(2,10))
    units     = units_raw if isinstance(units_raw, list) else []
    with lock: qc["projects_loaded"] += 1

    if not units:
        with lock: qc["projects_empty"] += 1
        return pid, {"units":[],"trackers":[],"events":[],"timezone":"UTC","qc_local":{"empty":True}}

    with lock: qc["projects_with_data"] += 1

    proj_events = []
    ev_raw = safe_get(f"{API_BASE}/events", p_hdrs, retries=1)
    if ev_raw and isinstance(ev_raw, list):
        proj_events = [{**e,"_project_name":name,"_project_id":pid} for e in ev_raw[:50]]
        with lock: qc["has_events"] = True

    tr_raw       = safe_get(f"{API_BASE}/trackers", p_hdrs, retries=2, timeout=(2,10))
    trackers_map = {}
    if isinstance(tr_raw, list):
        for tr in tr_raw:
            if isinstance(tr, dict):
                tid = tr.get("id", tr.get("uuid",""))
                if tid: trackers_map[tid] = tr

    local_units, local_trackers = [], []
    local_qc = {"units":len(units),"units_no_tracker":0,"trackers":0,
                "trackers_no_lastupdate":0,"trackers_no_lasttrack":0,
                "trackers_duplicate":0,"trackers_stale":0}
    seen_ids = set()

    for u in units:
        uid       = u.get("id","")
        unit_name = u.get("name","?")
        tr_list   = u.get("trackers",[])
        local_units.append({**u,"_project_id":pid,"_project_name":name,"_offline_delay":offline_delay})

        if not tr_list:
            local_qc["units_no_tracker"] += 1
            continue

        for t in tr_list:
            if isinstance(t, str): t = trackers_map.get(t)
            if not t: continue

            tid = t.get("id", t.get("uuid",""))
            if tid and tid in seen_ids:
                local_qc["trackers_duplicate"] += 1
            elif tid:
                seen_ids.add(tid)

            if not t.get("lastUpdate"):
                local_qc["trackers_no_lastupdate"] += 1
            if not t.get("lastTrack"):
                local_qc["trackers_no_lasttrack"] += 1

            lu = t.get("lastUpdate")
            if lu:
                try:
                    if (now - datetime.fromisoformat(lu.replace("Z","+00:00"))).total_seconds() > 86400:
                        local_qc["trackers_stale"] += 1
                except: pass

            local_trackers.append({
                **t,
                "_unit_id":uid,"_unit_name":unit_name,
                "_project_id":pid,"_project_name":name,
                "_offline_delay":offline_delay,
                "_is_connected":is_connected(t, offline_delay),
                "_battery_status":battery_status(t),
                "_battery_volt":battery_volt(t),
                "_weight_status":weight_status(t),
                "_last_seen_seconds":last_seen_seconds(t),
            })
            local_qc["trackers"] += 1

    proj_tz = "UTC"
    if _tf:
        for t in local_trackers:
            lt = t.get("lastTrack") or {}
            lat, lon = lt.get("lat"), lt.get("lon")
            if lat and lon:
                tz = _tf.timezone_at(lat=lat, lng=lon)
                if tz:
                    proj_tz = tz
                    break

    with lock:
        qc["units_total"]            += len(local_units)
        qc["units_no_tracker"]       += local_qc["units_no_tracker"]
        qc["trackers_total"]         += local_qc["trackers"]
        qc["trackers_no_lastupdate"] += local_qc["trackers_no_lastupdate"]
        qc["trackers_no_lasttrack"]  += local_qc["trackers_no_lasttrack"]
        qc["trackers_duplicate_id"]  += local_qc["trackers_duplicate"]
        qc["trackers_stale_24h"]     += local_qc["trackers_stale"]
        qc["tracker_ids_seen"].update(seen_ids)

    return pid, {"units":local_units,"trackers":local_trackers,
                 "events":proj_events,"timezone":proj_tz,"qc_local":local_qc}


def load_all_data(email, key):
    with _load_log_lock:
        _load_log.clear()
    u_hdrs = user_headers(email, key)
    raw    = safe_get(f"{API_BASE}/projects", u_hdrs, retries=3, timeout=(3,10))
    if not raw:
        return {"projects":[],"project_data":{},"all_units":[],
                "all_trackers":[],"all_events":[],"qc":{},"loaded_at":None}

    all_proj     = raw if isinstance(raw, list) else [raw]
    project_data = {}
    all_units, all_trackers, all_events = [], [], []
    now  = datetime.now(timezone.utc)
    lock = threading.Lock()

    qc = {
        "total_projects":0,"projects_loaded":0,"projects_no_key":0,
        "projects_empty":0,"projects_with_data":0,"units_total":0,
        "units_no_tracker":0,"trackers_total":0,"trackers_no_lastupdate":0,
        "trackers_no_lasttrack":0,"trackers_duplicate_id":0,"trackers_stale_24h":0,
        "has_events":False,"tracker_ids_seen":set(),"issues":[],
        "total_projects": len(all_proj),
    }

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(_load_one_project, p, u_hdrs, now, lock, qc): p for p in all_proj}
        for future in as_completed(futures):
            try:
                pid, result = future.result(timeout=30)
            except FuturesTimeout:
                continue
            except Exception:
                continue
            if result is None: continue
            p = next((x for x in all_proj if x.get("id") == pid), None)
            if p is None: continue
            project_data[pid] = result
            all_units.extend(result["units"])
            all_trackers.extend(result["trackers"])
            all_events.extend(result["events"])
        
# ════════════════════════════════════════════════════════════
    qc["tracker_ids_unique"] = len(qc["tracker_ids_seen"])
    del qc["tracker_ids_seen"]

    return {"projects":all_proj,"project_data":project_data,"all_units":all_units,
            "all_trackers":all_trackers,"all_events":all_events,"qc":qc,
            "loaded_at":datetime.now(timezone.utc).isoformat()}


# ════════════════════════════════════════════════════════════
# SECTION 6 — SEGMENTATION PROJETS
# ════════════════════════════════════════════════════════════

def compute_segments(projects, project_data, now, activity_sec, ending_days, past_days):

    def has_signal_today(p):
        trkrs = project_data.get(p.get("id",""), {}).get("trackers", [])
        return any(0 <= t.get("_last_seen_seconds", -1) < activity_sec for t in trkrs)

    archived, past, total, active, ending, anomalies = [], [], [], [], [], []

    for p in projects:
        end      = p.get("endDate")
        is_arch  = p.get("archived", False)
        end_diff = None  # jours depuis endDate (positif = passé)

        if end:
            try:
                end_diff = (now - datetime.fromisoformat(end.replace("Z","+00:00"))).days
            except:
                pass

        # ── Archivé explicitement
        if is_arch:
            archived.append(p)
            continue

        # ── Signal aujourd'hui ?
        signal = has_signal_today(p)

        # ── endDate dépassée
        if end_diff is not None and end_diff > 0:
            past.append(p)
            if signal:
                # Capteur actif sur projet terminé → anomalie + compté actif
                active.append(p)
                anomalies.append(p)
            continue

        # ── Projet en cours
        total.append(p)
        if signal:
            active.append(p)

        # ── Fin imminente
        if end:
            try:
                diff_future = (datetime.fromisoformat(end.replace("Z","+00:00")) - now).days
                if 0 < diff_future < int(ending_days):
                    ending.append(p)
            except:
                pass

    return {
        "archived":  archived,
        "past":      past,
        "total":     total,
        "active":    active,
        "ending":    ending,
        "anomalies": anomalies,  # ← projets terminés mais encore actifs
    }

# ════════════════════════════════════════════════════════════
# SECTION 7 — HELPERS AFFICHAGE
# ════════════════════════════════════════════════════════════

def banner(text, tone="info"):
    icons = {"ok":"v","warn":"!","danger":"x","info":"i"}
    return html.Div([
        html.Span(icons.get(tone,""), style={"fontWeight":"700","fontSize":"1rem"}),
        html.Span(f" {text}")
    ], className=f"banner {tone}")

def section_label(text):
    return html.Div(text, className="section-label")

def kpi_card(label, value, sub="", color=None, tab_target=None):
    style = {"cursor":"pointer"} if tab_target else {}
    return html.Div([
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className="kpi-value", style={"color": color or C["text"]}),
        html.Div(sub, className="kpi-sub"),
    ], className="kpi-card", style=style)

def make_table(rows, page_size=15):
    if not rows:
        return html.Div("Aucune donnee.", style={"color":C["text_muted"],"padding":"16px 0","fontSize":"0.85rem"})
    cols = [{"name": c, "id": c} for c in rows[0].keys() if not c.startswith("_")]
    return html.Div(
        dash_table.DataTable(
            data=rows, columns=cols,
            page_size=page_size, sort_action="native", filter_action="native",
            row_selectable="single", selected_rows=[],
            style_table={"overflowX":"auto", "minWidth":"800px"},
            style_header={
                "backgroundColor": "var(--bg)",
                "fontWeight":       "700",
                "border":           "1px solid var(--border)",
                "fontSize":         "11px",
                "color":            "var(--text-muted)",
                "textTransform":    "uppercase",
                "letterSpacing":    "0.06em",
                "padding":          "10px 12px",
            },
            style_cell={
                "textAlign":       "left",
                "padding":         "9px 12px",
                "border":          "1px solid var(--border)",
                "fontFamily":      "DM Sans, sans-serif",
                "fontSize":        "13px",
                "backgroundColor": "var(--surface)",
                "color":           "var(--text)",
                "minWidth":        "120px",
                "maxWidth":        "200px",
                "overflow":        "hidden",
                "textOverflow":    "ellipsis",
            },
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "var(--bg)"},
                {"if": {"state": "selected"}, "backgroundColor": "var(--accent-bg)",
                "border": "1px solid var(--accent)"},
            ],
        ),
        style={"border":f"1px solid {C['border']}","borderRadius":"10px","overflowX":"auto","overflowY":"visible"}
    )

def build_tracker_rows(trackers):
    rows = []
    for t in trackers:
        msg     = _msg(t)
        volt    = t.get("_battery_volt",-1)
        temp    = msg.get("temperature",-1)
        weight  = msg.get("weight",-1)
        shackle = msg.get("shackle_battery",-1)
        lt      = t.get("lastTrack") or {}
        lat, lon = lt.get("lat",0), lt.get("lon",0)
        conn    = t.get("_is_connected",False)
        rows.append({
            "_id":              t.get("id") or t.get("uuid",""),
            "Capteur":          t.get("name","?"),
            "Unité":            t.get("_unit_name","?"),
            "Projet":           t.get("_project_name","?"),
            "Statut":           "🟢 Connecté" if conn else "🔴 Déconnecté",
            "Dernière activité":fmt_paris(t.get("lastUpdate","")),
            "Âge":              age_full(t.get("lastUpdate","")),
            "Batt. (V)":        f"{volt:.2f}" if isinstance(volt,(int,float)) and volt > 0 else "—",
            "Peson batt":       f"{shackle:.2f}" if isinstance(shackle,(int,float)) and shackle > 0 else "—",
            "Temp.":            f"{temp:.1f}°C" if isinstance(temp,(int,float)) and temp > 0 else "—",
            "Poids (kg)":       f"{int(weight)}" if isinstance(weight,(int,float)) and weight >= 0 else "—",
            "GPS":              f"{round(lat,5)}, {round(lon,5)}" if lat and lon else "—",
        })
    return rows


# ════════════════════════════════════════════════════════════
# SECTION 8 — RENDUS PAR ONGLET
# ════════════════════════════════════════════════════════════

def make_table_searchable(rows, section_id, page_size=15):
    """Tableau avec barre de recherche globale au-dessus."""
    if not rows:
        return banner("Aucune donnée.", "info")

    search_id = {"type": "urgence-search", "section": section_id}

    return html.Div([
        dcc.Input(
            id=search_id,
            type="text",
            placeholder="⌕ Rechercher...",
            debounce=True,
            className="search-input",
        ),
        html.Div(id={"type": "urgence-table", "section": section_id},
                 children=make_table(rows, page_size)),
        dcc.Store(id={"type": "urgence-rows", "section": section_id},
                  data=rows),
    ])


def collapsible(title, count, content, tone=None):
    """Section pliable/dépliable — fermée par défaut."""
    colors = {"danger": C["red"], "warn": C["orange"], "ok": C["green"]}
    color  = colors.get(tone, C["text_muted"])
    return html.Details([
        html.Summary([
            html.Span("▶", style={
                "fontSize": "0.6rem",
                "marginRight": "8px",
                "color": color,
            }),
            html.Span(title, style={
                "fontSize": "0.68rem",
                "fontWeight": "700",
                "color": color,
                "letterSpacing": "0.1em",
                "textTransform": "uppercase",
            }),
            html.Span(f" — {count}", style={
                "fontSize": "0.68rem",
                "fontWeight": "700",
                "color": color,
                "marginLeft": "2px",
            }),
        ], style={
            "display": "flex",
            "alignItems": "center",
            "cursor": "pointer",
            "padding": "10px 0",
            "borderBottom": f"1px solid {C['border']}",
            "listStyle": "none",
            "userSelect": "none",
        }),
        html.Div(content, style={"marginTop": "12px", "marginBottom": "8px"}),
    ], open=False, style={"marginBottom": "8px"})


def render_urgences(data, bt, activity_min, ending_days, past_days):
    now       = datetime.now(timezone.utc)
    paris_now = now.astimezone(PARIS_TZ)
    ref_h, ref_m = map(int, (activity_min or "00:01").split(":"))
    ref_dt    = paris_now.replace(hour=ref_h, minute=ref_m, second=0, microsecond=0)
    activity_sec = max(1, int((paris_now - ref_dt).total_seconds()))
    segs = compute_segments(data["projects"], data["project_data"], now,
                            activity_sec, ending_days, past_days)
    all_t        = data["all_trackers"]
    disconnected = [t for t in all_t if not t.get("_is_connected", False)]
    battery_low  = [t for t in all_t if battery_status(t, bt) == "faible"]
    battery_unk  = [t for t in all_t if battery_status(t, bt) == "inconnu" and "battery_volt" in _msg(t)]
    weight_unk   = [t for t in all_t if t.get("_weight_status") == "inconnu" and "weight" in _msg(t)]

    ending_rows = []
    for p in segs["ending"]:
        end = p.get("endDate")
        try:
            dt     = datetime.fromisoformat(end.replace("Z","+00:00"))
            diff   = (dt - now).days
            endstr = dt.strftime("%d/%m/%Y")
        except: diff, endstr = "?","?"
        ending_rows.append({
            "Projet":         p.get("name","?"),
            "Date de fin":    endstr,
            "Jours restants": diff,
            "Capteurs":       len(data["project_data"].get(p.get("id"),{}).get("trackers",[]))
        })

    all_hors, all_manquants = [], []
    for _p in segs["total"] + segs["past"]:
        _trkrs = data["project_data"].get(_p.get("id",""), {}).get("trackers", [])
        _hs, _mq = check_schedule_anomalies(
            _trkrs, _p.get("schedule", {}), now
        )
        all_hors.extend(_hs)
        all_manquants.extend(_mq)

     # Projets dont endDate est dépassée mais non archivés
    anomalies = segs.get("anomalies", [])
    anomalie_rows = [{
        "Projet":   p.get("name","?"),
        "Type":     p.get("type","?"),
        "Date fin": fmt_date(p.get("endDate")),
        "Capteurs": len(data["project_data"].get(p.get("id"),{}).get("trackers",[])),
    } for p in anomalies]

    nb_urg = (len(disconnected) + len(battery_low) +
              len(ending_rows) + len(all_hors) + len(all_manquants) + len(anomalies))

    disc_rows   = build_tracker_rows(disconnected)
    batl_rows   = build_tracker_rows(battery_low)
    batunk_rows = build_tracker_rows(battery_unk)
    wunk_rows   = build_tracker_rows(weight_unk)
    hors_rows   = build_tracker_rows(all_hors)
    mq_rows     = build_tracker_rows(all_manquants)

    return html.Div([
        banner(
            "Aucune urgence — tous les systèmes sont opérationnels." if nb_urg == 0
            else f"{nb_urg} alerte(s) nécessitent votre attention",
            "ok" if nb_urg == 0 else "danger"
        ),
        html.Div(style={"height":"16px"}),

        collapsible("Capteurs déconnectés", len(disconnected),
            make_table_searchable(disc_rows, "deconnectes") if disc_rows
            else banner("Tous les capteurs sont connectés.", "ok"),
            tone="danger" if disconnected else "ok"),

        collapsible("Batterie faible", len(battery_low),
            make_table_searchable(batl_rows, "batterie_faible") if batl_rows
            else banner("Toutes les batteries sont au-dessus du seuil.", "ok"),
            tone="warn" if battery_low else "ok"),

        collapsible("Batterie inconnue", len(battery_unk),
            make_table_searchable(batunk_rows, "batterie_inconnue") if batunk_rows
            else banner("Aucun capteur avec tension inconnue.", "ok"),
            tone="warn" if battery_unk else None),

        collapsible("Peson inconnu", len(weight_unk),
            make_table_searchable(wunk_rows, "peson_inconnu") if wunk_rows
            else banner("Tous les pesons transmettent des données.", "ok"),
            tone="warn" if weight_unk else None),

        collapsible("Capteurs actifs hors horaire", len(all_hors),
            make_table_searchable(hors_rows, "hors_schedule") if hors_rows
            else banner("Aucun capteur actif hors des heures prévues.", "ok"),
            tone="warn" if all_hors else None),

        collapsible("Capteurs inactifs pendant horaire", len(all_manquants),
            make_table_searchable(mq_rows, "inactif_schedule") if mq_rows
            else banner("Tous les capteurs actifs pendant les heures prévues.", "ok"),
            tone="warn" if all_manquants else None),

        collapsible("Projets bientôt terminés", len(ending_rows),
            make_table_searchable(ending_rows, "fin_imminente") if ending_rows
            else banner("Aucun projet ne se termine dans les prochains jours.", "ok"),
            tone="warn" if ending_rows else None),

        collapsible("Projets terminés encore actifs", len(anomalies),
            make_table_searchable(anomalie_rows, "proj_termines_actifs") if anomalies
            else banner("Aucun projet terminé avec capteurs encore actifs.", "ok"),
            tone="warn" if anomalies else None),

    ], className="tab-content-anim")

def render_scores(data, bt, am, ed):
    _now_s  = datetime.now(timezone.utc)
    _pnow   = _now_s.astimezone(PARIS_TZ)
    _rh, _rm = map(int, (am or "00:01").split(":"))
    _act_sec = max(1, int((_pnow - _pnow.replace(hour=_rh, minute=_rm, second=0, microsecond=0)).total_seconds()))
    segs   = compute_segments(data["projects"], data["project_data"],
                              _now_s, _act_sec, ed, PAST_DAYS)
    pd_map = data["project_data"]
    COLOR_MAP = {"excellent":C["green"],"good":C["accent"],"medium":C["orange"],
                 "bad":C["red"],"empty":C["text_light"]}
    BG_MAP    = {"excellent":C["green_bg"],"good":C["accent_bg"],"medium":C["orange_bg"],
                 "bad":C["red_bg"],"empty":C["bg"]}

    legend = html.Div([
        html.Span(">= 80 — Excellent", style={"background":C["green_bg"],"color":C["green"],
            "border":f"1px solid {C['green_bdr']}","fontSize":"0.72rem","fontWeight":"700",
            "padding":"3px 10px","borderRadius":"20px","marginRight":"6px"}),
        html.Span("55-79 — Bon", style={"background":C["accent_bg"],"color":C["accent"],
            "border":"1px solid rgba(93,144,80,0.3)","fontSize":"0.72rem","fontWeight":"700",
            "padding":"3px 10px","borderRadius":"20px","marginRight":"6px"}),
        html.Span("30-54 — Moyen", style={"background":C["orange_bg"],"color":C["orange"],
            "border":f"1px solid {C['orange_bdr']}","fontSize":"0.72rem","fontWeight":"700",
            "padding":"3px 10px","borderRadius":"20px","marginRight":"6px"}),
        html.Span("< 30 — Critique", style={"background":C["red_bg"],"color":C["red"],
            "border":f"1px solid {C['red_border']}","fontSize":"0.72rem","fontWeight":"700",
            "padding":"3px 10px","borderRadius":"20px"}),
    ], style={"display":"flex","flexWrap":"wrap","gap":"6px","marginBottom":"20px"})

    cards = []
    for p in segs["total"]:
        pid   = p.get("id")
        trkrs = pd_map.get(pid, {}).get("trackers", [])
        if not trkrs: continue
        delay = p.get("offlineDelay", 60)
        score = health_score(trkrs, delay, bt)
        conn  = sum(1 for t in trkrs if t.get("_is_connected", False))
        bat_ok= sum(1 for t in trkrs if battery_status(t, bt) == "ok")
        disc  = len(trkrs) - conn
        cls   = score_class(score)
        flags = compute_project_flags(p, trkrs, datetime.now(timezone.utc), bt)
        d     = flags["details"]

        flag_row = html.Div([
            flag_badge("⚡ KO",            d["ko_count"],      "urgence-ko",      C["red"])
                if flags["capteur_ko"] else html.Span(),
            flag_badge("🕐 Hors schedule", d["hors_count"],    "urgence-hors",    C["orange"])
                if flags["hors_schedule"] else html.Span(),
            flag_badge("⚠ Inactif",        d["inactif_count"], "urgence-inactif", "#B45309")
                if flags["inactif_schedule"] else html.Span(),
        ], style={"marginTop": "8px", "minHeight": "22px"})

        # Tooltip détails au survol
        detail_lines = d["ko_list"] + d["hors_list"] + d["inactif_list"]
        detail_title = "\n".join(detail_lines) if detail_lines else ""

        cards.append(html.Div([
            html.Div([
                html.Div(p.get("name","?"), className="score-name",
                         title=detail_title),
                html.Div([
                    html.Span(score_label(score),
                              style={"fontSize":"0.72rem","color":C["text_muted"],"marginRight":"8px"}),
                    html.Span(f"{score}%", className="score-badge",
                              style={"background":BG_MAP[cls],"color":COLOR_MAP[cls],
                                     "border":f"1px solid {C['border']}"}),
                ], style={"display":"flex","alignItems":"center"}),
            ], className="score-header"),
            html.Div(className="score-track", children=[
                html.Div(className="score-fill",
                         style={"width":f"{score}%","background":COLOR_MAP[cls]}),
            ]),
            html.Div(
                f"{len(trkrs)} capteurs · {conn} connectés · {disc} déco. · {bat_ok} batt. OK · délai {delay}s",
                className="score-meta"
            ),
            flag_row,
        ], className="score-card"))

    return html.Div([
        section_label(f"Score de santé — {len(cards)} projet(s)"),
        legend,
        html.Div(cards),
    ], className="tab-content-anim")


def render_projets(data, bt, activity_min, ending_days, past_days, filtreTous="Tous", filtreType="Tous", filtreSearch=""):
    now    = datetime.now(timezone.utc)
    _pnow  = now.astimezone(PARIS_TZ)
    _rh, _rm = map(int, (activity_min or "00:01").split(":"))
    _act_sec = max(1, int((_pnow - _pnow.replace(hour=_rh, minute=_rm, second=0, microsecond=0)).total_seconds()))
    segs = compute_segments(data["projects"], data["project_data"], now,
                            _act_sec, ending_days, past_days)
    pd_map = data["project_data"]

    all_types    = sorted(set(p.get("type","?") for p in data["projects"]
                              if p.get("type") and p.get("type") != "KYD"))
    type_options = ["Tous"] + all_types

    statut_options = ["Tous","Actifs","Inactifs","Fin imminente","Récemment terminés"]

    filtre_map = {
        "Actifs":             segs["active"],
        "Inactifs":           [p for p in segs["total"] if p not in segs["active"]],
        "Fin imminente":      segs["ending"],
        "Récemment terminés": segs["past"],
        "Tous":               data["projects"],
    }
    projets_affiches = filtre_map.get(filtreTous, data["projects"])
    projets_affiches = [p for p in projets_affiches if p.get("type") != "KYD"]
    if filtreType != "Tous":
        projets_affiches = [p for p in projets_affiches if p.get("type","?") == filtreType]
    if filtreSearch and filtreSearch.strip():
        q = filtreSearch.strip().lower()
        projets_affiches = [p for p in projets_affiches if q in p.get("name","").lower()]

    labels_map = {
        "Actifs":             f"{len(projets_affiches)} projet(s) actif(s)",
        "Inactifs":           f"{len(projets_affiches)} projet(s) inactif(s)",
        "Fin imminente":      f"{len(projets_affiches)} projet(s) en fin imminente",
        "Récemment terminés": f"{len(projets_affiches)} projet(s) récemment terminé(s)",
        "Tous":               f"{len(projets_affiches)} projet(s) au total",
    }
    titre = labels_map.get(filtreTous, f"{len(projets_affiches)} projets")

    rows = []
    for p in projets_affiches:
        pid   = p.get("id")
        pdata = pd_map.get(pid,{})
        trkrs = pdata.get("trackers",[])
        delay = p.get("offlineDelay",60)
        score = health_score(trkrs, delay, bt)
        conn  = sum(1 for t in trkrs if t.get("_is_connected",False))
        disc  = len(trkrs) - conn
        bat_l = sum(1 for t in trkrs if battery_status(t, bt) == "faible")

        if p in segs["ending"]:   statut = "🟠 Bientôt terminé"
        elif p in segs["active"]: statut = "🟢 Actif"
        elif p in segs["past"]:   statut = "🔴 Récemment terminé"
        elif p.get("archived"):   statut = "⚫ Archivé"
        else:                     statut = "⚪ Inactif"

        last_seen = max((t.get("lastUpdate","") for t in trkrs), default="")
        last_str  = fmt_paris(last_seen)

        rows.append({
            "_pid":              p.get("id"),
            "Projet":            p.get("name","?"),
            "Type":              p.get("type","?"),
            "Statut":            statut,
            "Score santé":       f"{score}%",
            "Capteurs":          len(trkrs),
            "Connectés":         conn,
            "Déconnectés":       disc,
            "Batt. faible":      bat_l,
            "Dernière activité": last_str,
            "Délai offline":     f"{delay}s",
            "Fuseau horaire":    fmt_tz(pdata.get("timezone","UTC")),
            "Début":             fmt_date(p.get("startDate")),
            "Fin":               fmt_date(p.get("endDate")),
        })

    if filtreTous == "Inactifs" and rows:
        df = pd.DataFrame(rows)
        df["_sort"] = pd.to_datetime(df["Dernière activité"], format="%d/%m/%Y %H:%M", errors="coerce")
        df = df.sort_values("_sort", ascending=False).drop(columns=["_sort"])
        rows = df.to_dict("records")

    nb_archived = len([p for p in data["projects"] if p.get("archived")])

    # ── 3 filtres en ligne ────────────────────────────────────
    filtres = html.Div([
        html.Div([
            html.Label("Statut", className="filter-label"),
            dcc.Dropdown(
                id="proj-statut",
                options=[{"label":v,"value":v} for v in statut_options],
                value=filtreTous, clearable=False, className="dd-filter",
            ),
        ], style={"flex":"1"}),
        html.Div([
            html.Label("Type", className="filter-label"),
            dcc.Dropdown(
                id="proj-type",
                options=[{"label":t,"value":t} for t in type_options],
                value=filtreType, clearable=False, className="dd-filter",
            ),
        ], style={"flex":"1"}),
        html.Div([
            html.Label("Rechercher", className="filter-label"),
            dcc.Input(
                id="proj-search",
                type="text",
                placeholder="Nom du projet...",
                value=filtreSearch or "",
                debounce=True,
                className="search-input",
                style={"marginBottom":"0"},
            ),
        ], style={"flex":"1"}),
    ], style={"display":"flex","gap":"12px","marginBottom":"16px"})

    return html.Div([
        filtres,
        section_label(titre),
        html.Div(
            dash_table.DataTable(
                id="table-projets",
                data=rows,
                columns=[{"name":c,"id":c} for c in rows[0].keys() if not c.startswith("_")] if rows else [],
                page_size=15,
                sort_action="native",
                filter_action="native",
                row_selectable="single",
                selected_rows=[],
                style_table={"overflowX":"auto","minWidth":"800px"},
                style_header={
                    "backgroundColor": "var(--bg)",
                    "fontWeight":      "700",
                    "border":          "1px solid var(--border)",
                    "fontSize":        "11px",
                    "color":           "var(--text-muted)",
                    "textTransform":   "uppercase",
                    "letterSpacing":   "0.06em",
                    "padding":         "10px 12px",
                },
                style_cell={
                    "textAlign":       "left",
                    "padding":         "9px 12px",
                    "border":          "1px solid var(--border)",
                    "fontFamily":      "DM Sans, sans-serif",
                    "fontSize":        "13px",
                    "backgroundColor": "var(--surface)",
                    "color":           "var(--text)",
                    "minWidth":        "120px",
                    "maxWidth":        "200px",
                    "overflow":        "hidden",
                    "textOverflow":    "ellipsis",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "var(--bg)"},
                    {"if": {"state": "selected"}, "backgroundColor": "var(--accent-bg)",
                    "border": "1px solid var(--accent)"},
                ],
            ),
            style={"border":"1px solid var(--border)","borderRadius":"10px",
                    "overflowX":"auto","overflowY":"visible"}
        ) if rows else html.Div("Aucune donnée.", style={"color":C["text_muted"],"padding":"16px 0"}),

        html.Div(
            html.Button(
                f"📦 Voir les projets archivés ({nb_archived})",
                id="btn-open-archives", n_clicks=0,
                style={"background":"transparent","border":f"1px solid {C['border']}",
                       "borderRadius":"8px","padding":"10px 18px","fontSize":"0.8rem",
                       "fontWeight":"500","color":C["text_muted"],"cursor":"pointer",
                       "marginTop":"16px","fontFamily":"inherit","transition":"all 0.15s"}
            ),
            style={"textAlign":"right"}
        ),
    ], className="tab-content-anim")


def render_capteurs(data, filtre_conn="Connectés", filtre_batt="Tous", filtre_proj="Tous"):
    all_t   = data["all_trackers"]
    projets = sorted(set(t.get("_project_name","?") for t in all_t))

    filtered = all_t[:]
    if filtre_proj != "Tous":
        filtered = [t for t in filtered if t.get("_project_name") == filtre_proj]
    if filtre_conn == "Connectés":
        filtered = [t for t in filtered if t.get("_is_connected")]
    elif filtre_conn == "Déconnectés":
        filtered = [t for t in filtered if not t.get("_is_connected")]
    if filtre_batt == "OK":
        filtered = [t for t in filtered if t.get("_battery_status") == "ok"]
    elif filtre_batt == "Faible":
        filtered = [t for t in filtered if t.get("_battery_status") == "faible"]
    elif filtre_batt == "Inconnue":
        filtered = [t for t in filtered if t.get("_battery_status") == "inconnu"]

    rows = build_tracker_rows(filtered)

    return html.Div([
        html.Div([
            html.Div([
                html.Label("Projet", className="filter-label"),
                dcc.Dropdown(id="cap-proj",
                             options=[{"label":"Tous","value":"Tous"}]+[{"label":p,"value":p} for p in projets],
                             value=filtre_proj, clearable=False, className="dd-filter"),
            ], style={"flex":"1"}),
            html.Div([
                html.Label("Connexion", className="filter-label"),
                dcc.Dropdown(id="cap-conn",
                             options=[{"label":v,"value":v} for v in ["Tous","Connectés","Déconnectés"]],
                             value=filtre_conn, clearable=False, className="dd-filter"),
            ], style={"flex":"1"}),
            html.Div([
                html.Label("Batterie", className="filter-label"),
                dcc.Dropdown(id="cap-batt",
                             options=[{"label":v,"value":v} for v in ["Tous","OK","Faible","Inconnue"]],
                             value=filtre_batt, clearable=False, className="dd-filter"),
            ], style={"flex":"1"}),
        ], style={"display":"flex","gap":"12px","marginBottom":"16px"}),

        section_label(f"Résultats — {len(filtered)} capteur(s)"),

        html.Div(
            dash_table.DataTable(
                id="table-capteurs",
                data=rows,
                columns=[{"name":c,"id":c} for c in rows[0].keys()
                         if not c.startswith("_")] if rows else [],
                page_size=15,
                sort_action="native",
                filter_action="native",
                row_selectable="single",
                selected_rows=[],
                style_table={"overflowX":"auto","minWidth":"800px"},
                style_header={
                    "backgroundColor": "var(--bg)",
                    "fontWeight":      "700",
                    "border":          "1px solid var(--border)",
                    "fontSize":        "11px",
                    "color":           "var(--text-muted)",
                    "textTransform":   "uppercase",
                    "letterSpacing":   "0.06em",
                    "padding":         "10px 12px",
                },
                style_cell={
                    "textAlign":       "left",
                    "padding":         "9px 12px",
                    "border":          "1px solid var(--border)",
                    "fontFamily":      "DM Sans, sans-serif",
                    "fontSize":        "13px",
                    "backgroundColor": "var(--surface)",
                    "color":           "var(--text)",
                    "minWidth":        "120px",
                    "maxWidth":        "200px",
                    "overflow":        "hidden",
                    "textOverflow":    "ellipsis",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "var(--bg)"},
                    {"if": {"state": "selected"}, "backgroundColor": "var(--accent-bg)",
                     "border": "1px solid var(--accent)"},
                ],
            ),
            style={"border":f"1px solid {C['border']}","borderRadius":"10px",
                   "overflowX":"auto","overflowY":"visible"}
        ),

        dcc.Store(id="store-capteur-rows", data=rows),

    ], className="tab-content-anim")

def render_qc(data):
    qc     = data.get("qc",{})
    issues = qc.get("issues",[])
    items  = [
        ("Projets total",       qc.get("total_projects",0),        "info"),
        ("Projets charges",     qc.get("projects_loaded",0),       "ok" if qc.get("projects_loaded")==qc.get("total_projects") else "warn"),
        ("Sans accessKey",      qc.get("projects_no_key",0),       "ok" if qc.get("projects_no_key",0)==0 else "err"),
        ("Projets vides",       qc.get("projects_empty",0),        "ok" if qc.get("projects_empty",0)==0 else "warn"),
        ("Avec donnees",        qc.get("projects_with_data",0),    "info"),
        ("Unites total",        qc.get("units_total",0),           "info"),
        ("Unites sans capteur", qc.get("units_no_tracker",0),      "ok" if qc.get("units_no_tracker",0)==0 else "warn"),
        ("Trackers total",      qc.get("trackers_total",0),        "info"),
        ("IDs uniques",         qc.get("tracker_ids_unique",0),    "info"),
        ("IDs dupliques",       qc.get("trackers_duplicate_id",0), "ok" if qc.get("trackers_duplicate_id",0)==0 else "err"),
        ("Sans lastUpdate",     qc.get("trackers_no_lastupdate",0),"ok" if qc.get("trackers_no_lastupdate",0)==0 else "err"),
        ("Sans lastTrack",      qc.get("trackers_no_lasttrack",0), "ok" if qc.get("trackers_no_lasttrack",0)==0 else "warn"),
        ("Stales > 24h",        qc.get("trackers_stale_24h",0),    "warn"),
        ("Events disponibles",  "Oui" if qc.get("has_events") else "Non","ok" if qc.get("has_events") else "warn"),
    ]
    cls_map = {"ok":"qc-ok","warn":"qc-warn","err":"qc-err","info":"qc-info"}
    return html.Div([
        html.Div([
            html.Div("Rapport qualite des données", className="qc-title"),
            *[html.Div([html.Span(k, className="qc-lbl"),
                        html.Span(str(v), className=cls_map.get(cls,"qc-info"))],
                       className="qc-row") for k,v,cls in items],
        ], className="qc-block"),
        html.Div(style={"height":"10px"}),
        html.Div([
            html.Div(f"Anomalies dtectees — {len(issues)}", className="qc-title"),
            make_table([{"Anomalie":i} for i in issues[:50]]) if issues
            else banner("Aucune anomalie detectee.", "ok"),
        ], className="qc-block"),
    ], className="tab-content-anim")


# ════════════════════════════════════════════════════════════
# SECTION 9 — APP DASH + LAYOUT
# ════════════════════════════════════════════════════════════

app = dash.Dash(__name__, title="CAD.42 — UNIFIELD Dashboard",
                suppress_callback_exceptions=True,
                meta_tags=[{"name":"viewport","content":"width=device-width, initial-scale=1"}],
                assets_folder="assets")
server = app.server


def _sidebar():
    return html.Div([
        html.Div([
            html.Div("CAD.42", className="logo-name"),
            html.Div("UNIFIELD Dashboard", className="logo-sub"),
        ]),
        html.Hr(className="sb-hr"),
        html.Div("Connexion", className="sb-section"),
        html.Label("Email", className="sb-label"),
        dcc.Input(id="input-email", type="email", placeholder="votre@email.com",
                  debounce=True, className="sb-input"),
        html.Label("Clé d'accès", className="sb-label"),
        dcc.Input(id="input-key", type="password", placeholder="User Access Key",
                  debounce=True, className="sb-input"),
        html.Div(id="conn-status"),
        html.Div(id="load-bar-wrap", children=[
            html.Div(className="load-wrap", children=[html.Div(className="load-bar")]),
            html.Div(id="load-hint-text", children="Connexion a UNIFIELD...", className="load-hint"),
        ], style={"display":"none"}),
        html.Button("Actualiser", id="btn-refresh", n_clicks=0,
                    className="btn-primary", style={"marginTop":"10px"}),
        html.Button("Vider cache", id="btn-clear", n_clicks=0, className="btn-secondary"),
        html.Hr(className="sb-hr"),
        html.Div(
            dcc.Checklist(
                id="btn-dark-mode",
                options=[{"label": "    🌙 Mode sombre", "value": "dark"}],
                value=[],
            ),
            className="dark-toggle-wrap"
        ),
        html.Div("Seuils", className="sb-section"),
        html.Label("Battérie faible (V)", className="sb-label"),
        dcc.Input(id="seuil-battery", type="number", value=BATTERY_WARNING_THRESHOLD,
                  step=0.1, min=2.0, max=5.0, debounce=True, className="sb-input"),
        html.Label("Fin imminente (jours)", className="sb-label"),
        dcc.Input(id="seuil-ending", type="number", value=ENDING_SOON_DAYS,
                  step=1, min=1, max=365, debounce=True, className="sb-input"),
        html.Label("Activité depuis", className="sb-label"),
        dcc.Input(id="seuil-activity", type="time", value="00:01",
                  debounce=True, className="sb-input"),
    ], className="sidebar")


app.layout = html.Div([
    # Stores
    dcc.Store(id="store-creds",       storage_type="session"),
    dcc.Store(id="store-seuils",      data={"bt":BATTERY_WARNING_THRESHOLD,"ed":ENDING_SOON_DAYS,
                                        "am":"00:01","pd":PAST_DAYS}),
    dcc.Store(id="store-ver",         data={"v":0,"email":""}),
    dcc.Store(id="store-filtre-proj", data="Tous"),
    dcc.Store(id="store-filtre-type", data="Tous"),
    dcc.Store(id="store-filtre-cap",  data={"conn":"Connectés","batt":"Tous","proj":"Tous"}),
    dcc.Store(id="store-projet-selec", data=None),
    dcc.Store(id="store-capteur-selec", data=None),
    dcc.Store(id="store-modal-archives", data=False),
    dcc.Store(id="active-tab",        data="urgences"),
    dcc.Store(id="store-urgence-anchor", data=None),
    dcc.Store(id="store-filtre-search", data=""),
    dcc.Store(id="store-dark-mode", data=False, storage_type="local"),
    # Interval — lecture cache uniquement, ZERO appel API
    dcc.Store(id="store-loading", data=False),
    dcc.Interval(id="interval-ui", interval=1000, n_intervals=0, disabled=True),

    html.Div([
        _sidebar(),
        html.Div([
            # Header
            html.Div([
                html.Div([
                    html.H1("Tableau de bord operationnel", className="page-title"),
                    html.P("UNIFIELD - CAD.42 — Vision temps reel des chantiers", className="page-sub"),
                ]),
                html.Div(id="page-meta", className="page-meta"),
            ], className="page-header"),

            # KPIs
            html.Div("Vue d'ensemble", className="section-label"),
            html.Div(id="kpi-row", className="kpi-grid"),
            html.Div(style={"height":"8px"}),

            # Onglets
            html.Div("Analyse", className="section-label"),
            html.Div([
                html.Button("⚠ Urgences",          id="tab-urgences",  n_clicks=0, className="tab-btn active"),
                html.Button("⬡ Scores",             id="tab-scores",    n_clicks=0, className="tab-btn"),
                html.Button("≡ Projets",            id="tab-projets",   n_clicks=0, className="tab-btn"),
                html.Button("◎ Capteurs",           id="tab-capteurs",  n_clicks=0, className="tab-btn"),
                html.Button("✦ Qualite des donnees",id="tab-qc",        n_clicks=0, className="tab-btn"),
            ], className="tab-bar"),

            html.Div(id="tab-content"),
        ], className="main-content"),
    ], className="page-layout"),
    html.Div(id="modal-container"),
    html.Div(id="scroll-trigger", style={"display":"none"}),
])


# ════════════════════════════════════════════════════════════
# SECTION 10 — CALLBACKS
# ════════════════════════════════════════════════════════════

app.clientside_callback(
    """
    function(value, is_dark) {
        var new_dark = value && value.includes('dark');
        if (new_dark) {
            document.body.classList.add('dark');
        } else {
            document.body.classList.remove('dark');
        }
        return new_dark;
    }
    """,
    Output("store-dark-mode", "data"),
    Input("btn-dark-mode",    "value"),
    State("store-dark-mode",  "data"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function(is_dark) {
        if (is_dark) {
            document.body.classList.add('dark');
            return ['dark'];
        } else {
            document.body.classList.remove('dark');
            return [];
        }
    }
    """,
    Output("btn-dark-mode", "value"),
    Input("store-dark-mode", "data"),
)

@app.callback(
    Output("store-creds", "data"),
    Input("input-email",  "value"),
    Input("input-key",    "value"),
)
def save_creds(email, key):
    if email and key:
        register_creds(email, key)
        return {"email": email, "key": key}
    return None


@app.callback(
    Output("store-seuils", "data"),
    Input("seuil-battery",  "value"),
    Input("seuil-ending",   "value"),
    Input("seuil-activity", "value"),
)
def save_seuils(batt, ending, activity):
    return {
        "bt": batt     or BATTERY_WARNING_THRESHOLD,
        "ed": ending   or ENDING_SOON_DAYS,
        "am": activity or "00:01",
        "pd": PAST_DAYS,
    }

@app.callback(
    Output("store-ver",     "data"),
    Output("store-loading", "data"),
    Input("btn-refresh",    "n_clicks"),
    Input("btn-clear",      "n_clicks"),
    Input("store-creds",    "data"),
    Input("interval-ui",    "n_intervals"),
    State("store-ver",      "data"),
    prevent_initial_call=False,
)
def sync_ver(nrefresh, nclear, creds, _, cur):
    if not creds:
        return {"v": 0, "email": ""}, False
    email, key = creds.get("email",""), creds.get("key","")
    if not email or not key:
        return {"v": 0, "email": ""}, False

    triggered = ctx.triggered_id

    if triggered == "store-creds":
        register_creds(email, key)
        v = get_cache_version(email, key)
        if cur and cur.get("v") == v and cur.get("email") == email:
            return dash.no_update, False
        return {"v": v, "email": email}, False

    elif triggered == "btn-refresh":
        register_creds(email, key)
        force_refresh(email, key)
        return {"v": 0, "email": email}, True  # active l'Interval

    elif triggered == "btn-clear":
        invalidate(email, key)
        register_creds(email, key)
        return {"v": 0, "email": email}, False

    # Interval actif — surveille la fin du chargement
    state   = _state(email, key)
    loading = state.get("loading", False)
    v       = get_cache_version(email, key)

    if cur and cur.get("v") == v and cur.get("email") == email:
        return dash.no_update, loading  # version inchangée, mais on garde loading pour l'Interval

    return {"v": v, "email": email}, loading  # coupe l'Interval quand loading=False

@app.callback(
    Output("interval-ui", "disabled"),
    Input("store-loading", "data"),
)
def toggle_interval(loading):
    return not loading

@app.callback(
    Output("conn-status",    "children"),
    Output("page-meta",      "children"),
    Output("load-bar-wrap",  "style"),
    Output("load-hint-text", "children"),
    Input("store-ver",   "data"),
    Input("interval-ui", "n_intervals"),
    State("store-creds", "data"),
    State("store-seuils", "data")
)
def update_status(ver, _, creds, seuils):
    hide = {"display":"none"}
    show = {"display":"block"}
    if not creds:
        return (html.Div([html.Span(className="dot-wait"),
                          html.Span("En attente d'identifiants")], className="conn-row"),
                "", hide, "")

    email, key = creds.get("email",""), creds.get("key","")
    state      = _state(email, key)
    data       = state.get("data")
    loading    = state.get("loading", False)
    err        = state.get("error")

    with _load_log_lock:
        load_text = _load_log[-1][-60:] if _load_log else "Connexion a UNIFIELD..."

    if err:     dot, text = html.Span(className="dot-err"),  f"Erreur : {err[:80]}"
    elif loading: dot, text = html.Span(className="dot-load"), "Chargement en cours..."
    elif data:  dot, text = html.Span(className="dot-live"), "Donnees disponibles"
    else:       dot, text = html.Span(className="dot-wait"), "Cliquez sur Actualiser"

    loaded_at = state.get("loaded_at")
    time_str  = (f"Chargé à {datetime.fromtimestamp(loaded_at, tz=PARIS_TZ).strftime('%H:%M')}"
                 if loaded_at else "")

    conn_row = html.Div([
        html.Div([dot, html.Span(text)], className="conn-row"),
        html.Div(time_str, style={"fontSize":"0.72rem","color":C["text_light"],"marginTop":"2px"}),
    ])

    meta = ""
    if data and data.get("qc"):
        data  = filter_data(data)
        qc    = data["qc"]
        now_h = datetime.now(timezone.utc)

        # Calcul flags globaux
        all_t    = data.get("all_trackers", [])
        all_proj = data.get("projects", [])
        pd_map   = data.get("project_data", {})

        total_ko      = sum(1 for t in all_t
                            if not t.get("_is_connected", False)
                            or battery_status(t) == "faible")
        total_hors    = 0
        total_inactif = 0
        for _p in all_proj:
            _trkrs = pd_map.get(_p.get("id",""), {}).get("trackers", [])
            _hs, _mq = check_schedule_anomalies(
                _trkrs, _p.get("schedule", {}), now_h
            )
            total_hors    += len(_hs)
            total_inactif += len(_mq)

        flag_items = []
        if total_ko > 0:
            flag_items.append(
                html.Span(f"⚡ {total_ko} KO",
                          style={"background":C["red"],"color":"#fff","fontSize":"0.68rem",
                                 "fontWeight":"700","padding":"2px 8px","borderRadius":"20px",
                                 "marginLeft":"6px"})
            )
        if total_hors > 0:
            flag_items.append(
                html.Span(f"🕐 {total_hors} hors schedule",
                          style={"background":C["orange"],"color":"#fff","fontSize":"0.68rem",
                                 "fontWeight":"700","padding":"2px 8px","borderRadius":"20px",
                                 "marginLeft":"6px"})
            )
        if total_inactif > 0:
            flag_items.append(
                html.Span(f"⚠ {total_inactif} inactifs",
                          style={"background":"#B45309","color":"#fff","fontSize":"0.68rem",
                                 "fontWeight":"700","padding":"2px 8px","borderRadius":"20px",
                                 "marginLeft":"6px"})
            )

        meta = html.Div([
            html.Div([
                html.Span(f"{qc.get('projects_loaded',0)}/{qc.get('total_projects',0)} projets chargés"),
                *flag_items,
            ], style={"display":"flex","alignItems":"center","flexWrap":"wrap","gap":"4px"}),
            html.Div(f"{qc.get('units_total',0)} unités · {qc.get('trackers_total',0)} capteurs"),
            html.Div(datetime.now().strftime("%d/%m/%Y %H:%M"),
                     style={"color":C["text_light"]}),
        ])

    return conn_row, meta, show if loading else hide, load_text


@app.callback(
    Output("kpi-row",     "children"),
    Input("store-ver",    "data"),
    Input("store-seuils", "data"),
    State("store-creds",  "data"),
)
def update_kpis(ver, seuils, creds):
    if not creds: return []
    data = get_cached_data(creds["email"], creds["key"])
    if not data or not data.get("projects"):
        return [kpi_card("Projets actifs", 0, "En attente de donnees")]
    data = filter_data(data)
    if not data.get("projects"):
        return [kpi_card("Projets actifs", 0, "En attente de donnees")]

    bt, ed, am = seuils["bt"], seuils["ed"], seuils.get("am","00:01")
    now   = datetime.now(timezone.utc)
    _pnow = now.astimezone(PARIS_TZ)
    _rh, _rm = map(int, am.split(":"))
    _act_sec = max(1, int((_pnow - _pnow.replace(hour=_rh, minute=_rm, second=0, microsecond=0)).total_seconds()))
    segs = compute_segments(data["projects"], data["project_data"],
                            now, _act_sec, ed, PAST_DAYS)
    all_t   = data["all_trackers"]
    conn    = [t for t in all_t if t.get("_is_connected",False)]
    bat_low = [t for t in all_t if battery_status(t, bt) == "faible"]
    pct     = round(len(conn)/len(all_t)*100) if all_t else 0

    return [
        kpi_card("Projets actifs", len(segs["active"]),
                 f"Signal depuis {am} - {len(segs['total'])} dans le parc",
                 C["green"] if segs["active"] else C["text_muted"], "projets"),
        kpi_card("Fin imminente", len(segs["ending"]),
                 f"Dans les {int(ed)} prochains jours",
                 C["orange"] if segs["ending"] else None, "urgences"),
        kpi_card("Projets termines", len(segs["past"]),
                 "endDate dépassée, non archivés",
                 C["orange"] if segs["past"] else None, "projets"),
        kpi_card("Capteurs connectes", len(conn),
                 f"{pct}% du parc - {len(all_t)} total",
                 C["green"] if pct >= 80 else C["orange"] if pct >= 50 else C["red"], "capteurs"),
        kpi_card("Batterie faible", len(bat_low),
                 f"Seuil < {bt}V",
                 C["orange"] if bat_low else None, "urgences"),
    ]


@app.callback(
    Output("active-tab",   "data"),
    Output("tab-urgences", "className"),
    Output("tab-scores",   "className"),
    Output("tab-projets",  "className"),
    Output("tab-capteurs", "className"),
    Output("tab-qc",       "className"),
    Input("tab-urgences",  "n_clicks"),
    Input("tab-scores",    "n_clicks"),
    Input("tab-projets",   "n_clicks"),
    Input("tab-capteurs",  "n_clicks"),
    Input("tab-qc",        "n_clicks"),
    State("active-tab",    "data"),
    prevent_initial_call=True,
)
def switch_tab(n1, n2, n3, n4, n5, current):
    tab_map = {
        "tab-urgences": "urgences", "tab-scores":  "scores",
        "tab-projets":  "projets",  "tab-capteurs":"capteurs", "tab-qc":"qc",
    }
    triggered = ctx.triggered_id
    current   = current or "urgences"
    new_tab   = tab_map.get(triggered, current)
    def cls(t): return "tab-btn active" if t == new_tab else "tab-btn"
    return new_tab, cls("urgences"), cls("scores"), cls("projets"), cls("capteurs"), cls("qc")


@app.callback(
    Output("tab-content", "children"),
    Input("active-tab",   "data"),
    Input("store-ver",    "data"),
    State("store-seuils",      "data"),
    State("store-filtre-proj",   "data"),
    State("store-filtre-cap",    "data"),
    State("store-filtre-type",   "data"),
    State("store-filtre-search", "data"),
    State("store-creds",       "data"),
)
def render_tab(tab, ver, seuils, filtre_proj, filtre_cap, filtre_type, filtre_search, creds):
    triggered = ctx.triggered_id

    if triggered == "store-ver":
        # Forcer urgences uniquement au premier chargement (v=1)
        if ver and ver.get("v", 0) == 1:
            tab = "urgences"
    elif not tab or tab not in ("urgences","scores","projets","capteurs","qc"):
        tab = "urgences"

    if not creds:
        return banner("Entrez vos identifiants dans la barre laterale pour commencer.", "info")
    data = get_cached_data(creds["email"], creds["key"])
    if not data or not data.get("projects"):
        st = _state(creds["email"], creds["key"])
        if st.get("loading"):
            return html.Div([
                html.Div(className="load-wrap", children=[html.Div(className="load-bar")]),
                html.Div("Chargement des donnees UNIFIELD en cours...",
                         className="load-hint", style={"marginTop":"8px"}),
            ], className="load-card")
        return banner("Aucune donnee. Cliquez sur Actualiser.", "info")
    data = filter_data(data)
    if not seuils:
        seuils = {"bt":BATTERY_WARNING_THRESHOLD,"ed":ENDING_SOON_DAYS,"am":"00:01"}
    bt, ed, am = seuils["bt"], seuils["ed"], seuils.get("am","00:01")
    if tab == "urgences": return render_urgences(data, bt, am, ed, PAST_DAYS)
    if tab == "scores":   return render_scores(data, bt, am, ed)
    if tab == "projets": return render_projets(data, bt, am, ed, PAST_DAYS,
                         filtre_proj or "Tous", filtre_type or "Tous", filtre_search or "")
    if tab == "capteurs":
        fc = filtre_cap or {}
        return render_capteurs(data, fc.get("conn","Connectés"),
                               fc.get("batt","Tous"), fc.get("proj","Tous"))
    return render_qc(data)

@app.callback(
    Output("tab-content", "children", allow_duplicate=True),
    Input("store-filtre-proj", "data"),
    Input("store-filtre-cap",  "data"),
    Input("store-filtre-type", "data"),
    Input("store-filtre-search", "data"),
    State("active-tab",        "data"),
    State("store-seuils",      "data"),
    State("store-creds",       "data"),
    prevent_initial_call=True,
)
def refresh_on_filter(filtre_proj, filtre_cap, filtre_type, filtre_search, tab, seuils, creds):
    if tab not in ("projets","capteurs"):
        return dash.no_update
    if not creds:
        return dash.no_update
    data = get_cached_data(creds["email"], creds["key"])
    if not data or not data.get("projects"):
        return dash.no_update
    data = filter_data(data)
    if not seuils:
        seuils = {"bt":BATTERY_WARNING_THRESHOLD,"ed":ENDING_SOON_DAYS,"am":"00:01"}
    bt, ed, am = seuils["bt"], seuils["ed"], seuils.get("am","00:01")
    if tab == "projets":
        return render_projets(data, bt, am, ed, PAST_DAYS,
                              filtre_proj or "Tous",
                              filtre_type or "Tous",
                              filtre_search or "")
    if tab == "capteurs":
        fc = filtre_cap or {}
        return render_capteurs(data,
                               fc.get("conn","Connectés"),
                               fc.get("batt","Tous"),
                               fc.get("proj","Tous"))
    return dash.no_update

@app.callback(
    Output("store-filtre-proj", "data"),
    Input("proj-statut", "value"),
    prevent_initial_call=True,
)
def update_filtre_proj(val):
    return val or "Tous"


@app.callback(
    Output("store-filtre-search", "data"),
    Input("proj-search", "value"),
    prevent_initial_call=True,
)
def update_filtre_search(val):
    return val or ""


@app.callback(
    Output("store-filtre-type", "data"),
    Input("proj-type", "value"),
    prevent_initial_call=True,
)
def update_filtre_type(val):
    return val or "Tous"


@app.callback(
    Output("store-filtre-cap", "data"),
    Input("cap-conn", "value"),
    Input("cap-batt", "value"),
    Input("cap-proj", "value"),
    State("store-filtre-cap", "data"),
    prevent_initial_call=True,
)
def update_filtre_cap(conn, batt, proj, current):
    return {
        "conn": conn or current.get("conn","Connectés"),
        "batt": batt or current.get("batt","Tous"),
        "proj": proj or current.get("proj","Tous"),
    }

@app.callback(
    Output("store-projet-selec", "data"),
    Input("table-projets", "derived_virtual_selected_rows"),
    State("table-projets", "derived_virtual_data"),
    prevent_initial_call=True,
)
def select_projet(sel_rows, virt_data):
    if not sel_rows or not virt_data:
        return None
    return virt_data[sel_rows[0]].get("_pid")


@app.callback(
    Output("modal-container", "children"),
    Input("store-projet-selec", "data"),
    State("store-filtre-proj",  "data"),
    State("store-filtre-type",  "data"),
    State("store-seuils",       "data"),
    State("store-creds",        "data"),
    prevent_initial_call=True,
)
def show_modal(pid, filtre_proj, filtre_type, seuils, creds):
    if not pid or not creds: return html.Div()
    data = get_cached_data(creds["email"], creds["key"])
    if not data: return html.Div()

    if not seuils:
        seuils = {"bt":BATTERY_WARNING_THRESHOLD,"ed":ENDING_SOON_DAYS,"am":"00:01"}
    bt, ed, am = seuils["bt"], seuils["ed"], seuils.get("am","00:01")
    now   = datetime.now(timezone.utc)
    _pnow = now.astimezone(PARIS_TZ)
    _rh, _rm = map(int, am.split(":"))
    _act_sec = max(1, int((_pnow - _pnow.replace(hour=_rh, minute=_rm, second=0, microsecond=0)).total_seconds()))
    segs = compute_segments(data["projects"], data["project_data"],
                            now, _act_sec, ed, PAST_DAYS)

    p = next((x for x in data["projects"] if x.get("id") == pid), None)
    if not p: return html.Div()
    pdata = data["project_data"].get(pid, {})
    trkrs = pdata.get("trackers", [])
    delay = p.get("offlineDelay", 60)
    score = health_score(trkrs, delay, bt)
    conn  = sum(1 for t in trkrs if t.get("_is_connected", False))
    disc  = len(trkrs) - conn
    bat_l = sum(1 for t in trkrs if battery_status(t, bt) == "faible")

    if p in segs["ending"]:   statut = "🟠 Bientôt terminé"
    elif p in segs["active"]: statut = "🟢 Actif"
    elif p in segs["past"]:   statut = "🔴 Récemment terminé"
    elif p.get("archived"):   statut = "⚫ Archivé"
    else:                     statut = "⚪ Inactif"

    last_seen = max((t.get("lastUpdate","") for t in trkrs), default="")
    last_str  = fmt_paris(last_seen)

    # ── Formatage horaires ────────────────────────────────────
    def fmt_schedule(schedule):
        if not schedule:
            return "Non défini"
        days_fr = {
            "mon":"Lun","tue":"Mar","wed":"Mer",
            "thu":"Jeu","fri":"Ven","sat":"Sam","sun":"Dim"
        }
        lines = []
        for day_key, day_fr in days_fr.items():
            cfg = schedule.get(day_key, {})
            if not isinstance(cfg, dict):
                continue
            enable = cfg.get("enable", False)
            times  = cfg.get("times", [])
            if not enable:
                lines.append(f"{day_fr} — Fermé")
            elif times:
                is_h24 = any(
                    s[0] == "00:00" and s[1] in ("23:59","24:00")
                    for s in times if len(s) >= 2
                )
                plages = " / ".join(f"{s[0]}–{s[1]}" for s in times if len(s) >= 2)
                lines.append(f"{day_fr} — {'24h/24' if is_h24 else plages}")
            else:
                lines.append(f"{day_fr} — Toute la journée")
        return " · ".join(lines) if lines else "Non défini"

    # ── Helper stat ───────────────────────────────────────────
    def stat(label, value):
        return html.Div([
            html.Div(label, className="modal-stat-label"),
            html.Div(str(value), className="modal-stat-value"),
        ], className="modal-stat")

    modal = html.Div([
        html.Div([
            html.Div([
                html.Div(p.get("name","?"), className="modal-title"),
                html.Div(f"{p.get('type','?')} · {fmt_tz(pdata.get('timezone','UTC'))}",
                         style={"fontSize":"0.78rem","color":C["text_muted"],"marginTop":"4px"}),
            ]),
            html.Button("✕", id="btn-close-modal", className="modal-close"),
        ], className="modal-header"),

        html.Div([
            stat("Statut",            statut),
            stat("Score santé",       f"{score}%"),
            stat("Capteurs",          len(trkrs)),
            stat("Connectés",         conn),
            stat("Déconnectés",       disc),
            stat("Batt. faible",      bat_l),
            stat("Dernière activité", last_str),
            stat("Début",             fmt_date(p.get("startDate"))),
            stat("Fin",               fmt_date(p.get("endDate"))),
            # ── Horaires pleine largeur ───────────────────────
            html.Div([
                html.Div("Horaires", className="modal-stat-label"),
                html.Div(
                    fmt_schedule(p.get("schedule", {})),
                    className="modal-stat-value",
                    style={"fontSize":"0.78rem","lineHeight":"1.6","fontWeight":"500"}
                ),
            ], className="modal-stat", style={"gridColumn":"1 / -1"}),
        ], className="modal-summary"),

        section_label(f"Capteurs — {len(trkrs)}"),
        make_table(build_tracker_rows(trkrs)),

    ], className="modal-box")

    return html.Div([
        html.Div(id="modal-projet-bg", n_clicks=0, className="modal-backdrop"),
        modal,
    ], className="modal-overlay")

@app.callback(
    Output("modal-container", "children", allow_duplicate=True),
    Input("store-capteur-selec", "data"),
    State("store-creds", "data"),
    State("store-seuils", "data"),
    prevent_initial_call=True,
)
def show_modal_capteur(tracker_id, creds, seuils):
    if not tracker_id:
        return html.Div()
    if not creds:
        return dash.no_update
    data = get_cached_data(creds["email"], creds["key"])
    if not data: return dash.no_update

    # Trouver le tracker dans all_trackers
    tracker = next(
        (t for t in data["all_trackers"]
         if t.get("id") == tracker_id or t.get("uuid") == tracker_id),
        None
    )
    if not tracker: return dash.no_update

    bt = (seuils or {}).get("bt", BATTERY_WARNING_THRESHOLD)
    msg     = _msg(tracker)
    volt    = tracker.get("_battery_volt", -1)
    temp    = msg.get("temperature", -1)
    weight  = msg.get("weight", -1)
    shackle = msg.get("shackle_battery", -1)
    lt      = tracker.get("lastTrack") or {}
    lat, lon = lt.get("lat", 0), lt.get("lon", 0)
    conn    = tracker.get("_is_connected", False)
    now     = datetime.now(timezone.utc)
    paris_today = now.astimezone(PARIS_TZ).date()

    # ── Events du capteur ─────────────────────────────────
    all_events = data.get("all_events", [])
    proj_id    = tracker.get("_project_id", "")

    # Filtrer les events du projet contenant ce capteur
    capteur_events = []
    boot_keywords  = ["boot","start","connect","online","power","init",
                      "wake","restart","reboot","activate"]
    boot_this_morning = None

    for e in all_events:
        if e.get("_project_id") != proj_id:
            continue
        # Vérifier si l'event concerne ce capteur
        e_trackers = e.get("trackers", [])
        if e_trackers and tracker_id not in [
            (tr if isinstance(tr, str) else tr.get("id","")) for tr in e_trackers
        ]:
            continue
        capteur_events.append(e)

        # Chercher le boot de ce matin
        etype = str(e.get("type") or e.get("eventType") or "").lower()
        emsg  = str(e.get("message") or e.get("msg") or "").lower()
        ts    = e.get("timestamp") or e.get("createdAt") or e.get("date") or ""
        if ts and any(kw in etype or kw in emsg for kw in boot_keywords):
            try:
                dt_event = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                if dt_event.astimezone(PARIS_TZ).date() == paris_today:
                    if boot_this_morning is None or dt_event < boot_this_morning:
                        boot_this_morning = dt_event
            except: pass

    capteur_events.sort(
        key=lambda e: e.get("timestamp") or e.get("createdAt") or "",
        reverse=True
    )

    def stat(label, value, full_width=False):
        style = {"gridColumn": "1 / -1"} if full_width else {}
        return html.Div([
            html.Div(label, className="modal-stat-label"),
            html.Div(str(value), className="modal-stat-value"),
        ], className="modal-stat", style=style)

    # GPS cliquable
    gps_content = "—"
    if lat and lon:
        maps_url = f"https://www.google.com/maps?q={lat},{lon}"
        gps_content = html.A(
            f"{round(lat,5)}, {round(lon,5)} 📍",
            href=maps_url, target="_blank",
            style={"color": C["accent"], "fontWeight": "600",
                   "textDecoration": "none", "fontSize": "0.82rem"}
        )

    # Events tableau
    event_rows = []
    for e in capteur_events[:10]:
        ts  = e.get("timestamp") or e.get("createdAt") or e.get("date") or ""
        ts_str = fmt_paris(str(ts)) if ts else "—"
        event_rows.append({
            "Date":    ts_str,
            "Type":    e.get("type") or e.get("eventType") or "?",
            "Message": str(e.get("message") or e.get("msg") or e.get("data") or "")[:80],
        })

    modal = html.Div([
        # Header
        html.Div([
            html.Div([
                html.Div(tracker.get("name","?"), className="modal-title"),
                html.Div(
                    f"{tracker.get('_project_name','?')} · {tracker.get('_unit_name','?')}",
                    style={"fontSize":"0.78rem","color":C["text_muted"],"marginTop":"4px"}
                ),
            ]),
            html.Button("✕", id="btn-close-capteur", className="modal-close"),
        ], className="modal-header"),

        # Stats
        html.Div([
            stat("Statut", "🟢 Connecté" if conn else "🔴 Déconnecté"),
            stat("Dernière activité", fmt_paris(tracker.get("lastUpdate",""))),
            stat("Allumage ce matin",
                 fmt_paris(boot_this_morning.isoformat()) if boot_this_morning else "Non détecté"),
            stat("Batterie (V)",
                 f"{volt:.2f} V" if volt > 0 else "—"),
            stat("Peson batterie",
                 f"{shackle:.2f} V" if isinstance(shackle,(int,float)) and shackle > 0 else "—"),
            stat("Température",
                 f"{temp:.1f} °C" if isinstance(temp,(int,float)) and temp > 0 else "—"),
            stat("Poids",
                 f"{int(weight)} kg" if isinstance(weight,(int,float)) and weight >= 0 else "—"),
            html.Div([
                html.Div("GPS", className="modal-stat-label"),
                html.Div(gps_content, className="modal-stat-value"),
            ], className="modal-stat"),
        ], className="modal-summary"),

        # Events
        section_label(f"Historique events — {len(capteur_events)} trouvé(s)"),
        make_table(event_rows) if event_rows
        else html.Div("Aucun event trouvé pour ce capteur.",
                      style={"color":C["text_muted"],"fontSize":"0.82rem","padding":"12px 0"}),

    ], className="modal-box")

    return html.Div([
        html.Div(id="modal-capteur-bg", n_clicks=0, className="modal-backdrop"),
        modal,
    ], className="modal-overlay")


app.clientside_callback(
    """
    function(n1, n2) {
        if (n1 || n2) return null;
        return window.dash_clientside.no_update;
    }
    """,
    Output("store-projet-selec", "data", allow_duplicate=True),
    Input("btn-close-modal",  "n_clicks"),
    Input("modal-projet-bg",  "n_clicks"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function(n1, n2) {
        if (n1 || n2) return null;
        return window.dash_clientside.no_update;
    }
    """,
    Output("store-capteur-selec", "data", allow_duplicate=True),
    Input("btn-close-capteur", "n_clicks"),
    Input("modal-capteur-bg",  "n_clicks"),
    prevent_initial_call=True,
)


@app.callback(
    Output("modal-container", "children", allow_duplicate=True),
    Input("store-modal-archives", "data"),
    State("store-creds", "data"),
    prevent_initial_call=True,
)
def show_modal_archives(open_flag, creds):
    if not open_flag or not creds:
        return html.Div()
    data = get_cached_data(creds["email"], creds["key"])
    if not data: return html.Div()

    archived = [p for p in data["projects"] if p.get("archived")]
    def sort_key(p):
        try:
            return datetime.fromisoformat(p.get("endDate","").replace("Z","+00:00"))
        except:
            return datetime.min.replace(tzinfo=timezone.utc)

    archived.sort(key=sort_key, reverse=True)

    rows = []
    for p in archived:
        rows.append({
            "Projet":    p.get("name","?"),
            "Type":      p.get("type","?"),
            "Ville":     p.get("city","—") or "—",
            "Début":     fmt_date(p.get("startDate")),
            "Fin":       fmt_date(p.get("endDate")),
            "Base":      p.get("database","—"),
        })

    modal = html.Div([
        html.Div([
            html.Div([
                html.Div("Projets archivés", className="modal-title"),
                html.Div(f"{len(archived)} projets · triés par date de fin décroissante",
                         style={"fontSize":"0.78rem","color":C["text_muted"],"marginTop":"4px"}),
            ]),
            html.Button("✕", id="btn-close-archives", className="modal-close"),
        ], className="modal-header"),
        make_table(rows, page_size=20),
    ], className="modal-box")

    return html.Div([
        html.Div(id="modal-archives-bg", n_clicks=0, className="modal-backdrop"),
        modal,
    ], className="modal-overlay")

@app.callback(
    Output("store-modal-archives", "data"),
    Input("btn-open-archives", "n_clicks"),
    prevent_initial_call=True,
)
def open_archives(n):
    return True if n else False


app.clientside_callback(
    """
    function(n1, n2) {
        if (n1 || n2) return false;
        return window.dash_clientside.no_update;
    }
    """,
    Output("store-modal-archives", "data", allow_duplicate=True),
    Input("btn-close-archives", "n_clicks"),
    Input("modal-archives-bg",  "n_clicks"),
    prevent_initial_call=True,
)

@app.callback(
    Output({"type": "urgence-table", "section": dash.MATCH}, "children"),
    Input({"type": "urgence-search", "section": dash.MATCH}, "value"),
    State({"type": "urgence-rows",   "section": dash.MATCH}, "data"),
    prevent_initial_call=True,
)
def filter_urgence_table(query, rows):
    if not rows:
        return banner("Aucune donnée.", "info")
    if not query or not query.strip():
        return make_table(rows)
    q = query.strip().lower()
    filtered = [
        r for r in rows
        if any(q in str(v).lower() for v in r.values())
    ]
    if not filtered:
        return html.Div(
            f"Aucun résultat pour « {query} »",
            style={"color": C["text_muted"], "fontSize": "0.82rem", "padding": "12px 0"}
        )
    return make_table(filtered)

@app.callback(
    Output("store-capteur-selec", "data", allow_duplicate=True),
    Input({"type": "urgence-table", "section": dash.ALL}, "selected_rows"),
    State({"type": "urgence-rows",  "section": dash.ALL}, "data"),
    prevent_initial_call=True,
)
def select_capteur_urgence(all_selected, all_rows):
    for selected, rows in zip(all_selected, all_rows):
        if selected and rows and selected[0] < len(rows):
            return rows[selected[0]].get("_id")
    return dash.no_update

@app.callback(
    Output("store-capteur-selec", "data", allow_duplicate=True),
    Input("table-capteurs", "selected_rows"),
    State("store-capteur-rows", "data"),
    prevent_initial_call=True,
)
def select_capteur_tab(selected, rows):
    if selected and rows and selected[0] < len(rows):
        return rows[selected[0]].get("_id")
    return dash.no_update

@app.callback(
    Output("store-urgence-anchor", "data"),
    Output("active-tab", "data", allow_duplicate=True),
    Input({"type": "flag-badge", "anchor": dash.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def flag_clicked(n_clicks):
    if not any(n_clicks):
        return dash.no_update, dash.no_update
    triggered = ctx.triggered_id
    if not triggered:
        return dash.no_update, dash.no_update
    anchor = triggered.get("anchor")
    return anchor, "urgences"


app.clientside_callback(
    """
    function(anchor) {
        if (!anchor) return '';
        setTimeout(function() {
            var el = document.getElementById(anchor);
            if (el) {
                el.scrollIntoView({behavior: 'smooth', block: 'start'});
                el.style.outline = '2px solid #DC2626';
                setTimeout(function() { el.style.outline = ''; }, 2000);
            }
        }, 300);
        return '';
    }
    """,
    Output("scroll-trigger", "children"),
    Input("store-urgence-anchor", "data"),
    prevent_initial_call=True,
)


# ════════════════════════════════════════════════════════════
# SECTION 11 — POINT D'ENTREE
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)