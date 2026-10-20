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

from scripts._tls import use_system_trust_store  # noqa: E402

use_system_trust_store()

from sqlalchemy.dialects.postgresql import insert  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.ai.provider import get_provider  # noqa: E402
from app.ingest.embed import refresh_embeddings  # noqa: E402
from app.db import get_engine  # noqa: E402
from app.models import Game  # noqa: E402
from scripts.seed_data import GAMES  # noqa: E402


async def main() -> None:
    engine = get_engine()
    provider = get_provider()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        for g in GAMES:
            row = {**g, "release_date": dt.date.fromisoformat(g["release_date"]), "source": "seed"}
            stmt = insert(Game).values(**row)
            update = {k: v for k, v in row.items() if k != "slug"}
            await session.execute(stmt.on_conflict_do_update(index_elements=["slug"], set_=update))
        await session.commit()

        n, tokens, cost = await refresh_embeddings(session)
        print(f"{len(GAMES)} games upserted; {n} embeddings (re)computed with provider={provider.name}, ~{tokens} tokens, est. cost ${cost / 1e6:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
