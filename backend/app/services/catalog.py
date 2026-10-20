import re
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Game
from ..schemas import GameCard, GameDetail

SORTS = {"relevance", "rating", "price_asc", "price_desc", "newest", "shortest"}


@dataclass
class Filters:
    q: str | None = None
    genres: list[str] = field(default_factory=list)       # ALL must match
    tags: list[str] = field(default_factory=list)         # ALL must match
    features: list[str] = field(default_factory=list)     # ALL must match
    platforms: list[str] = field(default_factory=list)    # ANY may match
    max_price_cents: int | None = None
    min_rating: int | None = None
    max_hours: float | None = None


def to_card(g: Game) -> GameCard:
    return GameCard(
        slug=g.slug, title=g.title, summary=g.summary, cover_url=g.cover_url, price_cents=g.price_cents,
        currency=g.currency, genres=g.genres, tags=g.tags[:6], platforms=g.platforms, rating=g.rating,
        avg_duration_hours=g.avg_duration_hours, release_date=g.release_date,
    )


def to_detail(g: Game) -> GameDetail:
    return GameDetail(**to_card(g).model_dump(), description=g.description, developer=g.developer,
                      features=g.features, difficulty=g.difficulty, rating_count=g.rating_count, req=g.req)


def prefix_tsquery(q: str) -> str | None:
    """Build a prefix tsquery from user text. Only word characters survive, so the
    string can never contain tsquery operators; it is also bound as a parameter."""
    words = re.findall(r"\w{1,40}", q.lower())[:8]
    return " & ".join(f"{w}:*" for w in words) or None


def apply_filters(stmt, f: Filters):
    if f.genres:
        stmt = stmt.where(Game.genres.contains(f.genres))
    if f.tags:
        stmt = stmt.where(Game.tags.contains(f.tags))
    if f.features:
        stmt = stmt.where(Game.features.contains(f.features))
    if f.platforms:
        stmt = stmt.where(Game.platforms.overlap(f.platforms))
    if f.max_price_cents is not None:
        stmt = stmt.where(Game.price_cents <= f.max_price_cents)
    if f.min_rating is not None:
        stmt = stmt.where(Game.rating >= f.min_rating)
    if f.max_hours is not None:
        stmt = stmt.where(Game.avg_duration_hours <= f.max_hours)
    return stmt


async def search_games(session: AsyncSession, f: Filters, sort: str, limit: int, offset: int) -> tuple[list[Game], int]:
    """Level 0: pure SQL (FTS + filters). No AI."""
    stmt = select(Game)
    rank = None
    if f.q and (pq := prefix_tsquery(f.q)):
        tsq = func.to_tsquery("simple", pq)
        stmt = stmt.where(Game.search.op("@@")(tsq))
        rank = func.ts_rank_cd(Game.search, tsq)
    stmt = apply_filters(stmt, f)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    order = {
        "rating": [Game.rating.desc().nulls_last()],
        "price_asc": [Game.price_cents.asc().nulls_last()],
        "price_desc": [Game.price_cents.desc().nulls_last()],
        "newest": [Game.release_date.desc().nulls_last()],
        "shortest": [Game.avg_duration_hours.asc().nulls_last()],
    }.get(sort)
    if order is None:                                   # relevance
        order = ([rank.desc()] if rank is not None else []) + [Game.rating.desc().nulls_last()]
    rows = (await session.execute(stmt.order_by(*order, Game.title).limit(limit).offset(offset))).scalars().all()
    return list(rows), total


async def facets(session: AsyncSession) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for name, col in (("genres", Game.genres), ("tags", Game.tags), ("features", Game.features), ("platforms", Game.platforms)):
        el = func.unnest(col).label("v")
        sub = select(el).subquery()
        rows = (await session.execute(select(sub.c.v, func.count()).group_by(sub.c.v).order_by(func.count().desc()).limit(60))).all()
        out[name] = [{"value": v, "count": c} for v, c in rows]
    return out
