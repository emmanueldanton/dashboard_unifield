from __future__ import annotations
from datetime import datetime, timezone
from dash import html

from config import C, PARIS_TZ, PAST_DAYS
from business.trackers import health_score, battery_status, score_class, score_label
from business.segments import compute_segments
from business.flags import compute_project_flags, flag_badge
from ui.components import section_label


def render_scores(data, bt, am, ed):
    _now_s  = datetime.now(timezone.utc)
    _pnow   = _now_s.astimezone(PARIS_TZ)
    _rh, _rm = map(int, (am or "00:01").split(":"))
    _act_sec = max(1, int((_pnow - _pnow.replace(hour=_rh, minute=_rm, second=0, microsecond=0)).total_seconds()))
    segs   = compute_segments(data["projects"], data["project_data"],
                              _now_s, _act_sec, ed, PAST_DAYS)
    pd_map = data["project_data"]
    COLOR_MAP = {"excellent":C["green"],"good":C["accent"],"medium":C["orange"],
                 "bad":C["red"],"empty":C["text_light"]}
    BG_MAP    = {"excellent":C["green_bg"],"good":C["accent_bg"],"medium":C["orange_bg"],
                 "bad":C["red_bg"],"empty":C["bg"]}

    legend = html.Div([
        html.Span(">= 80 — Excellent", style={"background":C["green_bg"],"color":C["green"],
            "border":f"1px solid {C['green_bdr']}","fontSize":"0.72rem","fontWeight":"700",
            "padding":"3px 10px","borderRadius":"20px","marginRight":"6px"}),
        html.Span("55-79 — Bon", style={"background":C["accent_bg"],"color":C["accent"],
            "border":"1px solid rgba(93,144,80,0.3)","fontSize":"0.72rem","fontWeight":"700",
            "padding":"3px 10px","borderRadius":"20px","marginRight":"6px"}),
        html.Span("30-54 — Moyen", style={"background":C["orange_bg"],"color":C["orange"],
            "border":f"1px solid {C['orange_bdr']}","fontSize":"0.72rem","fontWeight":"700",
            "padding":"3px 10px","borderRadius":"20px","marginRight":"6px"}),
        html.Span("< 30 — Critique", style={"background":C["red_bg"],"color":C["red"],
            "border":f"1px solid {C['red_border']}","fontSize":"0.72rem","fontWeight":"700",
            "padding":"3px 10px","borderRadius":"20px"}),
    ], style={"display":"flex","flexWrap":"wrap","gap":"6px","marginBottom":"20px"})

    cards = []
    for p in segs["total"]:
        pid   = p.get("id")
        trkrs = pd_map.get(pid, {}).get("trackers", [])
        if not trkrs: continue
        delay = p.get("offlineDelay", 60)
        score = health_score(trkrs, delay, bt)
        conn  = sum(1 for t in trkrs if t.get("_is_connected", False))
        bat_ok= sum(1 for t in trkrs if battery_status(t, bt) == "ok")
        disc  = len(trkrs) - conn
        cls   = score_class(score)
        flags = compute_project_flags(p, trkrs, datetime.now(timezone.utc), bt)
        d     = flags["details"]

        flag_row = html.Div([
            flag_badge("⚡ KO",            d["ko_count"],      "urgence-ko",      C["red"])
                if flags["capteur_ko"] else html.Span(),
            flag_badge("🕐 Hors schedule", d["hors_count"],    "urgence-hors",    C["orange"])
                if flags["hors_schedule"] else html.Span(),
            flag_badge("⚠ Inactif",        d["inactif_count"], "urgence-inactif", "#B45309")
                if flags["inactif_schedule"] else html.Span(),
        ], style={"marginTop": "8px", "minHeight": "22px"})

        detail_lines = d["ko_list"] + d["hors_list"] + d["inactif_list"]
        detail_title = "\n".join(detail_lines) if detail_lines else ""

        cards.append(html.Div([
            html.Div([
                html.Div(p.get("name","?"), className="score-name",
                         title=detail_title),
                html.Div([
                    html.Span(score_label(score),
                              style={"fontSize":"0.72rem","color":C["text_muted"],"marginRight":"8px"}),
                    html.Span(f"{score}%", className="score-badge",
                              style={"background":BG_MAP[cls],"color":COLOR_MAP[cls],
                                     "border":f"1px solid {C['border']}"}),
                ], style={"display":"flex","alignItems":"center"}),
            ], className="score-header"),
            html.Div(className="score-track", children=[
                html.Div(className="score-fill",
                         style={"width":f"{score}%","background":COLOR_MAP[cls]}),
            ]),
            html.Div(
                f"{len(trkrs)} capteurs · {conn} connectés · {disc} déco. · {bat_ok} batt. OK · délai {delay}s",
                className="score-meta"
            ),
            flag_row,
        ], className="score-card"))

    return html.Div([
        section_label(f"Score de santé — {len(cards)} projet(s)"),
        legend,
        html.Div(cards),
    ], className="tab-content-anim")
