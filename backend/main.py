import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api.middleware.audit import HIPAAAuditMiddleware
from api.middleware.error_handler import careguard_exception_handler, unhandled_exception_handler
from api.middleware.security_headers import SecurityHeadersMiddleware
from api.routes import auth, dashboard, discharge, twilio_voice
from config import get_settings
from exceptions import CareGuardError
import models.db  # noqa: F401 — registers all ORM models with Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is owned by Alembic — run `alembic upgrade head` before starting.
    # (Previously created here via Base.metadata.create_all, which caused schema
    # drift on column changes; see backend/alembic/README.md.)
    #
    # Data-only bootstrap (not schema): seed the initial admin so a fresh deploy
    # has a usable login. No-ops once any user exists. Guarded so a not-yet-
    # migrated DB doesn't block startup.
    try:
        from database import AsyncSessionLocal
        from services.auth_service import AuthService

        async with AsyncSessionLocal() as db:
            await AuthService(db).ensure_bootstrap_admin()
            await db.commit()
    except Exception:  # noqa: BLE001 — never let bootstrap crash the app
        logging.getLogger(__name__).warning(
            "Admin bootstrap skipped (DB not ready or already seeded)", exc_info=True
        )
    yield


app = FastAPI(
    lifespan=lifespan,
    title="CareGuard API",
    version=settings.app_version,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
)

# Middleware (order matters — outermost runs first)
app.add_middleware(HIPAAAuditMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
# Explicit CORS_ALLOW_ORIGINS wins (needed when the SPA is on a different host,
# e.g. Vercel → Railway). Otherwise: "*" in dev, the canonical app domain in prod.
_cors_origins = settings.cors_origins_list or (
    ["https://app.careguard.health"] if settings.is_production else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # Auth is a Bearer header, not cookies; credentials must be off when the
    # origin list is "*" (browsers reject "*" + credentials).
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Production transport hardening: force HTTPS and restrict the Host header.
if settings.is_production:
    app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[settings.domain, "app.careguard.health"],
    )

# Exception handlers
app.add_exception_handler(CareGuardError, careguard_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# Routers
app.include_router(auth.router)
app.include_router(discharge.router)
app.include_router(twilio_voice.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "ok", "version": settings.app_version}
