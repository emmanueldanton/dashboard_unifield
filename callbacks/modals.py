from __future__ import annotations
from datetime import datetime, timezone
import dash
from dash import html, Output, Input, State

from config import C, PARIS_TZ, BATTERY_WARNING_THRESHOLD, ENDING_SOON_DAYS, PAST_DAYS
from cache import get_cached_data
from business.trackers import (health_score, battery_status, fmt_paris,
                                fmt_date, fmt_tz, _msg)
from business.segments import compute_segments
from ui.components import section_label, make_table, build_tracker_rows


def register(app):

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

        def fmt_schedule(schedule):
            if not schedule:
                return "Non défini"
            days_fr = {"mon":"Lun","tue":"Mar","wed":"Mer",
                       "thu":"Jeu","fri":"Ven","sat":"Sam","sun":"Dim"}
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
        State("store-creds",  "data"),
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

        tracker = next(
            (t for t in data["all_trackers"]
             if t.get("id") == tracker_id or t.get("uuid") == tracker_id),
            None
        )
        if not tracker: return dash.no_update

        bt      = (seuils or {}).get("bt", BATTERY_WARNING_THRESHOLD)
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

        all_events = data.get("all_events", [])
        proj_id    = tracker.get("_project_id", "")

        capteur_events = []
        boot_keywords  = ["boot","start","connect","online","power","init",
                          "wake","restart","reboot","activate"]
        boot_this_morning = None

        for e in all_events:
            if e.get("_project_id") != proj_id:
                continue
            e_trackers = e.get("trackers", [])
            if e_trackers and tracker_id not in [
                (tr if isinstance(tr, str) else tr.get("id","")) for tr in e_trackers
            ]:
                continue
            capteur_events.append(e)

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

        gps_content = "—"
        if lat and lon:
            maps_url = f"https://www.google.com/maps?q={lat},{lon}"
            gps_content = html.A(
                f"{round(lat,5)}, {round(lon,5)} 📍",
                href=maps_url, target="_blank",
                style={"color": C["accent"], "fontWeight": "600",
                       "textDecoration": "none", "fontSize": "0.82rem"}
            )

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

            section_label(f"Historique events — {len(capteur_events)} trouvé(s)"),
            make_table(event_rows) if event_rows
            else html.Div("Aucun event trouvé pour ce capteur.",
                          style={"color":C["text_muted"],"fontSize":"0.82rem","padding":"12px 0"}),

        ], className="modal-box")

        return html.Div([
            html.Div(id="modal-capteur-bg", n_clicks=0, className="modal-backdrop"),
            modal,
        ], className="modal-overlay")

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
                "Projet": p.get("name","?"),
                "Type":   p.get("type","?"),
                "Ville":  p.get("city","—") or "—",
                "Début":  fmt_date(p.get("startDate")),
                "Fin":    fmt_date(p.get("endDate")),
                "Base":   p.get("database","—"),
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
