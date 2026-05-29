from __future__ import annotations
import logging

from dash import Output, Input

import config
from cache import register_creds
from config import BATTERY_WARNING_THRESHOLD, ENDING_SOON_DAYS, PAST_DAYS

log = logging.getLogger(__name__)


def register(app):

    @app.callback(
        Output("store-creds", "data"),
        Input("url", "pathname"),
    )
    def load_creds(pathname):
        """Populate store-creds from SSO session on every page navigation.

        In dev bypass mode (double condition), returns a synthetic dev credential.
        """
        bypass = config.UNIFIELD_DEV_AUTH_BYPASS and config.APP_ENV != "production"
        if bypass:
            register_creds()
            return {"email": "dev@cad42.local", "role": "admin", "display_name": "Dev User"}

        try:
            from flask import request as flask_request
            from auth.session_cookie import get_cookie
            from auth.session_store import get_session
            sid     = get_cookie(flask_request)
            session = get_session(sid) if sid else None
            if session:
                register_creds()
                return {
                    "email":        session["email"],
                    "display_name": session.get("display_name", session["email"]),
                    "role":         session["role"],
                }
        except Exception as exc:
            log.warning('{"event": "load_creds_error", "detail": "%s"}', str(exc)[:200])

        return None

    @app.callback(
        Output("store-seuils", "data"),
        Input("seuil-battery", "value"),
        Input("seuil-ending",  "value"),
        prevent_initial_call=True,
    )
    def save_seuils(batt, ending):
        return {
            "bt": batt   or BATTERY_WARNING_THRESHOLD,
            "ed": ending or ENDING_SOON_DAYS,
            "pd": PAST_DAYS,
        }
