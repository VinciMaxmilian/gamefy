import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import (
    Game, GameEmbedding, HardwareProfile, Library, PreferenceProfile, Rating, UserEvent, Wishlist,
)
from ..reco.engine import Candidate, Intent, Scored, rank
from ..reco.hardware import Compat, Hardware, check_compat
from ..reco.profile import Interaction, build_profile, game_features
from ..schemas import Compatibility, Recommendation
from .catalog import Filters, apply_filters, to_card


# ----------------------------------------------------------------- user state
async def load_hardware(session: AsyncSession, user_id: uuid.UUID) -> Hardware | None:
    hw = await session.get(HardwareProfile, user_id)
    if not hw:
        return None
    return Hardware(hw.gpu_tier, hw.cpu_tier, hw.ram_gb, hw.vram_gb, hw.storage_gb)


async def compute_profile(session: AsyncSession, user_id: uuid.UUID) -> tuple[dict[str, float], set[uuid.UUID], set[uuid.UUID]]:
    """Level 1. Returns (preference profile, excluded game ids, positively-signalled game ids)
    and persists the profile. Everything is scoped by `user_id` taken from the session."""
    s = get_settings()
    inter: list[Interaction] = []
    exclude: set[uuid.UUID] = set()
    positive: set[uuid.UUID] = set()

    def feats(g: Game) -> list[str]:
        return game_features(g.genres, g.tags, g.features)

    rows = (await session.execute(select(Wishlist, Game).join(Game, Game.id == Wishlist.game_id).where(Wishlist.user_id == user_id))).all()
    for w, g in rows:
        inter.append(Interaction("wishlist", feats(g), w.created_at)); exclude.add(g.id); positive.add(g.id)

    rows = (await session.execute(select(Library, Game).join(Game, Game.id == Library.game_id).where(Library.user_id == user_id))).all()
    for lib, g in rows:
        inter.append(Interaction("library", feats(g), lib.created_at)); exclude.add(g.id); positive.add(g.id)
        if lib.playtime_minutes:
            inter.append(Interaction("playtime", feats(g), lib.created_at, lib.playtime_minutes / 60))
        if lib.status == "dropped":
            inter.append(Interaction("ignore", feats(g), lib.created_at))

    rows = (await session.execute(select(Rating, Game).join(Game, Game.id == Rating.game_id).where(Rating.user_id == user_id))).all()
    for r, g in rows:
        inter.append(Interaction("rating", feats(g), r.updated_at, r.score)); exclude.add(g.id)
        if r.score >= 7:
            positive.add(g.id)

    ev = (await session.execute(
        select(UserEvent, Game).outerjoin(Game, Game.id == UserEvent.game_id)
        .where(UserEvent.user_id == user_id).order_by(UserEvent.created_at.desc()).limit(500))).all()
    for e, g in ev:
        if e.type == "search" and e.query:
            continue                                   # query text is mapped via the intent parser, not stored features
        if g is None:
            continue
        inter.append(Interaction(e.type, feats(g), e.created_at))
        if e.type == "ignore":
            exclude.add(g.id); positive.discard(g.id)

    pp = await session.get(PreferenceProfile, user_id)
    explicit = (pp.explicit if pp else {}) or {}
    profile = build_profile(inter, explicit, s.profile_half_life_days)
    stmt = insert(PreferenceProfile).values(user_id=user_id, weights=profile, explicit=explicit, updated_at=datetime.now(timezone.utc))
    await session.execute(stmt.on_conflict_do_update(index_elements=["user_id"], set_={"weights": profile, "updated_at": stmt.excluded.updated_at}))
    await session.commit()
    return profile, exclude, positive


async def taste_vector(session: AsyncSession, positive: set[uuid.UUID]) -> list[float] | None:
    if not positive:
        return None
    rows = (await session.execute(select(GameEmbedding.embedding).where(GameEmbedding.game_id.in_(positive)))).scalars().all()
    if not rows:
        return None
    n = len(rows[0])
    acc = [0.0] * n
    for v in rows:
        for i, x in enumerate(v):
            acc[i] += float(x)
    return [x / len(rows) for x in acc]


# --------------------------------------------------------------- candidates
async def vector_candidates(session: AsyncSession, vec: list[float], f: Filters, exclude: set[uuid.UUID],
                            limit: int = 150) -> list[tuple[Game, float]]:
    dist = GameEmbedding.embedding.cosine_distance(vec)
    stmt = select(Game, dist.label("d")).join(GameEmbedding, GameEmbedding.game_id == Game.id)
    stmt = apply_filters(stmt, f)
    if exclude:
        stmt = stmt.where(Game.id.notin_(exclude))
    rows = (await session.execute(stmt.order_by(dist).limit(limit))).all()
    return [(g, max(0.0, 1.0 - float(d))) for g, d in rows]


