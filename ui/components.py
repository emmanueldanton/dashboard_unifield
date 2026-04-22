from __future__ import annotations
from dash import dcc, html, dash_table

from config import C
from business.trackers import _msg, fmt_paris, age_full


def banner(text, tone="info"):
    icons = {"ok":"v","warn":"!","danger":"x","info":"i"}
    return html.Div([
        html.Span(icons.get(tone,""), style={"fontWeight":"700","fontSize":"1rem"}),
        html.Span(f" {text}")
    ], className=f"banner {tone}")


def section_label(text):
    return html.Div(text, className="section-label")


def kpi_card(label, value, sub="", color=None, tab_target=None):
    style = {"cursor":"pointer"} if tab_target else {}
    return html.Div([
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className="kpi-value", style={"color": color or C["text"]}),
        html.Div(sub, className="kpi-sub"),
    ], className="kpi-card", style=style)


def make_table(rows, page_size=15):
    if not rows:
        return html.Div("Aucune donnee.", style={"color":C["text_muted"],"padding":"16px 0","fontSize":"0.85rem"})
    cols = [{"name": c, "id": c} for c in rows[0].keys() if not c.startswith("_")]
    return html.Div(
        dash_table.DataTable(
            data=rows, columns=cols,
            page_size=page_size, sort_action="native", filter_action="native",
            row_selectable="single", selected_rows=[],
            style_table={"overflowX":"auto", "minWidth":"800px"},
            style_header={
                "backgroundColor": "var(--bg)",
                "fontWeight":       "700",
                "border":           "1px solid var(--border)",
                "fontSize":         "11px",
                "color":            "var(--text-muted)",
                "textTransform":    "uppercase",
                "letterSpacing":    "0.06em",
                "padding":          "10px 12px",
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
        style={"border":f"1px solid {C['border']}","borderRadius":"10px","overflowX":"auto","overflowY":"visible"}
    )


def build_tracker_rows(trackers):
    rows = []
    for t in trackers:
        msg     = _msg(t)
        volt    = t.get("_battery_volt",-1)
        temp    = msg.get("temperature",-1)
        weight  = msg.get("weight",-1)
        shackle = msg.get("shackle_battery",-1)
        lt      = t.get("lastTrack") or {}
        lat, lon = lt.get("lat",0), lt.get("lon",0)
        conn    = t.get("_is_connected",False)
        rows.append({
            "_id":              t.get("id") or t.get("uuid",""),
            "Capteur":          t.get("name","?"),
            "Unité":            t.get("_unit_name","?"),
            "Projet":           t.get("_project_name","?"),
            "Statut":           "🟢 Connecté" if conn else "🔴 Déconnecté",
            "Dernière activité":fmt_paris(t.get("lastUpdate","")),
            "Âge":              age_full(t.get("lastUpdate","")),
            "Batt. (V)":        f"{volt:.2f}" if isinstance(volt,(int,float)) and volt > 0 else "—",
            "Peson batt":       f"{shackle:.2f}" if isinstance(shackle,(int,float)) and shackle > 0 else "—",
            "Temp.":            f"{temp:.1f}°C" if isinstance(temp,(int,float)) and temp > 0 else "—",
            "Poids (kg)":       f"{int(weight)}" if isinstance(weight,(int,float)) and weight >= 0 else "—",
            "GPS":              f"{round(lat,5)}, {round(lon,5)}" if lat and lon else "—",
        })
    return rows


def make_table_searchable(rows, section_id, page_size=15):
    if not rows:
        return banner("Aucune donnée.", "info")

    search_id = {"type": "urgence-search", "section": section_id}

    return html.Div([
        dcc.Input(
            id=search_id,
            type="text",
            placeholder="⌕ Rechercher...",
            debounce=True,
            className="search-input",
        ),
        html.Div(id={"type": "urgence-table", "section": section_id},
                 children=make_table(rows, page_size)),
        dcc.Store(id={"type": "urgence-rows", "section": section_id},
                  data=rows),
    ])


def collapsible(title, count, content, tone=None):
    colors = {"danger": C["red"], "warn": C["orange"], "ok": C["green"]}
    color  = colors.get(tone, C["text_muted"])
    return html.Details([
        html.Summary([
            html.Span("▶", style={
                "fontSize": "0.6rem",
                "marginRight": "8px",
                "color": color,
            }),
            html.Span(title, style={
                "fontSize": "0.68rem",
                "fontWeight": "700",
                "color": color,
                "letterSpacing": "0.1em",
                "textTransform": "uppercase",
            }),
            html.Span(f" — {count}", style={
                "fontSize": "0.68rem",
                "fontWeight": "700",
                "color": color,
                "marginLeft": "2px",
            }),
        ], style={
            "display": "flex",
            "alignItems": "center",
            "cursor": "pointer",
            "padding": "10px 0",
            "borderBottom": f"1px solid {C['border']}",
            "listStyle": "none",
            "userSelect": "none",
        }),
        html.Div(content, style={"marginTop": "12px", "marginBottom": "8px"}),
    ], open=False, style={"marginBottom": "8px"})
