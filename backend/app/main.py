import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .routers import auth, games, me, reco
from .security.middleware import SecurityMiddleware, configure_logging
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
async def unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error", extra={"error": type(exc).__name__})
    return JSONResponse({"detail": "Internal error"}, status_code=500)   # no stack traces to clients


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/api/health/ready")
async def ready() -> JSONResponse:
    """Readiness probe: can we reach the database? Boolean only — no error details are exposed
    (the cause is in the server logs under 'ready_check_failed')."""
    from sqlalchemy import text
    from .db import get_engine
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("select 1 from games limit 1"))
        return JSONResponse({"ok": True, "db": True})
    except Exception as exc:  # noqa: BLE001
        log.error("ready_check_failed", extra={"error": type(exc).__name__})
        return JSONResponse({"ok": False, "db": False}, status_code=503)


for r in (auth.router, games.router, me.router, reco.router):
    app.include_router(r, prefix="/api")
