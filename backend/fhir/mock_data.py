"""
Mock Epic FHIR R4 data.

These dictionaries are byte-for-byte the shape Epic's FHIR R4 API returns —
a single ``Patient`` resource plus searchset ``Bundle``s for MedicationRequest,
Condition, DocumentReference and Appointment. ``DischargeParser`` parses them
with zero special-casing, so the mock path exercises the exact same code as a
live Epic pull. This lets the whole discharge → risk → outreach flow run with no
Epic OAuth credentials (set ``FHIR_PROVIDER=mock``).

To add a patient: append a ``_discharge(...)`` entry to ``MOCK_DISCHARGES``.
"""
import base64
from typing import Any

# Discharge dates are recent and relative-ish but fixed so risk scoring and the
# dashboard are deterministic across runs.


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _patient(
    epic_id: str, mrn: str, given: list[str], family: str, phone: str, dob: str, gender: str
) -> dict[str, Any]:
    return {
        "resourceType": "Patient",
        "id": epic_id,
        "identifier": [
            {"type": {"text": "MRN"}, "system": "urn:oid:1.2.840.114350.1.13.0.1.7.5.737384.0", "value": mrn},
        ],
        "active": True,
        "name": [{"use": "official", "family": family, "given": given}],
        "telecom": [
            {"system": "phone", "value": phone, "use": "mobile"},
        ],
        "gender": gender,
        "birthDate": dob,
    }


def _med(name: str, dose: float, unit: str, frequency_text: str, instructions: str) -> dict[str, Any]:
    return {
        "resource": {
            "resourceType": "MedicationRequest",
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {"text": name},
            "dosageInstruction": [
                {
                    "text": instructions,
                    "timing": {"code": {"text": frequency_text}},
                    "doseAndRate": [{"doseQuantity": {"value": dose, "unit": unit}}],
                }
            ],
        }
    }


def _condition(code: str, display: str, *, primary: bool = False) -> dict[str, Any]:
    return {
        "resource": {
            "resourceType": "Condition",
            "category": [
                {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-category",
                             "code": "encounter-diagnosis"}]}
            ],
            "code": {
                "coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": code, "display": display}],
                "text": display,
            },
            "rank": 1 if primary else 2,
        }
    }


def _document(instructions: str) -> dict[str, Any]:
    return {
        "resource": {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {"coding": [{"system": "http://loinc.org", "code": "18842-5",
                                 "display": "Discharge summary"}]},
            "content": [
                {"attachment": {"contentType": "text/plain", "data": _b64(instructions)}}
            ],
        }
    }


def _appointment(provider: str, specialty: str, start: str, location: str) -> dict[str, Any]:
    return {
        "resource": {
            "resourceType": "Appointment",
            "status": "booked",
            "serviceType": [{"text": specialty}],
            "start": start,
            "comment": location,
            "participant": [
                {"actor": {"reference": "Practitioner/PR-001", "display": provider}, "status": "accepted"}
            ],
        }
    }


