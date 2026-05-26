from __future__ import annotations
from datetime import datetime, timezone
import pandas as pd
from dash import dcc, html, dash_table

from config import C, PARIS_TZ, PAST_DAYS
from business.trackers import (
    health_score, battery_status, fmt_local, fmt_date, fmt_tz,
    score_class, score_label,
)
from business.segments import compute_segments
from business.flags import compute_project_flags, flag_badge
from ui.components import section_label


# ── Score cards (former scores.py — integrated per T030) ─────────────────────

def _render_score_cards(data, pd_map, segs, bt):
    COLOR_MAP = {
        "excellent": C["green"],  "good": C["accent"],
        "medium":    C["orange"], "bad":  C["red"], "empty": C["text_light"],
    }
    BG_MAP = {
        "excellent": C["green_bg"],   "good": C["accent_bg"],
        "medium":    C["orange_bg"],  "bad":  C["red_bg"],    "empty": C["bg"],
    }

    legend = html.Div([
        html.Span(">= 80 — Excellent", style={
            "background": C["green_bg"], "color": C["green"],
            "border": f"1px solid {C['green_bdr']}", "fontSize": "0.72rem",
            "fontWeight": "700", "padding": "3px 10px",
            "borderRadius": "20px", "marginRight": "6px"}),
        html.Span("55-79 — Bon", style={
            "background": C["accent_bg"], "color": C["accent"],
            "border": "1px solid rgba(93,144,80,0.3)", "fontSize": "0.72rem",
            "fontWeight": "700", "padding": "3px 10px",
            "borderRadius": "20px", "marginRight": "6px"}),
        html.Span("30-54 — Moyen", style={
            "background": C["orange_bg"], "color": C["orange"],
            "border": f"1px solid {C['orange_bdr']}", "fontSize": "0.72rem",
            "fontWeight": "700", "padding": "3px 10px",
            "borderRadius": "20px", "marginRight": "6px"}),
        html.Span("< 30 — Critique", style={
            "background": C["red_bg"], "color": C["red"],
            "border": f"1px solid {C['red_border']}", "fontSize": "0.72rem",
            "fontWeight": "700", "padding": "3px 10px", "borderRadius": "20px"}),
    ], style={"display": "flex", "flexWrap": "wrap", "gap": "6px", "marginBottom": "20px"})

    cards = []
    for p in segs["total"]:
        pid   = p.get("id")
        trkrs = pd_map.get(pid, {}).get("trackers", [])
        if not trkrs:
            continue
        delay = p.get("offlineDelay", 60)
        score = health_score(trkrs, delay, bt)
        conn  = sum(1 for t in trkrs if t.get("_is_connected", False))
        bat_ok = sum(1 for t in trkrs if battery_status(t, bt) == "ok")
        disc  = len(trkrs) - conn
        cls   = score_class(score)
        flags = compute_project_flags(p, trkrs, datetime.now(timezone.utc), bt)
        d     = flags["details"]

        flag_row = html.Div([
            flag_badge("⚡ KO", d["ko_count"], "urgence-ko", C["red"])
                if flags["capteur_ko"] else html.Span(),
            flag_badge("🕐 Hors schedule", d["hors_count"], "urgence-hors", C["orange"])
                if flags["hors_schedule"] else html.Span(),
            flag_badge("⚠ Inactif", d["inactif_count"], "urgence-inactif", "#B45309")
                if flags["inactif_schedule"] else html.Span(),
        ], style={"marginTop": "8px", "minHeight": "22px"})

        cards.append(html.Div([
            html.Div([
                html.Div(p.get("name", "?"), className="score-name"),
                html.Div([
                    html.Span(score_label(score),
                              style={"fontSize": "0.72rem", "color": C["text_muted"],
                                     "marginRight": "8px"}),
                    html.Span(f"{score}%", className="score-badge",
                              style={"background": BG_MAP[cls], "color": COLOR_MAP[cls],
                                     "border": f"1px solid {C['border']}"}),
                ], style={"display": "flex", "alignItems": "center"}),
            ], className="score-header"),
            html.Div(className="score-track", children=[
                html.Div(className="score-fill",
                         style={"width": f"{score}%", "background": COLOR_MAP[cls]}),
            ]),
            html.Div(
                f"{len(trkrs)} capteurs · {conn} connectés · {disc} déco. · "
                f"{bat_ok} batt. OK · délai {delay}s",
                className="score-meta"
            ),
            flag_row,
        ], className="score-card"))

    return html.Div([
        legend,
        html.Div(cards),
    ])


# ── Main render function (T030, T031) ─────────────────────────────────────────

def render_projets(data, bt, activity_min, ending_days, past_days,
                   filtreTous="Tous", filtreType="Tous", filtreSearch=""):
    now      = datetime.now(timezone.utc)
    _pnow    = now.astimezone(PARIS_TZ)
    _rh, _rm = map(int, (activity_min or "00:01").split(":"))
    _act_sec = max(1, int(
        (_pnow - _pnow.replace(hour=_rh, minute=_rm, second=0, microsecond=0)).total_seconds()
    ))
    segs   = compute_segments(data["projects"], data["project_data"],
                              now, _act_sec, ending_days, past_days)
    pd_map = data["project_data"]

    all_types    = sorted(set(p.get("type", "?") for p in data["projects"]
                              if p.get("type") and p.get("type") != "KYD"))
    type_options = ["Tous"] + all_types
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
        disc  = len(trkrs) - conn
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
            "Projet":            p.get("name", "?"),
            "Type":              p.get("type", "?"),
            "Statut":            statut,
            "Score santé":       f"{score}%",
            "Capteurs":          len(trkrs),
            "Connectés":         conn,
            "Déconnectés":       disc,
            "Batt. faible":      bat_l,
            "Dernière activité": last_str,
            "Fuseau":            fmt_tz(pdata.get("timezone", "UTC")),
            "Délai offline":     f"{delay}s",
            "Début":             fmt_date(p.get("startDate")),
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

    # ── Filters row (T031) — new IDs for callback compatibility ──────────────
    filtres = html.Div([
        html.Div([
            html.Label("Statut", className="filter-label"),
            dcc.RadioItems(
                id="filter-statut-projet",
                options=[{"label": v, "value": v} for v in statut_options],
                value=filtreTous,
                inline=True,
                className="snap-range-radio",
            ),
        ], style={"flex": "2"}),
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

    # ── Score cards (T030) ────────────────────────────────────────────────────
    score_section = html.Div([
        section_label(f"Score de santé — {len(segs['total'])} projet(s)"),
        _render_score_cards(data, pd_map, segs, bt),
    ])

    # ── Projects table ─────────────────────────────────────────────────────────
    table_el = (
        html.Div(
            dash_table.DataTable(
                id="table-projets",
                data=rows,
                columns=[{"name": c, "id": c} for c in rows[0].keys()
                         if not c.startswith("_")] if rows else [],
                page_size=15,
                sort_action="native",
                filter_action="native",
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
        score_section,
        html.Div(style={"height": "16px"}),
        section_label(titre),
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
