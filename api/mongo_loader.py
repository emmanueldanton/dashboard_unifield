"""MongoDB loader — iso-interface with api/loader.py.

Output dict keys and all _* enrichments on trackers must match exactly the structure
produced by api/loader.py (which is the REST-based reference loader).

Loading in 2 phases:
  Phase 1 (light): all projects + all trackers from MongoDB
  Phase 2 (detail): units, events for ACTIVE projects only (archived=False AND endDate > now)
                    Trackers are associated to projects via units in Python — never via $lookup.

Field adaptation: MongoDB documents may differ from REST shapes.  The _adapt_tracker()
function normalises them so business/ functions always receive the expected structure.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

try:
    from timezonefinder import TimezoneFinder
    _tf = TimezoneFinder()
except Exception:
    _tf = None

from api.mongo_client import get_db
from business.trackers import is_connected, battery_status, battery_volt, weight_status, last_seen_seconds

log = logging.getLogger(__name__)

# ── Field adaptation ──────────────────────────────────────────────────────────

def _adapt_tracker(t: dict) -> dict:
    """Normalise a MongoDB tracker document to the shape expected by business/.

    The REST API always nests sensor readings inside lastTrack.message.
    MongoDB may store some readings at the top level (e.g. battery_volt).
    This function guarantees the nested structure exists.
    """
    t = dict(t)

    # Ensure lastTrack is a dict
    last_track = t.get("lastTrack")
    if not isinstance(last_track, dict):
        last_track = {}
    else:
        last_track = dict(last_track)

    # Ensure message sub-dict exists
    msg = last_track.get("message")
    if not isinstance(msg, dict):
        msg = {}
    else:
        msg = dict(msg)

    # Promote flat battery_volt → lastTrack.message.battery_volt if absent there
    if "battery_volt" not in msg and "battery_volt" in t:
        msg["battery_volt"] = t["battery_volt"]

    # Promote flat weight → lastTrack.message.weight if absent
    if "weight" not in msg and "weight" in t:
        msg["weight"] = t["weight"]

    last_track["message"] = msg
    t["lastTrack"] = last_track

    # Convert ObjectId / bson types to str so JSON serialisation works
    if "_id" in t:
        t["_id"] = str(t["_id"])

    return t


def _adapt_project(p: dict) -> dict:
    """Normalise a MongoDB project document (ObjectId → str, dates to ISO str)."""
    p = dict(p)
    if "_id" in p:
        p["_id"] = str(p["_id"])
    # Ensure date fields are ISO strings (may be datetime objects in MongoDB)
    for field in ("startDate", "endDate", "createdAt", "updatedAt"):
        v = p.get(field)
        if isinstance(v, datetime):
            p[field] = v.replace(tzinfo=timezone.utc).isoformat() if v.tzinfo is None else v.isoformat()
    return p


def _adapt_unit(u: dict) -> dict:
    u = dict(u)
    if "_id" in u:
        u["_id"] = str(u["_id"])
    return u


# ── QC structure ──────────────────────────────────────────────────────────────

def _empty_qc(total_projects: int) -> dict:
    return {
        "total_projects":         total_projects,
        "projects_loaded":        0,
        "projects_no_key":        0,
        "projects_empty":         0,
        "projects_with_data":     0,
        "units_total":            0,
        "units_no_tracker":       0,
        "trackers_total":         0,
        "trackers_no_lastupdate": 0,
        "trackers_no_lasttrack":  0,
        "trackers_duplicate_id":  0,
        "trackers_stale_24h":     0,
        "has_events":             False,
        "tracker_ids_unique":     0,
        "issues":                 [],
    }


# ── Active project filter ─────────────────────────────────────────────────────

def _is_active(p: dict, now: datetime) -> bool:
    if p.get("archived"):
        return False
    end = p.get("endDate")
    if not end:
        return True
    try:
        if isinstance(end, datetime):
            dt = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        return dt > now
    except Exception:
        return True


# ── Main loader ───────────────────────────────────────────────────────────────

def load_all_data(_email=None, _key=None) -> dict:  # noqa: ARG001 — kept for iso-interface
    """Load all data from MongoDB and return the canonical dict structure.

    Signature keeps (email, key) args for drop-in compatibility with api/loader.py;
    they are ignored — MongoDB credentials come from config.UNIFIELD_MONGO_URI.
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    # ── Phase 1: light bulk loads ─────────────────────────────────────────────
    raw_projects = [_adapt_project(p) for p in db["projects"].find({}, {"_id": 1, "id": 1, "name": 1,
        "code": 1, "type": 1, "archived": 1, "startDate": 1, "endDate": 1,
        "offlineDelay": 1, "accessKey": 1, "schedule": 1, "database": 1,
        "description": 1, "city": 1})]

    if not raw_projects:
        log.warning('{"event": "mongo_refresh_failed", "reason": "no_projects"}')
        return {
            "projects": [], "project_data": {}, "all_units": [],
            "all_trackers": [], "all_events": [], "qc": {}, "loaded_at": None,
        }

    # Build a global tracker map (id → document) from a single collection scan
    tracker_map: dict[str, dict] = {}
    for raw_t in db["trackers"].find():
        t = _adapt_tracker(raw_t)
        tid = t.get("id") or t.get("uuid") or str(t.get("_id", ""))
        if tid:
            tracker_map[tid] = t

    qc = _empty_qc(len(raw_projects))

    # ── Phase 2: per-project detail (active projects only) ────────────────────
    project_data: dict[str, dict] = {}
    all_units:    list[dict] = []
    all_trackers: list[dict] = []
    all_events:   list[dict] = []

    active_pids = {
        p.get("id", str(p.get("_id", ""))): p
        for p in raw_projects if _is_active(p, now)
    }

    for p in raw_projects:
        pid  = p.get("id") or str(p.get("_id", ""))
        name = p.get("name", "?")

        if not pid:
            continue

        if p.get("archived") and pid not in active_pids:
            qc["projects_loaded"] += 1
            project_data[pid] = {"units": [], "trackers": [], "events": [], "timezone": "UTC",
                                 "qc_local": {"archived": True}}
            continue

        if pid not in active_pids:
            # endDate in the past — treat like archived for project_data
            qc["projects_loaded"] += 1
            project_data[pid] = {"units": [], "trackers": [], "events": [], "timezone": "UTC",
                                 "qc_local": {"archived": True}}
            continue

        offline_delay = int(p.get("offlineDelay") or 60)

        # Load units for this project
        units_raw = [_adapt_unit(u) for u in db["units"].find({"projectId": pid})]
        if not units_raw:
            # Try alternate projectId field conventions
            units_raw = [_adapt_unit(u) for u in db["units"].find({"project_id": pid})]

        qc["projects_loaded"] += 1

        if not units_raw:
            qc["projects_empty"] += 1
            project_data[pid] = {"units": [], "trackers": [], "events": [], "timezone": "UTC",
                                 "qc_local": {"empty": True}}
            continue

        qc["projects_with_data"] += 1

        # Events for this project
        proj_events: list[dict] = []
        ev_cursor = db["events"].find({"projectId": pid}, limit=50)
        for e in ev_cursor:
            ev = dict(e)
            if "_id" in ev:
                ev["_id"] = str(ev["_id"])
            ev["_project_name"] = name
            ev["_project_id"]   = pid
            proj_events.append(ev)
        if proj_events:
            qc["has_events"] = True

        # Associate trackers to units — in Python, no $lookup
        local_units: list[dict] = []
        local_trackers: list[dict] = []
        local_qc: dict = {
            "units": len(units_raw), "units_no_tracker": 0, "trackers": 0,
            "trackers_no_lastupdate": 0, "trackers_no_lasttrack": 0,
            "trackers_duplicate": 0, "trackers_stale": 0,
        }
        seen_ids: set[str] = set()

        for u in units_raw:
            uid       = u.get("id") or str(u.get("_id", ""))
            unit_name = u.get("name", "?")
            tr_refs   = u.get("trackers", [])

            local_units.append({
                **u,
                "_project_id":    pid,
                "_project_name":  name,
                "_offline_delay": offline_delay,
            })

            if not tr_refs:
                local_qc["units_no_tracker"] += 1
                continue

            for ref in tr_refs:
                # ref may be an id string or a partial tracker dict
                if isinstance(ref, dict):
                    tid = ref.get("id") or ref.get("uuid", "")
                    t = tracker_map.get(tid, ref)
                else:
                    tid = str(ref)
                    t = tracker_map.get(tid)
                    if t is None:
                        continue

                t = dict(t)

                if tid:
                    if tid in seen_ids:
                        local_qc["trackers_duplicate"] += 1
                    else:
                        seen_ids.add(tid)

                if not t.get("lastUpdate"):
                    local_qc["trackers_no_lastupdate"] += 1
                if not t.get("lastTrack"):
                    local_qc["trackers_no_lasttrack"] += 1

                lu = t.get("lastUpdate")
                if lu:
                    try:
                        lu_str = lu if isinstance(lu, str) else lu.isoformat()
                        dt = datetime.fromisoformat(lu_str.replace("Z", "+00:00"))
                        if (now - dt).total_seconds() > 86400:
                            local_qc["trackers_stale"] += 1
                    except Exception:
                        pass

                enriched = {
                    **t,
                    "_unit_id":          uid,
                    "_unit_name":        unit_name,
                    "_project_id":       pid,
                    "_project_name":     name,
                    "_offline_delay":    offline_delay,
                    "_is_connected":     is_connected(t, offline_delay),
                    "_battery_status":   battery_status(t),
                    "_battery_volt":     battery_volt(t),
                    "_weight_status":    weight_status(t),
                    "_last_seen_seconds": last_seen_seconds(t),
                }
                local_trackers.append(enriched)
                local_qc["trackers"] += 1

        # Timezone detection (same logic as REST loader)
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

        for t in local_trackers:
            t["_project_tz"] = proj_tz

        # Accumulate QC
        qc["units_total"]             += len(local_units)
        qc["units_no_tracker"]        += local_qc["units_no_tracker"]
        qc["trackers_total"]          += local_qc["trackers"]
        qc["trackers_no_lastupdate"]  += local_qc["trackers_no_lastupdate"]
        qc["trackers_no_lasttrack"]   += local_qc["trackers_no_lasttrack"]
        qc["trackers_duplicate_id"]   += local_qc["trackers_duplicate"]
        qc["trackers_stale_24h"]      += local_qc["trackers_stale"]
        for tid in seen_ids:
            pass  # count below
        qc["tracker_ids_unique"] = qc.get("tracker_ids_unique", 0) + len(seen_ids)

        project_data[pid] = {
            "units":     local_units,
            "trackers":  local_trackers,
            "events":    proj_events,
            "timezone":  proj_tz,
            "qc_local":  local_qc,
        }
        all_units.extend(local_units)
        all_trackers.extend(local_trackers)
        all_events.extend(proj_events)

    log.info('{"event": "mongo_refresh_ok", "projects": %d, "trackers": %d}',
             qc["projects_loaded"], qc["trackers_total"])

    return {
        "projects":     raw_projects,
        "project_data": project_data,
        "all_units":    all_units,
        "all_trackers": all_trackers,
        "all_events":   all_events,
        "qc":           qc,
        "loaded_at":    now.isoformat(),
    }
