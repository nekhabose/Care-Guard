import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api.middleware.audit import HIPAAAuditMiddleware
from api.middleware.error_handler import careguard_exception_handler, unhandled_exception_handler
from api.middleware.security_headers import SecurityHeadersMiddleware
from api.routes import dashboard, discharge, twilio_voice
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.careguard.health"] if settings.is_production else ["*"],
    allow_credentials=True,
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
app.include_router(discharge.router)
app.include_router(twilio_voice.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "ok", "version": settings.app_version}
