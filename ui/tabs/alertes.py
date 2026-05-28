from __future__ import annotations
from dash import dcc, html, dash_table

from config import C, BATTERY_WARNING_THRESHOLD, ENDING_SOON_DAYS
from ui.components import section_label, banner


def render_alertes():
    seuils_form = html.Div([
        html.Div([
            html.Label("Batterie faible (V)", className="filter-label"),
            dcc.Input(
                id="seuil-battery",
                type="number",
                value=BATTERY_WARNING_THRESHOLD,
                step=0.1, min=2.0, max=5.0,
                debounce=True,
                className="sb-input",
            ),
        ], style={"flex": "1"}),
        html.Div([
            html.Label("Fin imminente (jours)", className="filter-label"),
            dcc.Input(
                id="seuil-ending",
                type="number",
                value=ENDING_SOON_DAYS,
                step=1, min=1, max=365,
                debounce=True,
                className="sb-input",
            ),
        ], style={"flex": "1"}),
        html.Button(
            "Enregistrer",
            id="btn-save-seuils",
            n_clicks=0,
            className="btn-primary",
            style={"alignSelf": "flex-end", "width": "auto", "padding": "9px 20px"},
        ),
    ], style={"display": "flex", "gap": "12px", "alignItems": "flex-end"})

    return html.Div([
        html.Div(id="alertes-container"),

        html.Div(style={"height": "32px"}),
        section_label("Seuils d'alerte"),
        seuils_form,

    ], className="tab-content-anim")


def build_alert_table(rows: list) -> html.Div:
    nb_alerts = len(rows)
    table_el = (
        html.Div(
            dash_table.DataTable(
                id="table-alertes",
                data=rows,
                columns=[{"name": c, "id": c} for c in rows[0].keys()] if rows else [],
                page_size=50,
                sort_action="native",
                style_table={"overflowX": "auto"},
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
                    "minWidth": "100px", "maxWidth": "300px",
                    "overflow": "hidden", "textOverflow": "ellipsis",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "var(--bg)"},
                ],
            ),
            style={"border": f"1px solid {C['border']}", "borderRadius": "10px",
                   "overflowX": "auto"}
        ) if rows else banner("Aucune alerte enregistrée.", "info")
    )
    return html.Div([
        section_label(f"Historique alertes - {nb_alerts} entrée(s)"),
        table_el,
    ])
