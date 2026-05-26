from __future__ import annotations
from datetime import datetime, timezone

import dash
from dash import html, Output, Input, State, ctx

from config import C, PARIS_TZ
from cache import (register_creds, force_refresh, invalidate,
                   get_cache_version, get_cached_data, _state,
                   is_mongo_ok, last_success_ts)
from business.trackers import battery_status, filter_data
from business.schedule import check_schedule_anomalies
from business.segments import compute_segments
from ui.components import kpi_card


def register(app):

    # ── Trigger force-refresh every 15 min and on btn-refresh click ───────────
    @app.callback(
        Output("store-ver",     "data"),
        Output("store-loading", "data"),
        Input("btn-refresh",    "n_clicks"),
        Input("interval-15min", "n_intervals"),
        Input("store-creds",    "data"),
        State("store-ver",      "data"),
        prevent_initial_call=False,
    )
    def sync_ver(nrefresh, n15, creds, cur):
        triggered = ctx.triggered_id

        if triggered == "store-creds":
            register_creds()
            v = get_cache_version()
            if cur and cur.get("v") == v:
                return dash.no_update, False
            email = (creds or {}).get("email", "")
            return {"v": v, "email": email}, False

        if triggered == "btn-refresh":
            register_creds()
            force_refresh()
            email = (creds or {}).get("email", "")
            return {"v": 0, "email": email}, True

        if triggered == "interval-15min":
            register_creds()
            force_refresh()
            email = (creds or {}).get("email", "")
            return {"v": 0, "email": email}, True

        email = (creds or {}).get("email", "")
        state = _state()
        loading = state.get("loading", False)
        v = get_cache_version()
        if cur and cur.get("v") == v:
            return dash.no_update, loading
        return {"v": v, "email": email}, loading

    # interval-ui is enabled only while loading (animation only) ─ D-008
    @app.callback(
        Output("interval-ui", "disabled"),
        Input("store-loading", "data"),
    )
    def toggle_interval_ui(loading):
        return not loading

    # ── MongoDB connectivity status → conn-status store ───────────────────────
    @app.callback(
        Output("conn-status", "data"),
        Input("store-ver",    "data"),
    )
    def update_conn_status(_ver):
        return is_mongo_ok()

    # ── Header metadata (last refresh, conn indicator) ────────────────────────
    @app.callback(
        Output("header-last-refresh", "children"),
        Output("header-conn-status",  "children"),
        Output("header-user-email",   "children"),
        Input("store-ver",   "data"),
        Input("conn-status", "data"),
        State("store-creds", "data"),
    )
    def update_header_meta(_ver, mongo_ok, creds):
        email = (creds or {}).get("email", "")

        last_ts = last_success_ts()
        if last_ts:
            last_str = datetime.fromtimestamp(last_ts, tz=PARIS_TZ).strftime("%d/%m %H:%M")
            refresh_label = f"Dernière MAJ : {last_str}"
        else:
            refresh_label = "Aucune donnée chargée"

        if mongo_ok:
            conn_el = html.Span([
                html.Span(className="dot-live"), " MongoDB OK"
            ], className="conn-badge conn-ok")
        else:
            conn_el = html.Span([
                html.Span(className="dot-err"), " MongoDB hors ligne"
            ], className="conn-badge conn-err")

        return refresh_label, conn_el, email

    # ── KPI row ───────────────────────────────────────────────────────────────
    @app.callback(
        Output("kpi-row",     "children"),
        Input("store-ver",    "data"),
        Input("store-seuils", "data"),
    )
    def update_kpis(ver, seuils):
        from config import PAST_DAYS
        data = get_cached_data()
        if not data or not data.get("projects"):
            return [kpi_card("Projets actifs", 0, "En attente de données")]
        data = filter_data(data)
        if not data.get("projects"):
            return [kpi_card("Projets actifs", 0, "En attente de données")]

        bt = (seuils or {}).get("bt", 3.5)
        ed = (seuils or {}).get("ed", 30)
        am = (seuils or {}).get("am", "00:01")
        now   = datetime.now(timezone.utc)
        _pnow = now.astimezone(PARIS_TZ)
        _rh, _rm = map(int, am.split(":"))
        _act_sec = max(1, int(
            (_pnow - _pnow.replace(hour=_rh, minute=_rm, second=0, microsecond=0)).total_seconds()
        ))
        segs  = compute_segments(data["projects"], data["project_data"], now, _act_sec, ed, PAST_DAYS)
        all_t = data["all_trackers"]
        conn    = [t for t in all_t if t.get("_is_connected", False)]
        bat_low = [t for t in all_t
                   if battery_status(t, bt) == "faible"
                   and 0 <= t.get("_last_seen_seconds", -1) < _act_sec]
        pct = round(len(conn) / len(all_t) * 100) if all_t else 0

        return [
            kpi_card("Projets actifs",    len(segs["active"]),
                     f"Signal depuis {am} — {len(segs['total'])} dans le parc",
                     C["green"] if segs["active"] else C["text_muted"], "projets"),
            kpi_card("Fin imminente",     len(segs["ending"]),
                     f"Dans les {int(ed)} prochains jours",
                     C["orange"] if segs["ending"] else None, "urgences"),
            kpi_card("Projets terminés",  len(segs["past"]),
                     "endDate dépassée, non archivés",
                     C["orange"] if segs["past"] else None, "projets"),
            kpi_card("Dispositifs connectés", len(conn),
                     f"{pct}% du parc — {len(all_t)} total",
                     C["green"] if pct >= 80 else C["orange"] if pct >= 50 else C["red"], "capteurs"),
            kpi_card("Batterie faible",   len(bat_low),
                     f"Seuil < {bt}V",
                     C["orange"] if bat_low else None, "urgences"),
        ]
