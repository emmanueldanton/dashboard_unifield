from __future__ import annotations
from dash import html

from config import PARIS_TZ
from business.trackers import battery_status, age_full
from business.schedule import parse_schedule, is_time_in_schedule


def compute_project_flags(p, trkrs, now, bt):
    schedule  = p.get("schedule", {})
    parsed    = parse_schedule(schedule)
    paris_now = now.astimezone(PARIS_TZ)

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

    hors_details    = []
    inactif_details = []

    if parsed is not None:
        in_schedule_now = is_time_in_schedule(paris_now, parsed)

        days_order = ["mon","tue","wed","thu","fri","sat","sun"]
        day_key    = days_order[paris_now.weekday()]
        day_cfg    = parsed.get(day_key, {})
        times      = day_cfg.get("times", [])
        plage_str  = (" / ".join(f"{s[0]}-{s[1]}" for s in times if len(s) >= 2)
                      if times else "?")

        for t in trkrs:
            connected = t.get("_is_connected", False)
            last_sec  = t.get("_last_seen_seconds", -1)
            name      = t.get("name", "?")

            if in_schedule_now:
                if not connected:
                    duree = age_full(t.get("lastUpdate", ""))
                    inactif_details.append(
                        f"{name} — absent depuis {duree} (plage {plage_str})"
                    )
            else:
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
