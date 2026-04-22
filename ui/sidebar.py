from __future__ import annotations
from dash import dcc, html

from config import BATTERY_WARNING_THRESHOLD, ENDING_SOON_DAYS


def sidebar():
    return html.Div([
        html.Div([
            html.Div("CAD.42", className="logo-name"),
            html.Div("UNIFIELD Dashboard", className="logo-sub"),
        ]),
        html.Hr(className="sb-hr"),
        html.Div("Connexion", className="sb-section"),
        html.Label("Email", className="sb-label"),
        dcc.Input(id="input-email", type="email", placeholder="votre@email.com",
                  debounce=True, className="sb-input"),
        html.Label("Clé d'accès", className="sb-label"),
        dcc.Input(id="input-key", type="password", placeholder="User Access Key",
                  debounce=True, className="sb-input"),
        html.Div(id="conn-status"),
        html.Div(id="load-bar-wrap", children=[
            html.Div(className="load-wrap", children=[html.Div(className="load-bar")]),
            html.Div(id="load-hint-text", children="Connexion a UNIFIELD...", className="load-hint"),
        ], style={"display":"none"}),
        html.Button("Actualiser", id="btn-refresh", n_clicks=0,
                    className="btn-primary", style={"marginTop":"10px"}),
        html.Button("Vider cache", id="btn-clear", n_clicks=0, className="btn-secondary"),
        html.Hr(className="sb-hr"),
        html.Div(
            dcc.Checklist(
                id="btn-dark-mode",
                options=[{"label": "    🌙 Mode sombre", "value": "dark"}],
                value=[],
            ),
            className="dark-toggle-wrap"
        ),
        html.Div("Seuils", className="sb-section"),
        html.Label("Battérie faible (V)", className="sb-label"),
        dcc.Input(id="seuil-battery", type="number", value=BATTERY_WARNING_THRESHOLD,
                  step=0.1, min=2.0, max=5.0, debounce=True, className="sb-input"),
        html.Label("Fin imminente (jours)", className="sb-label"),
        dcc.Input(id="seuil-ending", type="number", value=ENDING_SOON_DAYS,
                  step=1, min=1, max=365, debounce=True, className="sb-input"),
        html.Label("Activité depuis", className="sb-label"),
        dcc.Input(id="seuil-activity", type="time", value="00:01",
                  debounce=True, className="sb-input"),
    ], className="sidebar")
