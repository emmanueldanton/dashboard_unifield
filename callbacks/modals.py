from __future__ import annotations
from datetime import datetime, timezone
import dash
from dash import html, Output, Input, State

from config import C, PARIS_TZ, BATTERY_WARNING_THRESHOLD, ENDING_SOON_DAYS, PAST_DAYS, ACTIVITY_WINDOW_SECONDS
from cache import get_cached_data
from business.trackers import (health_score, battery_status, fmt_local,
                                fmt_date, fmt_tz, _msg, score_class, score_label)
from business.flags import compute_project_flags
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
        data = get_cached_data(creds.get("email"), creds.get("key", ""))
        if not data: return html.Div()

        if not seuils:
            seuils = {"bt": BATTERY_WARNING_THRESHOLD, "ed": ENDING_SOON_DAYS}
        bt  = seuils.get("bt", BATTERY_WARNING_THRESHOLD)
        ed  = seuils.get("ed", ENDING_SOON_DAYS)
        now = datetime.now(timezone.utc)
        segs = compute_segments(data["projects"], data["project_data"],
                                now, ACTIVITY_WINDOW_SECONDS, ed, PAST_DAYS)

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

        flags = compute_project_flags(p, trkrs, now, bt)
        d     = flags["details"]

        _COLOR = {
            "excellent": C["green"],  "good": C["accent"],
            "medium":    C["orange"], "bad":  C["red"], "empty": C["text_light"],
        }
        _BG = {
            "excellent": C["green_bg"],  "good": C["accent_bg"],
            "medium":    C["orange_bg"], "bad":  C["red_bg"], "empty": C["bg"],
        }
        cls = score_class(score)

        def flag_pill(label, count, color):
            if not count:
                return html.Span()
            return html.Span(f"{label} {count}", style={
                "background": color, "color": "#fff",
                "fontSize": "0.68rem", "fontWeight": "700",
                "padding": "3px 9px", "borderRadius": "20px",
                "marginRight": "4px", "display": "inline-block",
            })

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
                    lines.append(f"{day_fr} - Fermé")
                elif times:
                    is_h24 = any(
                        s[0] == "00:00" and s[1] in ("23:59","24:00")
                        for s in times if len(s) >= 2
                    )
                    plages = " / ".join(f"{s[0]}–{s[1]}" for s in times if len(s) >= 2)
                    lines.append(f"{day_fr} - {'24h/24' if is_h24 else plages}")
                else:
                    lines.append(f"{day_fr} - Toute la journée")
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
                stat("Statut",   statut),
                stat("Type",     p.get("type", "-")),
                stat("Ville",    p.get("city", "-") or "-"),
                stat("Fuseau",   fmt_tz(pdata.get("timezone", "UTC"))),
                stat("Délai offline", f"{delay}s"),
                stat("Capteurs", len(trkrs)),
                stat("Connectés", conn),
                stat("Déconnectés", disc),
                stat("Batt. faible", bat_l),
                stat("Début",    fmt_date(p.get("startDate"))),
                stat("Fin",      fmt_date(p.get("endDate"))),
                stat("Dernière activité (Heure locale)", last_str),

                # Score avec barre visuelle
                html.Div([
                    html.Div("Score santé", className="modal-stat-label"),
                    html.Div([
                        html.Span(f"{score}%", style={
                            "fontWeight": "700", "color": _COLOR[cls], "fontSize": "1.05rem",
                        }),
                        html.Span(f" - {score_label(score)}", style={
                            "fontSize": "0.78rem", "color": C["text_muted"], "marginLeft": "6px",
                        }),
                        html.Div(className="score-track", style={"marginTop": "6px"}, children=[
                            html.Div(className="score-fill",
                                     style={"width": f"{score}%", "background": _COLOR[cls]}),
                        ]),
                    ]),
                ], className="modal-stat", style={"gridColumn": "1 / -1"}),

                # Alertes actives
                html.Div([
                    html.Div("Alertes", className="modal-stat-label"),
                    html.Div([
                        flag_pill("⚡ KO",           d["ko_count"],     C["red"])     if flags["capteur_ko"]       else html.Span(),
                        flag_pill("🕐 Hors schedule", d["hors_count"],   C["orange"])  if flags["hors_schedule"]    else html.Span(),
                        flag_pill("⚠ Inactif",       d["inactif_count"], "#B45309")   if flags["inactif_schedule"] else html.Span(),
                        html.Span("Aucune alerte", style={"color": C["text_muted"], "fontSize": "0.78rem"})
                            if not any([flags["capteur_ko"], flags["hors_schedule"], flags["inactif_schedule"]]) else html.Span(),
                    ], className="modal-stat-value"),
                ], className="modal-stat", style={"gridColumn": "1 / -1"}),

                # Description
                html.Div([
                    html.Div("Description", className="modal-stat-label"),
                    html.Div(p.get("description") or "-", className="modal-stat-value",
                             style={"fontSize": "0.78rem", "lineHeight": "1.6"}),
                ], className="modal-stat", style={"gridColumn": "1 / -1"}),

                # Horaires
                html.Div([
                    html.Div("Horaires", className="modal-stat-label"),
                    html.Div(
                        fmt_schedule(p.get("schedule", {})),
                        className="modal-stat-value",
                        style={"fontSize": "0.78rem", "lineHeight": "1.6", "fontWeight": "500"},
                    ),
                ], className="modal-stat", style={"gridColumn": "1 / -1"}),

            ], className="modal-summary"),

            section_label(f"Capteurs - {len(trkrs)}"),
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
        data = get_cached_data(creds.get("email"), creds.get("key", ""))
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

        gps_content = "-"
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
            ts_str = fmt_local(str(ts), tracker.get("_project_tz","UTC")) if ts else "-"
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
                     f"{volt:.2f} V" if volt > 0 else "-"),
                stat("Peson batterie",
                     f"{shackle:.2f} V" if isinstance(shackle,(int,float)) and shackle > 0 else "-"),
                stat("Température",
                     f"{temp:.1f} °C" if isinstance(temp,(int,float)) and temp > 0 else "-"),
                stat("Poids",
                     f"{int(weight)} kg" if isinstance(weight,(int,float)) and weight >= 0 else "-"),
                html.Div([
                    html.Div("GPS", className="modal-stat-label"),
                    html.Div(gps_content, className="modal-stat-value"),
                ], className="modal-stat"),
            ], className="modal-summary"),

            section_label(f"Historique events - {len(capteur_events)} trouvé(s)"),
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
        data = get_cached_data(creds.get("email"), creds.get("key", ""))
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
                "Ville":  p.get("city","-") or "-",
                "Début":  fmt_date(p.get("startDate")),
                "Fin":    fmt_date(p.get("endDate")),
                "Base":   p.get("database","-"),
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

                section("KPIs - Bandeau permanent", [
                    ("Projets actifs",
                    "Projets dont au moins un dispositif a envoyé un lastUpdate dans les 60 dernières secondes précédant le dernier chargement MongoDB. Rafraîchi toutes les 15 min."),
                    ("Fin imminente",
                    "Projets dont la date de fin (endDate) est dans moins de X jours. X = seuil configuré dans l'onglet Gestion des alertes (défaut : 30 jours)."),
                    ("Projets terminés",
                    "Projets dont la date de fin est dépassée mais qui ne sont pas encore archivés dans MongoDB."),
                    ("Dispositifs connectés",
                    "Dispositifs dont le lastUpdate est inférieur au délai offline du projet (offlineDelay). Le pourcentage représente la santé globale du parc."),
                    ("Batterie faible",
                    "Dispositifs connectés dont la tension (battery_volt) est sous le seuil configuré (défaut : 3.5V). Cliquable - redirige vers l'onglet Dispositifs filtré."),
                ]),

                section("Onglet Tableau de bord", [
                    ("Vue d'ensemble",
                    "Affiche un bandeau de statut global (tout OK ou nombre d'alertes), suivi de 7 sections collapsibles. Chaque section indique le nombre d'éléments concernés dans son titre."),
                    ("Capteurs inactifs pendant horaire",
                    "Capteurs déconnectés alors que : (1) le schedule du projet est actif en ce moment, (2) le capteur était actif lors du dernier chargement (lastUpdate < 60s), (3) le capteur a un peson fonctionnel."),
                    ("Capteurs actifs hors horaire",
                    "Capteurs connectés ou ayant émis dans la dernière heure, alors que le schedule du projet indique que les équipements devraient être éteints."),
                    ("Batterie faible",
                    "Capteurs connectés (ou vus dans les dernières 24h) avec battery_volt sous le seuil configuré."),
                    ("Batterie inconnue",
                    "Capteurs dont le champ battery_volt est présent dans le message mais avec une valeur invalide ou absente."),
                    ("Peson inconnu",
                    "Capteurs dont le champ weight est présent dans le message mais avec une valeur invalide (< 0 ou absente)."),
                    ("Projets bientôt terminés",
                    "Projets dont la date de fin est dans moins de X jours (seuil configurable)."),
                    ("Projets terminés encore actifs",
                    "Projets dont la date de fin est dépassée mais qui ont encore des capteurs émettant aujourd'hui. Anomalie à investiguer."),
                ]),

                section("Onglet Projets", [
                    ("Filtre par défaut",
                    "L'onglet s'ouvre sur les projets Actifs. Les filtres Statut, Type et Recherche sont combinables. Le label au-dessus du tableau reflète la sélection active."),
                    ("Statut Actifs",
                    "Au moins un dispositif avec lastUpdate < 60s lors du dernier chargement MongoDB."),
                    ("Statut Inactifs",
                    "Projets en cours (endDate non dépassée) sans aucun dispositif actif lors du dernier chargement."),
                    ("Statut Fin imminente",
                    "endDate dans moins de X jours (seuil configurable)."),
                    ("Statut Récemment terminés",
                    "endDate dépassée, non encore archivé dans MongoDB."),
                    ("Colonne Score santé",
                    "Colorée selon 4 niveaux - Excellent ≥ 80% (vert), Bon 55–79% (bleu), Moyen 30–54% (orange), Critique < 30% (rouge). Formule : +50 pts si connecté, +30 pts si batterie OK, +20 pts si poids mesuré, moyenne sur tous les capteurs du projet."),
                    ("Panneau de détail (clic sur une ligne)",
                    "Ouvre un modal avec : score santé visuel + label, alertes actives (⚡ KO / 🕐 Hors schedule / ⚠ Inactif), type, ville, fuseau, délai offline, capteurs connectés/déco/batterie, dates, description, horaires configurés, et tableau complet des dispositifs du projet."),
                    ("Projets archivés",
                    "Accessibles via le bouton en bas de page. Triés par date de fin décroissante."),
                    ("Fuseau horaire",
                    "Détecté automatiquement via les coordonnées GPS du dernier lastTrack. Fallback sur UTC si aucun GPS disponible."),
                ]),

                section("Onglet Dispositifs", [
                    ("Filtre par défaut",
                    "L'onglet s'ouvre sur les dispositifs Connectés. Les filtres Connexion, Batterie et Projets sont combinables. Le label reflète le nombre de résultats et les filtres actifs."),
                    ("Statut connecté",
                    "lastUpdate du dispositif inférieur au offlineDelay du projet (offlineDelay, souvent 60 secondes)."),
                    ("Panneau de détail (clic sur une ligne)",
                    "Ouvre un modal avec : statut, dernière activité en heure locale, allumage ce matin, batterie (V), peson batterie, température, poids, GPS cliquable (Google Maps), et les 10 derniers events du capteur."),
                    ("Dernière activité",
                    "lastUpdate converti en heure locale du projet (fuseau GPS détecté ou UTC)."),
                    ("Batterie (V)",
                    "Valeur battery_volt dans lastTrack.message."),
                    ("Peson batterie",
                    "Valeur shackle_battery dans lastTrack.message - batterie interne du peson."),
                    ("Poids (kg)",
                    "Valeur weight dans lastTrack.message."),
                    ("GPS",
                    "Coordonnées lat/lon de lastTrack. Cliquable vers Google Maps."),
                ]),

                section("Onglet Gestion des alertes", [
                    ("Batterie faible (V)",
                    "Seuil de tension en dessous duquel un dispositif est considéré en batterie faible. Affecte les KPIs, l'onglet Tableau de bord et les panneaux de détail. Défaut : 3.5V."),
                    ("Fin imminente (jours)",
                    "Nombre de jours avant la date de fin d'un projet pour déclencher l'alerte 'Fin imminente'. Défaut : 30 jours."),
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