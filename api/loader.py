from __future__ import annotations
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from datetime import datetime, timezone

try:
    from timezonefinder import TimezoneFinder
    _tf = TimezoneFinder()
except Exception:
    _tf = None

from config import API_BASE, MAX_WORKERS
from api.client import safe_get, user_headers, project_headers, _load_log, _load_log_lock
from business.trackers import is_connected, battery_status, battery_volt, weight_status, last_seen_seconds


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

    qc["tracker_ids_unique"] = len(qc["tracker_ids_seen"])
    del qc["tracker_ids_seen"]

    return {"projects":all_proj,"project_data":project_data,"all_units":all_units,
            "all_trackers":all_trackers,"all_events":all_events,"qc":qc,
            "loaded_at":datetime.now(timezone.utc).isoformat()}
