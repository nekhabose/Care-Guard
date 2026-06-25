"""
Outreach scheduling tasks — run via Celery + SQS.

Schedules the 5-touch outreach sequence based on risk level.
Each task initiates a Twilio outbound call at the right time.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from config import get_settings
from database import AsyncSessionLocal
from repositories.patient import PatientRepository
from repositories.session import SessionRepository
from services.telephony import place_outbound_call
from .celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

OUTREACH_HOURS: dict[str, list[int]] = {
    "high":   [24, 72, 168, 336, 720],
    "medium": [48, 168, 720],
    "low":    [168, 720],
}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def schedule_outreach_calls(self, patient_id: str, discharge_id: str) -> dict:
    """Create OutreachSession records and queue individual call tasks.

    Returns a JSON-serializable summary stored in the result backend, e.g.::

        {"patient_id": "...", "risk_level": "high", "sessions_scheduled": 5,
         "session_ids": [...]}
    """
    try:
        result = asyncio.run(_schedule(patient_id, discharge_id))
    except Exception as exc:
        logger.exception("schedule_outreach_calls failed patient_id=%s", patient_id)
        raise self.retry(exc=exc)
    logger.info(
        "schedule_outreach_calls done patient_id=%s sessions=%s",
        patient_id, result["sessions_scheduled"],
    )
    return result


async def _schedule(patient_id: str, discharge_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        patient = await PatientRepository(db).get(uuid.UUID(patient_id))
        # Honor the patient's right to opt out of automated outreach.
        if patient.call_opt_out:
            logger.info("Skipping outreach — patient opted out patient_id=%s", patient_id)
            return {
                "patient_id": patient_id,
                "discharge_id": discharge_id,
                "risk_level": patient.risk_level or "medium",
                "sessions_scheduled": 0,
                "session_ids": [],
                "skipped": "call_opt_out",
            }
        session_repo = SessionRepository(db)
        risk_level = patient.risk_level or "medium"
        hours_list = OUTREACH_HOURS.get(risk_level, OUTREACH_HOURS["medium"])

        now = datetime.now(timezone.utc)
        session_ids: list[str] = []
        for i, hours in enumerate(hours_list):
            eta = now + timedelta(hours=hours)
            session = await session_repo.create(
                patient_id=uuid.UUID(patient_id),
                discharge_id=uuid.UUID(discharge_id),
                scheduled_at=eta,
                channel="voice",
                outreach_number=i + 1,
            )
            session_ids.append(str(session.id))
            initiate_call.apply_async(
                args=[str(session.id), patient_id, discharge_id],
                eta=eta,
            )
        await db.commit()

    return {
        "patient_id": patient_id,
        "discharge_id": discharge_id,
        "risk_level": risk_level,
        "sessions_scheduled": len(session_ids),
        "session_ids": session_ids,
    }


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def initiate_call(self, session_id: str, patient_id: str, discharge_id: str) -> dict:
    """Place the outbound Twilio call for one scheduled session.

    Returns ``{"session_id", "status", "twilio_sid"}`` to the result backend.
    """
    try:
        result = asyncio.run(_initiate(session_id, patient_id))
    except Exception as exc:
        logger.exception("initiate_call failed session_id=%s", session_id)
        raise self.retry(exc=exc)
    return result


async def _initiate(session_id: str, patient_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        patient = await PatientRepository(db).get(uuid.UUID(patient_id))
        # EncryptedString decrypts phone_enc on load, so this is plaintext.
        patient_phone = patient.phone

    twilio_sid = place_outbound_call(settings, session_id, patient_phone)
    return {"session_id": session_id, "status": "initiated", "twilio_sid": twilio_sid}
