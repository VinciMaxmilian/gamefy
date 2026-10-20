import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass
from functools import lru_cache

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, Response
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_session
from ..kv import get_kv
from ..tlsutil import client_verify
from ..models import Profile
from .ratelimit import hash_value, hit

ACCESS_COOKIE = "gf_at"
REFRESH_COOKIE = "gf_rt"
CSRF_COOKIE = "gf_csrf"


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    email: str | None
    plan: str
    role: str

    @property
    def limits_key(self) -> str:
        return "admin" if self.role == "admin" else self.plan


@lru_cache
def _jwks() -> PyJWKClient:
    s = get_settings()
    return PyJWKClient(f"{s.supabase_url}/auth/v1/.well-known/jwks.json", cache_keys=True, lifespan=3600)


def verify_access_token(token: str) -> dict:
    """Verify a Supabase access token. Algorithm is pinned per key type; 'none' and
    unexpected algorithms are rejected. Raises jwt.PyJWTError on any problem."""
    s = get_settings()
    alg = jwt.get_unverified_header(token).get("alg")
    if alg == "HS256" and s.supabase_jwt_secret:
        key = s.supabase_jwt_secret
    elif alg in ("ES256", "RS256") and s.supabase_url:
        key = _jwks().get_signing_key_from_jwt(token).key
    else:
        raise jwt.InvalidAlgorithmError("unsupported algorithm")
    return jwt.decode(
        token, key, algorithms=[alg], audience="authenticated",
        options={"require": ["exp", "sub"]}, leeway=5,
    )


async def _fetch_gotrue_user(token: str) -> dict | None:
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=6, verify=client_verify()) as client:
            r = await client.get(f"{s.supabase_url}/auth/v1/user",
                                 headers={"apikey": s.supabase_publishable_key, "Authorization": f"Bearer {token}"})
    except httpx.HTTPError:
        return None
    return r.json() if r.status_code == 200 else None


async def verify_token(token: str) -> dict:
    """Async verification used by the app. Local verification when we can (HS256 secret or JWKS);
    otherwise — HS256 project without SUPABASE_JWT_SECRET — ask Supabase Auth itself, with a short
    cache (positive 60s, negative 30s) so bad tokens cannot turn into unbounded outbound calls.
    Raises jwt.PyJWTError when the token is not acceptable."""
    s = get_settings()
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except jwt.PyJWTError:
        raise
    if not (alg == "HS256" and not s.supabase_jwt_secret and s.supabase_url):
        return await asyncio.to_thread(verify_access_token, token)   # JWKS fetch is blocking I/O
    kv = get_kv()
    key = "jwtv:" + hashlib.sha256(token.encode()).hexdigest()
    if (cached := await kv.get(key)) is not None:
        if cached == "0":
            raise jwt.InvalidTokenError("rejected")
        return json.loads(cached)
    user = await _fetch_gotrue_user(token)
    if not user or not user.get("id"):
        await kv.set(key, "0", 30)
        raise jwt.InvalidTokenError("rejected by auth provider")
    claims = {"sub": user["id"], "email": user.get("email"), "aud": "authenticated"}
    await kv.set(key, json.dumps(claims), 60)
    return claims


def set_auth_cookies(response: Response, access: str, refresh: str | None, expires_in: int) -> None:
    s = get_settings()
    common = dict(httponly=True, secure=s.cookie_secure, samesite="lax")
    response.set_cookie(ACCESS_COOKIE, access, max_age=expires_in, path="/", **common)
    if refresh:
        response.set_cookie(REFRESH_COOKIE, refresh, max_age=60 * 60 * 24 * 30, path="/api/auth", **common)


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")


async def _load_principal(request: Request, session: AsyncSession) -> Principal | None:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        return None
    try:
        claims = await verify_token(token)
        user_id = uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
    # Plan and role ALWAYS come from our database, never from the token or the client.
    try:
        await session.execute(insert(Profile).values(id=user_id).on_conflict_do_nothing())
        profile = (await session.execute(select(Profile).where(Profile.id == user_id))).scalar_one()
        await session.commit()
    except IntegrityError:          # valid token for an auth user that no longer exists (deleted account)
        await session.rollback()
        return None
    return Principal(user_id=user_id, email=claims.get("email"), plan=profile.plan, role=profile.role)


async def optional_user(request: Request, session: AsyncSession = Depends(get_session)) -> Principal | None:
    cached = getattr(request.state, "principal", "unset")
    if cached != "unset":
        return cached
    principal = await _load_principal(request, session)
    request.state.principal = principal
    if principal:
        s = get_settings()
        await hit("user", hash_value(str(principal.user_id)), s.limits_for(principal.limits_key).requests_per_minute, 60)
    return principal


async def current_user(principal: Principal | None = Depends(optional_user)) -> Principal:
    if principal is None:
        raise HTTPException(401, "Authentication required")
    return principal


async def premium_user(principal: Principal = Depends(current_user)) -> Principal:
    if principal.plan != "premium" and principal.role != "admin":
        raise HTTPException(402, "Premium plan required")
    return principal


async def admin_user(principal: Principal = Depends(current_user)) -> Principal:
    if principal.role != "admin":
        raise HTTPException(403, "Forbidden")
    return principal
