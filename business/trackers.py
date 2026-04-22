from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import BATTERY_WARNING_THRESHOLD, PARASITE_KEYWORDS, PARIS_TZ


def filter_data(data):
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


def fmt_paris(date_str):
    if not date_str:
        return "Jamais"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.astimezone(PARIS_TZ).strftime("%d/%m/%Y %H:%M")
    except:
        return "?"
