from __future__ import annotations
from datetime import datetime


def compute_segments(projects, project_data, now, activity_sec, ending_days, past_days):

    def has_signal_today(p):
        trkrs = project_data.get(p.get("id",""), {}).get("trackers", [])
        return any(0 <= t.get("_last_seen_seconds", -1) < activity_sec for t in trkrs)

    archived, past, total, active, ending, anomalies = [], [], [], [], [], []

    for p in projects:
        end      = p.get("endDate")
        is_arch  = p.get("archived", False)
        end_diff = None

        if end:
            try:
                end_diff = (now - datetime.fromisoformat(end.replace("Z","+00:00"))).days
            except:
                pass

        if is_arch:
            archived.append(p)
            continue

        signal = has_signal_today(p)

        if end_diff is not None and end_diff > 0:
            past.append(p)
            if signal:
                active.append(p)
                anomalies.append(p)
            continue

        total.append(p)
        if signal:
            active.append(p)

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
        "anomalies": anomalies,
    }
