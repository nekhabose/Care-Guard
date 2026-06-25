"""
Auth API — staff login for the care coordinator dashboard.

``POST /auth/login`` exchanges email + password for a short-lived bearer token;
``GET /auth/me`` echoes the current token's identity. Every other dashboard
route requires the token this endpoint mints (see ``api/deps.require_reader``).
"""
import uuid

from fastapi import APIRouter, Depends

from api.deps import get_auth_service, get_current_user, get_user_repo
from exceptions import AuthenticationError
from models.schemas import LoginRequest, TokenResponse, UserRead
from repositories.user import UserRepository
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    auth: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    user, token, expires_in = await auth.authenticate(body.email, body.password)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
async def me(
    current: dict = Depends(get_current_user),
    users: UserRepository = Depends(get_user_repo),
) -> UserRead:
    try:
        user_id = uuid.UUID(str(current["sub"]))
    except (ValueError, KeyError):
        raise AuthenticationError("Malformed token subject")
    user = await users.get(user_id)
    if user is None or not user.is_active:
        # Token is valid but the account is gone/disabled — treat as unauthenticated.
        raise AuthenticationError("Account is no longer active")
    return UserRead.model_validate(user)
