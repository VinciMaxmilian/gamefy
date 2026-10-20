import os
import time
import uuid

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-test-secret-test-secret-123")
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:dev@localhost:5432/gamefy_dev"))

from app import kv as kvmod  # noqa: E402
from app.config import get_settings  # noqa: E402

SECRET = os.environ["SUPABASE_JWT_SECRET"]
ORIGIN = "http://localhost:5173"


def make_token(user_id: uuid.UUID | None = None, *, exp_in: int = 3600, alg: str = "HS256", secret: str = SECRET) -> tuple[str, uuid.UUID]:
    uid = user_id or uuid.uuid4()
    now = int(time.time())
    payload = {"sub": str(uid), "aud": "authenticated", "email": f"{uid.hex[:8]}@example.com", "iat": now, "exp": now + exp_in}
    return jwt.encode(payload, secret, algorithm=alg), uid


@pytest.fixture(autouse=True)
def fresh_kv():
    kvmod.set_kv(kvmod.MemoryKV())
    yield


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/auth/csrf")
        c.headers["X-CSRF-Token"] = r.json()["csrf"]
        c.headers["Origin"] = ORIGIN
        yield c


@pytest.fixture
async def db_ready():
    """Skip integration tests when no seeded database is reachable."""
    from sqlalchemy import text
    from app.db import get_engine
    try:
        async with get_engine().connect() as conn:
            n = (await conn.execute(text("select count(*) from games"))).scalar_one()
        if n == 0:
            pytest.skip("database not seeded")
    except Exception:
        pytest.skip("database not available")


async def create_user(client: AsyncClient) -> uuid.UUID:
    """Log in as a fresh user: create the auth user (Supabase does this in prod) and set a signed cookie."""
    from sqlalchemy import text
    from app.db import get_engine
    token, uid = make_token()
    async with get_engine().begin() as conn:
        await conn.execute(text("insert into auth.users (id, email) values (:i, :e) on conflict do nothing"),
                           {"i": uid, "e": f"{uid.hex[:8]}@example.com"})
    client.cookies.set("gf_at", token)
    return uid
