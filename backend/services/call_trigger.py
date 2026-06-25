"""
CallTriggerService — on-demand outreach, the manual counterpart to the
scheduled Celery sequence.

Lets the dashboard (or a demo script) initiate a check-in call without waiting
for Epic to fire a discharge webhook:

  * ``seed_from_mock``  — runs the full discharge intake (FHIR → risk → DB) for
                          every built-in mock patient, so the cohort exists.
  * ``call_patient``    — places an immediate voice call to one patient now.
  * ``call_high_risk``  — places an immediate call to every high-risk patient.

The call is placed synchronously (no Celery worker required) so the demo works
with just the API server running.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings
from exceptions import NotFoundError, ValidationError
from fhir.client import BaseFHIRClient
from fhir.mock_client import MockFHIRClient
from models.db import OutreachSession, Patient
from repositories.discharge import DischargeRepository
from repositories.patient import PatientRepository
from repositories.session import SessionRepository
from services.discharge import DischargeService
from services.telephony import place_outbound_call

logger = logging.getLogger(__name__)


class CallTriggerService:
    def __init__(
        self,
        db: AsyncSession,
        fhir_client: BaseFHIRClient,
        settings: Settings,
    ) -> None:
        self._db = db
        self._settings = settings
        self._patient_repo = PatientRepository(db)
        self._discharge_repo = DischargeRepository(db)
        self._session_repo = SessionRepository(db)
        self._discharge_service = DischargeService(db, fhir_client)

    async def seed_from_mock(self, hospital_name: str = "CareGuard Demo Hospital") -> list[Patient]:
        """Intake every built-in mock patient so the cohort exists without Epic.

        Idempotent: re-running upserts the same patients and re-scores risk.
        """
        ids = MockFHIRClient.available_patient_ids()
        for epic_id in ids:
            await self._discharge_service.handle_discharge_event(epic_id, hospital_name)
        await self._db.commit()
        logger.info("Seeded %d mock patients", len(ids))
        return await self._patient_repo.get_all(limit=10_000)

    async def call_patient(self, patient_id: uuid.UUID) -> OutreachSession:
        """Place an immediate outbound call to one patient and log the session."""
        patient = await self._patient_repo.get(patient_id)
        if patient is None:
            raise NotFoundError("Patient", str(patient_id))
        if patient.call_opt_out:
            raise ValidationError("Patient has opted out of automated outreach calls.")
        return await self._place_call(patient)

    async def call_high_risk(self) -> list[OutreachSession]:
        """Place an immediate call to every high-risk patient who hasn't opted out."""
        patients = [
            p for p in await self._patient_repo.get_by_risk_level("high")
            if not p.call_opt_out
        ]
        if not patients:
            raise ValidationError("No callable high-risk patients (all opted out or none).")
        sessions = [await self._place_call(p) for p in patients]
        return sessions

    async def _place_call(self, patient: Patient) -> OutreachSession:
        discharge = await self._discharge_repo.get_latest_for_patient(patient.id)
        if discharge is None:
            raise ValidationError(
                "Patient has no discharge on record; run intake (seed) first."
            )

        # Manual calls slot in after any already-scheduled outreach for a clean
        # number in the timeline (#1, #2, ...).
        existing = await self._session_repo.get_by_patient(patient.id)
        now = datetime.now(timezone.utc)
        session = await self._session_repo.create(
            patient_id=patient.id,
            discharge_id=discharge.id,
            scheduled_at=now,
            channel="voice",
            outreach_number=len(existing) + 1,
            status="scheduled",
        )

        # phone_enc is decrypted on load by EncryptedString.
        twilio_sid = place_outbound_call(self._settings, str(session.id), patient.phone)
        await self._session_repo.update(
            session,
            status="in_progress",
            started_at=now,
            twilio_call_sid=twilio_sid,
        )
        await self._db.commit()
        logger.info(
            "Manual call placed patient_id=%s session_id=%s", patient.id, session.id
        )
        return session
