"""Tiny key-value layer used for rate limits, quotas and caches.

Backends: Upstash Redis (REST — works from serverless) or in-process memory.
Memory is per-instance, so limits are only approximate without Redis; it is the
dev/test fallback and also the degraded mode if Redis is unreachable (fail to a
local limiter, never fail open).
"""
import logging
import time
from typing import Protocol

import httpx

from .config import get_settings

log = logging.getLogger("gamefy.kv")


class KV(Protocol):
    async def incr(self, key: str, ttl: int) -> int: ...
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int) -> None: ...


class MemoryKV:
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float]] = {}

    def _gc(self) -> None:
        if len(self._data) > 20_000:
            now = time.monotonic()
            self._data = {k: v for k, v in self._data.items() if v[1] > now}

    async def incr(self, key: str, ttl: int) -> int:
        now = time.monotonic()
        val, exp = self._data.get(key, ("0", 0.0))
        if exp <= now:
            val, exp = "0", now + ttl
        n = int(val) + 1
        self._data[key] = (str(n), exp)
        self._gc()
        return n

    async def get(self, key: str) -> str | None:
        item = self._data.get(key)
        if not item or item[1] <= time.monotonic():
            return None
        return item[0]

    async def set(self, key: str, value: str, ttl: int) -> None:
        self._data[key] = (value, time.monotonic() + ttl)
        self._gc()


class UpstashKV:
    """Upstash Redis REST client with a minimal circuit breaker."""

    def __init__(self, url: str, token: str, fallback: MemoryKV) -> None:
        self._url = url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._fallback = fallback
        self._open_until = 0.0
        self._failures = 0

    async def _pipeline(self, commands: list[list]) -> list:
        async with httpx.AsyncClient(timeout=1.5) as client:
            r = await client.post(f"{self._url}/pipeline", json=commands, headers=self._headers)
            r.raise_for_status()
            return [item.get("result") for item in r.json()]

    def _tripped(self) -> bool:
        return time.monotonic() < self._open_until

    def _fail(self, exc: Exception) -> None:
        self._failures += 1
        log.warning("redis_error", extra={"error": type(exc).__name__})
        if self._failures >= 3:
            self._open_until = time.monotonic() + 30
            self._failures = 0

    async def incr(self, key: str, ttl: int) -> int:
        if self._tripped():
            return await self._fallback.incr(key, ttl)
        try:
            res = await self._pipeline([["INCR", key], ["EXPIRE", key, ttl, "NX"]])
            self._failures = 0
            return int(res[0])
        except Exception as exc:  # noqa: BLE001
            self._fail(exc)
            return await self._fallback.incr(key, ttl)

    async def get(self, key: str) -> str | None:
        if self._tripped():
            return await self._fallback.get(key)
        try:
            return (await self._pipeline([["GET", key]]))[0]
        except Exception as exc:  # noqa: BLE001
            self._fail(exc)
            return await self._fallback.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:
        if self._tripped():
            return await self._fallback.set(key, value, ttl)
        try:
            await self._pipeline([["SET", key, value, "EX", ttl]])
        except Exception as exc:  # noqa: BLE001
            self._fail(exc)
            await self._fallback.set(key, value, ttl)


_kv: KV | None = None


def get_kv() -> KV:
    global _kv
    if _kv is None:
        s = get_settings()
        mem = MemoryKV()
        _kv = UpstashKV(s.upstash_redis_rest_url, s.upstash_redis_rest_token, mem) if s.upstash_redis_rest_url else mem
    return _kv


def set_kv(kv: KV | None) -> None:  # tests
    global _kv
    _kv = kv
