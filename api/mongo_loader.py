"""MongoDB loader — iso-interface with api/loader.py.

Architecture réelle : 1 base MongoDB = 1 projet (pattern NNNN_slug).
Pas de base centrale — découverte automatique de toutes les bases avec trackers.

Phase 1 : toutes les bases NNNN_* — trackers + lastTrack résolu + enrichissements
          → marque chaque base "active" si lastUpdate d'au moins un tracker < 30s
Phase 2 : bases actives seulement — units, events, association tracker↔unit (in-place)

Output dict keys and all _* enrichments must match api/loader.py exactly.
"""
from __future__ import annotations
import re
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

# Pattern des bases projets : NNNN_slug (ex: 0382_eiffaget)
_DB_PATTERN = re.compile(r'^\d+_')

# Délai offline par défaut en secondes (1 heure)
_DEFAULT_OFFLINE_DELAY = 3600

# Seuil d'activité : tracker "actif" si lastUpdate émis il y a moins de N secondes
ACTIVE_TRACKER_SECONDS = 30


# ── Adaptateurs ──────────────────────────────────────────────────────────────

def _dt_to_iso(v) -> str | None:
    """Convertit un datetime MongoDB (naïf ou aware) en ISO string."""
    if v is None:
        return None
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat()
    return str(v)


def _oid_to_str(v) -> str:
    """Convertit un ObjectId ou tout objet en string."""
    return str(v) if v is not None else ""


def _adapt_tracker(raw: dict, resolved_last_track: dict | None) -> dict:
    """Normalise un document tracker MongoDB vers la structure attendue par business/."""
    t = dict(raw)

    t["_id"]  = _oid_to_str(t.get("_id"))
    t["uuid"] = t.get("uuid") or t["_id"]
    t["lastUpdate"] = _dt_to_iso(t.get("lastUpdate"))

    last_track = resolved_last_track or {}
    msg = last_track.get("message")
    if not isinstance(msg, dict):
        msg = {}

    # Fallback batteryLevel (%) → battery_volt approximatif si absent dans message
    if "battery_volt" not in msg:
        pct = t.get("batteryLevel", -1)
        if isinstance(pct, (int, float)) and pct >= 0:
            msg["battery_volt"] = round(3.0 + (pct / 100) * 1.2, 2)

    t["lastTrack"] = {**last_track, "message": msg}

    for field in ("project", "config"):
        if field in t and not isinstance(t[field], str):
            t[field] = _oid_to_str(t[field])

    return t


def _adapt_unit(raw: dict) -> dict:
    u = dict(raw)
    u["_id"]      = _oid_to_str(u.get("_id"))
    u["trackers"] = [_oid_to_str(ref) for ref in u.get("trackers", [])]
    for field in ("startDate", "lastUpdate", "createdDate"):
        if field in u:
            u[field] = _dt_to_iso(u[field])
    return u


def _adapt_event(raw: dict, pid: str, name: str) -> dict:
    e = dict(raw)
    e["_id"]          = _oid_to_str(e.get("_id"))
    e["_project_id"]   = pid
    e["_project_name"] = name
    for field in ("startDate", "endDate", "createdDate"):
        if field in e:
            e[field] = _dt_to_iso(e[field])
    e["trackers"] = [_oid_to_str(r) for r in e.get("trackers", [])]
    e["units"]    = [_oid_to_str(r) for r in e.get("units", [])]
    return e


# ── Critère d'activité ────────────────────────────────────────────────────────

def _has_active_tracker(trackers: list[dict], now: datetime) -> bool:
    """True si au moins un tracker a émis dans les ACTIVE_TRACKER_SECONDS."""
    for t in trackers:
        lu = t.get("lastUpdate")
        if not lu:
            continue
        try:
            dt = datetime.fromisoformat(str(lu).replace("Z", "+00:00"))
            if (now - dt).total_seconds() <= ACTIVE_TRACKER_SECONDS:
                return True
        except Exception:
            pass
    return False


# ── QC structure ─────────────────────────────────────────────────────────────

