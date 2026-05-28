from __future__ import annotations
from datetime import datetime, timezone
from dash import html

from config import ACTIVITY_WINDOW_SECONDS
from business.trackers import battery_status, fmt_date
from business.schedule import check_schedule_anomalies
from business.segments import compute_segments
from ui.components import banner, collapsible, make_table_searchable, build_tracker_rows


def render_urgences(data, bt, ending_days, past_days):
    now          = datetime.now(timezone.utc)
    activity_sec = ACTIVITY_WINDOW_SECONDS
    segs = compute_segments(data["projects"], data["project_data"], now,
                            activity_sec, ending_days, past_days)
    from business.trackers import _msg

    all_t = data["all_trackers"]

    battery_low = [t for t in all_t
                   if battery_status(t, bt) == "faible"
                   and (t.get("_is_connected", False)
                        or 0 <= t.get("_last_seen_seconds", -1) < 86400)]

    battery_unk = [t for t in all_t
                   if battery_status(t, bt) == "inconnu"
                   and "battery_volt" in _msg(t)]

    weight_unk  = [t for t in all_t
                   if t.get("_weight_status") == "inconnu"
                   and "weight" in _msg(t)
                   and (t.get("_is_connected", False)
                        or 0 <= t.get("_last_seen_seconds", -1) < 86400)]

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
        _proj_tz = data["project_data"].get(_p.get("id",""), {}).get("timezone", "UTC")
        _hs, _mq = check_schedule_anomalies(
            _trkrs, _p.get("schedule", {}), now, _proj_tz
        )
        all_hors.extend(_hs)
        all_manquants.extend(_mq)

    anomalies = segs.get("anomalies", [])
    anomalie_rows = [{
        "Projet":   p.get("name","?"),
        "Type":     p.get("type","?"),
        "Date fin": fmt_date(p.get("endDate")),
        "Capteurs": len(data["project_data"].get(p.get("id"),{}).get("trackers",[])),
    } for p in anomalies]

    nb_urg = (len(battery_low) + len(ending_rows) + len(all_hors) + len(all_manquants) + len(anomalies))

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

        collapsible("Capteurs inactifs pendant horaire", len(all_manquants),
            make_table_searchable(mq_rows, "inactif_schedule") if mq_rows
            else banner("Tous les capteurs actifs pendant les heures prévues.", "ok"),
            tone="warn" if all_manquants else None),

        collapsible("Capteurs actifs hors horaire", len(all_hors),
            make_table_searchable(hors_rows, "hors_schedule") if hors_rows
            else banner("Aucun capteur actif hors des heures prévues.", "ok"),
            tone="warn" if all_hors else None),
        
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


        collapsible("Projets bientôt terminés", len(ending_rows),
            make_table_searchable(ending_rows, "fin_imminente") if ending_rows
            else banner("Aucun projet ne se termine dans les prochains jours.", "ok"),
            tone="warn" if ending_rows else None),

        collapsible("Projets terminés encore actifs", len(anomalies),
            make_table_searchable(anomalie_rows, "proj_termines_actifs") if anomalies
            else banner("Aucun projet terminé avec capteurs encore actifs.", "ok"),
            tone="warn" if anomalies else None),

    ], className="tab-content-anim")
