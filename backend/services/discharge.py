"""
DischargeService — coordinates the end-to-end discharge intake flow.

Ties together: FHIR pull → risk scoring → DB persistence → outreach scheduling.
The service is the only layer that knows all three sub-systems exist.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from fhir.client import BaseFHIRClient
from fhir.parser import DischargeParser
from repositories.discharge import DischargeRepository
from repositories.patient import PatientRepository
from services.risk import RiskInput, RiskScoringService

logger = logging.getLogger(__name__)


class DischargeService:
    def __init__(
        self,
        db: AsyncSession,
        fhir_client: BaseFHIRClient,
    ) -> None:
        self._patient_repo = PatientRepository(db)
        self._discharge_repo = DischargeRepository(db)
        self._fhir = fhir_client

    async def handle_discharge_event(self, epic_patient_id: str, hospital_name: str) -> tuple[str, str]:
        """
        Process a discharge event.

        Returns (patient_id, discharge_id) as strings for the task queue.
        """
        raw = await self._fhir.get_discharge_data(epic_patient_id)
        parsed = DischargeParser.parse(raw)

        # Upsert patient. The `_enc` columns are EncryptedString, so these plain
        # values are encrypted automatically on write and decrypted on read.
        patient = await self._patient_repo.get_by_epic_id(epic_patient_id)
        if not patient:
            patient = await self._patient_repo.create(
                epic_patient_id=epic_patient_id,
                mrn=parsed.mrn,
                first_name_enc=parsed.first_name,
                last_name_enc=parsed.last_name,
                phone_enc=parsed.phone,
                date_of_birth=parsed.date_of_birth,
            )
        else:
            # Refresh demographics from the source of truth (FHIR) on re-intake —
            # phone/name/MRN may have changed since the last discharge.
            await self._patient_repo.update(
                patient,
                mrn=parsed.mrn,
                first_name_enc=parsed.first_name,
                last_name_enc=parsed.last_name,
                phone_enc=parsed.phone,
                date_of_birth=parsed.date_of_birth,
            )

        # Calculate readmission risk
        risk_input = RiskInput(
            prior_readmissions_90d=parsed.prior_readmissions_90d,
            hrrp_condition=parsed.hrrp_condition,
            medication_count=len(parsed.medications),
            age=parsed.age,
            has_followup_appointment=bool(parsed.followup_appointments),
            lives_alone=parsed.lives_alone,
        )
        risk = RiskScoringService.score(risk_input)
        await self._patient_repo.update(patient, risk_score=risk.score, risk_level=risk.level)

        # Persist discharge
        discharge = await self._discharge_repo.create(
            patient_id=patient.id,
            discharge_date=parsed.discharge_date,
            hospital_name=hospital_name,
            primary_diagnosis_code=parsed.primary_diagnosis_code,
            primary_diagnosis_name=parsed.primary_diagnosis_name,
            hrrp_condition=parsed.hrrp_condition,
            medications=parsed.medications,
            followup_appointments=parsed.followup_appointments,
            discharge_instructions=parsed.discharge_instructions,
            instructions_summary=parsed.instructions_summary,
        )

        logger.info(
            "Discharge intake complete patient_id=%s risk_level=%s hrrp=%s",
            patient.id, risk.level, parsed.hrrp_condition,
        )
        return str(patient.id), str(discharge.id)
