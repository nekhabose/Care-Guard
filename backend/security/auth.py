"""
Dashboard authentication & role-based access control (HIPAA §164.312(a)(1)).

Tokens are short-lived JWTs carrying a ``sub`` (user id) and ``role``. The
``Role`` ladder is least-privilege: read access for everyone authenticated,
mutations restricted to clinical leads and admins.

Token minting lives here so the issuer (an SSO bridge, an admin CLI, or tests)
shares one code path with verification.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum

import jwt as pyjwt
from jwt.exceptions import InvalidTokenError

from config import get_settings


class Role(StrEnum):
    VIEWER = "viewer"        # read-only dashboards
    NURSE = "nurse"          # read + acknowledge
    CARE_LEAD = "care_lead"  # resolve escalations
    ADMIN = "admin"          # everything


# Mutating actions require at least these roles.
WRITE_ROLES: frozenset[str] = frozenset({Role.CARE_LEAD, Role.ADMIN})
# Any authenticated, recognised role may read.
READ_ROLES: frozenset[str] = frozenset({Role.VIEWER, Role.NURSE, Role.CARE_LEAD, Role.ADMIN})


def create_access_token(
    sub: str,
    role: str | Role,
    expires_minutes: int | None = None,
) -> str:
    """Mint a signed, expiring dashboard token."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    ttl = expires_minutes if expires_minutes is not None else settings.jwt_expiry_minutes
    payload = {
        "sub": sub,
        "role": str(role),
        "iat": now,
        "exp": now + timedelta(minutes=ttl),
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a token. Raises ``InvalidTokenError`` if bad/expired."""
    settings = get_settings()
    return pyjwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub"]},
    )


# --- Twilio media-stream (WebSocket) handshake tokens ---
#
# The ConversationRelay WebSocket has no per-message auth, so we bind it to the
# session with a short-lived signed token minted in the (signature-validated)
# TwiML response and verified on connect. This stops anyone who guesses a
# session UUID from opening the socket.
_STREAM_PURPOSE = "twilio_stream"
_STREAM_TTL_MINUTES = 15


def create_stream_token(session_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(session_id),
        "purpose": _STREAM_PURPOSE,
        "iat": now,
        "exp": now + timedelta(minutes=_STREAM_TTL_MINUTES),
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_stream_token(token: str, session_id: str) -> None:
    """Validate a stream token is well-formed, unexpired, and for this session.

    Raises ``InvalidTokenError`` on any mismatch.
    """
    settings = get_settings()
    payload = pyjwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub"]},
    )
    if payload.get("purpose") != _STREAM_PURPOSE or payload.get("sub") != str(session_id):
        raise InvalidTokenError("Stream token does not match session")


__all__ = [
    "Role",
    "WRITE_ROLES",
    "READ_ROLES",
    "create_access_token",
    "decode_token",
    "create_stream_token",
    "verify_stream_token",
    "InvalidTokenError",
]
