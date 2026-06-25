"""
EpicFHIRClient — authenticated async FHIR R4 client.

Uses OAuth 2.0 client credentials (JWT assertion) for system-to-system access.
All requests include the Bearer token; token is cached and refreshed on expiry.

``BaseFHIRClient`` is the abstract contract the rest of the app depends on, so a
mock client (see ``fhir.mock_client``) can stand in when Epic creds aren't
available — both return the same ``get_discharge_data`` shape.
"""
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
import jwt

from config import get_settings
from exceptions import FHIRAuthError, FHIRRequestError

logger = logging.getLogger(__name__)
settings = get_settings()

# LOINC code for discharge summary documents
DISCHARGE_SUMMARY_LOINC = "18842-5"

# ICD-10 → HRRP condition mapping (abbreviated; full mapping in production)
HRRP_ICD_MAP = {
    "I50": "heart_failure",
    "I21": "ami", "I22": "ami",
    "J18": "pneumonia", "J15": "pneumonia",
    "J44": "copd", "J43": "copd",
    "Z96.6": "hip_knee",
    "Z96.64": "hip_knee",
    "I25.10": "cabg",
}


class BaseFHIRClient(ABC):
    """Contract for any source of discharge data (live Epic or mock)."""

    @abstractmethod
    async def get_discharge_data(self, epic_patient_id: str) -> dict[str, Any]:
        """Return the raw FHIR resource set for one patient.

        Shape: ``{"patient", "medications", "conditions", "documents",
        "appointments"}`` — exactly what ``DischargeParser.parse`` consumes.
        """
        ...


class EpicFHIRClient(BaseFHIRClient):
    def __init__(self) -> None:
        self._base_url = settings.epic_fhir_base_url
        self._client_id = settings.epic_client_id
        self._private_key_path = settings.epic_private_key_path
        self._private_key_pem = settings.epic_private_key
        self._access_token: str | None = None
        self._token_expiry: float = 0

    def _load_private_key(self) -> str:
        """Prefer an injected PEM (e.g. from Secrets Manager) over a disk path."""
        if self._private_key_pem:
            return self._private_key_pem
        with open(self._private_key_path) as f:
            return f.read()

    async def get_discharge_data(self, epic_patient_id: str) -> dict[str, Any]:
        """Fetch all FHIR resources needed for discharge processing."""
        today = time.strftime("%Y-%m-%d")
        headers = {"Authorization": f"Bearer {await self._get_token()}"}

        async with httpx.AsyncClient(timeout=30) as http:
            results = await asyncio.gather(
                self._get(http, headers, f"/Patient/{epic_patient_id}"),
                self._get(http, headers, f"/MedicationRequest?patient={epic_patient_id}&status=active"),
                self._get(http, headers, f"/Condition?patient={epic_patient_id}&category=encounter-diagnosis"),
                self._get(http, headers, f"/DocumentReference?patient={epic_patient_id}&type={DISCHARGE_SUMMARY_LOINC}"),
                self._get(http, headers, f"/Appointment?patient={epic_patient_id}&status=booked&date=ge{today}"),
            )

        patient, medications, conditions, documents, appointments = results
        return {
            "patient": patient,
            "medications": medications,
            "conditions": conditions,
            "documents": documents,
            "appointments": appointments,
        }

    async def _get(self, http: httpx.AsyncClient, headers: dict, path: str) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        response = await http.get(url, headers=headers)
        if response.status_code != 200:
            resource = path.split("/")[1].split("?")[0]
            raise FHIRRequestError(resource, response.status_code)
        return response.json()

    async def _get_token(self) -> str:
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        private_key = self._load_private_key()

        now = int(time.time())
        assertion = jwt.encode(
            {
                "iss": self._client_id,
                "sub": self._client_id,
                "aud": f"{self._base_url}/oauth2/token",
                "jti": f"token-{now}",
                "iat": now,
                "exp": now + 300,
            },
            private_key,
            algorithm="RS384",
        )

        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"{self._base_url}/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    "client_assertion": assertion,
                    "scope": "system/Patient.read system/MedicationRequest.read "
                             "system/Condition.read system/DocumentReference.read "
                             "system/Appointment.read",
                },
            )

        if response.status_code != 200:
            raise FHIRAuthError(f"Token request failed: {response.text}")

        data = response.json()
        self._access_token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        logger.info("FHIR token refreshed, expires_in=%s", data.get("expires_in"))
        return self._access_token
