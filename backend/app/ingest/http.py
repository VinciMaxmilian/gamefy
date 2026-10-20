"""Outbound HTTP for ingestion. Base URLs are hard-coded per client: no URL ever comes from
imported data, so there is no SSRF surface. Redirects are not followed; responses are size-capped."""
import asyncio
import logging
import time

import httpx

log = logging.getLogger("gamefy.ingest")
USER_AGENT = "Gamefy/0.1 (+https://github.com/VinciMaxmilian/gamefy)"   # CheapShark rejects generic/missing UAs
MAX_BYTES = 8 * 1024 * 1024


class Throttled:
    def __init__(self, base_url: str, min_interval: float, headers: dict | None = None, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.min_interval = min_interval
        self._last = 0.0
        self._lock = asyncio.Lock()
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=False,
                                         headers={"User-Agent": USER_AGENT, **(headers or {})})

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(self, method: str, path: str, *, retries: int = 4, **kw) -> httpx.Response:
        url = f"{self.base_url}{path}"
        for attempt in range(retries + 1):
            async with self._lock:                       # serialises + spaces requests => respects rate limits
                wait = self._last + self.min_interval - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last = time.monotonic()
            try:
                r = await self._client.request(method, url, **kw)
            except httpx.TransportError as exc:
                if attempt == retries:
                    raise
                log.warning("transport_error", extra={"error": type(exc).__name__, "attempt": attempt})
                await asyncio.sleep(2 ** attempt)
                continue
            if len(r.content) > MAX_BYTES:
                raise ValueError("response too large")
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                delay = float(r.headers.get("Retry-After", 0) or 0) or 2 ** (attempt + 1)
                log.warning("backoff", extra={"status": r.status_code, "sleep": delay})
                await asyncio.sleep(min(delay, 60))
                continue
            return r
        raise RuntimeError("unreachable")

    async def get_json(self, path: str, **kw):
        r = await self.request("GET", path, **kw)
        r.raise_for_status()
        return r.json()
