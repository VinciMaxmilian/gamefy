import uuid

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Game, StoreLink
from .allowlist import classify_url


async def upsert_game(session: AsyncSession, g: dict) -> uuid.UUID:
    """Upsert by igdb_id, falling back to slug. Existing curated fields that the source leaves empty are kept."""
    existing = None
    if g.get("igdb_id"):
        existing = (await session.execute(select(Game).where(Game.igdb_id == g["igdb_id"]))).scalar_one_or_none()
    if existing is None:
        existing = (await session.execute(select(Game).where(Game.slug == g["slug"]))).scalar_one_or_none()
    if existing is None:
        row = Game(**{k: v for k, v in g.items() if v is not None})
        session.add(row)
        await session.flush()
        return row.id
    for k, v in g.items():
        if v in (None, "", [], {}) and getattr(existing, k, None):
            continue                                    # do not blank out data we already have
        if k == "slug" and existing.slug != v:
            continue                                    # never rename public URLs
        setattr(existing, k, v)
    existing.source = g.get("source", existing.source)
    return existing.id


async def replace_links(session: AsyncSession, game_id: uuid.UUID, source: str, links: list[dict]) -> int:
    """Replace this source's links for a game. Every URL is re-validated against the allow-list."""
    clean = []
    for l in links:
        c = classify_url(l["url"])
        if not c or c[0] != l["store"] and l["source"] != "cheapshark":
            continue
        clean.append({**l, "url": c[1], "game_id": game_id, "source": source})
    await session.execute(delete(StoreLink).where(StoreLink.game_id == game_id, StoreLink.source == source))
    if clean:
        await session.execute(insert(StoreLink).values([
            {k: l.get(k) for k in ("game_id", "store", "source", "url", "price_cents", "normal_price_cents", "currency", "external_id")}
            | {"currency": l.get("currency") or "USD"} for l in clean]))
    return len(clean)


async def recompute_best_price(session: AsyncSession, game_id: uuid.UUID | None = None) -> None:
    """games.price_cents := cheapest current USD price across stores (kept for filters/sorting)."""
    await session.execute(text("""
        update games g set price_cents = s.best
        from (select game_id, min(price_cents) as best from store_links
              where price_cents is not null and currency = 'USD' group by game_id) s
        where g.id = s.game_id and (cast(:gid as uuid) is null or g.id = cast(:gid as uuid))
    """), {"gid": game_id})


async def count_games(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Game))).scalar_one()
