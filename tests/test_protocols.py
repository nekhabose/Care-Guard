from agent.protocols.factory import ProtocolFactory
from agent.protocols.heart_failure import HeartFailureProtocol
from agent.protocols.pneumonia import PneumoniaProtocol


def test_factory_returns_correct_protocol_for_heart_failure():
    protocol = ProtocolFactory.get("heart_failure")
    assert isinstance(protocol, HeartFailureProtocol)


def test_factory_returns_correct_protocol_for_pneumonia():
    protocol = ProtocolFactory.get("pneumonia")
    assert isinstance(protocol, PneumoniaProtocol)


def test_factory_returns_base_protocol_for_unknown_condition():
    protocol = ProtocolFactory.get("unknown_condition")
    assert protocol is not None


def test_factory_returns_base_for_none():
    protocol = ProtocolFactory.get(None)
    assert protocol is not None


def test_system_prompt_includes_patient_context():
    protocol = ProtocolFactory.get("heart_failure")
    prompt = protocol.build_system_prompt(
        hospital_name="City Hospital",
        patient_first_name="Jane",
        patient_last_name="Doe",
        date_of_birth="March 14, 1948",
        discharge_date="2026-05-20",
        diagnosis="Heart failure",
        medications="Furosemide 40mg daily",
        followup_appointments="Cardiology on 2026-06-05",
        instructions_summary="Weigh daily.",
    )
    assert "City Hospital" in prompt
    assert "Jane" in prompt
    assert "weight" in prompt.lower()
    assert "heart failure" in prompt.lower()
    # Identity verification must be present and reference the DOB.
    assert "March 14, 1948" in prompt
    assert "date of birth" in prompt.lower()


def test_heart_failure_checklist_includes_weight():
    protocol = HeartFailureProtocol()
    checklist = "\n".join(protocol.checklist)
    assert "weigh" in checklist.lower()


def test_supported_conditions_lists_all_registered():
    conditions = ProtocolFactory.supported_conditions()
    assert "heart_failure" in conditions
    assert "pneumonia" in conditions
    assert "copd" in conditions
    assert "hip_knee" in conditions
