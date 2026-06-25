"""Staff login — password hashing + AuthService credential checks."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from exceptions import AuthenticationError
from security.auth import Role, decode_token
from security.passwords import hash_password, verify_password
from services.auth_service import AuthService


def test_password_hash_roundtrip():
    h = hash_password("s3cret-pw")
    assert h != "s3cret-pw"
    assert verify_password("s3cret-pw", h)
    assert not verify_password("wrong", h)


def test_password_rejects_oversize():
    with pytest.raises(ValueError):
        hash_password("x" * 73)


def _service_with_user(user) -> AuthService:
    svc = AuthService.__new__(AuthService)  # bypass __init__/DB
    svc.db = None
    svc.users = SimpleNamespace(
        get_by_email=AsyncMock(return_value=user),
        update=AsyncMock(return_value=user),
    )
    return svc


def _user(active=True, password="correct-horse"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="nurse@hospital.org",
        name="Nora Nurse",
        role=Role.NURSE,
        is_active=active,
        password_hash=hash_password(password),
    )


@pytest.mark.asyncio
async def test_authenticate_success_mints_token_with_claims():
    user = _user()
    svc = _service_with_user(user)

    got_user, token, expires_in = await svc.authenticate("nurse@hospital.org", "correct-horse")

    assert got_user is user
    assert expires_in > 0
    claims = decode_token(token)
    assert claims["sub"] == str(user.id)
    assert claims["role"] == "nurse"
    assert claims["name"] == "Nora Nurse"
    assert claims["email"] == "nurse@hospital.org"
    svc.users.update.assert_awaited_once()  # last_login_at recorded


@pytest.mark.asyncio
async def test_authenticate_wrong_password_rejected():
    svc = _service_with_user(_user())
    with pytest.raises(AuthenticationError):
        await svc.authenticate("nurse@hospital.org", "nope")


@pytest.mark.asyncio
async def test_authenticate_unknown_email_rejected():
    svc = _service_with_user(None)
    with pytest.raises(AuthenticationError):
        await svc.authenticate("ghost@hospital.org", "whatever")


@pytest.mark.asyncio
async def test_authenticate_inactive_account_rejected():
    svc = _service_with_user(_user(active=False))
    with pytest.raises(AuthenticationError):
        await svc.authenticate("nurse@hospital.org", "correct-horse")
