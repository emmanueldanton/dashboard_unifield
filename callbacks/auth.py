from __future__ import annotations
from dash import Output, Input

from config import BATTERY_WARNING_THRESHOLD, ENDING_SOON_DAYS, PAST_DAYS
from cache import register_creds


def register(app):

    @app.callback(
        Output("store-creds", "data"),
        Input("input-email", "value"),
        Input("input-key",   "value"),
    )
    def save_creds(email, key):
        if email and key:
            register_creds(email, key)
            return {"email": email, "key": key}
        return None

    @app.callback(
        Output("store-seuils", "data"),
        Input("seuil-battery",  "value"),
        Input("seuil-ending",   "value"),
        Input("seuil-activity", "value"),
    )
    def save_seuils(batt, ending, activity):
        return {
            "bt": batt     or BATTERY_WARNING_THRESHOLD,
            "ed": ending   or ENDING_SOON_DAYS,
            "am": activity or "00:01",
            "pd": PAST_DAYS,
        }
