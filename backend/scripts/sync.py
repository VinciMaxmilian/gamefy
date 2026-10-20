"""Catalog sync jobs (run offline: GitHub Actions / your machine — not in the request path).

    python -m scripts.sync igdb   --pages 3 --page-size 100 --min-ratings 100   # games + store links
    python -m scripts.sync steam  --limit 150 [--stale-days 7]                  # requirements, summary, Steam price
    python -m scripts.sync prices --limit 150                                   # CheapShark cross-store prices
    python -m scripts.sync steam-changed --since-hours 48                       # refresh only apps Steam says changed
    python -m scripts.sync igdb-check                                           # verify IGDB credentials (no DB writes)
    python -m scripts.sync purge-seed                                           # drop the demo catalog

Every job is idempotent and commits per game, so a rate-limit stop loses nothing.
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.db import get_engine  # noqa: E402
from app.ingest import igdb as igdb_mod  # noqa: E402
from app.ingest import store  # noqa: E402
from app.ingest.cheapshark import CheapShark  # noqa: E402
from app.ingest.embed import refresh_embeddings  # noqa: E402
from app.ingest.steam import Steam, to_enrichment  # noqa: E402
from app.models import Game, StoreLink  # noqa: E402


async def cmd_igdb(a) -> None:
    client = igdb_mod.IGDB()
    n = skipped = links = 0
    try:
        async with AsyncSession(get_engine()) as session:
            for page in range(a.pages):
                batch = await client.games(limit=a.page_size, offset=page * a.page_size, min_ratings=a.min_ratings)
                if not batch:
                    break
                for raw in batch:
                    mapped = igdb_mod.to_game(raw)
                    if not mapped:
                        skipped += 1
                        continue
                    gid = await store.upsert_game(session, mapped["game"])
                    links += await store.replace_links(session, gid, "igdb", mapped["links"])
                    n += 1
                await session.commit()
                print(f"page {page + 1}: {n} imported, {skipped} skipped")
            done, tokens, cost = await refresh_embeddings(session)
            print(f"done: {n} games, {links} store links, {done} embeddings (~{tokens} tokens, ${cost / 1e6:.4f})")
    finally:
        await client.aclose()


async def cmd_igdb_check(_a) -> None:
    """Validate IGDB credentials end to end WITHOUT touching the database: token, one query, mapping."""
    from app.config import get_settings
    st = get_settings()
    print(f"IGDB_CLIENT_ID     : {'set (' + st.igdb_client_id[:4] + '…)' if st.igdb_client_id else 'MISSING'}")
    print(f"IGDB_CLIENT_SECRET : {'set' if st.igdb_client_secret else 'MISSING'}")
    try:
        client = igdb_mod.IGDB()
    except RuntimeError as exc:
        print(f"FAILED: {exc}. Export both variables first (see docs/ENVIRONMENT.md → IGDB).")
        raise SystemExit(1)
    try:
        raw = await client.games(limit=3, min_ratings=500)
    except Exception as exc:  # noqa: BLE001
        import httpx
        if isinstance(exc, httpx.HTTPStatusError):
            print(f"FAILED: HTTP {exc.response.status_code} from {exc.request.url.host}: {exc.response.text[:200]}")
            print("  400/403 from id.twitch.tv  -> wrong Client ID/Secret (generate a new secret in the Twitch console)")
            print("  401 from api.igdb.com      -> token rejected; 429 -> rate limited (4 req/s)")
        else:
            print(f"FAILED: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
    finally:
        await client.aclose()
    print(f"OK: token obtained and /games answered with {len(raw)} records. Mapped preview:")
    for r in raw:
        m = igdb_mod.to_game(r)
        if m:
            g = m["game"]
            print(f"  - {g['title']} | genres={g['genres']} | platforms={g['platforms']} | steam_appid={g['steam_appid']} | links={[l['store'] for l in m['links']]}")


async def _steam_targets(session: AsyncSession, limit: int, appids: set[int] | None = None) -> list[Game]:
    q = select(Game).where(Game.steam_appid.is_not(None))
    if appids is not None:
        q = q.where(Game.steam_appid.in_(appids))
    return list((await session.execute(q.order_by(Game.rating_count.desc()).limit(limit))).scalars())


async def _enrich_from_steam(session: AsyncSession, steam: Steam, games: list[Game]) -> None:
    ok = 0
    for g in games:
        try:
            d = await steam.app_details(g.steam_appid)
        except Exception as exc:  # noqa: BLE001 - one bad app must not stop the batch
            print(f"! {g.slug}: {type(exc).__name__}")
            continue
        if not d:
            continue
        e = to_enrichment(g.steam_appid, d)
        if e["req"]:
            g.req = e["req"]
        if e["summary"] and not g.summary:
            g.summary = e["summary"]
        if e["cover_url"] and not g.cover_url:
            g.cover_url = e["cover_url"]
        await store.replace_links(session, g.id, "steam", [{"store": "steam", "source": "steam", "url": e["url"], **(e["price"] or {})}])
        await store.recompute_best_price(session, g.id)
        await session.commit()
        ok += 1
    print(f"steam: enriched {ok}/{len(games)}")


async def cmd_steam(a) -> None:
    steam = Steam()
    try:
        async with AsyncSession(get_engine()) as session:
            await _enrich_from_steam(session, steam, await _steam_targets(session, a.limit))
    finally:
        await steam.aclose()


async def cmd_steam_changed(a) -> None:
    steam = Steam()
    try:
        since = int(time.time() - a.since_hours * 3600)
        changed = {app["appid"] async for app in steam.modified_apps(since)}
        print(f"steam reports {len(changed)} changed apps")
        async with AsyncSession(get_engine()) as session:
            await _enrich_from_steam(session, steam, await _steam_targets(session, a.limit, changed))
    finally:
        await steam.aclose()


async def cmd_prices(a) -> None:
    cs = CheapShark()
    ok = 0
    try:
        async with AsyncSession(get_engine()) as session:
            for g in await _steam_targets(session, a.limit):
                try:
                    gid = await cs.game_id_for_steam_app(g.steam_appid)
                    deals = await cs.deals_for(gid) if gid else []
                except Exception as exc:  # noqa: BLE001
                    print(f"! {g.slug}: {type(exc).__name__}")
                    continue
                await store.replace_links(session, g.id, "cheapshark", deals)
                await store.recompute_best_price(session, g.id)
                await session.commit()
                ok += bool(deals)
            print(f"cheapshark: prices for {ok} games")
    finally:
        await cs.aclose()


async def cmd_purge_seed(_a) -> None:
    async with AsyncSession(get_engine()) as session:
        r = await session.execute(delete(Game).where(Game.source == "seed"))
        await session.commit()
        print(f"removed {r.rowcount} demo games")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("igdb"); s.add_argument("--pages", type=int, default=3); s.add_argument("--page-size", type=int, default=100); s.add_argument("--min-ratings", type=int, default=100); s.set_defaults(fn=cmd_igdb)
    s = sub.add_parser("steam"); s.add_argument("--limit", type=int, default=150); s.set_defaults(fn=cmd_steam)
    s = sub.add_parser("steam-changed"); s.add_argument("--since-hours", type=int, default=48); s.add_argument("--limit", type=int, default=300); s.set_defaults(fn=cmd_steam_changed)
    s = sub.add_parser("prices"); s.add_argument("--limit", type=int, default=150); s.set_defaults(fn=cmd_prices)
    sub.add_parser("purge-seed").set_defaults(fn=cmd_purge_seed)
    sub.add_parser("igdb-check").set_defaults(fn=cmd_igdb_check)
    a = p.parse_args()
    asyncio.run(a.fn(a))


if __name__ == "__main__":
    main()
