from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

settings = get_settings()

# Require TLS to the database in production (HIPAA transmission security).
# asyncpg negotiates SSL when passed ssl=True; opt-in elsewhere via DB_REQUIRE_SSL.
_require_ssl = settings.db_require_ssl if settings.db_require_ssl is not None else settings.is_production
_connect_args = {"ssl": True} if _require_ssl else {}

engine = create_async_engine(
    settings.database_url,
    echo=not settings.is_production,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
