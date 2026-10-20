import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .routers import auth, games, me, reco
from .security.middleware import SECURITY_HEADERS, SecurityMiddleware, configure_logging
from .security.ratelimit import ip_limiter

configure_logging()
log = logging.getLogger("gamefy")
s = get_settings()

# No interactive docs / OpenAPI in production (smaller attack surface).
app = FastAPI(
    title="Gamefy API", version="0.1.0",
    docs_url=None if s.is_prod else "/api/docs",
    redoc_url=None, openapi_url=None if s.is_prod else "/api/openapi.json",
    dependencies=[Depends(ip_limiter)],
)

# Order matters: the last added runs first. CORS must wrap the security layer so
# rejected preflight/CSRF responses still carry correct CORS headers.
app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=s.cors_origin_list,          # explicit allow-list, never "*" with credentials
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
    max_age=600,
)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Field names + messages only; never echo the submitted values back.
    errors = [{"loc": [str(p) for p in e["loc"]], "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse({"detail": errors}, status_code=422)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    rid = getattr(request.state, "request_id", None)
    log.exception("unhandled_error", extra={"error": type(exc).__name__, "request_id": rid, "path": request.url.path})
    # No stack traces to clients; the request id lets you find the traceback in the server logs.
    # This response is produced outside SecurityMiddleware, so apply the same headers here.
    return JSONResponse({"detail": "Internal error", "request_id": rid}, status_code=500,
                        headers={**SECURITY_HEADERS, "X-Request-ID": rid or ""})


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/api/health/ip")
async def ip_probe(request: Request) -> dict:
    """Diagnostic: which header the rate limiter trusts for the client IP, and a hash of the value.
    Compare the hash from two vantage points (direct vs via the Netlify proxy) to verify the real
    client IP survives the proxy. Never returns the raw IP."""
    from .security.ratelimit import client_ip_source, hash_value
    ip, source = client_ip_source(request)
    return {"source": source, "ip_hash": hash_value(ip)}


REQUIRED_TABLES = {"profiles", "games", "game_embeddings", "wishlist", "library", "ratings", "user_events",
                   "preference_profiles", "hardware_profiles", "usage_log", "audit_log", "store_links"}


@app.get("/api/health/ready")
async def ready() -> JSONResponse:
    """Readiness probe: can we reach the database? Boolean only — no error details are exposed
    (the cause is in the server logs under 'ready_check_failed')."""
    from sqlalchemy import text
    from .db import get_engine
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("select 1 from games limit 1"))
            present = {r[0] for r in await conn.execute(text("select table_name from information_schema.tables where table_schema = 'public'"))}
        missing = sorted(REQUIRED_TABLES - present)
        return JSONResponse({"ok": not missing, "db": True, "missing_tables": missing}, status_code=200 if not missing else 503)
    except Exception as exc:  # noqa: BLE001
        log.error("ready_check_failed", extra={"error": type(exc).__name__})
        return JSONResponse({"ok": False, "db": False}, status_code=503)


for r in (auth.router, games.router, me.router, reco.router):
    app.include_router(r, prefix="/api")
