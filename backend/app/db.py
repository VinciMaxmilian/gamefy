from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from .config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Lazy engine. NullPool + no prepared-statement cache so it works behind
    Supabase's transaction pooler (PgBouncer) from short-lived serverless functions."""
    global _engine, _sessionmaker
    if _engine is None:
        s = get_settings()
        if not s.database_url:
            raise RuntimeError("DATABASE_URL is not configured")
        local = "localhost" in s.database_url or "127.0.0.1" in s.database_url
        _engine = create_async_engine(
            s.async_database_url,
            poolclass=NullPool,
            connect_args={
                "statement_cache_size": 0,
                "ssl": False if local else "require",
                "server_settings": {"application_name": "gamefy-api"},
            },
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def get_session() -> AsyncIterator[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    async with _sessionmaker() as session:
        yield session
