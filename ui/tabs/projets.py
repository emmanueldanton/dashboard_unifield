from __future__ import annotations
from datetime import datetime, timezone
import pandas as pd
from dash import dcc, html, dash_table

from config import C, PARIS_TZ, PAST_DAYS, ACTIVITY_WINDOW_SECONDS
from business.trackers import health_score, battery_status, fmt_local, fmt_date, fmt_tz
from business.segments import compute_segments
from ui.components import section_label


_SCORE_CONDS = [
    {"if": {"filter_query": "{_score_num} >= 80",                    "column_id": "Score santé"},
     "backgroundColor": C["green_bg"],  "color": C["green"],  "fontWeight": "700"},
    {"if": {"filter_query": "{_score_num} >= 55 && {_score_num} < 80", "column_id": "Score santé"},
     "backgroundColor": C["accent_bg"], "color": C["accent"], "fontWeight": "700"},
    {"if": {"filter_query": "{_score_num} >= 30 && {_score_num} < 55", "column_id": "Score santé"},
     "backgroundColor": C["orange_bg"], "color": C["orange"], "fontWeight": "700"},
    {"if": {"filter_query": "{_score_num} >= 0  && {_score_num} < 30", "column_id": "Score santé"},
     "backgroundColor": C["red_bg"],    "color": C["red"],    "fontWeight": "700"},
]