def _empty_qc(total: int) -> dict:
    return {
        "total_projects":         total,
        "projects_loaded":        0,
        "projects_active":        0,
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


# ── Phase 1 : trackers de toutes les bases ────────────────────────────────────

def _phase1_load_trackers(
    client, dbname: str, now: datetime,
) -> tuple[dict, dict, bool] | None:
    """Charge les trackers d'une base projet (sans units ni events).

    Returns (project_meta, tracker_map, is_active) ou None si la base est ignorée.
    tracker_map : {str(_id): tracker adapté + enrichissements business}
    is_active   : True si au moins un tracker a lastUpdate < ACTIVE_TRACKER_SECONDS
    """
    db = client[dbname]

    try:
        cols = set(db.list_collection_names())
    except Exception as exc:
        log.warning('{"event": "mongo_db_skip", "db": "%s", "reason": "%s"}', dbname, exc)
        return None

    if "trackers" not in cols:
        return None

    try:
        raw_trackers = list(db["trackers"].find(
            {},
            {"uuid": 1, "name": 1, "type": 1, "version": 1,
             "lastTrack": 1, "lastUpdate": 1, "batteryLevel": 1,
             "project": 1, "description": 1, "comment": 1}
        ))
    except Exception:
        return None

    if not raw_trackers:
        return None

    parts = dbname.split("_", 1)
    code  = parts[0]
    slug  = parts[1] if len(parts) > 1 else dbname
    pid   = dbname
    name  = slug
    offline_delay = _DEFAULT_OFFLINE_DELAY

    project_meta = {
        "id":           pid,
        "name":         name,
        "code":         code,
        "archived":     False,
        "offlineDelay": offline_delay,
        "startDate":    None,
        "endDate":      None,
        "type":         "construction",
        "city":         "",
        "description":  "",
        "schedule":     {},
        "database":     dbname,
    }

    # Résolution batch lastTrack ObjectId → document tracks
    last_track_oids = [
        t["lastTrack"] for t in raw_trackers
        if t.get("lastTrack") and not isinstance(t.get("lastTrack"), dict)
    ]
    tracks_by_id: dict[str, dict] = {}
    if last_track_oids and "tracks" in cols:
        try:
            for tr in db["tracks"].find({"_id": {"$in": last_track_oids}}):
                tracks_by_id[str(tr["_id"])] = tr
        except Exception as exc:
            log.debug('{"event": "tracks_lookup_failed", "db": "%s", "err": "%s"}', dbname, exc)

    # Construire tracker_map avec enrichissements business
    tracker_map: dict[str, dict] = {}
    for raw_t in raw_trackers:
        lt_ref = raw_t.get("lastTrack")
        if lt_ref and not isinstance(lt_ref, dict):
            resolved = tracks_by_id.get(str(lt_ref))
        elif isinstance(lt_ref, dict):
            resolved = lt_ref
        else:
            resolved = None

        t = _adapt_tracker(raw_t, resolved)

        # Champs projet et unité (unité inconnue en Phase 1)
        t["_project_id"]        = pid
        t["_project_name"]      = name
        t["_offline_delay"]     = offline_delay
        t["_unit_id"]           = ""
        t["_unit_name"]         = "—"
        t["_project_tz"]        = "UTC"
        t["_is_connected"]      = is_connected(t, offline_delay)
        t["_battery_status"]    = battery_status(t)
        t["_battery_volt"]      = battery_volt(t)
        t["_weight_status"]     = weight_status(t)
        t["_last_seen_seconds"] = last_seen_seconds(t)

        oid_str = _oid_to_str(raw_t.get("_id"))
        if oid_str:
            tracker_map[oid_str] = t

    is_active = _has_active_tracker(list(tracker_map.values()), now)
    return project_meta, tracker_map, is_active


# ── Phase 2 : détail des bases actives ───────────────────────────────────────

def _phase2_load_details(
    client, dbname: str, pid: str, name: str,
    tracker_map: dict[str, dict], offline_delay: int,
    now: datetime, qc: dict,
) -> dict:
    """Charge units + events et enrichit tracker_map in-place (_unit_id, _unit_name, _project_tz).

    Retourne project_data : {units, trackers, events, timezone, qc_local}
    """
    db = client[dbname]
    try:
        cols = set(db.list_collection_names())
    except Exception:
        cols = set()

    # Charger les units
    units_raw: list[dict] = []
    if "units" in cols:
        try:
            units_raw = [_adapt_unit(u) for u in db["units"].find(
                {},
                {"name": 1, "type": 1, "trackers": 1, "startDate": 1,
                 "lastUpdate": 1, "status": 1, "schedule": 1}
            )]
        except Exception:
            pass

    # Charger les events (50 max)
    proj_events: list[dict] = []
    if "events" in cols:
        try:
            for e in db["events"].find({}, limit=50):
                proj_events.append(_adapt_event(e, pid, name))
        except Exception:
            pass

    # Association trackers → units (mutation in-place sur tracker_map)
    local_units: list[dict] = []
    seen_oids: set[str] = set()
    local_qc = {
        "units": len(units_raw), "units_no_tracker": 0, "trackers": 0,
        "trackers_no_lastupdate": 0, "trackers_no_lasttrack": 0,
        "trackers_duplicate": 0, "trackers_stale": 0,
    }

    for u in units_raw:
        uid       = u.get("_id", "")
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

        for ref_str in tr_refs:
            t = tracker_map.get(ref_str)
            if t is None:
                continue

            if ref_str in seen_oids:
                local_qc["trackers_duplicate"] += 1
            else:
                seen_oids.add(ref_str)
                t["_unit_id"]   = uid
                t["_unit_name"] = unit_name

            if not t.get("lastUpdate"):
                local_qc["trackers_no_lastupdate"] += 1
            if not t.get("lastTrack"):
                local_qc["trackers_no_lasttrack"] += 1

            lu = t.get("lastUpdate")
            if lu:
                try:
                    dt = datetime.fromisoformat(lu.replace("Z", "+00:00"))
                    if (now - dt).total_seconds() > 86400:
                        local_qc["trackers_stale"] += 1
                except Exception:
                    pass

            local_qc["trackers"] += 1

    # Tous les trackers de la base (avec et sans unité)
    all_local_trackers = list(tracker_map.values())

    # Détection de timezone (coordonnées validées avant appel)
    proj_tz = "UTC"
    if _tf:
        for t in all_local_trackers:
            lt = t.get("lastTrack") or {}
            lat, lon = lt.get("lat"), lt.get("lon")
            if (lat and lon
                    and -90 <= lat <= 90
                    and -180 <= lon <= 180):
                tz = _tf.timezone_at(lat=lat, lng=lon)
                if tz:
                    proj_tz = tz
                    break

    for t in all_local_trackers:
        t["_project_tz"] = proj_tz

    # Mise à jour QC global
    qc["projects_loaded"]        += 1
    qc["units_total"]            += len(local_units)
    qc["units_no_tracker"]       += local_qc["units_no_tracker"]
    qc["trackers_total"]         += local_qc["trackers"]
    qc["trackers_no_lastupdate"] += local_qc["trackers_no_lastupdate"]
    qc["trackers_no_lasttrack"]  += local_qc["trackers_no_lasttrack"]
    qc["trackers_duplicate_id"]  += local_qc["trackers_duplicate"]
    qc["trackers_stale_24h"]     += local_qc["trackers_stale"]
    qc["tracker_ids_unique"]     += len(seen_oids)
    if proj_events:
        qc["has_events"] = True
    if all_local_trackers:
        qc["projects_with_data"] += 1
    else:
        qc["projects_empty"] += 1

    return {
        "units":    local_units,
        "trackers": all_local_trackers,
        "events":   proj_events,
        "timezone": proj_tz,
        "qc_local": local_qc,
    }


# ── Loader principal ──────────────────────────────────────────────────────────

def load_all_data(_email=None, _key=None) -> dict:
    """Charge toutes les données depuis MongoDB (multi-base) — chargement en 2 phases.

    Phase 1 : tous les NNNN_* → trackers uniquement, détection bases actives (< 30s)
    Phase 2 : bases actives seulement → units, events, association tracker↔unit

    Signature conserve (email, key) pour compatibilité drop-in avec api/loader.py.
    """
    client = get_db().client
    now    = datetime.now(timezone.utc)

    try:
        all_dbs = client.list_database_names()
    except Exception as exc:
        log.error('{"event": "mongo_refresh_failed", "reason": "list_databases", "error": "%s"}', exc)
        return {
            "projects": [], "project_data": {}, "all_units": [],
            "all_trackers": [], "all_events": [], "qc": {}, "loaded_at": None,
        }

    project_dbs = [db for db in all_dbs if _DB_PATTERN.match(db)]
    qc = _empty_qc(len(project_dbs))

    # ── Phase 1 : trackers de toutes les bases ────────────────────────────────
    phase1: list[tuple[dict, dict, bool]] = []
    for dbname in project_dbs:
        try:
            result = _phase1_load_trackers(client, dbname, now)
        except Exception as exc:
            log.warning('{"event": "phase1_error", "db": "%s", "error": "%s"}', dbname, exc)
            continue
        if result is not None:
            phase1.append(result)

    active_count   = sum(1 for _, _, active in phase1 if active)
    inactive_count = len(phase1) - active_count
    log.info(
        '{"event": "phase1_done", "dbs_scanned": %d, "with_trackers": %d, "active": %d, "inactive": %d}',
        len(project_dbs), len(phase1), active_count, inactive_count,
    )
    qc["projects_active"] = active_count

    # ── Phase 2 : détails des bases actives ───────────────────────────────────
    projects:     list[dict] = []
    project_data: dict       = {}
    all_events:   list[dict] = []

    for project_meta, tracker_map, is_active in phase1:
        projects.append({**project_meta, "active": is_active})

        if not is_active:
            continue

        pid          = project_meta["id"]
        name         = project_meta["name"]
        offline_delay = project_meta["offlineDelay"]

        try:
            pdata = _phase2_load_details(
                client, pid, pid, name, tracker_map, offline_delay, now, qc,
            )
        except Exception as exc:
            log.warning('{"event": "phase2_error", "db": "%s", "error": "%s"}', pid, exc)
            continue

        project_data[pid] = pdata
        all_events.extend(pdata["events"])

    # ── Flatten all_trackers (toutes bases, enrichis par Phase 2 si active) ───
    all_trackers: list[dict] = []
    all_units:    list[dict] = []
    for _, tracker_map, _ in phase1:
        all_trackers.extend(tracker_map.values())
    for pdata in project_data.values():
        all_units.extend(pdata["units"])

    log.info(
        '{"event": "mongo_refresh_ok", "dbs_scanned": %d, "active": %d, "trackers_total": %d, "units": %d}',
        len(project_dbs), active_count, len(all_trackers), len(all_units),
    )

    return {
        "projects":     projects,
        "project_data": project_data,
        "all_units":    all_units,
        "all_trackers": all_trackers,
        "all_events":   all_events,
        "qc":           qc,
        "loaded_at":    now.isoformat(),
    }
