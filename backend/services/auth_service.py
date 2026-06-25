"""
AuthService — staff login + account bootstrap.

Authenticates a dashboard user against the ``users`` table and mints a
short-lived JWT carrying the authoritative ``role`` claim (RBAC). Login failures
are deliberately indistinguishable (unknown email vs. wrong password vs. disabled
account) to avoid leaking which accounts exist.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from exceptions import AuthenticationError, ConflictError
from models.db.user import User
from repositories.user import UserRepository
from security.auth import Role, create_access_token
from security.passwords import hash_password, verify_password

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)

    async def authenticate(self, email: str, password: str) -> tuple[User, str, int]:
        """Verify credentials and return (user, access_token, expires_in_seconds)."""
        user = await self.users.get_by_email(email)
        # Verify a hash even when the user is missing to keep timing uniform.
        valid = verify_password(password, user.password_hash) if user else verify_password(password, _DUMMY_HASH)
        if not user or not valid or not user.is_active:
            raise AuthenticationError()

        await self.users.update(user, last_login_at=datetime.now(timezone.utc))

        settings = get_settings()
        token = create_access_token(
            sub=str(user.id),
            role=user.role,
            extra={"name": user.name, "email": user.email},
        )
        return user, token, settings.jwt_expiry_minutes * 60

    async def create_user(
        self, email: str, name: str, password: str, role: str | Role = Role.VIEWER
    ) -> User:
        if await self.users.get_by_email(email):
            raise ConflictError(f"A user with email {email!r} already exists")
        return await self.users.create(
            email=email.strip().lower(),
            name=name,
            password_hash=hash_password(password),
            role=str(role),
        )

    async def ensure_bootstrap_admin(self) -> None:
        """Create the initial admin from settings if no users exist yet.

        Idempotent and safe to call on every startup: no-ops once any user
        exists, or if no bootstrap password is configured.
        """
        settings = get_settings()
        if not settings.bootstrap_admin_password:
            return
        if await self.users.count() > 0:
            return
        await self.create_user(
            email=settings.bootstrap_admin_email,
            name=settings.bootstrap_admin_name,
            password=settings.bootstrap_admin_password,
            role=Role.ADMIN,
        )
        logger.info("Bootstrapped initial admin account %s", settings.bootstrap_admin_email)


# A valid bcrypt hash, used as a constant-time decoy when the email is unknown so
# login timing doesn't reveal which accounts exist. Computed once at import.
_DUMMY_HASH = hash_password("careguard-decoy-not-a-real-password")
