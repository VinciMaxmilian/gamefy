import asyncio
import logging
import re
import time

import httpx

from ..config import get_settings
from ..tlsutil import client_verify
from .provider import EmbedResult, GenerateResult, estimate_tokens, l2_normalize

BASE = "https://generativelanguage.googleapis.com/v1beta"
log = logging.getLogger("gamefy.gemini")


def retry_delay(r: httpx.Response, attempt: int) -> float:
    """How long to wait after a 429/5xx: Retry-After header, else Google's own hint ("retryDelay": "23s"), else exponential."""
    if h := r.headers.get("retry-after"):
        try:
            return float(h)
        except ValueError:
            pass
    if m := re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', r.text):
        return float(m.group(1)) + 1
    return min(5.0 * 2 ** attempt, 60.0)


def pace_delay(n_texts: int, tokens: int, elapsed: float, rpm: int, tpm: int) -> float:
    """Seconds to wait after a batch so the long-run rate stays under both the request and the token limit."""
    return max(0.0, max(n_texts * 60 / max(rpm, 1), tokens * 60 / max(tpm, 1)) - elapsed)


async def post_with_retry(client, url: str, *, json: dict, headers: dict, attempts: int = 6, sleep=asyncio.sleep) -> httpx.Response:
    for attempt in range(attempts):
        r = await client.post(url, json=json, headers=headers)
        if (r.status_code == 429 or r.status_code >= 500) and attempt < attempts - 1:
            delay = retry_delay(r, attempt)
            log.warning("gemini_backoff", extra={"status": r.status_code, "sleep": delay, "attempt": attempt})
            print(f"  Gemini asked us to slow down ({r.status_code}); waiting {delay:.0f}s…")
            await sleep(delay)
            continue
        r.raise_for_status()
        return r
    raise RuntimeError("unreachable")


class GeminiProvider:
    """Google Gemini over REST. The API key is sent in a header (never in the URL, so it
    cannot leak into logs) and is read only from the environment."""

    name = "gemini"

    def __init__(self) -> None:
        self._s = get_settings()
        self._headers = {"x-goog-api-key": self._s.gemini_api_key, "content-type": "application/json"}

    async def embed(self, texts: list[str], *, task: str = "document") -> EmbedResult:
        s = self._s
        model = s.gemini_embed_model
        task_type = "RETRIEVAL_QUERY" if task == "query" else "RETRIEVAL_DOCUMENT"
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(timeout=s.ai_timeout_seconds, verify=client_verify()) as client:
            for i in range(0, len(texts), 20):  # small batches: smoother against per-minute limits (API max is 100)
                chunk = texts[i:i + 20]
                started = time.monotonic()
                body = {"requests": [{
                    "model": f"models/{model}",
                    "content": {"parts": [{"text": t}]},
                    "taskType": task_type,
                    "outputDimensionality": s.embed_dim,
                } for t in chunk]}
                r = await post_with_retry(client, f"{BASE}/models/{model}:batchEmbedContents", json=body, headers=self._headers)
                # Truncated (Matryoshka) vectors must be re-normalised for cosine search.
                vectors += [l2_normalize(e["values"]) for e in r.json()["embeddings"]]
                if task == "document":               # indexing: stay under the provider's per-minute limits (queries are single and unpaced)
                    await asyncio.sleep(pace_delay(len(chunk), sum(estimate_tokens(t) for t in chunk), time.monotonic() - started, s.gemini_embed_rpm, s.gemini_embed_tpm))
        tokens = sum(estimate_tokens(t) for t in texts)
        cost = int(tokens * s.embed_cost_per_mtok_usd)  # micro-USD: tokens/1e6 * $/Mtok * 1e6
        return EmbedResult(vectors, tokens, model, self.name, cost)

    async def generate(self, system: str, user: str, *, max_output_tokens: int = 512,
                       json_schema: dict | None = None) -> GenerateResult:
        s = self._s
        gen_cfg: dict = {"maxOutputTokens": max_output_tokens, "temperature": 0.2}
        if json_schema:
            gen_cfg |= {"responseMimeType": "application/json", "responseSchema": json_schema}
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": gen_cfg,
        }
        async with httpx.AsyncClient(timeout=s.ai_timeout_seconds, verify=client_verify()) as client:
            r = await post_with_retry(client, f"{BASE}/models/{s.gemini_chat_model}:generateContent", json=body, headers=self._headers, attempts=3)
        data = r.json()
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        usage = data.get("usageMetadata", {})
        return GenerateResult(text, usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0),
                              s.gemini_chat_model, self.name, 0)
