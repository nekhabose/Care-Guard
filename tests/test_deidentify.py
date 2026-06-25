"""De-identification — Safe Harbor age banding, pseudonyms, no PHI leakage."""
import uuid
from datetime import date
from types import SimpleNamespace

from services.deidentify import age_band, deidentify_patient, pseudonymize


def test_age_band_buckets_and_safe_harbor_cap():
    ref = date(2026, 6, 24)
    assert age_band(date(1960, 1, 1), ref) == "60-69"
    assert age_band(date(1955, 12, 31), ref) == "70-79"
    # Ages over 89 must collapse to a single bucket.
    assert age_band(date(1930, 1, 1), ref) == "90+"
    assert age_band(None, ref) is None


def test_pseudonym_is_stable_and_opaque():
    pid = uuid.uuid4()
    a = pseudonymize(pid)
    b = pseudonymize(pid)
    assert a == b                       # stable for longitudinal analysis
    assert str(pid) not in a            # not reversible to the raw id
    assert len(a) == 16


def _patient(**kw):
    base = dict(
        id=uuid.uuid4(),
        first_name="Jane", last_name="Smith", phone="+15551234567",
        mrn="MRN-9", epic_patient_id="epic-1",
        date_of_birth=date(1950, 3, 15), risk_level="high", risk_score=80,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_record_contains_no_identifiers():
    patient = _patient()
    discharge = SimpleNamespace(
        hrrp_condition="heart_failure", medications=[{}, {}], discharge_date=date(2026, 6, 1)
    )
    record = deidentify_patient(patient, discharge, sessions=[], escalations=[])

    blob = str(record)
    for identifier in ("Jane", "Smith", "+15551234567", "MRN-9", "epic-1", str(patient.id)):
        assert identifier not in blob
    assert record["age_band"] == "70-79"
    assert record["hrrp_condition"] == "heart_failure"
    assert record["medication_count"] == 2
    assert record["discharge_year"] == 2026
