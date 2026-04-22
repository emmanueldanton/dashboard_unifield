from __future__ import annotations
from dash import dcc, html, dash_table

from config import C
from ui.components import section_label, build_tracker_rows


def render_capteurs(data, filtre_conn="Connectés", filtre_batt="Tous", filtre_proj="Tous"):
    all_t   = data["all_trackers"]
    projets = sorted(set(t.get("_project_name","?") for t in all_t))

    filtered = all_t[:]
    if filtre_proj != "Tous":
        filtered = [t for t in filtered if t.get("_project_name") == filtre_proj]
    if filtre_conn == "Connectés":
        filtered = [t for t in filtered if t.get("_is_connected")]
    elif filtre_conn == "Déconnectés":
        filtered = [t for t in filtered if not t.get("_is_connected")]
    if filtre_batt == "OK":
        filtered = [t for t in filtered if t.get("_battery_status") == "ok"]
    elif filtre_batt == "Faible":
        filtered = [t for t in filtered if t.get("_battery_status") == "faible"]
    elif filtre_batt == "Inconnue":
        filtered = [t for t in filtered if t.get("_battery_status") == "inconnu"]

    rows = build_tracker_rows(filtered)

    return html.Div([
        html.Div([
            html.Div([
                html.Label("Projet", className="filter-label"),
                dcc.Dropdown(id="cap-proj",
                             options=[{"label":"Tous","value":"Tous"}]+[{"label":p,"value":p} for p in projets],
                             value=filtre_proj, clearable=False, className="dd-filter"),
            ], style={"flex":"1"}),
            html.Div([
                html.Label("Connexion", className="filter-label"),
                dcc.Dropdown(id="cap-conn",
                             options=[{"label":v,"value":v} for v in ["Tous","Connectés","Déconnectés"]],
                             value=filtre_conn, clearable=False, className="dd-filter"),
            ], style={"flex":"1"}),
            html.Div([
                html.Label("Batterie", className="filter-label"),
                dcc.Dropdown(id="cap-batt",
                             options=[{"label":v,"value":v} for v in ["Tous","OK","Faible","Inconnue"]],
                             value=filtre_batt, clearable=False, className="dd-filter"),
            ], style={"flex":"1"}),
        ], style={"display":"flex","gap":"12px","marginBottom":"16px"}),

        section_label(f"Résultats — {len(filtered)} capteur(s)"),

        html.Div(
            dash_table.DataTable(
                id="table-capteurs",
                data=rows,
                columns=[{"name":c,"id":c} for c in rows[0].keys()
                         if not c.startswith("_")] if rows else [],
                page_size=15,
                sort_action="native",
                filter_action="native",
                row_selectable="single",
                selected_rows=[],
                style_table={"overflowX":"auto","minWidth":"800px"},
                style_header={
                    "backgroundColor": "var(--bg)",
                    "fontWeight":      "700",
                    "border":          "1px solid var(--border)",
                    "fontSize":        "11px",
                    "color":           "var(--text-muted)",
                    "textTransform":   "uppercase",
                    "letterSpacing":   "0.06em",
                    "padding":         "10px 12px",
                },
                style_cell={
                    "textAlign":       "left",
                    "padding":         "9px 12px",
                    "border":          "1px solid var(--border)",
                    "fontFamily":      "DM Sans, sans-serif",
                    "fontSize":        "13px",
                    "backgroundColor": "var(--surface)",
                    "color":           "var(--text)",
                    "minWidth":        "120px",
                    "maxWidth":        "200px",
                    "overflow":        "hidden",
                    "textOverflow":    "ellipsis",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "var(--bg)"},
                    {"if": {"state": "selected"}, "backgroundColor": "var(--accent-bg)",
                     "border": "1px solid var(--accent)"},
                ],
            ),
            style={"border":f"1px solid {C['border']}","borderRadius":"10px",
                   "overflowX":"auto","overflowY":"visible"}
        ),

        dcc.Store(id="store-capteur-rows", data=rows),

    ], className="tab-content-anim")