def render_projets(data, bt, ending_days, past_days,
                   filtreTous="Actifs", filtreType="Tous", filtreSearch=""):
    now    = datetime.now(timezone.utc)
    segs   = compute_segments(data["projects"], data["project_data"],
                              now, ACTIVITY_WINDOW_SECONDS, ending_days, past_days)
    pd_map = data["project_data"]

    all_types    = sorted(set(p.get("type", "?") for p in data["projects"]
                              if p.get("type") and p.get("type") != "KYD"))
    type_options   = ["Tous"] + all_types
    statut_options = ["Tous", "Actifs", "Inactifs", "Fin imminente", "Récemment terminés"]

    filtre_map = {
        "Actifs":             segs["active"],
        "Inactifs":           [p for p in segs["total"] if p not in segs["active"]],
        "Fin imminente":      segs["ending"],
        "Récemment terminés": segs["past"],
        "Tous":               data["projects"],
    }
    projets_affiches = filtre_map.get(filtreTous, data["projects"])
    projets_affiches = [p for p in projets_affiches if p.get("type") != "KYD"]
    if filtreType != "Tous":
        projets_affiches = [p for p in projets_affiches
                            if p.get("type", "?") == filtreType]
    if filtreSearch and filtreSearch.strip():
        q = filtreSearch.strip().lower()
        projets_affiches = [p for p in projets_affiches
                            if q in p.get("name", "").lower()]

    labels_map = {
        "Actifs":             f"{len(projets_affiches)} projet(s) actif(s)",
        "Inactifs":           f"{len(projets_affiches)} projet(s) inactif(s)",
        "Fin imminente":      f"{len(projets_affiches)} projet(s) en fin imminente",
        "Récemment terminés": f"{len(projets_affiches)} projet(s) récemment terminé(s)",
        "Tous":               f"{len(projets_affiches)} projet(s) au total",
    }
    titre = labels_map.get(filtreTous, f"{len(projets_affiches)} projets")

    rows = []
    for p in projets_affiches:
        pid   = p.get("id")
        pdata = pd_map.get(pid, {})
        trkrs = pdata.get("trackers", [])
        delay = p.get("offlineDelay", 60)
        score = health_score(trkrs, delay, bt)
        conn  = sum(1 for t in trkrs if t.get("_is_connected", False))
        bat_l = sum(1 for t in trkrs if battery_status(t, bt) == "faible")

        if p in segs["ending"]:   statut = "🟠 Bientôt terminé"
        elif p in segs["active"]: statut = "🟢 Actif"
        elif p in segs["past"]:   statut = "🔴 Récemment terminé"
        elif p.get("archived"):   statut = "⚫ Archivé"
        else:                     statut = "⚪ Inactif"

        last_seen = max((t.get("lastUpdate", "") for t in trkrs), default="")
        last_str  = fmt_local(last_seen, pdata.get("timezone", "UTC"))

        rows.append({
            "_pid":              p.get("id"),
            "_score_num":        score,
            "Projet":            p.get("name", "?"),
            "Type":              p.get("type", "?"),
            "Statut":            statut,
            "Score santé":       f"{score}%",
            "Capteurs":          len(trkrs),
            "Connectés":         conn,
            "Batt. faible":      bat_l,
            "Dernière activité": last_str,
            "Fuseau":            fmt_tz(pdata.get("timezone", "UTC")),
            "Fin":               fmt_date(p.get("endDate")),
        })

    if filtreTous == "Inactifs" and rows:
        df = pd.DataFrame(rows)
        df["_sort"] = pd.to_datetime(
            df["Dernière activité"], format="%d/%m/%Y %H:%M", errors="coerce"
        )
        df = df.sort_values("_sort", ascending=False).drop(columns=["_sort"])
        rows = df.to_dict("records")

    nb_archived = len([p for p in data["projects"] if p.get("archived")])

    filtres = html.Div([
        html.Div([
            html.Label("Statut", className="filter-label"),
            dcc.Dropdown(
                id="filter-statut-projet",
                options=[{"label": v, "value": v} for v in statut_options],
                value=filtreTous,
                clearable=False,
                className="dd-filter",
            ),
        ], style={"flex": "1.5"}),
        html.Div([
            html.Label("Type", className="filter-label"),
            dcc.Dropdown(
                id="filter-type-projet",
                options=[{"label": t, "value": t} for t in type_options],
                value=filtreType,
                clearable=False,
                className="dd-filter",
            ),
        ], style={"flex": "1"}),
        html.Div([
            html.Label("Rechercher", className="filter-label"),
            dcc.Input(
                id="search-projet",
                type="text",
                placeholder="Nom du projet...",
                value=filtreSearch or "",
                debounce=True,
                className="search-input",
                style={"marginBottom": "0"},
            ),
        ], style={"flex": "1"}),
    ], style={"display": "flex", "gap": "12px", "marginBottom": "16px",
              "flexWrap": "wrap", "alignItems": "flex-end"})

    table_el = (
        html.Div(
            dash_table.DataTable(
                id="table-projets",
                data=rows,
                columns=[{"name": c, "id": c} for c in rows[0].keys()
                         if not c.startswith("_")] if rows else [],
                page_size=20,
                sort_action="native",
                row_selectable="single",
                selected_rows=[],
                style_table={"overflowX": "auto", "minWidth": "800px"},
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
                    "minWidth": "120px", "maxWidth": "200px",
                    "overflow": "hidden", "textOverflow": "ellipsis",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "var(--bg)"},
                    {"if": {"state": "selected"},
                     "backgroundColor": "var(--accent-bg)",
                     "border": "1px solid var(--accent)"},
                    *_SCORE_CONDS,
                ],
            ),
            style={"border": "1px solid var(--border)", "borderRadius": "10px",
                   "overflowX": "auto", "overflowY": "visible"}
        ) if rows else html.Div(
            "Aucune donnée.", style={"color": C["text_muted"], "padding": "16px 0"}
        )
    )

    return html.Div([
        filtres,
        html.Div(id="label-projets", children=section_label(titre)),
        html.Div(id="projets-container", children=table_el),
        html.Div(
            html.Button(
                f"📦 Voir les projets archivés ({nb_archived})",
                id="btn-open-archives", n_clicks=0,
                style={"background": "transparent", "border": f"1px solid {C['border']}",
                       "borderRadius": "8px", "padding": "10px 18px", "fontSize": "0.8rem",
                       "fontWeight": "500", "color": C["text_muted"], "cursor": "pointer",
                       "marginTop": "16px", "fontFamily": "inherit", "transition": "all 0.15s"}
            ),
            style={"textAlign": "right"}
        ),
    ], className="tab-content-anim")
