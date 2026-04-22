from __future__ import annotations
import dash
from dash import html, Output, Input, State, ctx

from config import C
from ui.components import banner, make_table


def register(app):

    # ── Dark mode ─────────────────────────────────────────────

    app.clientside_callback(
        """
        function(value, is_dark) {
            var new_dark = value && value.includes('dark');
            if (new_dark) {
                document.body.classList.add('dark');
            } else {
                document.body.classList.remove('dark');
            }
            return new_dark;
        }
        """,
        Output("store-dark-mode", "data"),
        Input("btn-dark-mode",    "value"),
        State("store-dark-mode",  "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(is_dark) {
            if (is_dark) {
                document.body.classList.add('dark');
                return ['dark'];
            } else {
                document.body.classList.remove('dark');
                return [];
            }
        }
        """,
        Output("btn-dark-mode", "value"),
        Input("store-dark-mode", "data"),
    )

    # ── Close modals ──────────────────────────────────────────

    app.clientside_callback(
        """
        function(n1, n2) {
            if (n1 || n2) return null;
            return window.dash_clientside.no_update;
        }
        """,
        Output("store-projet-selec", "data", allow_duplicate=True),
        Input("btn-close-modal",  "n_clicks"),
        Input("modal-projet-bg",  "n_clicks"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(n1, n2) {
            if (n1 || n2) return null;
            return window.dash_clientside.no_update;
        }
        """,
        Output("store-capteur-selec", "data", allow_duplicate=True),
        Input("btn-close-capteur", "n_clicks"),
        Input("modal-capteur-bg",  "n_clicks"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        """
        function(n1, n2) {
            if (n1 || n2) return false;
            return window.dash_clientside.no_update;
        }
        """,
        Output("store-modal-archives", "data", allow_duplicate=True),
        Input("btn-close-archives", "n_clicks"),
        Input("modal-archives-bg",  "n_clicks"),
        prevent_initial_call=True,
    )

    # ── Smooth scroll ─────────────────────────────────────────

    app.clientside_callback(
        """
        function(anchor) {
            if (!anchor) return '';
            setTimeout(function() {
                var el = document.getElementById(anchor);
                if (el) {
                    el.scrollIntoView({behavior: 'smooth', block: 'start'});
                    el.style.outline = '2px solid #DC2626';
                    setTimeout(function() { el.style.outline = ''; }, 2000);
                }
            }, 300);
            return '';
        }
        """,
        Output("scroll-trigger", "children"),
        Input("store-urgence-anchor", "data"),
        prevent_initial_call=True,
    )

    # ── Urgences table search ─────────────────────────────────

    @app.callback(
        Output({"type": "urgence-table", "section": dash.MATCH}, "children"),
        Input({"type": "urgence-search", "section": dash.MATCH}, "value"),
        State({"type": "urgence-rows",   "section": dash.MATCH}, "data"),
        prevent_initial_call=True,
    )
    def filter_urgence_table(query, rows):
        if not rows:
            return banner("Aucune donnée.", "info")
        if not query or not query.strip():
            return make_table(rows)
        q = query.strip().lower()
        filtered = [
            r for r in rows
            if any(q in str(v).lower() for v in r.values())
        ]
        if not filtered:
            return html.Div(
                f"Aucun résultat pour « {query} »",
                style={"color": C["text_muted"], "fontSize": "0.82rem", "padding": "12px 0"}
            )
        return make_table(filtered)

    # ── Capteur selection ─────────────────────────────────────

    @app.callback(
        Output("store-capteur-selec", "data", allow_duplicate=True),
        Input({"type": "urgence-table", "section": dash.ALL}, "selected_rows"),
        State({"type": "urgence-rows",  "section": dash.ALL}, "data"),
        prevent_initial_call=True,
    )
    def select_capteur_urgence(all_selected, all_rows):
        for selected, rows in zip(all_selected, all_rows):
            if selected and rows and selected[0] < len(rows):
                return rows[selected[0]].get("_id")
        return dash.no_update

    @app.callback(
        Output("store-capteur-selec", "data", allow_duplicate=True),
        Input("table-capteurs", "selected_rows"),
        State("store-capteur-rows", "data"),
        prevent_initial_call=True,
    )
    def select_capteur_tab(selected, rows):
        if selected and rows and selected[0] < len(rows):
            return rows[selected[0]].get("_id")
        return dash.no_update

    # ── Flag badge click ──────────────────────────────────────

    @app.callback(
        Output("store-urgence-anchor", "data"),
        Output("active-tab", "data", allow_duplicate=True),
        Input({"type": "flag-badge", "anchor": dash.ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def flag_clicked(n_clicks):
        if not any(n_clicks):
            return dash.no_update, dash.no_update
        triggered = ctx.triggered_id
        if not triggered:
            return dash.no_update, dash.no_update
        anchor = triggered.get("anchor")
        return anchor, "urgences"
