"""
NotificationService — sends care team escalation alerts.

The transport is abstracted behind ``BaseNotifier`` so business logic never
knows which provider is in use. Providers are selected at runtime by
``settings.notification_provider``:

    ntfy        free push notifications via ntfy.sh (no API key required)
    telegram    Telegram bot message (free; needs bot token + chat id)
    twilio_sms  SMS via Twilio (reuses Twilio creds; carrier charges apply)
    sns         AWS SNS (legacy; requires a signed AWS BAA)
    noop        logs only — used in tests and local development

HIPAA: alert payloads carry UUIDs only, never PHI (no name/DOB/phone).
"""
import json
import logging
import uuid
from abc import ABC, abstractmethod

import httpx

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_SEVERITY_PREFIX = {
    "urgent": "[URGENT] CareGuard",
    "high": "[HIGH] CareGuard",
    "medium": "[MEDIUM] CareGuard",
}
# ntfy priority levels: 5=max … 1=min
_NTFY_PRIORITY = {"urgent": "5", "high": "4", "medium": "3"}


class BaseNotifier(ABC):
    @abstractmethod
    async def send_escalation(
        self,
        session_id: uuid.UUID,
        patient_id: uuid.UUID,
        severity: str,
        reason: str,
        symptoms: list[str],
    ) -> None: ...

    @staticmethod
    def _subject(severity: str) -> str:
        return _SEVERITY_PREFIX.get(severity, "CareGuard")

    @staticmethod
    def _body(patient_id: uuid.UUID, severity: str, reason: str, symptoms: list[str]) -> str:
        # UUIDs only — never PHI.
        sym = ", ".join(symptoms) if symptoms else "none reported"
        return (
            f"Patient {patient_id} — {severity.upper()} escalation\n"
            f"Reason: {reason}\n"
            f"Symptoms: {sym}"
        )


class NtfyNotifier(BaseNotifier):
    """Free push notifications via ntfy.sh — no account or API key needed."""

    def __init__(self) -> None:
        if not settings.ntfy_topic:
            raise ValueError("NTFY_TOPIC is not set; cannot send ntfy alerts")
        self._url = f"{settings.ntfy_base_url.rstrip('/')}/{settings.ntfy_topic}"

    async def send_escalation(self, session_id, patient_id, severity, reason, symptoms) -> None:
        body = self._body(patient_id, severity, reason, symptoms)
        # HTTP header values must be ASCII — keep the title plain (no em-dash).
        headers = {
            "Title": f"{self._subject(severity)} - Patient escalation",
            "Priority": _NTFY_PRIORITY.get(severity, "3"),
            "Tags": "rotating_light,hospital",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.post(self._url, content=body.encode("utf-8"), headers=headers)
                resp.raise_for_status()
            logger.info(
                "Escalation ntfy sent session_id=%s severity=%s", session_id, severity
            )
        except Exception:
            logger.exception("ntfy publish failed session_id=%s", session_id)
            raise


class TelegramNotifier(BaseNotifier):
    """Sends a message via the Telegram Bot API (free)."""

    def __init__(self) -> None:
        if not (settings.telegram_bot_token and settings.telegram_chat_id):
            raise ValueError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")
        self._url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    async def send_escalation(self, session_id, patient_id, severity, reason, symptoms) -> None:
        text = f"*{self._subject(severity)}*\n{self._body(patient_id, severity, reason, symptoms)}"
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.post(
                    self._url,
                    json={
                        "chat_id": settings.telegram_chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
                    },
                )
                resp.raise_for_status()
            logger.info(
                "Escalation telegram sent session_id=%s severity=%s", session_id, severity
            )
        except Exception:
            logger.exception("Telegram send failed session_id=%s", session_id)
            raise


class TwilioSMSNotifier(BaseNotifier):
    """Sends the alert as an SMS via Twilio (uses the configured Twilio creds)."""

    def __init__(self) -> None:
        if not settings.escalation_sms_to:
            raise ValueError("ESCALATION_SMS_TO is not set; cannot send SMS alerts")
        from twilio.rest import Client  # imported lazily; heavy SDK

        self._client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self._to = settings.escalation_sms_to
        self._from = settings.twilio_phone_number

    async def send_escalation(self, session_id, patient_id, severity, reason, symptoms) -> None:
        import asyncio

        message = f"{self._subject(severity)}\n{self._body(patient_id, severity, reason, symptoms)}"
        try:
            # Twilio's SDK is sync; offload so we don't block the event loop.
            sms = await asyncio.to_thread(
                self._client.messages.create, body=message, from_=self._from, to=self._to
            )
            logger.info(
                "Escalation SMS sent session_id=%s severity=%s sid=%s",
                session_id, severity, sms.sid,
            )
        except Exception:
            logger.exception("Twilio SMS failed session_id=%s", session_id)
            raise


class SNSNotifier(BaseNotifier):
    """Legacy AWS SNS transport. Requires a signed AWS BAA."""

    def __init__(self) -> None:
        import boto3  # imported lazily so AWS SDK isn't required for other providers

        self._sns = boto3.client("sns", region_name=settings.aws_region)

    async def send_escalation(self, session_id, patient_id, severity, reason, symptoms) -> None:
        payload = {
            "type": "ESCALATION",
            "severity": severity,
            "patient_id": str(patient_id),
            "session_id": str(session_id),
            "reason": reason,
            "symptoms": symptoms,
        }
        try:
            self._sns.publish(
                TopicArn=settings.sns_escalation_topic_arn,
                Subject=f"{self._subject(severity)} — Patient escalation",
                Message=json.dumps(payload),
                MessageAttributes={
                    "severity": {"DataType": "String", "StringValue": severity}
                },
            )
            logger.info(
                "Escalation SNS published session_id=%s severity=%s", session_id, severity
            )
        except Exception:
            logger.exception("SNS publish failed session_id=%s", session_id)
            raise


class NoOpNotifier(BaseNotifier):
    """Used in tests and local development."""

    async def send_escalation(self, session_id, patient_id, severity, reason, symptoms) -> None:
        logger.info(
            "NoOpNotifier escalation session_id=%s severity=%s reason=%s",
            session_id, severity, reason,
        )


_PROVIDERS: dict[str, type[BaseNotifier]] = {
    "ntfy": NtfyNotifier,
    "telegram": TelegramNotifier,
    "twilio_sms": TwilioSMSNotifier,
    "sns": SNSNotifier,
    "noop": NoOpNotifier,
}


def get_notifier() -> BaseNotifier:
    """Build the notifier named by ``settings.notification_provider``.

    Falls back to ``NoOpNotifier`` if the selected provider is misconfigured,
    so a bad alert setting can never take the call flow down.
    """
    from config import BAA_NOTIFICATION_PROVIDERS

    provider = (settings.notification_provider or "noop").lower()
    if settings.is_production and provider not in BAA_NOTIFICATION_PROVIDERS:
        # Defence in depth — config validation already blocks this at startup.
        raise RuntimeError(
            f"notification_provider={provider!r} has no BAA and is forbidden in production"
        )
    cls = _PROVIDERS.get(provider)
    if cls is None:
        logger.warning("Unknown notification_provider=%r; using no-op", provider)
        return NoOpNotifier()
    try:
        return cls()
    except Exception:
        logger.exception(
            "Notifier %r failed to initialize; falling back to no-op", provider
        )
        return NoOpNotifier()
