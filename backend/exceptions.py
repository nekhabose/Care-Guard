"""
Application-wide exception hierarchy.

All domain exceptions inherit from CareGuardError so callers can catch
broadly or narrowly as needed.
"""


class CareGuardError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


# --- Domain errors ---

class NotFoundError(CareGuardError):
    def __init__(self, resource: str, id: str) -> None:
        super().__init__(f"{resource} '{id}' not found", code="NOT_FOUND")
        self.resource = resource
        self.id = id


class ConflictError(CareGuardError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="CONFLICT")


class ValidationError(CareGuardError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="VALIDATION_ERROR")


class AuthenticationError(CareGuardError):
    """Bad credentials or a disabled account. Maps to HTTP 401."""

    def __init__(self, message: str = "Invalid email or password") -> None:
        super().__init__(message, code="AUTHENTICATION_ERROR")


# --- FHIR errors ---

class FHIRAuthError(CareGuardError):
    def __init__(self, message: str = "FHIR authentication failed") -> None:
        super().__init__(message, code="FHIR_AUTH_ERROR")


class FHIRRequestError(CareGuardError):
    def __init__(self, resource: str, status_code: int) -> None:
        super().__init__(
            f"FHIR request for {resource} failed with status {status_code}",
            code="FHIR_REQUEST_ERROR",
        )
        self.status_code = status_code


class FHIRParseError(CareGuardError):
    def __init__(self, resource: str, detail: str) -> None:
        super().__init__(
            f"Failed to parse FHIR {resource}: {detail}",
            code="FHIR_PARSE_ERROR",
        )


# --- Agent errors ---

class AgentError(CareGuardError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="AGENT_ERROR")


class ToolExecutionError(AgentError):
    def __init__(self, tool_name: str, detail: str) -> None:
        super().__init__(f"Tool '{tool_name}' failed: {detail}")
        self.tool_name = tool_name


class ProtocolNotFoundError(AgentError):
    def __init__(self, condition: str) -> None:
        super().__init__(f"No protocol registered for condition: {condition}")


# --- Outreach errors ---

class OutreachError(CareGuardError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="OUTREACH_ERROR")


class TwilioCallError(OutreachError):
    def __init__(self, detail: str) -> None:
        super().__init__(f"Twilio call failed: {detail}")
