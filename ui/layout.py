from __future__ import annotations
from dash import dcc, html

from config import BATTERY_WARNING_THRESHOLD, ENDING_SOON_DAYS, PAST_DAYS


def create_layout():
    return html.Div([
        # ── Stores ────────────────────────────────────────────────────────────
        dcc.Store(id="store-creds",          storage_type="session"),
        dcc.Store(id="store-seuils",         data={"bt": BATTERY_WARNING_THRESHOLD,
                                                    "ed": ENDING_SOON_DAYS,
                                                    "am": "00:01", "pd": PAST_DAYS}),
        dcc.Store(id="store-ver",            data={"v": 0, "email": ""}),
        dcc.Store(id="store-filtre-proj",    data="Tous"),
        dcc.Store(id="store-filtre-type",    data="Tous"),
        dcc.Store(id="store-filtre-cap",     data={"conn": "Connectés", "batt": "Tous", "proj": "Tous"}),
        dcc.Store(id="store-projet-selec",   data=None),
        dcc.Store(id="store-capteur-selec",  data=None),
        dcc.Store(id="store-modal-archives", data=False),
        dcc.Store(id="store-urgence-anchor", data=None),
        dcc.Store(id="store-filtre-search",  data=""),
        dcc.Store(id="store-dark-mode",      data=True, storage_type="local"),
        dcc.Store(id="store-loading",        data=False),
        dcc.Store(id="store-doc-open",       data=False),

        # Location — used to trigger SSO session read on page load
        dcc.Location(id="url", refresh=False),

        # Single source of truth for active tab (D-005)
        dcc.Store(id="active-tab", data="dashboard"),

        # conn-status tracks MongoDB connectivity (True = ok, False = degraded)
        dcc.Store(id="conn-status", data=True),

        # Intervals — NEVER share outputs between these two (D-008)
        dcc.Interval(id="interval-ui",   interval=1_000,   n_intervals=0, disabled=True),
        dcc.Interval(id="interval-15min", interval=900_000, n_intervals=0, disabled=False),

        # ── Page layout ───────────────────────────────────────────────────────
        html.Div([

            # ── SMSI Header ───────────────────────────────────────────────────
            html.Header([

                # Title row
                html.Div([
                    html.Div([
                        html.H1("Tableau de bord opérationnel UNIFIELD — CAD.42",
                                className="smsi-title"),
                        html.P("Console SMSI · CAD.42 Services SAS · ISO 27001:2022",
                               className="smsi-subtitle"),
                    ], className="smsi-title-block"),

                    # Session metadata + controls
                    html.Div([
                        html.Span(id="header-user-email",  className="header-meta-item"),
                        html.Span(id="header-last-refresh", className="header-meta-item"),
                        html.Span(id="header-conn-status",  className="header-meta-item"),
                        html.Button("Actualiser", id="btn-refresh", n_clicks=0,
                                    className="btn-refresh"),
                    ], className="smsi-meta-row"),
                ], className="smsi-header-top"),

                # KPI row
                html.Div(id="kpi-row", className="kpi-grid"),

                # Tab navigation — active-tab store is the single source of truth
                html.Nav([
                    html.Button("Tableau de bord",   id="btn-tab-dashboard",   n_clicks=0, className="tab-btn"),
                    html.Button("Dispositifs",        id="btn-tab-dispositifs", n_clicks=0, className="tab-btn"),
                    html.Button("Projets",            id="btn-tab-projets",     n_clicks=0, className="tab-btn"),
                    html.Button("Gestion des Alertes", id="btn-tab-alertes",   n_clicks=0, className="tab-btn"),
                ], className="smsi-tab-bar"),

            ], className="smsi-header"),

            # ── Tab content ───────────────────────────────────────────────────
            html.Main(
                html.Div(id="tab-content"),
                className="smsi-main",
            ),

        ], className="smsi-page"),

        html.Div(id="modal-container"),
        html.Div(id="scroll-trigger", style={"display": "none"}),
    ])
