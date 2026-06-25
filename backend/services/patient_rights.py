"""
PatientRightsService — HIPAA Privacy Rule patient rights.

Coordinates the three patient-rights flows the care team fulfils on a patient's
behalf:

  * ``export_record``  — Right of access (§164.524): the designated record set,
                         decrypted, as a single JSON document.
  * ``set_call_opt_out`` — Right to opt out of automated outreach calls.
  * ``erase_transcripts`` — Right to erasure: hard-delete conversation
                         transcripts and any stored call recordings for a patient.

All PHI access here flows through the audited dashboard routes; this service
never logs PHI (only UUIDs).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from exceptions import NotFoundError
from models.db import Patient
from repositories.discharge import DischargeRepository
from repositories.escalation import EscalationRepository
from repositories.patient import PatientRepository
from repositories.session import SessionRepository, TurnRepository
from services.recording import get_recording_store

logger = logging.getLogger(__name__)


class PatientRightsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._patient_repo = PatientRepository(db)
        self._discharge_repo = DischargeRepository(db)
        self._session_repo = SessionRepository(db)
        self._turn_repo = TurnRepository(db)
        self._escalation_repo = EscalationRepository(db)

    async def _require_patient(self, patient_id: uuid.UUID) -> Patient:
        patient = await self._patient_repo.get(patient_id)
        if patient is None:
            raise NotFoundError("Patient", str(patient_id))
        return patient

    async def export_record(self, patient_id: uuid.UUID) -> dict[str, Any]:
        """Right of access — the patient's full designated record set."""
        patient = await self._require_patient(patient_id)
        discharges = await self._discharge_repo.get_by_patient(patient_id)
        sessions = await self._session_repo.get_by_patient(patient_id)
        escalations = await self._escalation_repo.get_by_patient(patient_id)

        session_docs = []
        for session in sessions:
            turns = await self._turn_repo.get_by_session(session.id)
            session_docs.append({
                "id": str(session.id),
                "scheduled_at": _iso(session.scheduled_at),
                "started_at": _iso(session.started_at),
                "completed_at": _iso(session.completed_at),
                "status": session.status,
                "channel": session.channel,
                "outreach_number": session.outreach_number,
                "transcript": [
                    {"role": t.role, "content": t.content, "at": _iso(t.created_at)}
                    for t in turns
                ],
            })

        logger.info("Patient record exported patient_id=%s", patient_id)
        return {
            "notice": "Designated record set export — HIPAA right of access (§164.524).",
            "exported_at": _iso(datetime.now(timezone.utc)),
            "patient": {
                "id": str(patient.id),
                "epic_patient_id": patient.epic_patient_id,
                "mrn": patient.mrn,
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "phone": patient.phone,
                "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
                "risk_score": patient.risk_score,
                "risk_level": patient.risk_level,
                "call_opt_out": patient.call_opt_out,
            },
            "discharges": [
                {
                    "id": str(d.id),
                    "discharge_date": d.discharge_date.isoformat(),
                    "hospital_name": d.hospital_name,
                    "primary_diagnosis_code": d.primary_diagnosis_code,
                    "primary_diagnosis_name": d.primary_diagnosis_name,
                    "hrrp_condition": d.hrrp_condition,
                    "medications": d.medications,
                    "followup_appointments": d.followup_appointments,
                    "instructions_summary": d.instructions_summary,
                }
                for d in discharges
            ],
            "sessions": session_docs,
            "escalations": [
                {
                    "id": str(e.id),
                    "severity": e.severity,
                    "reason": e.reason,
                    "symptoms_flagged": e.symptoms_flagged,
                    "resolved_at": _iso(e.resolved_at),
                    "created_at": _iso(e.created_at),
                }
                for e in escalations
            ],
        }

    async def set_call_opt_out(self, patient_id: uuid.UUID, opt_out: bool) -> Patient:
        """Record the patient's outreach-call preference."""
        patient = await self._require_patient(patient_id)
        await self._patient_repo.update(patient, call_opt_out=opt_out)
        logger.info("Patient call_opt_out=%s patient_id=%s", opt_out, patient_id)
        return patient

    async def erase_transcripts(
        self, patient_id: uuid.UUID, delete_recordings: bool = True
    ) -> dict[str, Any]:
        """Right to erasure — delete transcripts and recordings for a patient."""
        await self._require_patient(patient_id)
        sessions = await self._session_repo.get_by_patient(patient_id)

        turns_deleted = await self._turn_repo.delete_by_sessions([s.id for s in sessions])

        recordings_deleted = 0
        if delete_recordings:
            store = get_recording_store()
            for session in sessions:
                if session.recording_s3_key:
                    try:
                        await store.delete_recording(session.recording_s3_key)
                    except Exception:
                        logger.exception(
                            "Failed to delete recording session_id=%s", session.id
                        )
                        continue
                    await self._session_repo.update(session, recording_s3_key=None)
                    recordings_deleted += 1

        logger.warning(
            "Erasure complete patient_id=%s turns=%s recordings=%s",
            patient_id, turns_deleted, recordings_deleted,
        )
        return {
            "patient_id": str(patient_id),
            "turns_deleted": turns_deleted,
            "recordings_deleted": recordings_deleted,
            "erased_at": _iso(datetime.now(timezone.utc)),
        }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
