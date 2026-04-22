from __future__ import annotations
from config import PARIS_TZ


def parse_schedule(schedule):
    if not schedule:
        return None

    days_order = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    result = {}
    has_real_schedule = False

    for day in days_order:
        cfg = schedule.get(day, {})

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

        elif isinstance(cfg, list) and len(cfg) >= 2:
            enable = str(cfg[2]).lower() == "true" if len(cfg) > 2 else True
            times  = [[cfg[0], cfg[1]]] if cfg[0] and cfg[1] else []
            is_h24 = len(cfg) >= 2 and cfg[0] == "00:00" and cfg[1] in ("23:59", "24:00")
            if enable and times and not is_h24:
                has_real_schedule = True
            result[day] = {"enable": enable, "times": times, "h24": is_h24}

        else:
            result[day] = {"enable": False, "times": [], "h24": False}

    return result if has_real_schedule else None


def is_time_in_schedule(dt_paris, parsed_schedule):
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
    parsed = parse_schedule(schedule)
    if parsed is None:
        return [], []

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
            if connected or (0 <= last_sec < 3600):
                hors_schedule.append(t)

    return hors_schedule, manquants
