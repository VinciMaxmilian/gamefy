"""Provider-agnostic AI interface. Nothing outside app/ai imports a vendor SDK."""
import hashlib
import math
import re
from dataclasses import dataclass
from typing import Protocol

from ..config import get_settings


@dataclass
class EmbedResult:
    vectors: list[list[float]]
    tokens_in: int
    model: str
    provider: str
    cost_micro_usd: int = 0


@dataclass
class GenerateResult:
    text: str
    tokens_in: int
    tokens_out: int
    model: str
    provider: str
    cost_micro_usd: int = 0


class AIProvider(Protocol):
    name: str

    async def embed(self, texts: list[str], *, task: str = "document") -> EmbedResult:
        """task: 'document' (indexing) or 'query' (searching)."""
        ...

    async def generate(self, system: str, user: str, *, max_output_tokens: int = 512,
                       json_schema: dict | None = None) -> GenerateResult: ...


def l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class LocalHashProvider:
    """Deterministic, offline bag-of-words hashing embedder. NOT semantically deep —
    it exists so dev, CI and degraded mode work without any API key or cost."""

    name = "local-hash"

    async def embed(self, texts: list[str], *, task: str = "document") -> EmbedResult:
        dim = get_settings().embed_dim
        out = []
        for t in texts:
            v = [0.0] * dim
            for tok in re.findall(r"[\w-]{2,}", t.lower()):
                h = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "big")
                v[h % dim] += 1.0 if (h >> 63) & 1 else -1.0
            out.append(l2_normalize(v))
        return EmbedResult(out, sum(estimate_tokens(t) for t in texts), "local-hash-v1", self.name, 0)

    async def generate(self, system: str, user: str, *, max_output_tokens: int = 512,
                       json_schema: dict | None = None) -> GenerateResult:
        raise NotImplementedError("No generative provider configured")


_provider: AIProvider | None = None


def get_provider() -> AIProvider:
    global _provider
    if _provider is None:
        s = get_settings()
        if s.gemini_api_key:
            from .gemini import GeminiProvider
            _provider = GeminiProvider()
        else:
            _provider = LocalHashProvider()
    return _provider


def set_provider(p: AIProvider | None) -> None:  # tests
    global _provider
    _provider = p
