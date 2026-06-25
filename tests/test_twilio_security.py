"""Twilio webhook signature validation (integrity / anti-spoofing)."""
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from twilio.request_validator import RequestValidator

import api.deps as deps
from api.deps import verify_twilio_signature

_TOKEN = "test-auth-token"
_URL = "https://api.careguard.health/twilio/status"


def _request(form: dict, signature: str) -> Request:
    body = urlencode(form).encode()
    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "https",
        "server": ("api.careguard.health", 443),
        "path": "/twilio/status",
        "query_string": b"",
        "headers": [
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"x-twilio-signature", signature.encode()),
            (b"host", b"api.careguard.health"),
        ],
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


@pytest.fixture(autouse=True)
def _enable_validation(monkeypatch):
    monkeypatch.setattr(deps.get_settings(), "twilio_validate_signatures", True)
    monkeypatch.setattr(deps.get_settings(), "twilio_auth_token", _TOKEN)
    # The validator reconstructs the signed URL from base_url (robust behind a
    # tunnel/proxy), so base_url must match the host Twilio signed against.
    monkeypatch.setattr(deps.get_settings(), "base_url", "https://api.careguard.health")


@pytest.mark.asyncio
async def test_valid_signature_passes():
    form = {"CallSid": "CA123", "CallStatus": "completed"}
    signature = RequestValidator(_TOKEN).compute_signature(_URL, form)
    # Should not raise.
    await verify_twilio_signature(_request(form, signature))


@pytest.mark.asyncio
async def test_invalid_signature_is_rejected():
    form = {"CallSid": "CA123", "CallStatus": "completed"}
    with pytest.raises(HTTPException) as exc:
        await verify_twilio_signature(_request(form, "bogus-signature"))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_validation_skipped_without_token(monkeypatch):
    monkeypatch.setattr(deps.get_settings(), "twilio_auth_token", "")
    # No token configured (dev) — validation is a no-op, never raises.
    await verify_twilio_signature(_request({"CallSid": "CA1"}, "anything"))


# --- WebSocket handshake authorization ---

class _FakeWS:
    def __init__(self, params: dict):
        self.query_params = params


def test_ws_handshake_accepts_valid_token(monkeypatch):
    import api.routes.twilio_voice as tv
    from security.auth import create_stream_token

    monkeypatch.setattr(tv.settings, "twilio_validate_signatures", True)
    sid = "22222222-2222-2222-2222-222222222222"
    ws = _FakeWS({"token": create_stream_token(sid)})
    assert tv._authorize_stream(ws, sid) is True


def test_ws_handshake_rejects_missing_token_in_prod(monkeypatch):
    import api.routes.twilio_voice as tv

    monkeypatch.setattr(tv.settings, "twilio_validate_signatures", True)
    assert tv._authorize_stream(_FakeWS({}), "any-session") is False


def test_ws_handshake_rejects_token_for_other_session(monkeypatch):
    import api.routes.twilio_voice as tv
    from security.auth import create_stream_token

    monkeypatch.setattr(tv.settings, "twilio_validate_signatures", True)
    ws = _FakeWS({"token": create_stream_token("session-A")})
    assert tv._authorize_stream(ws, "session-B") is False
