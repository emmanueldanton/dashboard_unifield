from __future__ import annotations
from datetime import datetime, timezone
from dash import dcc, html, Output, Input, State, ctx

from config import C, PARIS_TZ
from api.client import _load_log, _load_log_lock
from cache import (register_creds, force_refresh, invalidate,
                   get_cache_version, get_cached_data, _state)
from business.trackers import battery_status, filter_data
from business.schedule import check_schedule_anomalies
from business.segments import compute_segments
from ui.components import kpi_card


def register(app):

    @app.callback(
        Output("store-ver",     "data"),
        Output("store-loading", "data"),
        Input("btn-refresh",    "n_clicks"),
        Input("btn-clear",      "n_clicks"),
        Input("store-creds",    "data"),
        Input("interval-ui",    "n_intervals"),
        State("store-ver",      "data"),
        prevent_initial_call=False,
    )
    def sync_ver(nrefresh, nclear, creds, _, cur):
        if not creds:
            return {"v": 0, "email": ""}, False
        email, key = creds.get("email",""), creds.get("key","")
        if not email or not key:
            return {"v": 0, "email": ""}, False

        triggered = ctx.triggered_id

        if triggered == "store-creds":
            register_creds(email, key)
            v = get_cache_version(email, key)
            if cur and cur.get("v") == v and cur.get("email") == email:
                return dcc.no_update, False
            return {"v": v, "email": email}, False

        elif triggered == "btn-refresh":
            register_creds(email, key)
            force_refresh(email, key)
            return {"v": 0, "email": email}, True

        elif triggered == "btn-clear":
            invalidate(email, key)
            register_creds(email, key)
            return {"v": 0, "email": email}, False

        state   = _state(email, key)
        loading = state.get("loading", False)
        v       = get_cache_version(email, key)

        if cur and cur.get("v") == v and cur.get("email") == email:
            return dcc.no_update, loading

        return {"v": v, "email": email}, loading

    @app.callback(
        Output("interval-ui", "disabled"),
        Input("store-loading", "data"),
    )
    def toggle_interval(loading):
        return not loading

    @app.callback(
        Output("conn-status",    "children"),
        Output("page-meta",      "children"),
        Output("load-bar-wrap",  "style"),
        Output("load-hint-text", "children"),
        Input("store-ver",   "data"),
        Input("interval-ui", "n_intervals"),
        State("store-creds", "data"),
        State("store-seuils", "data")
    )
    def update_status(ver, _, creds, seuils):
        hide = {"display":"none"}
        show = {"display":"block"}
        if not creds:
            return (html.Div([html.Span(className="dot-wait"),
                              html.Span("En attente d'identifiants")], className="conn-row"),
                    "", hide, "")

        email, key = creds.get("email",""), creds.get("key","")
        state      = _state(email, key)
        data       = state.get("data")
        loading    = state.get("loading", False)
        err        = state.get("error")

        with _load_log_lock:
            load_text = _load_log[-1][-60:] if _load_log else "Connexion a UNIFIELD..."

        if err:       dot, text = html.Span(className="dot-err"),  f"Erreur : {err[:80]}"
        elif loading: dot, text = html.Span(className="dot-load"), "Chargement en cours..."
        elif data:    dot, text = html.Span(className="dot-live"), "Donnees disponibles"
        else:         dot, text = html.Span(className="dot-wait"), "Cliquez sur Actualiser"

        loaded_at = state.get("loaded_at")
        time_str  = (f"Chargé à {datetime.fromtimestamp(loaded_at, tz=PARIS_TZ).strftime('%H:%M')}"
                     if loaded_at else "")

        conn_row = html.Div([
            html.Div([dot, html.Span(text)], className="conn-row"),
            html.Div(time_str, style={"fontSize":"0.72rem","color":C["text_light"],"marginTop":"2px"}),
        ])

        meta = ""
        if data and data.get("qc"):
            data  = filter_data(data)
            qc    = data["qc"]
            now_h = datetime.now(timezone.utc)

            all_t    = data.get("all_trackers", [])
            all_proj = data.get("projects", [])
            pd_map   = data.get("project_data", {})

            total_ko      = sum(1 for t in all_t
                                if not t.get("_is_connected", False)
                                or battery_status(t) == "faible")
            total_hors    = 0
            total_inactif = 0
            for _p in all_proj:
                _trkrs = pd_map.get(_p.get("id",""), {}).get("trackers", [])
                _hs, _mq = check_schedule_anomalies(
                    _trkrs, _p.get("schedule", {}), now_h
                )
                total_hors    += len(_hs)
                total_inactif += len(_mq)

            flag_items = []
            if total_ko > 0:
                flag_items.append(
                    html.Span(f"⚡ {total_ko} KO",
                              style={"background":C["red"],"color":"#fff","fontSize":"0.68rem",
                                     "fontWeight":"700","padding":"2px 8px","borderRadius":"20px",
                                     "marginLeft":"6px"})
                )
            if total_hors > 0:
                flag_items.append(
                    html.Span(f"🕐 {total_hors} hors schedule",
                              style={"background":C["orange"],"color":"#fff","fontSize":"0.68rem",
                                     "fontWeight":"700","padding":"2px 8px","borderRadius":"20px",
                                     "marginLeft":"6px"})
                )
            if total_inactif > 0:
                flag_items.append(
                    html.Span(f"⚠ {total_inactif} inactifs",
                              style={"background":"#B45309","color":"#fff","fontSize":"0.68rem",
                                     "fontWeight":"700","padding":"2px 8px","borderRadius":"20px",
                                     "marginLeft":"6px"})
                )

            meta = html.Div([
                html.Div([
                    html.Span(f"{qc.get('projects_loaded',0)}/{qc.get('total_projects',0)} projets chargés"),
                    *flag_items,
                ], style={"display":"flex","alignItems":"center","flexWrap":"wrap","gap":"4px"}),
                html.Div(f"{qc.get('units_total',0)} unités · {qc.get('trackers_total',0)} capteurs"),
                html.Div(datetime.now().strftime("%d/%m/%Y %H:%M"),
                         style={"color":C["text_light"]}),
            ])

        return conn_row, meta, show if loading else hide, load_text

    @app.callback(
        Output("kpi-row",     "children"),
        Input("store-ver",    "data"),
        Input("store-seuils", "data"),
        State("store-creds",  "data"),
    )
    def update_kpis(ver, seuils, creds):
        from config import PAST_DAYS
        if not creds: return []
        data = get_cached_data(creds["email"], creds["key"])
        if not data or not data.get("projects"):
            return [kpi_card("Projets actifs", 0, "En attente de donnees")]
        data = filter_data(data)
        if not data.get("projects"):
            return [kpi_card("Projets actifs", 0, "En attente de donnees")]

        bt, ed, am = seuils["bt"], seuils["ed"], seuils.get("am","00:01")
        now   = datetime.now(timezone.utc)
        _pnow = now.astimezone(PARIS_TZ)
        _rh, _rm = map(int, am.split(":"))
        _act_sec = max(1, int((_pnow - _pnow.replace(hour=_rh, minute=_rm, second=0, microsecond=0)).total_seconds()))
        segs = compute_segments(data["projects"], data["project_data"],
                                now, _act_sec, ed, PAST_DAYS)
        all_t   = data["all_trackers"]
        conn    = [t for t in all_t if t.get("_is_connected",False)]
        bat_low = [t for t in all_t if battery_status(t, bt) == "faible"]
        pct     = round(len(conn)/len(all_t)*100) if all_t else 0

        return [
            kpi_card("Projets actifs", len(segs["active"]),
                     f"Signal depuis {am} - {len(segs['total'])} dans le parc",
                     C["green"] if segs["active"] else C["text_muted"], "projets"),
            kpi_card("Fin imminente", len(segs["ending"]),
                     f"Dans les {int(ed)} prochains jours",
                     C["orange"] if segs["ending"] else None, "urgences"),
            kpi_card("Projets termines", len(segs["past"]),
                     "endDate dépassée, non archivés",
                     C["orange"] if segs["past"] else None, "projets"),
            kpi_card("Capteurs connectes", len(conn),
                     f"{pct}% du parc - {len(all_t)} total",
                     C["green"] if pct >= 80 else C["orange"] if pct >= 50 else C["red"], "capteurs"),
            kpi_card("Batterie faible", len(bat_low),
                     f"Seuil < {bt}V",
                     C["orange"] if bat_low else None, "urgences"),
        ]
