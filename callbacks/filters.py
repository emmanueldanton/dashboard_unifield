from __future__ import annotations
import dash
from dash import Output, Input, State


def register(app):

    @app.callback(
        Output("store-filtre-proj", "data"),
        Input("proj-statut", "value"),
        prevent_initial_call=True,
    )
    def update_filtre_proj(val):
        return val or "Tous"

    @app.callback(
        Output("store-filtre-search", "data"),
        Input("proj-search", "value"),
        prevent_initial_call=True,
    )
    def update_filtre_search(val):
        return val or ""

    @app.callback(
        Output("store-filtre-type", "data"),
        Input("proj-type", "value"),
        prevent_initial_call=True,
    )
    def update_filtre_type(val):
        return val or "Tous"

    @app.callback(
        Output("store-filtre-cap", "data"),
        Input("cap-conn", "value"),
        Input("cap-batt", "value"),
        Input("cap-proj", "value"),
        State("store-filtre-cap", "data"),
        prevent_initial_call=True,
    )
    def update_filtre_cap(conn, batt, proj, current):
        return {
            "conn": conn or current.get("conn","Connectés"),
            "batt": batt or current.get("batt","Tous"),
            "proj": proj or current.get("proj","Tous"),
        }

    @app.callback(
        Output("store-projet-selec", "data"),
        Input("table-projets", "derived_virtual_selected_rows"),
        State("table-projets", "derived_virtual_data"),
        prevent_initial_call=True,
    )
    def select_projet(sel_rows, virt_data):
        if not sel_rows or not virt_data:
            return None
        return virt_data[sel_rows[0]].get("_pid")
