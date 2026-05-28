from __future__ import annotations
import logging
import requests
import config

log = logging.getLogger(__name__)


def probe_auth_api() -> None:
    """Vérifie les endpoints auth-api au démarrage (non-bloquant, log uniquement).

    Appelé dans un thread daemon depuis app.py si UNIFIELD_DEV_AUTH_BYPASS est False.
    Un status < 500 indique que l'endpoint existe ; 400/422 est attendu sur une probe.
    """
    if not config.AUTH_API_BASE_URL:
        log.warning(
            '{"event": "auth_api_probe_skip", "reason": "AUTH_API_BASE_URL not set",'
            ' "impact": "SSO will fail in production"}'
        )
        return
    if not config.AUTH_API_SERVICE_CONSUMER_SECRET:
        log.warning(
            '{"event": "auth_api_probe_skip",'
            ' "reason": "AUTH_API_SERVICE_CONSUMER_SECRET not set",'
            ' "impact": "code exchange will fail"}'
        )
    try:
        resp = requests.get(
            f"{config.AUTH_API_BASE_URL}/api/v1/auth/login-url",
            params={"redirect_uri": "http://probe", "state": "probe", "slug": "unifield"},
            timeout=5,
        )
        reachable = resp.status_code < 500
        log.info(
            '{"event": "auth_api_probe", "url": "%s", "status": %d, "reachable": %s}',
            config.AUTH_API_BASE_URL, resp.status_code, reachable,
        )
    except Exception as exc:
        log.warning(
            '{"event": "auth_api_probe_failed", "url": "%s", "detail": "%s",'
            ' "impact": "SSO may not work in production"}',
            config.AUTH_API_BASE_URL, str(exc)[:120],
        )


def build_auth_url(state: str) -> str:
    redirect_uri = (
        config.PUBLIC_URL.rstrip("/")
        + config.BASE_PATH.rstrip("/")
        + "/auth/complete"
    )
    resp = requests.get(
        f"{config.AUTH_API_BASE_URL}/api/v1/auth/login-url",
        params={"redirect_uri": redirect_uri, "state": state, "slug": "unifield"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["url"]


def exchange_code(code: str, state: str) -> dict:
    resp = requests.post(
        f"{config.AUTH_API_BASE_URL}/api/v1/auth/exchange",
        json={
            "code":   code,
            "state":  state,
            "slug":   "unifield",
            "secret": config.AUTH_API_SERVICE_CONSUMER_SECRET,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
