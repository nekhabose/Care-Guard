"""
FastAPI dependency providers — single source of truth for DI.

Import these in routes; never construct services or clients in routes directly.
"""
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings, get_settings
from database import get_db
from fhir.client import BaseFHIRClient, EpicFHIRClient
from fhir.mock_client import MockFHIRClient
from repositories.discharge import DischargeRepository
from repositories.escalation import EscalationRepository
from repositories.patient import PatientRepository
from repositories.session import SessionRepository, TurnRepository
from repositories.user import UserRepository
from security.auth import InvalidTokenError, READ_ROLES, decode_token
from services.auth_service import AuthService
from services.call_trigger import CallTriggerService
from services.discharge import DischargeService
from services.notification import BaseNotifier, get_notifier
from services.onboarding import PatientOnboardingService
from services.outreach import OutreachService
from services.patient_rights import PatientRightsService

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Authenticate the caller. Enforces signature AND expiry."""
    try:
        return decode_token(credentials.credentials)
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def require_role(*allowed: str):
    """Dependency factory — authorize the caller by role (RBAC).

    Authenticates first, then checks the token's ``role`` claim against the
    allowed set. 403 if authenticated but lacking the role.
    """
    allowed_set = frozenset(str(r) for r in allowed)

    def _dependency(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this action",
            )
        return user

    return _dependency


# Any authenticated, recognised role may read PHI dashboards.
require_reader = require_role(*READ_ROLES)


async def verify_twilio_signature(request: Request) -> None:
    """Reject Twilio webhooks without a valid ``X-Twilio-Signature``.

    Skips validation only when no auth token is configured (local/mock dev);
    production refuses to boot without one (see config._enforce_production).
    """
    settings = get_settings()
    if not (settings.twilio_validate_signatures and settings.twilio_auth_token):
        return

    from twilio.request_validator import RequestValidator

    validator = RequestValidator(settings.twilio_auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    # Twilio signs the exact public URL it POSTed to (the one we handed it in
    # base_url), including the query string. Reconstruct from base_url rather than
    # request.url, whose host/scheme are unreliable behind a tunnel/proxy.
    url = f"{settings.base_url.rstrip('/')}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    form = await request.form()
    params = {k: v for k, v in form.items()}

    if not validator.validate(url, params, signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Twilio signature"
        )


def get_fhir_client(settings: Settings = Depends(get_settings)) -> BaseFHIRClient:
    if settings.fhir_provider.lower() == "epic":
        return EpicFHIRClient()
    return MockFHIRClient()


def get_notifier_dep() -> BaseNotifier:
    return get_notifier()


def get_patient_repo(db: AsyncSession = Depends(get_db)) -> PatientRepository:
    return PatientRepository(db)


def get_discharge_repo(db: AsyncSession = Depends(get_db)) -> DischargeRepository:
    return DischargeRepository(db)


def get_session_repo(db: AsyncSession = Depends(get_db)) -> SessionRepository:
    return SessionRepository(db)


def get_escalation_repo(db: AsyncSession = Depends(get_db)) -> EscalationRepository:
    return EscalationRepository(db)


def get_discharge_service(
    db: AsyncSession = Depends(get_db),
    fhir_client: BaseFHIRClient = Depends(get_fhir_client),
) -> DischargeService:
    return DischargeService(db, fhir_client)


def get_call_trigger_service(
    db: AsyncSession = Depends(get_db),
    fhir_client: BaseFHIRClient = Depends(get_fhir_client),
    settings: Settings = Depends(get_settings),
) -> CallTriggerService:
    return CallTriggerService(db, fhir_client, settings)


def get_patient_rights_service(db: AsyncSession = Depends(get_db)) -> PatientRightsService:
    return PatientRightsService(db)


def get_onboarding_service(db: AsyncSession = Depends(get_db)) -> PatientOnboardingService:
    return PatientOnboardingService(db)


def get_user_repo(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)
