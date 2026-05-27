from __future__ import annotations
from datetime import datetime, timedelta, timezone

import dash
import plotly.graph_objects as go
from dash import html, Output, Input, State, ctx

from config import (
    BATTERY_WARNING_THRESHOLD, ENDING_SOON_DAYS, PAST_DAYS, C,
)
from cache import get_cached_data, _state
from business.trackers import filter_data
from ui.components import banner, build_tracker_rows as _btr


def register(app):

    # ── 1. Active tab from button clicks (T023a) ──────────────────────────────
    @app.callback(
        Output("active-tab", "data"),
        Input("btn-tab-dashboard",   "n_clicks"),
        Input("btn-tab-dispositifs", "n_clicks"),
        Input("btn-tab-projets",     "n_clicks"),
        Input("btn-tab-alertes",     "n_clicks"),
        prevent_initial_call=True,
    )
    def update_active_tab(n1, n2, n3, n4):
        tab_map = {
            "btn-tab-dashboard":   "dashboard",
            "btn-tab-dispositifs": "dispositifs",
            "btn-tab-projets":     "projets",
            "btn-tab-alertes":     "alertes",
        }
        return tab_map.get(ctx.triggered_id, "dashboard")

    # ── 2. Tab button CSS (T023c) ─────────────────────────────────────────────
    @app.callback(
        Output("btn-tab-dashboard",   "className"),
        Output("btn-tab-dispositifs", "className"),
        Output("btn-tab-projets",     "className"),
        Output("btn-tab-alertes",     "className"),
        Input("active-tab", "data"),
    )
    def update_tab_buttons(tab):
        def cls(t):
            return "tab-btn active" if tab == t else "tab-btn"
        return cls("dashboard"), cls("dispositifs"), cls("projets"), cls("alertes")

    # ── 3. Render tab content (T023b) ─────────────────────────────────────────
    @app.callback(
        Output("tab-content", "children"),
        Input("active-tab",   "data"),
        Input("store-ver",    "data"),
        State("store-seuils", "data"),
        State("store-creds",  "data"),
    )
    def render_tab_content(tab, ver, seuils, creds):
        tab = tab or "dashboard"

        data = get_cached_data()
        if not data or not data.get("projects"):
            st = _state()
            if st.get("loading"):
                return html.Div([
                    html.Div(className="load-wrap",
                             children=[html.Div(className="load-bar")]),
                    html.Div("Chargement des données UNIFIELD en cours...",
                             className="load-hint", style={"marginTop": "8px"}),
                ], className="load-card")
            return banner("Aucune donnée. Cliquez sur Actualiser.", "info")

        data   = filter_data(data)
        seuils = seuils or {}
        bt     = seuils.get("bt", BATTERY_WARNING_THRESHOLD)
        am     = seuils.get("am", "00:01")
        ed     = seuils.get("ed", ENDING_SOON_DAYS)

        if tab == "dashboard":
            from ui.tabs.dashboard import render_dashboard
            return render_dashboard(data, bt, am, ed, PAST_DAYS)
        if tab == "dispositifs":
            from ui.tabs.dispositifs import render_dispositifs
            return render_dispositifs(data)
        if tab == "projets":
            from ui.tabs.projets import render_projets
            return render_projets(data, bt, am, ed, PAST_DAYS)
        if tab == "alertes":
            from ui.tabs.alertes import render_alertes
            return render_alertes(data)
        from ui.tabs.dashboard import render_dashboard
        return render_dashboard(data, bt, am, ed, PAST_DAYS)

    # ── 4. Snapshot graph (T024) ──────────────────────────────────────────────
    @app.callback(
        Output("snap-graph", "figure"),
        Input("snap-project", "value"),
        Input("snap-range",   "value"),
        prevent_initial_call=False,
    )
    def update_snap_graph(project_id, range_val):
        range_hours = {"6h": 6, "24h": 24, "7j": 168}.get(range_val or "24h", 24)
        since = datetime.now(timezone.utc) - timedelta(hours=range_hours)

        query: dict = {"ts": {"$gte": since}}
        if project_id and project_id != "__all__":
            query["project_id"] = project_id

        try:
            from api.mongo_client import get_db
            db  = get_db()
            docs = list(db["snapshots"].find(query, {"_id": 0}).sort("ts", 1))
        except Exception:
            docs = []

        if not docs:
            fig = go.Figure()
            fig.add_annotation(
                text="Aucune donnée disponible — les données apparaîtront après le premier cycle de refresh",
                xref="paper", yref="paper", x=0.5, y=0.5,
                showarrow=False, font={"size": 13, "color": C["text_muted"]},
            )
            fig.update_layout(
                plot_bgcolor=C["bg"], paper_bgcolor=C["bg"],
                xaxis={"visible": False}, yaxis={"visible": False},
            )
            return fig

        ts          = [d["ts"] for d in docs]
        connected   = [d.get("connected", 0)    for d in docs]
        disconnected= [d.get("disconnected", 0) for d in docs]
        battery_low = [d.get("battery_low", 0)  for d in docs]

        fig = go.Figure([
            go.Scatter(x=ts, y=connected,    name="Connectés",    line={"color": C["green"]}),
            go.Scatter(x=ts, y=disconnected, name="Déconnectés",  line={"color": C["red"]}),
            go.Scatter(x=ts, y=battery_low,  name="Batt. faible", line={"color": C["orange"]}),
        ])
        fig.update_layout(
            plot_bgcolor=C["bg"], paper_bgcolor=C["bg"],
            font={"color": C["text"], "family": "DM Sans"},
            legend={"orientation": "h", "y": -0.2},
            margin={"t": 20, "b": 40, "l": 40, "r": 20},
            xaxis={"gridcolor": C["border"], "color": C["text_muted"]},
            yaxis={"gridcolor": C["border"], "color": C["text_muted"]},
        )
        return fig

    # ── 5. Filter dispositifs table (T028) ────────────────────────────────────
    @app.callback(
        Output("table-dispositifs", "data"),
        Output("table-dispositifs", "columns"),
        Input("filter-connexion",    "value"),
        Input("filter-batterie",     "value"),
        Input("filter-projet-multi", "value"),
        prevent_initial_call=True,
    )
    def filter_dispositifs(conn_filter, batt_filter, proj_filter):
        data = get_cached_data()
        if not data:
            return [], []
        all_t = data.get("all_trackers", [])

        filtered = all_t[:]
        if proj_filter:
            filtered = [t for t in filtered if t.get("_project_name") in proj_filter]
        if conn_filter == "Connectés":
            filtered = [t for t in filtered if t.get("_is_connected")]
        elif conn_filter == "Déconnectés":
            filtered = [t for t in filtered if not t.get("_is_connected")]
        if batt_filter == "OK":
            filtered = [t for t in filtered if t.get("_battery_status") == "ok"]
        elif batt_filter in ("Faible", "Critique"):
            filtered = [t for t in filtered if t.get("_battery_status") == "faible"]
        elif batt_filter == "Inconnue":
            filtered = [t for t in filtered if t.get("_battery_status") == "inconnu"]

        rows = _btr(filtered)
        cols = [{"name": c, "id": c} for c in rows[0].keys()
                if not c.startswith("_")] if rows else []
        return rows, cols

    # ── 6. Device detail modal (T029) ─────────────────────────────────────────
    @app.callback(
        Output("modal-dispositif",         "style"),
        Output("modal-dispositif-content", "children"),
        Input("table-dispositifs",         "selected_rows"),
        State("store-dispositif-rows",     "data"),
        prevent_initial_call=True,
    )
    def show_device_detail(selected_rows, rows):
        if not selected_rows or not rows:
            return {"display": "none"}, html.Div()
        idx = selected_rows[0]
        if idx >= len(rows):
            return {"display": "none"}, html.Div()

        row = rows[idx]

        def stat(label, value):
            return html.Div([
                html.Div(label, className="modal-stat-label"),
                html.Div(str(value), className="modal-stat-value"),
            ], className="modal-stat")

        content = html.Div([
            html.Div([
                html.Div(row.get("Capteur", "?"), className="modal-title"),
                html.Button("✕", id="btn-close-dispositif", className="modal-close"),
            ], className="modal-header"),
            html.Div([
                stat("Statut",       row.get("Statut", "—")),
                stat("Projet",       row.get("Projet", "—")),
                stat("Unité",        row.get("Unité",  "—")),
                stat("Dernière activité", row.get("Dernière activité (Heure locale)", "—")),
                stat("Âge",          row.get("Âge",     "—")),
                stat("Batt. (V)",    row.get("Batt. (V)", "—")),
                stat("Poids (kg)",   row.get("Poids (kg)", "—")),
                stat("GPS",          row.get("GPS",    "—")),
                stat("Temp.",        row.get("Temp.",  "—")),
            ], className="modal-summary"),
        ], className="modal-box")

        return {"display": "flex"}, content

    # ── 7. Close device detail modal ──────────────────────────────────────────
    app.clientside_callback(
        """
        function(n1, n2) {
            if (n1 || n2) return {"display": "none"};
            return window.dash_clientside.no_update;
        }
        """,
        Output("modal-dispositif", "style", allow_duplicate=True),
        Input("btn-close-dispositif",  "n_clicks"),
        Input("modal-dispositif-bg",   "n_clicks"),
        prevent_initial_call=True,
    )

    # ── 8. Filter projets (T032) ──────────────────────────────────────────────
    @app.callback(
        Output("projets-container", "children"),
        Input("search-projet",       "value"),
        Input("filter-type-projet",  "value"),
        Input("filter-statut-projet","value"),
        State("store-seuils",        "data"),
        prevent_initial_call=True,
    )
    def filter_projets(search, type_filter, statut_filter, seuils):
        from datetime import datetime, timezone
        import pandas as pd
        from dash import dash_table
        from business.trackers import health_score, battery_status, fmt_local, fmt_date, fmt_tz
        from business.segments import compute_segments
        from config import PARIS_TZ

        data = get_cached_data()
        if not data or not data.get("projects"):
            return dash.no_update

        data = filter_data(data)
        seuils  = seuils or {}
        bt      = seuils.get("bt", BATTERY_WARNING_THRESHOLD)
        am      = seuils.get("am", "00:01")
        ed      = seuils.get("ed", ENDING_SOON_DAYS)

        now      = datetime.now(timezone.utc)
        _pnow    = now.astimezone(PARIS_TZ)
        _rh, _rm = map(int, (am or "00:01").split(":"))
        _act_sec = max(1, int(
            (_pnow - _pnow.replace(hour=_rh, minute=_rm, second=0, microsecond=0)).total_seconds()
        ))
        segs   = compute_segments(data["projects"], data["project_data"], now, _act_sec, ed, PAST_DAYS)
        pd_map = data["project_data"]

        filtre_map = {
            "Actifs":             segs["active"],
            "Inactifs":           [p for p in segs["total"] if p not in segs["active"]],
            "Fin imminente":      segs["ending"],
            "Récemment terminés": segs["past"],
            "Tous":               data["projects"],
        }
        projets = filtre_map.get(statut_filter or "Tous", data["projects"])
        projets = [p for p in projets if p.get("type") != "KYD"]
        if type_filter and type_filter != "Tous":
            projets = [p for p in projets if p.get("type", "?") == type_filter]
        if search and search.strip():
            q = search.strip().lower()
            projets = [p for p in projets if q in p.get("name", "").lower()]

        rows = []
        for p in projets:
            pid   = p.get("id")
            pdata = pd_map.get(pid, {})
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
            last_seen = max((t.get("lastUpdate", "") for t in trkrs), default="")
            rows.append({
                "_pid":          pid,
                "Projet":        p.get("name", "?"),
                "Type":          p.get("type", "?"),
                "Statut":        statut,
                "Score santé":   f"{score}%",
                "Capteurs":      len(trkrs),
                "Connectés":     conn,
                "Déconnectés":   disc,
                "Batt. faible":  bat_l,
                "Dernière activité": fmt_local(last_seen, pdata.get("timezone", "UTC")),
                "Début":         fmt_date(p.get("startDate")),
                "Fin":           fmt_date(p.get("endDate")),
            })

        return html.Div(
            dash_table.DataTable(
                id="table-projets",
                data=rows,
                columns=[{"name": c, "id": c} for c in rows[0].keys()
                         if not c.startswith("_")] if rows else [],
                page_size=15,
                sort_action="native",
                filter_action="native",
                row_selectable="single",
                selected_rows=[],
                style_table={"overflowX": "auto", "minWidth": "800px"},
                style_header={
                    "backgroundColor": "var(--bg)", "fontWeight": "700",
                    "border": "1px solid var(--border)", "fontSize": "11px",
                    "color": "var(--text-muted)", "textTransform": "uppercase",
                    "letterSpacing": "0.06em", "padding": "10px 12px",
                },
                style_cell={
                    "textAlign": "left", "padding": "9px 12px",
                    "border": "1px solid var(--border)",
                    "fontFamily": "DM Sans, sans-serif", "fontSize": "13px",
                    "backgroundColor": "var(--surface)", "color": "var(--text)",
                    "minWidth": "120px", "maxWidth": "200px",
                    "overflow": "hidden", "textOverflow": "ellipsis",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "var(--bg)"},
                    {"if": {"state": "selected"},
                     "backgroundColor": "var(--accent-bg)",
                     "border": "1px solid var(--accent)"},
                ],
            ),
            style={"border": f"1px solid {C['border']}", "borderRadius": "10px",
                   "overflowX": "auto"}
        ) if rows else html.Div(
            "Aucune donnée.", style={"color": C["text_muted"], "padding": "16px 0"}
        )
