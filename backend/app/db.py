import uuid
from collections.abc import AsyncIterator

from sqlalchemy.engine import make_url
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
        # Supabase's pooler runs in *transaction* mode: consecutive transactions of one request may land on
        # different server connections, so named prepared statements break ("already exists" / "does not
        # exist"). Disable both asyncpg's and SQLAlchemy's statement caches and give every statement a unique
        # name (documented SQLAlchemy recipe for PgBouncer/Supavisor transaction pooling).
        url = make_url(s.async_database_url).update_query_dict({"prepared_statement_cache_size": "0"})
        _engine = create_async_engine(
            url,
            poolclass=NullPool,
            connect_args={
                "statement_cache_size": 0,
                "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
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
