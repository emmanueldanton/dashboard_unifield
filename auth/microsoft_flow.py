from __future__ import annotations
import logging
import uuid
from urllib.parse import quote

import requests
import config

log = logging.getLogger(__name__)


def probe_auth_api() -> None:
    """Vérifie l'endpoint auth-api au démarrage (non-bloquant, log uniquement)."""
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
            f"{config.AUTH_API_BASE_URL}/v1/auth/microsoft/start",
            params={"consumer": "unifield", "returnTo": "http://probe"},
            allow_redirects=False,
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
    """Construit l'URL de démarrage SSO vers auth-api.

    Auth-api redirige le browser vers Microsoft Entra, puis revient sur returnTo
    avec ?auth_code=<opaque>. L'état CSRF est embarqué dans returnTo.
    """
    callback = (
        config.PUBLIC_URL.rstrip("/")
        + config.BASE_PATH.rstrip("/")
        + "/auth/complete"
    )
    return_to = f"{callback}?state={state}"
    return (
        f"{config.AUTH_API_BASE_URL}/v1/auth/microsoft/start"
        f"?consumer=unifield&returnTo={quote(return_to, safe='')}"
    )


def exchange_code(code: str) -> dict:
    """Échange un auth_code opaque contre les tokens (accessToken, refreshToken, user).

    Header Authorization: ServiceConsumer unifield:<secret>  (jamais dans le body).
    """
    resp = requests.post(
        f"{config.AUTH_API_BASE_URL}/v1/auth/code/exchange",
        headers={
            "Authorization": (
                f"ServiceConsumer unifield:{config.AUTH_API_SERVICE_CONSUMER_SECRET}"
            ),
            "Content-Type": "application/json",
            "X-Request-ID": str(uuid.uuid4()),
        },
        json={"code": code},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_user_profile(access_token: str) -> dict | None:
    """Récupère le profil canonique depuis auth-api (anti-spoofing).

    Retourne None si indisponible - l'appelant doit utiliser token_data["user"] en fallback.
    """
    try:
        resp = requests.get(
            f"{config.AUTH_API_BASE_URL}/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
        if resp.ok:
            return resp.json()
    except Exception as exc:
        log.warning(
            '{"event": "fetch_user_profile_failed", "detail": "%s"}', str(exc)[:120]
        )
    return None


def revoke_token(access_token: str) -> None:
    """Révoque l'access token côté auth-api (best-effort, ne bloque jamais)."""
    try:
        requests.post(
            f"{config.AUTH_API_BASE_URL}/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={},
            timeout=5,
        )
    except Exception:
        pass
