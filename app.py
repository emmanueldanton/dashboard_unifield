from __future__ import annotations
import logging

import dash
from flask import jsonify, redirect, request

import config
from auth.routes import bp as auth_bp, register_mailgun_webhook
from auth.session_cookie import get_cookie
from auth.session_store import get_session
from ui.layout import create_layout
from callbacks import register_all_callbacks

log = logging.getLogger(__name__)

app = dash.Dash(
    __name__,
    title="CAD.42 — UNIFIELD Dashboard",
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    assets_folder="assets",
    requests_pathname_prefix=config.BASE_PATH,
    routes_pathname_prefix=config.BASE_PATH,
)
server = app.server

server.register_blueprint(auth_bp)
register_mailgun_webhook(server)

_BYPASS_PATHS = {"/unifield/mailgun-webhook"}
_BYPASS_PREFIX = "/unifield/auth/"
_ASSET_PREFIX  = "/unifield/assets/"
_DASH_PREFIX   = "/unifield/_dash"


@server.before_request
def check_auth():
    path = request.path

    if (path.startswith(_BYPASS_PREFIX)
            or path in _BYPASS_PATHS
            or path.startswith(_ASSET_PREFIX)
            or path.startswith(_DASH_PREFIX)):
        return None

    bypass = config.UNIFIELD_DEV_AUTH_BYPASS and config.APP_ENV != "production"
    if bypass:
        return None

    sid     = get_cookie(request)
    session = get_session(sid) if sid else None
    if not session:
        if "application/json" in request.headers.get("Accept", ""):
            return jsonify({"error": "unauthorized"}), 401
        return redirect(config.BASE_PATH + "auth/login", code=302)

    return None


app.layout = create_layout()
register_all_callbacks(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)