def _bundle(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {"resourceType": "Bundle", "type": "searchset", "total": len(entries), "entry": entries}


def _discharge(
    patient: dict[str, Any],
    medications: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    instructions: str,
    appointments: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "patient": patient,
        "medications": _bundle(medications),
        "conditions": _bundle(conditions),
        "documents": _bundle([_document(instructions)]),
        "appointments": _bundle(appointments),
    }


# --------------------------------------------------------------------------
# Sample patients — one per major HRRP condition.
# --------------------------------------------------------------------------

MOCK_DISCHARGES: dict[str, dict[str, Any]] = {
    # Heart failure — high risk (matches the dashboard's Eleanor Whitfield)
    "EPIC-88213": _discharge(
        patient=_patient("EPIC-88213", "MRN-44021", ["Eleanor"], "Whitfield",
                         "+13125550101", "1948-03-14", "female"),
        medications=[
            _med("Furosemide", 40, "mg", "Twice daily", "Take 40 mg by mouth twice daily for fluid"),
            _med("Lisinopril", 10, "mg", "Once daily", "Take 10 mg by mouth every morning"),
            _med("Carvedilol", 12.5, "mg", "Twice daily", "Take 12.5 mg by mouth twice daily with food"),
            _med("Spironolactone", 25, "mg", "Once daily", "Take 25 mg by mouth daily"),
            _med("Potassium Chloride", 20, "mEq", "Once daily", "Take 20 mEq by mouth daily"),
        ],
        conditions=[
            _condition("I50.23", "Acute on chronic systolic heart failure", primary=True),
            _condition("E11.9", "Type 2 diabetes mellitus without complications"),
            _condition("N18.3", "Chronic kidney disease, stage 3"),
        ],
        instructions=(
            "DISCHARGE INSTRUCTIONS — Heart Failure. Weigh yourself every morning; "
            "call the care team if you gain more than 3 lbs in a day or 5 lbs in a week. "
            "Limit sodium to under 2,000 mg per day and fluids to 2 liters per day. "
            "Take all medications exactly as prescribed. Seek emergency care for chest pain, "
            "severe shortness of breath, or new confusion."
        ),
        appointments=[
            _appointment("Dr. Amara Okafor, Cardiology", "Cardiology",
                         "2026-06-30T14:30:00Z", "Heart & Vascular Clinic, 3rd Floor"),
        ],
    ),
    # COPD — high risk, no follow-up booked (drives risk up)
    "EPIC-77104": _discharge(
        patient=_patient("EPIC-77104", "MRN-51890", ["Marcus"], "Delgado",
                         "+13125550102", "1955-11-02", "male"),
        medications=[
            _med("Albuterol", 90, "mcg", "Every 4-6 hours as needed", "2 puffs inhaled every 4-6 hours as needed"),
            _med("Tiotropium", 18, "mcg", "Once daily", "Inhale 1 capsule once daily"),
            _med("Prednisone", 20, "mg", "Once daily (taper)", "Take 20 mg daily, taper per schedule"),
            _med("Azithromycin", 250, "mg", "Once daily", "Take 250 mg daily for 5 days"),
        ],
        conditions=[
            _condition("J44.1", "COPD with acute exacerbation", primary=True),
            _condition("F17.210", "Nicotine dependence, cigarettes"),
        ],
        instructions=(
            "DISCHARGE INSTRUCTIONS — COPD. Use your rescue inhaler as needed and continue "
            "your maintenance inhaler daily. Complete the full steroid taper and antibiotic course. "
            "Avoid smoke and known triggers. Call the care team if your breathing worsens, you need "
            "your rescue inhaler more than every 4 hours, or your mucus changes color."
        ),
        appointments=[],
    ),
    # Pneumonia — medium risk
    "EPIC-66920": _discharge(
        patient=_patient("EPIC-66920", "MRN-33442", ["Priya"], "Nair",
                         "+13125550103", "1969-07-21", "female"),
        medications=[
            _med("Amoxicillin-Clavulanate", 875, "mg", "Twice daily", "Take 875 mg twice daily for 7 days"),
            _med("Guaifenesin", 600, "mg", "Twice daily", "Take 600 mg twice daily as needed for cough"),
            _med("Acetaminophen", 650, "mg", "Every 6 hours as needed", "Take 650 mg every 6 hours as needed for fever"),
        ],
        conditions=[
            _condition("J18.9", "Pneumonia, unspecified organism", primary=True),
        ],
        instructions=(
            "DISCHARGE INSTRUCTIONS — Pneumonia. Finish the entire antibiotic course even if you "
            "feel better. Rest and drink plenty of fluids. Use the incentive spirometer 10 times "
            "every hour while awake. Return to the ED for high fever, worsening shortness of breath, "
            "chest pain, or coughing up blood."
        ),
        appointments=[
            _appointment("Dr. Liam Foster, Primary Care", "Primary Care",
                         "2026-07-02T10:00:00Z", "Riverside Family Medicine"),
        ],
    ),
    # Orthopedic (hip/knee replacement) — lower risk
    "EPIC-55831": _discharge(
        patient=_patient("EPIC-55831", "MRN-77215", ["Walter"], "Brennan",
                         "+13125550104", "1952-01-09", "male"),
        medications=[
            _med("Oxycodone", 5, "mg", "Every 6 hours as needed", "Take 5 mg every 6 hours as needed for pain"),
            _med("Enoxaparin", 40, "mg", "Once daily", "Inject 40 mg under the skin once daily for 14 days"),
            _med("Docusate", 100, "mg", "Twice daily", "Take 100 mg twice daily to prevent constipation"),
        ],
        conditions=[
            _condition("Z96.641", "Presence of right artificial hip joint", primary=True),
            _condition("M16.11", "Unilateral primary osteoarthritis, right hip"),
        ],
        instructions=(
            "DISCHARGE INSTRUCTIONS — Hip Replacement. Follow hip precautions: do not bend past "
            "90 degrees, cross your legs, or twist the operated leg. Use your walker for all walking. "
            "Give the blood-thinner injection daily as directed. Watch for and report calf pain, "
            "swelling, redness, fever, or drainage from the incision."
        ),
        appointments=[
            _appointment("Dr. Sofia Reyes, Orthopedics", "Orthopedic Surgery",
                         "2026-07-07T09:15:00Z", "Orthopedic Surgery Clinic, Suite 210"),
            _appointment("Helen Park, PT", "Physical Therapy",
                         "2026-06-27T13:00:00Z", "Outpatient Rehab"),
        ],
    ),
}

# Returned for any unknown id so the mock never raises on a new patient.
DEFAULT_DISCHARGE_ID = "EPIC-88213"
