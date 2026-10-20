"""Load the sample catalog and (re)build embeddings.

    DATABASE_URL=... GEMINI_API_KEY=... python -m scripts.seed

Idempotent: games are upserted by slug; embeddings are only recomputed when the semantic
document (or embedding model) changed, so re-running costs nothing.
"""
import asyncio
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.ai.provider import get_provider  # noqa: E402
from app.ai.semantic_doc import build_semantic_doc, doc_hash  # noqa: E402
from app.db import get_engine  # noqa: E402
from app.models import Game, GameEmbedding  # noqa: E402
from app.reco.hardware import gpu_tier  # noqa: E402,F401
from scripts.seed_data import GAMES  # noqa: E402


async def main() -> None:
    engine = get_engine()
    provider = get_provider()
    async with AsyncSession(engine) as session:
        for g in GAMES:
            row = {**g, "release_date": dt.date.fromisoformat(g["release_date"]), "source": "seed"}
            stmt = insert(Game).values(**row)
            update = {k: v for k, v in row.items() if k != "slug"}
            await session.execute(stmt.on_conflict_do_update(index_elements=["slug"], set_=update))
        await session.commit()

        games = (await session.execute(select(Game))).scalars().all()
        existing = {e.game_id: e for e in (await session.execute(select(GameEmbedding))).scalars()}
        todo, docs = [], []
        for g in games:
            doc, flagged = build_semantic_doc({
                "title": g.title, "genres": g.genres, "tags": g.tags, "features": g.features, "platforms": g.platforms,
                "avg_duration_hours": g.avg_duration_hours, "difficulty": g.difficulty, "summary": g.summary,
                "description": g.description,
            })
            if flagged:
                print(f"! {g.slug}: suspicious free text dropped from semantic doc")
            model_id = getattr(provider, "name", "unknown")
            h = doc_hash(doc, model_id)
            if (e := existing.get(g.id)) and e.doc_hash == h:
                continue
            todo.append((g, h)); docs.append(doc)

        print(f"{len(games)} games, {len(todo)} embeddings to (re)compute with provider={provider.name}")
        if todo:
            res = await provider.embed(docs, task="document")
            for (g, h), vec in zip(todo, res.vectors):
                stmt = insert(GameEmbedding).values(game_id=g.id, embedding=vec, doc_hash=h, model=res.model)
                await session.execute(stmt.on_conflict_do_update(
                    index_elements=["game_id"], set_={"embedding": vec, "doc_hash": h, "model": res.model}))
            await session.commit()
            print(f"embedded {len(todo)} docs, ~{res.tokens_in} tokens, est. cost ${res.cost_micro_usd / 1e6:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
