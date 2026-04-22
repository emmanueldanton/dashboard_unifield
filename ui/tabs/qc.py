from __future__ import annotations
from dash import html

from ui.components import banner, make_table


def render_qc(data):
    qc     = data.get("qc",{})
    issues = qc.get("issues",[])
    items  = [
        ("Projets total",       qc.get("total_projects",0),        "info"),
        ("Projets charges",     qc.get("projects_loaded",0),       "ok" if qc.get("projects_loaded")==qc.get("total_projects") else "warn"),
        ("Sans accessKey",      qc.get("projects_no_key",0),       "ok" if qc.get("projects_no_key",0)==0 else "err"),
        ("Projets vides",       qc.get("projects_empty",0),        "ok" if qc.get("projects_empty",0)==0 else "warn"),
        ("Avec donnees",        qc.get("projects_with_data",0),    "info"),
        ("Unites total",        qc.get("units_total",0),           "info"),
        ("Unites sans capteur", qc.get("units_no_tracker",0),      "ok" if qc.get("units_no_tracker",0)==0 else "warn"),
        ("Trackers total",      qc.get("trackers_total",0),        "info"),
        ("IDs uniques",         qc.get("tracker_ids_unique",0),    "info"),
        ("IDs dupliques",       qc.get("trackers_duplicate_id",0), "ok" if qc.get("trackers_duplicate_id",0)==0 else "err"),
        ("Sans lastUpdate",     qc.get("trackers_no_lastupdate",0),"ok" if qc.get("trackers_no_lastupdate",0)==0 else "err"),
        ("Sans lastTrack",      qc.get("trackers_no_lasttrack",0), "ok" if qc.get("trackers_no_lasttrack",0)==0 else "warn"),
        ("Stales > 24h",        qc.get("trackers_stale_24h",0),    "warn"),
        ("Events disponibles",  "Oui" if qc.get("has_events") else "Non","ok" if qc.get("has_events") else "warn"),
    ]
    cls_map = {"ok":"qc-ok","warn":"qc-warn","err":"qc-err","info":"qc-info"}
    return html.Div([
        html.Div([
            html.Div("Rapport qualite des données", className="qc-title"),
            *[html.Div([html.Span(k, className="qc-lbl"),
                        html.Span(str(v), className=cls_map.get(cls,"qc-info"))],
                       className="qc-row") for k,v,cls in items],
        ], className="qc-block"),
        html.Div(style={"height":"10px"}),
        html.Div([
            html.Div(f"Anomalies dtectees — {len(issues)}", className="qc-title"),
            make_table([{"Anomalie":i} for i in issues[:50]]) if issues
            else banner("Aucune anomalie detectee.", "ok"),
        ], className="qc-block"),
    ], className="tab-content-anim")
