from __future__ import annotations
import config

COOKIE_NAME = "unifield.sid"


def set_cookie(response, sid: str):
    response.set_cookie(
        COOKIE_NAME,
        sid,
        httponly=True,
        samesite="Lax",
        secure=(config.APP_ENV == "production"),
        path=config.BASE_PATH,
        max_age=86_400,
    )
    return response


def get_cookie(request) -> str | None:
    return request.cookies.get(COOKIE_NAME)
