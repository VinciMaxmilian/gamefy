import re
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..ingest.allowlist import STORE_NAMES, classify_url
from ..models import Game, StoreLink
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


_DIRECT = {"steam": 0, "igdb": 1, "cheapshark": 2}


async def store_offers(session: AsyncSession, game_id) -> list[dict]:
    """One offer per store: cheapest known price; link prefers the store's own URL over a redirect.
    URLs are re-validated against the allow-list on the way out (defence in depth)."""
    rows = (await session.execute(select(StoreLink).where(StoreLink.game_id == game_id))).scalars().all()
    by_store: dict[str, list[StoreLink]] = {}
    for r in rows:
        if (c := classify_url(r.url)):
            by_store.setdefault(r.store, []).append(r)
    offers = []
    for store, items in by_store.items():
        priced = [i for i in items if i.price_cents is not None]
        best = min(priced, key=lambda i: i.price_cents) if priced else None
        link = min(items, key=lambda i: _DIRECT.get(i.source, 9))
        normal = best.normal_price_cents if best else None
        offers.append({
            "store": store, "name": STORE_NAMES.get(store, store.title()), "url": link.url,
            "price_cents": best.price_cents if best else None, "normal_price_cents": normal,
            "discount_percent": round(100 * (1 - best.price_cents / normal)) if best and normal and normal > best.price_cents else 0,
            "currency": best.currency if best else "USD",
            "updated_at": max(i.updated_at for i in items).isoformat(),
        })
    offers.sort(key=lambda o: (o["price_cents"] is None, o["price_cents"] or 0, o["name"]))
    return offers
