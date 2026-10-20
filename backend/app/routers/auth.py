import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_session
from ..schemas import Credentials, EmailOnly, ResetPassword
from ..security.audit import audit
from ..security.auth import (
    ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE, Principal, clear_auth_cookies, optional_user, set_auth_cookies,
    verify_token,
)
from ..security.middleware import new_csrf_token
from ..security.passwords import validate_password
from ..security.ratelimit import client_ip, hash_value, hit

log = logging.getLogger("gamefy.auth")
router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_FAIL = "Invalid email or password"


async def _gotrue(method: str, path: str, *, json: dict | None = None, bearer: str | None = None,
                  params: dict | None = None, secret: bool = False) -> httpx.Response:
    s = get_settings()
    if not s.supabase_url:
        raise HTTPException(503, "Auth is not configured")
    headers = {"apikey": s.supabase_secret_key if secret else s.supabase_publishable_key}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            return await client.request(method, f"{s.supabase_url}/auth/v1{path}", json=json, headers=headers, params=params)
    except httpx.HTTPError as exc:
        log.error("gotrue_unreachable", extra={"error": type(exc).__name__})
        raise HTTPException(502, "Auth provider unavailable") from exc


@router.get("/csrf")
async def csrf(request: Request, response: Response) -> dict:
    """Issues the double-submit CSRF token. Cookie is readable by the SPA by design;
    the middleware requires it to be echoed in the X-CSRF-Token header on unsafe requests."""
    token = request.cookies.get(CSRF_COOKIE) or new_csrf_token()
    response.set_cookie(CSRF_COOKIE, token, max_age=60 * 60 * 24 * 30, path="/", httponly=False,
                        secure=get_settings().cookie_secure, samesite="lax")
    return {"csrf": token}


@router.post("/signup", status_code=202)
async def signup(body: Credentials, request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    ip = hash_value(client_ip(request))
    await hit("signup_ip", ip, 5, 3600)
    if problems := validate_password(body.password, body.email):
        raise HTTPException(422, detail=problems)
    r = await _gotrue("POST", "/signup", json={"email": body.email, "password": body.password})
    if r.status_code >= 500:
        raise HTTPException(502, "Auth provider unavailable")
    await audit(session, request, "signup", ok=r.status_code < 400)
    # Same response whether the email exists or not (no account enumeration).
    return {"message": "If this email can be registered, your account is ready. Check your inbox if confirmation is required, then log in."}


@router.post("/login")
async def login(body: Credentials, request: Request, response: Response, session: AsyncSession = Depends(get_session)) -> dict:
    await hit("login_ip", hash_value(client_ip(request)), 20, 600)
    await hit("login_email", hash_value(body.email), 8, 900)      # brute force on one account
    r = await _gotrue("POST", "/token", json={"email": body.email, "password": body.password}, params={"grant_type": "password"})
    if r.status_code >= 500:
        raise HTTPException(502, "Auth provider unavailable")
    if r.status_code != 200:
        await audit(session, request, "login_failed", email_hash=hash_value(body.email))
        raise HTTPException(401, GENERIC_FAIL)
    data = r.json()
    set_auth_cookies(response, data["access_token"], data.get("refresh_token"), int(data.get("expires_in", 3600)))
    await audit(session, request, "login", user_id=_uid(data))
    return {"ok": True}


def _uid(data: dict):
    import uuid
    try:
        return uuid.UUID(data["user"]["id"])
    except (KeyError, ValueError):
        return None


@router.post("/refresh")
async def refresh(request: Request, response: Response) -> dict:
    await hit("refresh_ip", hash_value(client_ip(request)), 60, 600)
    rt = request.cookies.get(REFRESH_COOKIE)
    if not rt:
        raise HTTPException(401, "No session")
    r = await _gotrue("POST", "/token", json={"refresh_token": rt}, params={"grant_type": "refresh_token"})
    if r.status_code != 200:
        clear_auth_cookies(response)
        raise HTTPException(401, "Session expired")
    d = r.json()
    set_auth_cookies(response, d["access_token"], d.get("refresh_token"), int(d.get("expires_in", 3600)))
    return {"ok": True}


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    at = request.cookies.get(ACCESS_COOKIE)
    if at:
        try:
            await _gotrue("POST", "/logout", bearer=at)
        except HTTPException:
            pass                                     # still clear local cookies
    clear_auth_cookies(response)
    return {"ok": True}


@router.post("/recover", status_code=202)
async def recover(body: EmailOnly, request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    await hit("recover_ip", hash_value(client_ip(request)), 5, 3600)
    await hit("recover_email", hash_value(body.email), 3, 3600)
    s = get_settings()
    redirect = (s.cors_origin_list[0] if s.cors_origin_list else "") + "/reset-password"
    await _gotrue("POST", "/recover", json={"email": body.email}, params={"redirect_to": redirect})
    await audit(session, request, "recover_requested", email_hash=hash_value(body.email))
    return {"message": "If an account exists for this email, a recovery link is on its way."}


@router.post("/reset-password")
async def reset_password(body: ResetPassword, request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    await hit("reset_ip", hash_value(client_ip(request)), 10, 3600)
    invalid = HTTPException(400, "Invalid or expired recovery link")
    if body.token_hash:
        # Password policy FIRST: verifying consumes the one-time token, so a weak password must not burn it.
        if problems := validate_password(body.password):
            raise HTTPException(422, detail=problems)
        v = await _gotrue("POST", "/verify", json={"type": "recovery", "token_hash": body.token_hash})
        if v.status_code != 200 or "access_token" not in v.json():
            await audit(session, request, "password_reset_rejected")
            raise invalid
        access = v.json()["access_token"]
    else:
        try:
            claims = await verify_token(body.access_token or "")   # must be a valid Supabase token
        except Exception as exc:  # noqa: BLE001
            raise invalid from exc
        if problems := validate_password(body.password, claims.get("email", "")):
            raise HTTPException(422, detail=problems)
        access = body.access_token
    r = await _gotrue("PUT", "/user", json={"password": body.password}, bearer=access)
    if r.status_code != 200:
        raise invalid
    await audit(session, request, "password_reset")
    return {"ok": True}


@router.get("/session")
async def session_info(principal: Principal | None = Depends(optional_user)) -> dict:
    return {"authenticated": principal is not None}
