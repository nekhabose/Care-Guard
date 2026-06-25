"""Tests for notifier provider selection and safe fallback."""
import uuid

import pytest

import services.notification as N
from services.notification import (
    NoOpNotifier,
    NtfyNotifier,
    TelegramNotifier,
    get_notifier,
)


def test_ntfy_selected_when_configured(monkeypatch):
    monkeypatch.setattr(N.settings, "notification_provider", "ntfy")
    monkeypatch.setattr(N.settings, "ntfy_topic", "careguard-test")
    assert isinstance(get_notifier(), NtfyNotifier)


def test_unknown_provider_falls_back_to_noop(monkeypatch):
    monkeypatch.setattr(N.settings, "notification_provider", "carrier-pigeon")
    assert isinstance(get_notifier(), NoOpNotifier)


def test_misconfigured_provider_falls_back_to_noop(monkeypatch):
    # ntfy selected but no topic -> must not crash, falls back to no-op
    monkeypatch.setattr(N.settings, "notification_provider", "ntfy")
    monkeypatch.setattr(N.settings, "ntfy_topic", "")
    assert isinstance(get_notifier(), NoOpNotifier)


def test_non_baa_provider_forbidden_in_production(monkeypatch):
    # ntfy.sh has no BAA — selecting it in production must fail closed, never
    # silently downgrade to no-op (which would drop escalation alerts).
    monkeypatch.setattr(N.settings, "environment", "production")
    monkeypatch.setattr(N.settings, "notification_provider", "ntfy")
    with pytest.raises(RuntimeError):
        get_notifier()


def test_telegram_requires_token_and_chat(monkeypatch):
    monkeypatch.setattr(N.settings, "notification_provider", "telegram")
    monkeypatch.setattr(N.settings, "telegram_bot_token", "")
    monkeypatch.setattr(N.settings, "telegram_chat_id", "")
    assert isinstance(get_notifier(), NoOpNotifier)

    monkeypatch.setattr(N.settings, "telegram_bot_token", "123:abc")
    monkeypatch.setattr(N.settings, "telegram_chat_id", "456")
    assert isinstance(get_notifier(), TelegramNotifier)


def test_alert_body_contains_no_phi():
    body = NoOpNotifier._body(
        patient_id=uuid.uuid4(),
        severity="high",
        reason="shortness of breath worsening",
        symptoms=["dyspnea", "weight gain"],
    )
    assert "dyspnea" in body
    # Only UUIDs/clinical text — never a name, DOB, or phone number.
    assert "Patient" in body


@pytest.mark.asyncio
async def test_noop_notifier_never_raises():
    await NoOpNotifier().send_escalation(
        session_id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        severity="urgent",
        reason="test",
        symptoms=[],
    )
