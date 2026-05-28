from __future__ import annotations
import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify, redirect, request, Response

from auth.microsoft_flow import build_auth_url, exchange_code, fetch_user_profile, revoke_token
from auth.role_check import check_role, NoUnifieldRoleError
from auth.session_cookie import get_cookie, set_cookie
from auth.session_store import create_session, delete_session, get_session
import config

log = logging.getLogger(__name__)

bp = Blueprint("auth", __name__, url_prefix="/unifield/auth")

_pending_states: dict[str, float] = {}   # state_token -> created_at (epoch)
_STATE_TTL = 600                          # 10 min — un flow OAuth non complété expire


def cleanup_pending_states() -> None:
    """Purge les tokens OAuth dont le TTL est dépassé."""
    now     = time.time()
    expired = [s for s, ts in _pending_states.items() if now - ts > _STATE_TTL]
    for s in expired:
        _pending_states.pop(s, None)


@bp.route("/login")
def login():
    cleanup_pending_states()              # lazy cleanup avant chaque nouveau login
    state = secrets.token_urlsafe(16)
    _pending_states[state] = time.time()
    try:
        url = build_auth_url(state)
    except Exception as exc:
        log.error('{"event": "auth_build_url_failed", "detail": "%s"}', str(exc)[:200])
        return Response("Auth-api indisponible", status=503)
    return redirect(url, code=302)


@bp.route("/complete")
def complete():
    auth_code = request.args.get("auth_code", "")
    state     = request.args.get("state", "")

    if not auth_code or not state or state not in _pending_states:
        return Response("État invalide", status=400)
    if time.time() - _pending_states[state] > _STATE_TTL:
        _pending_states.pop(state, None)
        return Response("État expiré — relancer la connexion", status=400)
    _pending_states.pop(state, None)

    try:
        token_data = exchange_code(auth_code)
    except Exception as exc:
        log.error('{"event": "auth_exchange_failed", "detail": "%s"}', str(exc)[:200])
        return Response("Erreur auth-api", status=502)

    access_token = token_data.get("accessToken", "")
    user_info    = fetch_user_profile(access_token) or token_data.get("user") or {}

    try:
        role = check_role(user_info)
    except NoUnifieldRoleError:
        email = user_info.get("email", "?")
        log.warning('{"event": "login_denied", "email": "%s", "reason": "no_role"}', email)
        return Response(
            "<html><body><h2>Accès refusé — aucun rôle UNIFIELD</h2>"
            "<p>Votre compte ne dispose d'aucun rôle UNIFIELD valide.</p></body></html>",
            status=403,
            mimetype="text/html",
        )

    email = user_info.get("email", "")
    sid   = create_session(email, role, access_token=access_token)
    log.info('{"event": "login", "user": "%s", "role": "%s"}', email, role)
    resp = redirect(config.BASE_PATH, code=302)
    set_cookie(resp, sid)
    return resp


@bp.route("/logout")
def logout():
    sid = get_cookie(request)
    if sid:
        session = get_session(sid)
        if session and session.get("access_token"):
            revoke_token(session["access_token"])
        delete_session(sid)
    log.info('{"event": "logout"}')
    resp = redirect(config.BASE_PATH + "auth/login", code=302)
    resp.set_cookie("unifield.sid", "", expires=0, path=config.BASE_PATH)
    return resp


@bp.route("/me")
def me():
    sid  = get_cookie(request)
    data = get_session(sid) if sid else None
    if not data:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"email": data["email"], "role": data["role"]})


def register_mailgun_webhook(server):
    @server.route("/unifield/mailgun-webhook", methods=["POST"])
    def mailgun_webhook():
        payload   = request.form
        timestamp = payload.get("timestamp", "")
        token     = payload.get("token", "")
        signature = payload.get("signature", "")

        key = config.MAILGUN_WEBHOOK_SIGNING_KEY
        if not key:
            return jsonify({"error": "not configured"}), 503

        expected = hmac.new(
            key.encode("utf-8"),
            f"{timestamp}{token}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            return jsonify({"error": "invalid signature"}), 403

        event_type = payload.get("event", "unknown")
        msg_id     = payload.get("Message-Id") or payload.get("message-id", "")

        if msg_id:
            try:
                from api.mongo_client import get_db
                db = get_db()
                db["alert_history"].update_one(
                    {"mailgun_message_id": msg_id},
                    {"$set": {"mailgun_status": event_type}},
                )
            except Exception as exc:
                log.warning('{"event": "mailgun_webhook_db_err", "detail": "%s"}', str(exc)[:120])

        log.info('{"event": "mailgun_webhook", "type": "%s", "ts": "%s"}',
                 event_type, datetime.now(timezone.utc).isoformat())
        return jsonify({"ok": True})
