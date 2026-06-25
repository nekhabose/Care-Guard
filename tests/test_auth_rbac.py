"""Dashboard auth & RBAC — token lifecycle, expiry, and role enforcement."""
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api.deps import get_current_user, require_role
from security.auth import (
    InvalidTokenError,
    Role,
    create_access_token,
    create_stream_token,
    decode_token,
    verify_stream_token,
)


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_token_roundtrip_carries_role():
    token = create_access_token("user-1", Role.CARE_LEAD)
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["role"] == "care_lead"


def test_expired_token_is_rejected():
    token = create_access_token("user-1", Role.NURSE, expires_minutes=-1)
    with pytest.raises(InvalidTokenError):
        decode_token(token)


def test_get_current_user_rejects_garbage():
    with pytest.raises(HTTPException) as exc:
        get_current_user(_creds("not-a-jwt"))
    assert exc.value.status_code == 401


def test_require_role_allows_matching_role():
    dep = require_role(Role.CARE_LEAD, Role.ADMIN)
    user = {"sub": "u", "role": "admin"}
    assert dep(user=user) is user


def test_require_role_denies_insufficient_role():
    dep = require_role(Role.CARE_LEAD, Role.ADMIN)
    with pytest.raises(HTTPException) as exc:
        dep(user={"sub": "u", "role": "nurse"})
    assert exc.value.status_code == 403


# --- Twilio WS handshake tokens ---

def test_stream_token_roundtrip():
    sid = "11111111-1111-1111-1111-111111111111"
    verify_stream_token(create_stream_token(sid), sid)  # must not raise


def test_stream_token_rejected_for_wrong_session():
    token = create_stream_token("session-A")
    with pytest.raises(InvalidTokenError):
        verify_stream_token(token, "session-B")


def test_stream_token_rejects_access_token():
    # An ordinary dashboard token has no stream purpose — must not authorize a WS.
    access = create_access_token("session-A", Role.ADMIN)
    with pytest.raises(InvalidTokenError):
        verify_stream_token(access, "session-A")
