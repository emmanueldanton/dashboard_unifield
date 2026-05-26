from __future__ import annotations
import requests
import config


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
