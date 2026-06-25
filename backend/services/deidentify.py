"""
De-identification for analytics (HIPAA §164.514(b) — Safe Harbor).

Produces analytics rows with all 18 Safe Harbor identifiers removed:

* Names, phone, MRN, and Epic IDs are dropped.
* The patient UUID is replaced with a keyed HMAC pseudonym (stable across runs,
  not reversible without the key) so longitudinal analysis still works.
* Dates of birth become coarse age bands; ages over 89 collapse to ``90+``.
* Exact dates are reduced to the discharge *year* only.

The result is **not PHI** and is safe for analytics dashboards and export.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import date, datetime, timezone
from typing import Any

from config import get_settings
from models.db import Discharge, Escalation, OutreachSession, Patient


def pseudonymize(patient_id: Any) -> str:
    """Keyed HMAC pseudonym — stable, non-reversible without the secret key."""
    secret = get_settings().jwt_secret.encode()
    return hmac.new(secret, str(patient_id).encode(), hashlib.sha256).hexdigest()[:16]


def age_band(dob: date | None, ref: date | None = None) -> str | None:
    """Coarse age band. Safe Harbor: ages > 89 are aggregated into ``90+``."""
    if dob is None:
        return None
    ref = ref or datetime.now(timezone.utc).date()
    age = ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))
    if age >= 90:
        return "90+"
    if age < 0:
        return None
    lower = (age // 10) * 10
    return f"{lower}-{lower + 9}"


def deidentify_patient(
    patient: Patient,
    discharge: Discharge | None,
    sessions: list[OutreachSession],
    escalations: list[Escalation],
) -> dict[str, Any]:
    """Build one de-identified analytics record for a patient."""
    completed = sum(1 for s in sessions if s.status == "completed")
    return {
        "subject_id": pseudonymize(patient.id),
        "age_band": age_band(patient.date_of_birth),
        "risk_level": patient.risk_level,
        "hrrp_condition": discharge.hrrp_condition if discharge else None,
        "medication_count": len(discharge.medications or []) if discharge else 0,
        "discharge_year": discharge.discharge_date.year if discharge else None,
        "outreach_sessions": len(sessions),
        "completed_sessions": completed,
        "escalation_count": len(escalations),
        "had_urgent_escalation": any(e.severity == "urgent" for e in escalations),
    }
