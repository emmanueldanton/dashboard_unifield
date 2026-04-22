from __future__ import annotations
from dash import dcc, html

from config import BATTERY_WARNING_THRESHOLD, ENDING_SOON_DAYS, PAST_DAYS
from ui.sidebar import sidebar


def create_layout():
    return html.Div([
        # Stores
        dcc.Store(id="store-creds",       storage_type="session"),
        dcc.Store(id="store-seuils",      data={"bt":BATTERY_WARNING_THRESHOLD,"ed":ENDING_SOON_DAYS,
                                            "am":"00:01","pd":PAST_DAYS}),
        dcc.Store(id="store-ver",         data={"v":0,"email":""}),
        dcc.Store(id="store-filtre-proj", data="Tous"),
        dcc.Store(id="store-filtre-type", data="Tous"),
        dcc.Store(id="store-filtre-cap",  data={"conn":"Connectés","batt":"Tous","proj":"Tous"}),
        dcc.Store(id="store-projet-selec",  data=None),
        dcc.Store(id="store-capteur-selec", data=None),
        dcc.Store(id="store-modal-archives", data=False),
        dcc.Store(id="active-tab",          data="urgences"),
        dcc.Store(id="store-urgence-anchor", data=None),
        dcc.Store(id="store-filtre-search",  data=""),
        dcc.Store(id="store-dark-mode", data=False, storage_type="local"),
        dcc.Store(id="store-loading", data=False),
        dcc.Interval(id="interval-ui", interval=1000, n_intervals=0, disabled=True),

        html.Div([
            sidebar(),
            html.Div([
                html.Div([
                    html.Div([
                        html.H1("Tableau de bord operationnel", className="page-title"),
                        html.P("UNIFIELD - CAD.42 — Vision temps reel des chantiers", className="page-sub"),
                    ]),
                    html.Div(id="page-meta", className="page-meta"),
                ], className="page-header"),

                html.Div("Vue d'ensemble", className="section-label"),
                html.Div(id="kpi-row", className="kpi-grid"),
                html.Div(style={"height":"8px"}),

                html.Div("Analyse", className="section-label"),
                html.Div([
                    html.Button("⚠ Urgences",           id="tab-urgences",  n_clicks=0, className="tab-btn active"),
                    html.Button("⬡ Scores",              id="tab-scores",    n_clicks=0, className="tab-btn"),
                    html.Button("≡ Projets",             id="tab-projets",   n_clicks=0, className="tab-btn"),
                    html.Button("◎ Capteurs",            id="tab-capteurs",  n_clicks=0, className="tab-btn"),
                    html.Button("✦ Qualite des donnees", id="tab-qc",        n_clicks=0, className="tab-btn"),
                ], className="tab-bar"),

                html.Div(id="tab-content"),
            ], className="main-content"),
        ], className="page-layout"),
        html.Div(id="modal-container"),
        html.Div(id="scroll-trigger", style={"display":"none"}),
    ])
