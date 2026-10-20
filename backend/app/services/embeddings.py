import hashlib
import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..ai.provider import get_provider
from ..kv import get_kv
from ..models import UsageLog


async def log_usage(session: AsyncSession, user_id: uuid.UUID | None, kind: str, endpoint: str, *,
                    provider: str | None = None, model: str | None = None, tokens_in: int = 0,
                    tokens_out: int = 0, cost_micro_usd: int = 0, cached: bool = False) -> None:
    """Every AI-related call is recorded — this is what answers 'what does each user cost?'."""
    session.add(UsageLog(user_id=user_id, kind=kind, endpoint=endpoint, provider=provider, model=model,
                         tokens_in=tokens_in, tokens_out=tokens_out, cost_micro_usd=cost_micro_usd, cached=cached))
    await session.commit()


async def embed_query(session: AsyncSession, user_id: uuid.UUID | None, text: str, endpoint: str) -> list[float]:
    """Embed a search query with a 24h cache (popular/repeated queries cost nothing)."""
    provider = get_provider()
    key = "emb:" + hashlib.sha256(f"{provider.name}|{text.lower()}".encode()).hexdigest()
    kv = get_kv()
    if hit := await kv.get(key):
        await log_usage(session, user_id, "embed_query", endpoint, provider=provider.name, cached=True)
        return json.loads(hit)
    res = await provider.embed([text], task="query")
    vec = res.vectors[0]
    await kv.set(key, json.dumps([round(x, 6) for x in vec]), 86400)
    await log_usage(session, user_id, "embed_query", endpoint, provider=res.provider, model=res.model,
                    tokens_in=res.tokens_in, cost_micro_usd=res.cost_micro_usd)
    return vec
