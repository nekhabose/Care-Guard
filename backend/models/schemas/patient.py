import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class PatientCreate(BaseModel):
    epic_patient_id: str
    mrn: str | None = None
    first_name: str
    last_name: str
    phone: str
    date_of_birth: date | None = None


class PatientOnboard(BaseModel):
    """Manually onboard a patient (no Epic webhook) so they can be called.

    The minimum needed to create a callable record: a name, an E.164 mobile
    number, and a condition. Optional risk factors refine the risk score.
    """

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    # E.164, e.g. +14155550123. Use your own mobile to test a real call.
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    # One of ProtocolFactory's keys, or "general". Drives protocol + risk.
    condition: str = "general"
    date_of_birth: date | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    lives_alone: bool = False
    prior_readmissions_90d: int = Field(default=0, ge=0, le=20)
    has_followup_appointment: bool = True


class PatientUpdate(BaseModel):
    risk_score: int | None = None
    risk_level: str | None = None


class ContactPreferenceUpdate(BaseModel):
    """Patient's outreach-call preference (Privacy Rule right to opt out)."""

    call_opt_out: bool


class PatientRead(BaseModel):
    id: uuid.UUID
    epic_patient_id: str
    mrn: str | None
    first_name: str
    last_name: str
    phone: str
    date_of_birth: date | None
    risk_score: int | None
    risk_level: str | None
    call_opt_out: bool
    created_at: datetime

    model_config = {"from_attributes": True}
