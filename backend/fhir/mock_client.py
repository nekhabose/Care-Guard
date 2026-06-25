"""
MockFHIRClient — drop-in replacement for EpicFHIRClient with no network/keys.

Returns the same raw FHIR R4 shapes as the live client from the fixtures in
``mock_data``, so ``DischargeParser`` and everything downstream behave
identically. Selected via ``FHIR_PROVIDER=mock`` (the default).
"""
import copy
import logging
from typing import Any

from .client import BaseFHIRClient
from .mock_data import DEFAULT_DISCHARGE_ID, MOCK_DISCHARGES

logger = logging.getLogger(__name__)


class MockFHIRClient(BaseFHIRClient):
    async def get_discharge_data(self, epic_patient_id: str) -> dict[str, Any]:
        record = MOCK_DISCHARGES.get(epic_patient_id)
        if record is None:
            logger.info(
                "Mock FHIR: unknown id=%s, returning default sample", epic_patient_id
            )
            record = MOCK_DISCHARGES[DEFAULT_DISCHARGE_ID]
            # Echo back the requested id so downstream keys stay consistent.
            record = copy.deepcopy(record)
            record["patient"]["id"] = epic_patient_id
        else:
            # Deep-copy so callers can't mutate the shared fixtures.
            record = copy.deepcopy(record)
        logger.info("Mock FHIR discharge data served epic_patient_id=%s", epic_patient_id)
        return record

    @staticmethod
    def available_patient_ids() -> list[str]:
        """Convenience for seeding/demo: the ids with full sample records."""
        return list(MOCK_DISCHARGES.keys())
