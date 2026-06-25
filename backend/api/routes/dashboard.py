"""
Dashboard API — endpoints for the care coordinator frontend.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from api.deps import (
    get_call_trigger_service,
    get_discharge_repo,
    get_escalation_repo,
    get_onboarding_service,
    get_patient_repo,
    get_patient_rights_service,
    get_session_repo,
    require_reader,
    require_role,
)
from models.schemas import (
    ContactPreferenceUpdate,
    EscalationRead,
    EscalationResolve,
    OutreachSessionRead,
    PatientOnboard,
    PatientRead,
)
from repositories.discharge import DischargeRepository
from repositories.escalation import EscalationRepository
from repositories.patient import PatientRepository
from repositories.session import SessionRepository
from security.auth import Role
from services.call_trigger import CallTriggerService
from services.deidentify import deidentify_patient
from services.onboarding import PatientOnboardingService
from services.patient_rights import PatientRightsService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Resolving escalations mutates clinical state — restrict to leads/admins.
require_resolver = require_role(Role.CARE_LEAD, Role.ADMIN)
# Initiating a real outbound call is likewise a mutating clinical action.
require_caller = require_role(Role.CARE_LEAD, Role.ADMIN)
# Privacy-rights actions (full PHI export, opt-out) — leads/admins.
require_privacy = require_role(Role.CARE_LEAD, Role.ADMIN)
# Erasure is irreversible — admins only.
require_eraser = require_role(Role.ADMIN)


@router.get("/patients", response_model=list[PatientRead])
async def list_patients(
    risk_level: str | None = None,
    limit: int = 100,
    offset: int = 0,
    patient_repo: PatientRepository = Depends(get_patient_repo),
    _user: dict = Depends(require_reader),
):
    if risk_level:
        return await patient_repo.get_by_risk_level(risk_level)
    return await patient_repo.get_all(limit=limit, offset=offset)


@router.get("/patients/{patient_id}/sessions", response_model=list[OutreachSessionRead])
async def get_patient_sessions(
    patient_id: uuid.UUID,
    session_repo: SessionRepository = Depends(get_session_repo),
    _user: dict = Depends(require_reader),
):
    return await session_repo.get_by_patient(patient_id)


@router.get("/escalations", response_model=list[EscalationRead])
async def list_escalations(
    unresolved_only: bool = True,
    escalation_repo: EscalationRepository = Depends(get_escalation_repo),
    _user: dict = Depends(require_reader),
):
    if unresolved_only:
        return await escalation_repo.get_unresolved()
    return await escalation_repo.get_all()


@router.patch("/escalations/{escalation_id}/resolve", response_model=EscalationRead)
async def resolve_escalation(
    escalation_id: uuid.UUID,
    body: EscalationResolve,
    escalation_repo: EscalationRepository = Depends(get_escalation_repo),
    user: dict = Depends(require_resolver),
):
    escalation = await escalation_repo.get(escalation_id)
    return await escalation_repo.resolve(escalation, resolved_by=body.resolved_by or user.get("sub", "unknown"))


@router.post("/seed", response_model=list[PatientRead])
async def seed_mock_patients(
    call_service: CallTriggerService = Depends(get_call_trigger_service),
    _user: dict = Depends(require_caller),
):
    """Intake all built-in mock patients (FHIR → risk → DB) without Epic.

    Lets the system be demoed end-to-end when no discharge webhook has fired.
    Idempotent — safe to call repeatedly.
    """
    return await call_service.seed_from_mock()


@router.post("/patients/onboard", response_model=PatientRead, status_code=201)
async def onboard_patient(
    body: PatientOnboard,
    onboarding: PatientOnboardingService = Depends(get_onboarding_service),
    _user: dict = Depends(require_caller),
):
    """Manually enrol a patient (name + mobile + condition) so they're callable.

    Restricted to leads/admins (same as placing a call) — the record it creates
    can be dialled. Use your own number to test outreach end to end.
    """
    return await onboarding.onboard(body)


@router.post("/patients/{patient_id}/call", response_model=OutreachSessionRead)
async def call_patient_now(
    patient_id: uuid.UUID,
    call_service: CallTriggerService = Depends(get_call_trigger_service),
    _user: dict = Depends(require_caller),
):
    """Place an immediate AI voice check-in call to one patient."""
    return await call_service.call_patient(patient_id)


@router.post("/call-high-risk", response_model=list[OutreachSessionRead])
async def call_high_risk_now(
    call_service: CallTriggerService = Depends(get_call_trigger_service),
    _user: dict = Depends(require_caller),
):
    """Place an immediate call to every high-risk patient."""
    return await call_service.call_high_risk()


# --- Patient rights (HIPAA Privacy Rule) ---


@router.get("/patients/{patient_id}/export")
async def export_patient_record(
    patient_id: uuid.UUID,
    rights: PatientRightsService = Depends(get_patient_rights_service),
    _user: dict = Depends(require_privacy),
):
    """Right of access (§164.524) — the patient's full designated record set."""
    return await rights.export_record(patient_id)


@router.patch("/patients/{patient_id}/contact-preferences", response_model=PatientRead)
async def update_contact_preferences(
    patient_id: uuid.UUID,
    body: ContactPreferenceUpdate,
    rights: PatientRightsService = Depends(get_patient_rights_service),
    _user: dict = Depends(require_privacy),
):
    """Record the patient's right to opt in/out of automated outreach calls."""
    return await rights.set_call_opt_out(patient_id, body.call_opt_out)


@router.delete("/patients/{patient_id}/transcripts")
async def erase_patient_transcripts(
    patient_id: uuid.UUID,
    rights: PatientRightsService = Depends(get_patient_rights_service),
    _user: dict = Depends(require_eraser),
):
    """Right to erasure — delete this patient's transcripts and recordings."""
    return await rights.erase_transcripts(patient_id)


@router.get("/analytics/summary")
async def analytics_summary(
    patient_repo: PatientRepository = Depends(get_patient_repo),
    escalation_repo: EscalationRepository = Depends(get_escalation_repo),
    _user: dict = Depends(require_reader),
):
    all_patients = await patient_repo.get_all(limit=10_000)
    high_risk = [p for p in all_patients if p.risk_level == "high"]
    open_escalations = await escalation_repo.get_unresolved()
    urgent = [e for e in open_escalations if e.severity == "urgent"]

    return {
        "total_patients": len(all_patients),
        "high_risk_patients": len(high_risk),
        "open_escalations": len(open_escalations),
        "urgent_escalations": len(urgent),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/analytics/dataset")
async def deidentified_dataset(
    patient_repo: PatientRepository = Depends(get_patient_repo),
    discharge_repo: DischargeRepository = Depends(get_discharge_repo),
    session_repo: SessionRepository = Depends(get_session_repo),
    escalation_repo: EscalationRepository = Depends(get_escalation_repo),
    _user: dict = Depends(require_reader),
):
    """De-identified (Safe Harbor §164.514(b)) per-patient analytics rows.

    Contains no PHI — keyed pseudonyms, age bands, and coarse counts only.
    """
    patients = await patient_repo.get_all(limit=10_000)
    rows = []
    for patient in patients:
        discharge = await discharge_repo.get_latest_for_patient(patient.id)
        sessions = await session_repo.get_by_patient(patient.id)
        escalations = await escalation_repo.get_by_patient(patient.id)
        rows.append(deidentify_patient(patient, discharge, sessions, escalations))
    return {"count": len(rows), "records": rows}
