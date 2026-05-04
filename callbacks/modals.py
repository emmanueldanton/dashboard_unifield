from __future__ import annotations
from datetime import datetime, timezone
import dash
from dash import html, Output, Input, State

from config import C, PARIS_TZ, BATTERY_WARNING_THRESHOLD, ENDING_SOON_DAYS, PAST_DAYS
from cache import get_cached_data
from business.trackers import (health_score, battery_status, fmt_local,
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
        last_str  = fmt_local(last_seen, pdata.get("timezone","UTC"))

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
                stat("Dernière activité (Heure locale)", last_str),
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
            ts_str = fmt_local(str(ts), tracker.get("_project_tz","UTC")) if ts else "—"
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
                stat("Dernière activité (Heure locale)", fmt_local(tracker.get("lastUpdate",""), tracker.get("_project_tz","UTC"))),
                stat("Allumage ce matin",
                     fmt_local(boot_this_morning.isoformat(), tracker.get("_project_tz","UTC")) if boot_this_morning else "Non détecté"),
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

    @app.callback(
        Output("store-doc-open", "data"),
        Input("btn-open-doc", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_doc(n):
        return True if n else False

    @app.callback(
        Output("modal-container", "children", allow_duplicate=True),
        Input("store-doc-open", "data"),
        prevent_initial_call=True,
    )
    def show_modal_doc(open_flag):
        if not open_flag:
            return html.Div()

        def section(title, items):
            return html.Details([
                html.Summary(title, style={
                    "fontSize": "0.78rem", "fontWeight": "700",
                    "color": C["accent"], "cursor": "pointer",
                    "padding": "10px 0", "letterSpacing": "0.05em",
                    "textTransform": "uppercase",
                    "borderBottom": f"1px solid {C['border']}",
                    "listStyle": "none",
                }),
                html.Div([
                    html.Div([
                        html.Div(label, style={
                            "fontWeight": "600", "fontSize": "0.82rem",
                            "color": C["text"], "marginBottom": "2px"
                        }),
                        html.Div(desc, style={
                            "fontSize": "0.78rem", "color": C["text_muted"],
                            "lineHeight": "1.6"
                        }),
                    ], style={"marginBottom": "12px"})
                    for label, desc in items
                ], style={"padding": "12px 0"}),
            ], open=False, style={"marginBottom": "4px"})

        modal = html.Div([
            html.Div([
                html.Div([
                    html.Div("📖 Documentation", className="modal-title"),
                    html.Div("Logique des calculs et données affichées",
                            style={"fontSize":"0.78rem","color":C["text_muted"],"marginTop":"4px"}),
                ]),
                html.Button("✕", id="btn-close-doc", className="modal-close"),
            ], className="modal-header"),

            html.Div([

                section("KPIs — Vue d'ensemble", [
                    ("Projets actifs",
                    "Projets ayant au moins un capteur avec un lastUpdate récent depuis l'heure 'Activité depuis' configurée dans la sidebar. Calculé en heure de Paris."),
                    ("Fin imminente",
                    "Projets dont la date de fin (endDate) est dans moins de X jours. X = seuil 'Fin imminente' de la sidebar (défaut : 30 jours)."),
                    ("Projets terminés",
                    "Projets dont la date de fin est dépassée mais qui ne sont pas encore archivés dans UNIFIELD."),
                    ("Capteurs connectés",
                    "Capteurs dont le lastUpdate est inférieur au délai offline du projet (offlineDelay, souvent 60s). Le pourcentage représente la santé globale du parc."),
                    ("Batterie faible",
                    "Capteurs dont la tension (battery_volt) est sous le seuil configuré (défaut : 3.5V), ET ayant émis depuis l'heure 'Activité depuis'."),
                ]),

                section("Urgences", [
                    ("Capteurs inactifs pendant horaire",
                    "Capteurs déconnectés alors que : (1) le schedule du projet est actif en ce moment, (2) le capteur a émis aujourd'hui depuis 'Activité depuis', (3) le capteur a un peson fonctionnel (weight_status = ok)."),
                    ("Capteurs actifs hors horaire",
                    "Capteurs connectés ou ayant émis dans la dernière heure, alors que le schedule du projet indique que les équipements devraient être éteints."),
                    ("Batterie faible",
                    "Même logique que le KPI — capteurs avec battery_volt < seuil ET actifs depuis 'Activité depuis'. Les capteurs perdus depuis plusieurs jours sont exclus."),
                    ("Batterie inconnue",
                    "Capteurs dont le champ battery_volt est présent dans le message mais avec une valeur invalide ou absente."),
                    ("Peson inconnu",
                    "Capteurs dont le champ weight est présent dans le message mais avec une valeur invalide (< 0 ou absente)."),
                    ("Projets bientôt terminés",
                    "Projets dont la date de fin est dans moins de X jours (seuil configurable)."),
                    ("Projets terminés encore actifs",
                    "Projets dont la date de fin est dépassée mais qui ont encore des capteurs émettant aujourd'hui. Anomalie à investiguer."),
                ]),

                section("Scores de santé", [
                    ("Formule du score",
                    "Pour chaque capteur : +50 pts si connecté, +30 pts si batterie OK, +20 pts si poids mesuré. Score = moyenne des points / nombre de capteurs."),
                    ("Excellent (≥ 80%)", "Tous les capteurs connectés, batteries OK, poids mesurés."),
                    ("Bon (55–79%)",      "La majorité des capteurs fonctionne correctement."),
                    ("Moyen (30–54%)",    "Plusieurs capteurs déconnectés ou batteries faibles."),
                    ("Critique (< 30%)",  "La majorité des capteurs est en anomalie."),
                    ("Badges de flags",
                    "🔋 X batt. faible = Nombre de capteurs avec batterie faible ayant émis depuis 'Activité depuis'. 🕐 Hors schedule = actifs hors horaire. ⚠ Inactif = silencieux pendant les heures prévues."),
                ]),

                section("Projets", [
                    ("Actifs",
                    "Signal depuis l'heure 'Activité depuis'. Fenêtre calculée depuis minuit heure de Paris si schedule défini."),
                    ("Inactifs",
                    "Projets en cours mais sans signal depuis 'Activité depuis'."),
                    ("Fin imminente",
                    "endDate dans moins de X jours (seuil configurable)."),
                    ("Récemment terminés",
                    "endDate dépassée, non encore archivé. Hors du parc actif."),
                    ("Fuseau horaire",
                    "Détecté automatiquement via les coordonnées GPS du dernier lastTrack. Fallback sur UTC si aucun GPS disponible."),
                ]),

                section("Capteurs", [
                    ("Statut connecté",
                    "lastUpdate du capteur inférieur au offlineDelay du projet (souvent 60 secondes)."),
                    ("Dernière activité",
                    "lastUpdate converti en heure locale du projet (fuseau GPS détecté ou UTC)."),
                    ("Allumage ce matin",
                    "Premier event de type boot/connect/power_on détecté aujourd'hui pour ce capteur."),
                    ("Batterie (V)",
                    "Valeur battery_volt dans lastTrack.message."),
                    ("Peson batterie",
                    "Valeur shackle_battery dans lastTrack.message — batterie du peson lui-même."),
                    ("Poids (kg)",
                    "Valeur weight dans lastTrack.message."),
                    ("GPS",
                    "Coordonnées lat/lon de lastTrack. Cliquable vers Google Maps."),
                ]),

                section("Paramètres de la sidebar", [
                    ("Batterie faible (V)",
                    "Seuil de tension en dessous duquel un capteur est considéré en batterie faible. Défaut : 3.5V."),
                    ("Fin imminente (jours)",
                    "Nombre de jours avant la date de fin d'un projet pour déclencher l'alerte 'Fin imminente'. Défaut : 30 jours."),
                    ("Activité depuis",
                    "Heure de référence (heure de Paris) à partir de laquelle un capteur est considéré actif aujourd'hui. Défaut : 00:01. Exemple : 07:00 = seuls les capteurs ayant émis depuis 7h ce matin sont considérés actifs."),
                ]),

            ], style={"overflowY": "auto", "maxHeight": "65vh", "padding": "0 4px"}),

        ], className="modal-box", style={"maxWidth": "680px", "width": "90vw"})

        return html.Div([
            html.Div(id="modal-doc-bg", n_clicks=0, className="modal-backdrop"),
            modal,
        ], className="modal-overlay")

    app.clientside_callback(
        """
        function(n1, n2) {
            if (n1 || n2) return false;
            return window.dash_clientside.no_update;
        }
        """,
        Output("store-doc-open", "data", allow_duplicate=True),
        Input("btn-close-doc", "n_clicks"),
        Input("modal-doc-bg",  "n_clicks"),
        prevent_initial_call=True,
    )