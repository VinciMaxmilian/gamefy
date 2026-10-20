from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..ai.provider import get_provider
from ..config import get_settings
from ..db import get_session
from ..models import UserEvent
from ..reco.intent import parse_query
from ..schemas import Recommendation
from ..security.audit import audit
from ..security.auth import Principal, current_user
from ..security.ratelimit import quota_use
from ..security.sanitize import looks_like_injection
from ..services import embeddings, recommend

router = APIRouter(tags=["recommendations"])


class ForYou(BaseModel):
    personalized: bool
    items: list[Recommendation]


class SmartResult(BaseModel):
    query: str
    understood: dict
    remaining_today: int
    items: list[Recommendation]


@router.get("/reco/for-you", response_model=ForYou)
async def for_you(limit: Annotated[int, Query(ge=1, le=40)] = 20, explain: bool = False,
                  principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    """Level 1 + 2, no LLM: behaviour profile + embeddings + configurable ranking."""
    return await recommend.personalized(session, principal.user_id, limit, explain)


@router.get("/search/smart", response_model=SmartResult)
async def smart(request: Request, q: Annotated[str, Query(min_length=2, max_length=300)], explain: bool = False,
                fits_my_pc: bool = False, principal: Principal = Depends(current_user),
                session: AsyncSession = Depends(get_session)) -> dict:
    """Semantic search. Free plan has a small daily quota; no generative model is called —
    the rule-based parser extracts constraints and the embedding captures the rest."""
    s = get_settings()
    limits = s.limits_for(principal.limits_key)
    remaining = await quota_use("smart", str(principal.user_id), limits.smart_search_per_day)
    parsed = parse_query(q)
    if len(parsed.text) < 2:
        raise HTTPException(422, "Query too short")
    if looks_like_injection(parsed.text):
        await audit(session, request, "smart_search_flagged", user_id=principal.user_id)   # still just a search string; flagged for review

    try:
        vec = await embeddings.embed_query(session, principal.user_id, parsed.text, "/search/smart")
    except Exception as exc:  # noqa: BLE001 - provider down / timeout; the client falls back to classic search
        raise HTTPException(503, "Semantic search is temporarily unavailable") from exc

    profile, _, _ = await recommend.compute_profile(session, principal.user_id)
    hw = await recommend.load_hardware(session, principal.user_id) if fits_my_pc else None
    seeds = await recommend.find_by_titles(session, parsed.similar_titles)
    items = await recommend.smart_search(session, principal.user_id, vec, parsed, profile, set(), hw, seeds, 20, explain)
    session.add(UserEvent(user_id=principal.user_id, type="search", query=parsed.text[:200]))
    await session.commit()
    it = parsed.intent
    return {
        "query": parsed.text,
        "understood": {
            "genres": sorted(it.genres), "tags": sorted(it.tags), "features": sorted(it.features), "platforms": sorted(it.platforms),
            "max_price_cents": it.max_price_cents, "max_duration_hours": it.max_duration_hours,
            "similar_to": [g.title for g in seeds],
            "provider": get_provider().name,
        },
        "remaining_today": remaining,
        "items": items,
    }
