from __future__ import annotations
from dash import dcc, html

from config import BATTERY_WARNING_THRESHOLD, ENDING_SOON_DAYS, PAST_DAYS
from ui.components import section_label
from ui.tabs.urgences import render_urgences


def render_dashboard(data, bt=BATTERY_WARNING_THRESHOLD,
                     ed=ENDING_SOON_DAYS, past_days=PAST_DAYS):
    projects = data.get("projects", [])
    proj_options = [{"label": "Tous les projets", "value": "__all__"}] + [
        {"label": p.get("name", p.get("id", "?")), "value": p.get("id", "")}
        for p in projects if p.get("id")
    ]

    return html.Div([
        render_urgences(data, bt, ed, past_days),

        html.Div(style={"height": "32px"}),
        section_label("Évolution des états par projet"),

        html.Div([
            html.Div([
                html.Label("Projet", className="filter-label"),
                dcc.Dropdown(
                    id="snap-project",
                    options=proj_options,
                    value="__all__",
                    clearable=False,
                    className="dd-filter",
                ),
            ], style={"flex": "2"}),
            html.Div([
                html.Label("Plage", className="filter-label"),
                dcc.RadioItems(
                    id="snap-range",
                    options=[
                        {"label": "6 h",  "value": "6h"},
                        {"label": "24 h", "value": "24h"},
                        {"label": "7 j",  "value": "7j"},
                    ],
                    value="24h",
                    inline=True,
                    className="snap-range-radio",
                ),
            ], style={"flex": "1", "display": "flex", "flexDirection": "column", "justifyContent": "flex-end"}),
        ], style={"display": "flex", "gap": "16px", "alignItems": "flex-end", "marginBottom": "12px"}),

        dcc.Graph(
            id="snap-graph",
            config={"displayModeBar": False},
            style={"height": "320px"},
        ),

    ], className="tab-content-anim")
