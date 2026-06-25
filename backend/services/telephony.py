"""
Telephony helper — the single place that creates an outbound Twilio call.

Both the scheduled Celery outreach task (``tasks.outreach``) and the on-demand
"call now" path (``services.call_trigger``) route through here so there is one
source of truth for how a CareGuard voice call is placed.
"""
import logging

from config import Settings
from exceptions import TwilioCallError

logger = logging.getLogger(__name__)


def place_outbound_call(settings: Settings, session_id: str, to_phone: str) -> str:
    """Place an outbound voice call and return the Twilio call SID.

    Raises ``TwilioCallError`` if Twilio is not configured or the API rejects
    the call. The TwiML webhook and status callback both carry ``session_id``
    so the live conversation is wired back to the right OutreachSession.
    """
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_phone_number):
        raise TwilioCallError(
            "Twilio is not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN "
            "and TWILIO_PHONE_NUMBER to place real calls."
        )

    # Imported lazily so the dependency isn't required for non-calling code paths.
    from twilio.base.exceptions import TwilioRestException
    from twilio.rest import Client

    call_kwargs: dict = {
        "to": to_phone,
        "from_": settings.twilio_phone_number,
        "url": f"{settings.base_url}/twilio/twiml?session_id={session_id}",
        "status_callback": f"{settings.base_url}/twilio/status",
        "record": settings.recordings_enabled,
    }
    if settings.recordings_enabled:
        # Capture the recording into our KMS-encrypted bucket once it's ready.
        call_kwargs["recording_status_callback"] = f"{settings.base_url}/twilio/recording"
        call_kwargs["recording_status_callback_event"] = ["completed"]

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    try:
        call = client.calls.create(**call_kwargs)
    except TwilioRestException as exc:
        raise TwilioCallError(str(exc)) from exc

    logger.info("Call initiated session_id=%s twilio_sid=%s", session_id, call.sid)
    return call.sid
