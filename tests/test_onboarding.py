"""Manual patient onboarding — creates a callable patient + discharge + risk."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models.schemas import PatientOnboard
from services.onboarding import PatientOnboardingService


def _service():
    svc = PatientOnboardingService.__new__(PatientOnboardingService)
    svc._db = SimpleNamespace(commit=AsyncMock())
    created = SimpleNamespace(id=uuid.uuid4())
    svc._patient_repo = SimpleNamespace(
        create=AsyncMock(return_value=created),
        update=AsyncMock(return_value=created),
    )
    svc._discharge_repo = SimpleNamespace(create=AsyncMock())
    return svc, created


def test_onboard_schema_rejects_bad_phone():
    with pytest.raises(Exception):
        PatientOnboard(first_name="A", last_name="B", phone="not-a-number")


@pytest.mark.asyncio
async def test_onboard_creates_patient_discharge_and_scores_risk():
    svc, created = _service()
    data = PatientOnboard(
        first_name="Test",
        last_name="Patient",
        phone="+14155550123",
        condition="heart_failure",
        age=80,
        lives_alone=True,
        has_followup_appointment=False,
    )

    result = await svc.onboard(data)

    assert result is created
    # Patient created with encrypted-column kwargs + a synthetic manual epic id.
    pkwargs = svc._patient_repo.create.call_args.kwargs
    assert pkwargs["first_name_enc"] == "Test"
    assert pkwargs["phone_enc"] == "+14155550123"
    assert pkwargs["epic_patient_id"].startswith("manual-")

    # Risk written via update — HF + age>75 + lives_alone + no follow-up => high.
    risk_kwargs = svc._patient_repo.update.call_args.kwargs
    assert risk_kwargs["risk_level"] == "high"
    assert risk_kwargs["risk_score"] >= 60

    # A discharge row was created so the call path has something to attach to.
    dkwargs = svc._discharge_repo.create.call_args.kwargs
    assert dkwargs["hrrp_condition"] == "heart_failure"
    svc._db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_onboard_general_condition_is_low_risk():
    svc, _ = _service()
    data = PatientOnboard(
        first_name="Low",
        last_name="Risk",
        phone="+14155550999",
        condition="general",
    )
    await svc.onboard(data)
    assert svc._patient_repo.update.call_args.kwargs["risk_level"] == "low"
