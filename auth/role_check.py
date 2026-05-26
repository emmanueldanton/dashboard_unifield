from __future__ import annotations

VALID_ROLES = (
    "admin",
    "app:unifield:admin",
    "app:unifield:write",
    "app:unifield:read",
)


class NoUnifieldRoleError(Exception):
    pass


def check_role(user_info: dict) -> str:
    roles = user_info.get("roles") or []
    for role in VALID_ROLES:
        if role in roles:
            return role
    raise NoUnifieldRoleError(f"No valid UNIFIELD role found in: {roles}")
