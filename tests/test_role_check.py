import pytest
from auth.role_check import check_role, NoUnifieldRoleError


def _ui(roles):
    return {"roles": roles}


def test_admin():
    assert check_role(_ui(["admin"])) == "admin"


def test_unifield_admin():
    assert check_role(_ui(["app:unifield:admin"])) == "app:unifield:admin"


def test_unifield_read():
    assert check_role(_ui(["app:unifield:read"])) == "app:unifield:read"


def test_unifield_write():
    assert check_role(_ui(["app:unifield:write"])) == "app:unifield:write"


def test_no_valid_role():
    with pytest.raises(NoUnifieldRoleError):
        check_role(_ui([]))


def test_non_unifield_role_only():
    with pytest.raises(NoUnifieldRoleError):
        check_role(_ui(["some:other:role", "another:role"]))


def test_priority_order():
    # admin takes priority over read
    result = check_role(_ui(["app:unifield:read", "admin"]))
    assert result == "admin"