async def top_rated(session: AsyncSession, f: Filters, exclude: set[uuid.UUID], limit: int = 60) -> list[Game]:
    stmt = apply_filters(select(Game), f)
    if exclude:
        stmt = stmt.where(Game.id.notin_(exclude))
    return list((await session.execute(stmt.order_by(Game.rating.desc().nulls_last()).limit(limit))).scalars())


def _normalise_similarity(pairs: list[tuple[Game, float]]) -> dict[uuid.UUID, float]:
    """Cosine values from text embeddings cluster in a narrow band; rescale within the
    candidate set so the semantic component actually discriminates."""
    if not pairs:
        return {}
    vals = [s for _, s in pairs]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    return {g.id: (s - lo) / span for g, s in pairs}


def _to_candidate(g: Game, sim: float, hw: Hardware | None) -> Candidate:
    compat: Compat | None = check_compat(hw, g.req) if hw else None
    return Candidate(g.slug, g.genres, g.tags, g.features, g.platforms, g.price_cents, g.rating,
                     g.avg_duration_hours, sim, compat)


def _present(scored: list[Scored], by_slug: dict[str, Game], explain: bool) -> list[Recommendation]:
    out = []
    for s in scored:
        c = s.candidate
        out.append(Recommendation(
            game=to_card(by_slug[c.slug]), score=s.score, reasons=s.reasons,
            breakdown=s.breakdown if explain else None,
            compatibility=Compatibility(verdict=c.compat.verdict, reasons=c.compat.reasons) if c.compat else None))
    return out


# ------------------------------------------------------------------ public
async def personalized(session: AsyncSession, user_id: uuid.UUID, limit: int = 20, explain: bool = False) -> dict:
    s = get_settings()
    profile, exclude, positive = await compute_profile(session, user_id)
    hw = await load_hardware(session, user_id)
    f = Filters()
    sims: dict[uuid.UUID, float] = {}
    games: dict[uuid.UUID, Game] = {}

    if (tv := await taste_vector(session, positive)) is not None:
        pairs = await vector_candidates(session, tv, f, exclude)
        sims = _normalise_similarity(pairs)
        games.update({g.id: g for g, _ in pairs})
    for g in await top_rated(session, f, exclude):          # cold start + diversity
        games.setdefault(g.id, g)

    cands = [_to_candidate(g, sims.get(g.id, 0.0), hw) for g in games.values()]
    scored = rank(cands, profile, Intent(), s.reco_weights, limit)
    by_slug = {g.slug: g for g in games.values()}
    return {"personalized": bool(profile), "items": _present(scored, by_slug, explain)}


async def similar_to(session: AsyncSession, game: Game, limit: int = 8) -> list[Game]:
    emb = await session.get(GameEmbedding, game.id)
    if not emb:
        return []
    pairs = await vector_candidates(session, list(emb.embedding), Filters(), {game.id}, limit)
    return [g for g, _ in pairs]


async def find_by_titles(session: AsyncSession, titles: list[str]) -> list[Game]:
    out: dict[uuid.UUID, Game] = {}
    for t in titles:
        like = t.lower().strip()
        rows = (await session.execute(
            select(Game).where(func.lower(Game.title).like(f"%{like.replace('%', '').replace('_', '')}%")).limit(2))).scalars()
        for g in rows:
            out[g.id] = g
    return list(out.values())


async def smart_search(session: AsyncSession, user_id: uuid.UUID, query_vec: list[float], parsed, profile: dict[str, float],
                       exclude: set[uuid.UUID], hw: Hardware | None, seed_games: list[Game], limit: int = 20,
                       explain: bool = False) -> list[Recommendation]:
    s = get_settings()
    vec = list(query_vec)
    if seed_games:                                   # "parecido com X": blend in the seeds' embeddings
        embs = (await session.execute(select(GameEmbedding.embedding).where(GameEmbedding.game_id.in_([g.id for g in seed_games])))).scalars().all()
        if embs:
            for i in range(len(vec)):
                vec[i] = 0.5 * vec[i] + 0.5 * sum(float(e[i]) for e in embs) / len(embs)
    it = parsed.intent
    hard = Filters(platforms=sorted(it.platforms), max_price_cents=it.max_price_cents)   # stated by the user => hard
    pairs = await vector_candidates(session, vec, hard, exclude | {g.id for g in seed_games})
    sims = _normalise_similarity(pairs)
    cands = [_to_candidate(g, sims[g.id], hw) for g, _ in pairs]
    scored = rank(cands, profile, it, s.reco_weights, limit)
    return _present(scored, {g.slug: g for g, _ in pairs}, explain)
