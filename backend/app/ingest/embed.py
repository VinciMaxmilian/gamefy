from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..ai.provider import get_provider
from ..ai.semantic_doc import build_semantic_doc, doc_hash
from ..models import Game, GameEmbedding


async def refresh_embeddings(session: AsyncSession, batch: int = 50) -> tuple[int, int, int]:
    """(Re)embed only games whose semantic document or provider changed. Idempotent and cheap to re-run."""
    provider = get_provider()
    games = (await session.execute(select(Game))).scalars().all()
    existing = {e.game_id: e for e in (await session.execute(select(GameEmbedding))).scalars()}
    todo: list[tuple[Game, str, str]] = []
    for g in games:
        doc, flagged = build_semantic_doc({
            "title": g.title, "genres": g.genres, "tags": g.tags, "features": g.features, "platforms": g.platforms,
            "avg_duration_hours": g.avg_duration_hours, "difficulty": g.difficulty, "summary": g.summary, "description": g.description})
        if flagged:
            print(f"! {g.slug}: suspicious free text dropped from semantic doc")
        h = doc_hash(doc, provider.name)
        if (e := existing.get(g.id)) and e.doc_hash == h:
            continue
        todo.append((g, h, doc))
    tokens = cost = 0
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        res = await provider.embed([d for _, _, d in chunk], task="document")
        tokens += res.tokens_in; cost += res.cost_micro_usd
        for (g, h, _), vec in zip(chunk, res.vectors):
            stmt = insert(GameEmbedding).values(game_id=g.id, embedding=vec, doc_hash=h, model=res.model)
            await session.execute(stmt.on_conflict_do_update(index_elements=["game_id"], set_={"embedding": vec, "doc_hash": h, "model": res.model}))
        await session.commit()
    return len(todo), tokens, cost
