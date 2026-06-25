"""
PatientOnboardingService — create a callable patient without an Epic webhook.

The discharge webhook (FHIR → risk → DB) is the normal intake path; this is the
manual counterpart so a coordinator can add a patient straight from the
dashboard — e.g. enrol a test patient with their own mobile number to verify a
real outreach call end to end.

It mirrors ``DischargeService.handle_discharge_event``: upsert patient, score
risk, persist a (minimal) discharge — but takes the data from a form instead of
FHIR. A discharge row is required because the call path attaches each outreach
session to one.
"""
import logging
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from models.db import Patient
from models.schemas import PatientOnboard
from repositories.discharge import DischargeRepository
from repositories.patient import PatientRepository
from services.risk import RiskInput, RiskScoringService

logger = logging.getLogger(__name__)

# Friendly diagnosis names for the manual conditions (display only).
_CONDITION_NAMES = {
    "heart_failure": "Heart failure",
    "ami": "Acute myocardial infarction",
    "pneumonia": "Pneumonia",
    "copd": "COPD",
    "hip_knee": "Hip/knee replacement",
    "cabg": "Coronary artery bypass graft",
    "general": "General post-discharge",
}


class PatientOnboardingService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._patient_repo = PatientRepository(db)
        self._discharge_repo = DischargeRepository(db)

    async def onboard(self, data: PatientOnboard) -> Patient:
        # Synthetic, clearly-non-Epic id so manual records are distinguishable.
        epic_id = f"manual-{uuid.uuid4().hex[:12]}"

        patient = await self._patient_repo.create(
            epic_patient_id=epic_id,
            mrn=None,
            first_name_enc=data.first_name,
            last_name_enc=data.last_name,
            phone_enc=data.phone,
            date_of_birth=data.date_of_birth,
        )

        # Score readmission risk from the supplied factors (mirrors intake).
        derived_age = data.age if data.age is not None else _age_from_dob(data.date_of_birth)
        risk = RiskScoringService.score(
            RiskInput(
                prior_readmissions_90d=data.prior_readmissions_90d,
                hrrp_condition=data.condition,
                medication_count=0,
                age=derived_age or 0,
                has_followup_appointment=data.has_followup_appointment,
                lives_alone=data.lives_alone,
            )
        )
        await self._patient_repo.update(patient, risk_score=risk.score, risk_level=risk.level)

        # Minimal discharge so the call path has something to attach to.
        await self._discharge_repo.create(
            patient_id=patient.id,
            discharge_date=date.today(),
            hospital_name="Manual onboarding",
            primary_diagnosis_code=None,
            primary_diagnosis_name=_CONDITION_NAMES.get(data.condition, data.condition),
            hrrp_condition=data.condition,
            medications=[],
            followup_appointments=[],
            discharge_instructions=None,
            instructions_summary=None,
        )
        await self._db.commit()

        logger.info(
            "Onboarded patient patient_id=%s risk_level=%s condition=%s",
            patient.id, risk.level, data.condition,
        )
        return patient


def _age_from_dob(dob: date | None) -> int | None:
    if dob is None:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
