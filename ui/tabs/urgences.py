from __future__ import annotations
from datetime import datetime, timezone
from dash import html

from config import PARIS_TZ
from business.trackers import battery_status, fmt_date
from business.schedule import check_schedule_anomalies
from business.segments import compute_segments
from ui.components import banner, collapsible, make_table_searchable, build_tracker_rows


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

    from business.trackers import _msg
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
