import hashlib
import logging
import time

from fastapi import HTTPException, Request

from ..config import get_settings
from ..kv import get_kv

log = logging.getLogger("gamefy.ratelimit")


def client_ip_source(request: Request) -> tuple[str, str]:
    """(ip, which header it came from). Behind Netlify -> Vercel the proxy hop hides the real client
    unless the proxy forwards it; TRUSTED_IP_HEADER names the header to believe."""
    s = get_settings()
    for header in (s.trusted_ip_header, "x-real-ip", "x-forwarded-for"):
        v = request.headers.get(header)
        if v:
            return v.split(",")[0].strip()[:64], header
    return (request.client.host if request.client else "unknown"), "peer"


def client_ip(request: Request) -> str:
    return client_ip_source(request)[0]


def hash_value(value: str) -> str:
    """Stable, non-reversible identifier for logs/audit (no raw IPs or emails stored)."""
    return hashlib.sha256(value.encode()).hexdigest()[:24]


async def hit(scope: str, ident: str, limit: int, window_s: int) -> None:
    """Fixed-window counter. Raises 429 once `limit` is exceeded within the window."""
    if limit <= 0:
        raise HTTPException(429, "Limit not available on your plan", headers={"Retry-After": str(window_s)})
    bucket = int(time.time() // window_s)
    n = await get_kv().incr(f"rl:{scope}:{ident}:{bucket}", window_s + 1)
    if n > limit:
        log.warning("rate_limited", extra={"scope": scope, "limit": limit, "window_s": window_s})
        retry = window_s - int(time.time() % window_s)
        raise HTTPException(429, "Too many requests", headers={"Retry-After": str(max(retry, 1))})


async def quota_use(scope: str, user_id: str, limit: int) -> int:
    """Daily quota (UTC day). Returns remaining after this use; raises 429 when exhausted."""
    day = time.strftime("%Y%m%d", time.gmtime())
    if limit <= 0:
        raise HTTPException(402, "This feature is not included in your plan")
    n = await get_kv().incr(f"quota:{scope}:{user_id}:{day}", 86400 + 3600)
    if n > limit:
        log.warning("quota_exhausted", extra={"scope": scope})
        raise HTTPException(429, "Daily quota reached", headers={"Retry-After": "3600"})
    return limit - n


async def ip_limiter(request: Request) -> None:
    """Global per-IP guard (applied as an app dependency)."""
    s = get_settings()
    await hit("ip", hash_value(client_ip(request)), s.limits_for("visitor").requests_per_minute * 2, 60)
