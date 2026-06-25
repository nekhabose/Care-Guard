"""Tests for the mock Epic FHIR client and its data shape."""
import pytest

from fhir.mock_client import MockFHIRClient
from fhir.parser import DischargeParser


@pytest.mark.asyncio
async def test_mock_client_returns_all_sample_patients():
    client = MockFHIRClient()
    ids = client.available_patient_ids()
    assert "EPIC-88213" in ids
    assert len(ids) >= 4


@pytest.mark.asyncio
async def test_mock_data_parses_through_real_parser():
    client = MockFHIRClient()
    raw = await client.get_discharge_data("EPIC-88213")
    parsed = DischargeParser.parse(raw)

    assert parsed.epic_patient_id == "EPIC-88213"
    assert parsed.first_name == "Eleanor"
    assert parsed.last_name == "Whitfield"
    assert parsed.phone.startswith("+1")
    assert parsed.hrrp_condition == "heart_failure"
    assert parsed.primary_diagnosis_code == "I50.23"
    assert len(parsed.medications) == 5
    assert parsed.instructions_summary  # base64 doc decoded


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "epic_id,expected_condition",
    [
        ("EPIC-77104", "copd"),
        ("EPIC-66920", "pneumonia"),
        ("EPIC-55831", "hip_knee"),
    ],
)
async def test_each_sample_maps_to_its_hrrp_condition(epic_id, expected_condition):
    raw = await MockFHIRClient().get_discharge_data(epic_id)
    assert DischargeParser.parse(raw).hrrp_condition == expected_condition


@pytest.mark.asyncio
async def test_unknown_id_falls_back_with_echoed_id():
    raw = await MockFHIRClient().get_discharge_data("EPIC-UNKNOWN")
    parsed = DischargeParser.parse(raw)
    assert parsed.epic_patient_id == "EPIC-UNKNOWN"


@pytest.mark.asyncio
async def test_returned_data_is_isolated_copy():
    client = MockFHIRClient()
    a = await client.get_discharge_data("EPIC-88213")
    a["patient"]["name"][0]["family"] = "MUTATED"
    b = await client.get_discharge_data("EPIC-88213")
    assert b["patient"]["name"][0]["family"] == "Whitfield"
