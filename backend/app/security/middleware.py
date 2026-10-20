import hmac
import json
import logging
import secrets
import time
import uuid

from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..config import get_settings
from .auth import CSRF_COOKIE

log = logging.getLogger("gamefy.http")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    "Cache-Control": "no-store",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
                   "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)[-3000:]
        for k, v in record.__dict__.items():
            if k not in logging.LogRecord("", 0, "", 0, "", (), None).__dict__ and k not in payload and k != "message":
                payload[k] = v
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


class SecurityMiddleware:
    """Pure-ASGI middleware: request id, structured access log, body-size cap,
    CSRF (Origin check + double-submit token), security headers.

    Body cap applies to the declared Content-Length AND to the streamed bytes,
    so chunked requests cannot bypass it."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        s = get_settings()
        started = time.perf_counter()
        request_id = uuid.uuid4().hex[:16]
        headers = {k.decode().lower(): v.decode("latin-1") for k, v in scope["headers"]}
        method = scope["method"]
        status_holder = {"status": 500}
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                own = {h.lower() for h in SECURITY_HEADERS} - {"cache-control"}     # endpoints may set their own caching
                raw = [(k, v) for k, v in message.get("headers", []) if k.decode().lower() not in own | {"server"}]
                for k, v in SECURITY_HEADERS.items():
                    if k == "Cache-Control" and any(h[0].lower() == b"cache-control" for h in raw):
                        continue
                    raw.append((k.encode(), v.encode()))
                if s.is_prod:
                    raw.append((b"Strict-Transport-Security", b"max-age=63072000; includeSubDomains; preload"))
                raw.append((b"X-Request-ID", request_id.encode()))
                message["headers"] = raw
            await send(message)

        async def reject(status: int, detail: str) -> None:
            resp = JSONResponse({"detail": detail}, status_code=status)
            await resp(scope, receive, send_wrapper)

        # --- body size limit (declared) ---
        try:
            declared = int(headers.get("content-length", "0"))
        except ValueError:
            declared = 0
        if declared > s.max_body_bytes:
            await reject(413, "Request too large")
            return

        # --- CSRF for unsafe methods ---
        if method not in SAFE_METHODS:
            origin = headers.get("origin")
            allowed = s.cors_origin_list
            if origin and origin.rstrip("/") not in allowed:
                log.warning("csrf_origin_rejected", extra={"request_id": request_id, "origin": origin[:100]})
                await reject(403, "Origin not allowed")
                return
            cookies = _parse_cookies(headers.get("cookie", ""))
            token_cookie = cookies.get(CSRF_COOKIE, "")
            token_header = headers.get("x-csrf-token", "")
            if not token_cookie or not hmac.compare_digest(token_cookie, token_header):
                log.warning("csrf_token_rejected", extra={"request_id": request_id, "path": scope["path"]})
                await reject(403, "CSRF validation failed")
                return

        # --- body size limit (streamed) ---
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > s.max_body_bytes:
                    raise _BodyTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send_wrapper)
        except _BodyTooLarge:
            await reject(413, "Request too large")
        finally:
            log.info("request", extra={
                "request_id": request_id, "method": method, "path": scope["path"],
                "status": status_holder["status"],
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            })


class _BodyTooLarge(Exception):
    pass


def _parse_cookies(header: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in header.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


__all__ = ["SecurityMiddleware", "configure_logging", "new_csrf_token", "Response"]
