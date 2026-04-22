from __future__ import annotations
import dash
from dash import dcc, html, Output, Input, State, ctx

from config import BATTERY_WARNING_THRESHOLD, ENDING_SOON_DAYS, PAST_DAYS
from cache import get_cached_data, _state
from business.trackers import filter_data
from ui.components import banner
from ui.tabs.urgences import render_urgences
from ui.tabs.scores import render_scores
from ui.tabs.projets import render_projets
from ui.tabs.capteurs import render_capteurs
from ui.tabs.qc import render_qc


def register(app):

    @app.callback(
        Output("active-tab",   "data"),
        Output("tab-urgences", "className"),
        Output("tab-scores",   "className"),
        Output("tab-projets",  "className"),
        Output("tab-capteurs", "className"),
        Output("tab-qc",       "className"),
        Input("tab-urgences",  "n_clicks"),
        Input("tab-scores",    "n_clicks"),
        Input("tab-projets",   "n_clicks"),
        Input("tab-capteurs",  "n_clicks"),
        Input("tab-qc",        "n_clicks"),
        State("active-tab",    "data"),
        prevent_initial_call=True,
    )
    def switch_tab(n1, n2, n3, n4, n5, current):
        tab_map = {
            "tab-urgences": "urgences", "tab-scores":  "scores",
            "tab-projets":  "projets",  "tab-capteurs":"capteurs", "tab-qc":"qc",
        }
        triggered = ctx.triggered_id
        current   = current or "urgences"
        new_tab   = tab_map.get(triggered, current)
        def cls(t): return "tab-btn active" if t == new_tab else "tab-btn"
        return new_tab, cls("urgences"), cls("scores"), cls("projets"), cls("capteurs"), cls("qc")

    @app.callback(
        Output("tab-content", "children"),
        Input("active-tab",        "data"),
        Input("store-ver",         "data"),
        Input("store-seuils",      "data"),
        State("store-filtre-proj",   "data"),
        State("store-filtre-cap",    "data"),
        State("store-filtre-type",   "data"),
        State("store-filtre-search", "data"),
        State("store-creds",         "data"),
    )
    def render_tab(tab, ver, seuils, filtre_proj, filtre_cap, filtre_type, filtre_search, creds):
        triggered = ctx.triggered_id

        if triggered == "store-ver":
            if ver and ver.get("v", 0) == 1:
                tab = "urgences"
        elif not tab or tab not in ("urgences","scores","projets","capteurs","qc"):
            tab = "urgences"

        if not creds:
            return banner("Entrez vos identifiants dans la barre laterale pour commencer.", "info")
        data = get_cached_data(creds["email"], creds["key"])
        if not data or not data.get("projects"):
            st = _state(creds["email"], creds["key"])
            if st.get("loading"):
                return html.Div([
                    html.Div(className="load-wrap", children=[html.Div(className="load-bar")]),
                    html.Div("Chargement des donnees UNIFIELD en cours...",
                             className="load-hint", style={"marginTop":"8px"}),
                ], className="load-card")
            return banner("Aucune donnee. Cliquez sur Actualiser.", "info")
        data = filter_data(data)
        if not seuils:
            seuils = {"bt":BATTERY_WARNING_THRESHOLD,"ed":ENDING_SOON_DAYS,"am":"00:01"}
        bt, ed, am = seuils["bt"], seuils["ed"], seuils.get("am","00:01")
        if tab == "urgences": return render_urgences(data, bt, am, ed, PAST_DAYS)
        if tab == "scores":   return render_scores(data, bt, am, ed)
        if tab == "projets":  return render_projets(data, bt, am, ed, PAST_DAYS,
                              filtre_proj or "Tous", filtre_type or "Tous", filtre_search or "")
        if tab == "capteurs":
            fc = filtre_cap or {}
            return render_capteurs(data, fc.get("conn","Connectés"),
                                   fc.get("batt","Tous"), fc.get("proj","Tous"))
        return render_qc(data)

    @app.callback(
        Output("tab-content", "children", allow_duplicate=True),
        Input("store-filtre-proj",   "data"),
        Input("store-filtre-cap",    "data"),
        Input("store-filtre-type",   "data"),
        Input("store-filtre-search", "data"),
        State("active-tab",   "data"),
        State("store-seuils", "data"),
        State("store-creds",  "data"),
        prevent_initial_call=True,
    )
    def refresh_on_filter(filtre_proj, filtre_cap, filtre_type, filtre_search, tab, seuils, creds):
        if tab not in ("projets","capteurs"):
            return dash.no_update
        if not creds:
            return dash.no_update
        data = get_cached_data(creds["email"], creds["key"])
        if not data or not data.get("projects"):
            return dash.no_update
        data = filter_data(data)
        if not seuils:
            seuils = {"bt":BATTERY_WARNING_THRESHOLD,"ed":ENDING_SOON_DAYS,"am":"00:01"}
        bt, ed, am = seuils["bt"], seuils["ed"], seuils.get("am","00:01")
        if tab == "projets":
            return render_projets(data, bt, am, ed, PAST_DAYS,
                                  filtre_proj or "Tous",
                                  filtre_type or "Tous",
                                  filtre_search or "")
        if tab == "capteurs":
            fc = filtre_cap or {}
            return render_capteurs(data,
                                   fc.get("conn","Connectés"),
                                   fc.get("batt","Tous"),
                                   fc.get("proj","Tous"))
        return dash.no_update
