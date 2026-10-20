from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Game
from ..reco.hardware import check_compat
from ..schemas import Compatibility, GameCard, GameDetail, Page, Platform, Slug, Token
from ..security.auth import Principal, optional_user
from ..services import catalog, recommend

router = APIRouter(prefix="/games", tags=["games"])


@router.get("", response_model=Page)
async def list_games(
    q: Annotated[str | None, Query(max_length=200)] = None,
    genres: Annotated[list[Token] | None, Query(max_length=10)] = None,
    tags: Annotated[list[Token] | None, Query(max_length=10)] = None,
    features: Annotated[list[Token] | None, Query(max_length=10)] = None,
    platforms: Annotated[list[Platform] | None, Query(max_length=6)] = None,
    max_price: Annotated[int | None, Query(ge=0, le=100_000, description="cents")] = None,
    min_rating: Annotated[int | None, Query(ge=0, le=100)] = None,
    max_hours: Annotated[float | None, Query(gt=0, le=2000)] = None,
    sort: Annotated[str, Query(pattern="^(relevance|rating|price_asc|price_desc|newest|shortest)$")] = "relevance",
    limit: Annotated[int, Query(ge=1, le=48)] = 24,
    offset: Annotated[int, Query(ge=0, le=2000)] = 0,
    session: AsyncSession = Depends(get_session),
) -> Page:
    f = catalog.Filters(q=q, genres=genres or [], tags=tags or [], features=features or [], platforms=platforms or [],
                        max_price_cents=max_price, min_rating=min_rating, max_hours=max_hours)
    rows, total = await catalog.search_games(session, f, sort, limit, offset)
    return Page(items=[catalog.to_card(g) for g in rows], total=total, limit=limit, offset=offset)


@router.get("/facets")
async def get_facets(session: AsyncSession = Depends(get_session)) -> dict:
    return await catalog.facets(session)


@router.get("/{slug}")
async def game_detail(slug: Slug, session: AsyncSession = Depends(get_session),
                      principal: Principal | None = Depends(optional_user)) -> dict:
    g = (await session.execute(select(Game).where(Game.slug == slug))).scalar_one_or_none()
    if not g:
        raise HTTPException(404, "Game not found")
    detail = catalog.to_detail(g).model_dump(mode="json")
    detail["stores"] = await catalog.store_offers(session, g.id)
    detail["compatibility"] = None
    if principal and (hw := await recommend.load_hardware(session, principal.user_id)):
        c = check_compat(hw, g.req)
        detail["compatibility"] = Compatibility(verdict=c.verdict, reasons=c.reasons).model_dump()
    return detail


@router.get("/{slug}/similar", response_model=list[GameCard])
async def similar(slug: Slug, session: AsyncSession = Depends(get_session)) -> list[GameCard]:
    g = (await session.execute(select(Game).where(Game.slug == slug))).scalar_one_or_none()
    if not g:
        raise HTTPException(404, "Game not found")
    return [catalog.to_card(x) for x in await recommend.similar_to(session, g)]
