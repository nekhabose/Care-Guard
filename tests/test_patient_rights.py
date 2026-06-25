"""Patient-rights flows: export, opt-out enforcement, erasure."""
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config import get_settings
from exceptions import ValidationError
from services.call_trigger import CallTriggerService
from services.patient_rights import PatientRightsService


def _patient(**kw):
    base = dict(
        id=uuid.uuid4(), epic_patient_id="epic-1", mrn="MRN-9",
        first_name="Jane", last_name="Smith", phone="+15551234567",
        date_of_birth=date(1950, 3, 15), risk_score=80, risk_level="high",
        call_opt_out=False,
    )
    base.update(kw)
    return SimpleNamespace(**base)


# --- Opt-out enforcement ---

@pytest.mark.asyncio
async def test_call_patient_blocked_when_opted_out():
    svc = CallTriggerService(db=None, fhir_client=None, settings=get_settings())
    svc._patient_repo = AsyncMock()
    svc._patient_repo.get.return_value = _patient(call_opt_out=True)
    with pytest.raises(ValidationError):
        await svc.call_patient(uuid.uuid4())


@pytest.mark.asyncio
async def test_call_high_risk_skips_opted_out():
    svc = CallTriggerService(db=None, fhir_client=None, settings=get_settings())
    svc._patient_repo = AsyncMock()
    svc._patient_repo.get_by_risk_level.return_value = [_patient(call_opt_out=True)]
    # All high-risk patients opted out -> nothing callable.
    with pytest.raises(ValidationError):
        await svc.call_high_risk()


# --- Erasure ---

@pytest.mark.asyncio
async def test_erase_transcripts_deletes_turns():
    svc = PatientRightsService(db=AsyncMock())
    pid = uuid.uuid4()
    svc._patient_repo = AsyncMock()
    svc._patient_repo.get.return_value = _patient(id=pid)
    svc._session_repo = AsyncMock()
    svc._session_repo.get_by_patient.return_value = [
        SimpleNamespace(id=uuid.uuid4(), recording_s3_key=None)
    ]
    svc._turn_repo = AsyncMock()
    svc._turn_repo.delete_by_sessions.return_value = 7

    result = await svc.erase_transcripts(pid, delete_recordings=False)
    assert result["turns_deleted"] == 7
    assert result["recordings_deleted"] == 0


# --- Right of access ---

@pytest.mark.asyncio
async def test_export_record_returns_decrypted_phi():
    svc = PatientRightsService(db=AsyncMock())
    pid = uuid.uuid4()
    svc._patient_repo = AsyncMock()
    svc._patient_repo.get.return_value = _patient(id=pid)
    svc._discharge_repo = AsyncMock()
    svc._discharge_repo.get_by_patient.return_value = []
    svc._session_repo = AsyncMock()
    svc._session_repo.get_by_patient.return_value = []
    svc._escalation_repo = AsyncMock()
    svc._escalation_repo.get_by_patient.return_value = []

    out = await svc.export_record(pid)
    # The patient's own record set legitimately contains their PHI.
    assert out["patient"]["first_name"] == "Jane"
    assert out["patient"]["call_opt_out"] is False
    assert "designated record set" in out["notice"].lower()
