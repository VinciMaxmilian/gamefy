"""Catalog sync over HTTPS (Supabase REST API) — same sources and validation as scripts/sync.py, but it needs only
SUPABASE_URL + SUPABASE_SECRET_KEY (no direct database access).

    python -m scripts.sync_rest igdb  --pages 3 --page-size 100 --min-ratings 100
    python -m scripts.sync_rest steam --limit 150
    python -m scripts.sync_rest status

Embeddings are not built here (they need the vector type and a Gemini key): run `scripts.sync embed` afterwards.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts._tls import use_system_trust_store  # noqa: E402

use_system_trust_store()

from app.ingest import igdb as igdb_mod  # noqa: E402
from app.ingest import rest_store as rs  # noqa: E402
from app.ingest.steam import Steam, to_enrichment  # noqa: E402


async def cmd_igdb(a) -> None:
    client, rest = igdb_mod.IGDB(), rs.Rest()
    n = skipped = links = 0
    try:
        for page in range(a.pages):
            batch = await client.games(limit=a.page_size, offset=page * a.page_size, min_ratings=a.min_ratings)
            if not batch:
                break
            mapped = [m for m in (igdb_mod.to_game(r) for r in batch) if m]
            skipped += len(batch) - len(mapped)
            ids = await rs.upsert_games(rest, mapped)
            for m in mapped:
                gid = ids.get(m["game"]["igdb_id"])
                if not gid:
                    skipped += 1
                    continue
                links += await rs.replace_links(rest, gid, "igdb", m["links"])
                n += 1
            print(f"page {page + 1}: {n} imported, {skipped} skipped, {links} store links so far")
        print(f"done: {n} games, {links} store links. Next: scripts.sync_rest steam / scripts.sync embed")
    finally:
        await client.aclose(); await rest.aclose()


async def cmd_steam(a) -> None:
    steam, rest = Steam(), rs.Rest()
    ok = 0
    try:
        games = await rest.select("games", {"select": "id,slug,summary,cover_url,steam_appid", "steam_appid": "not.is.null",
                                            "order": "rating_count.desc", "limit": str(a.limit)})
        for g in games:
            try:
                d = await steam.app_details(g["steam_appid"])
            except Exception as exc:  # noqa: BLE001 - one bad app must not stop the batch
                print(f"! {g['slug']}: {type(exc).__name__}")
                continue
            if not d:
                continue
            e = to_enrichment(g["steam_appid"], d)
            patch = {}
            if e["req"]:
                patch["req"] = e["req"]
            if e["summary"] and not g.get("summary"):
                patch["summary"] = e["summary"]
            if e["cover_url"] and not g.get("cover_url"):
                patch["cover_url"] = e["cover_url"]
            if patch:
                await rest.patch("games", {"id": f"eq.{g['id']}"}, patch)
            await rs.replace_links(rest, g["id"], "steam", [{"store": "steam", "source": "steam", "url": e["url"], **(e["price"] or {})}])
            await rs.recompute_best_price(rest, g["id"])
            ok += 1
            if ok % 10 == 0:
                print(f"steam: {ok}/{len(games)}")
        print(f"steam: enriched {ok}/{len(games)}")
    finally:
        await steam.aclose(); await rest.aclose()


async def cmd_status(_a) -> None:
    rest = rs.Rest()
    try:
        for t in ("games", "store_links", "game_embeddings"):
            r = await rest.http.request("GET", f"/{t}", params={"select": "*", "limit": "1"}, headers={"Prefer": "count=exact"})
            print(f"{t:16} {r.headers.get('content-range', '?').split('/')[-1]}")
    finally:
        await rest.aclose()


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("igdb"); s.add_argument("--pages", type=int, default=3); s.add_argument("--page-size", type=int, default=100); s.add_argument("--min-ratings", type=int, default=100); s.set_defaults(fn=cmd_igdb)
    s = sub.add_parser("steam"); s.add_argument("--limit", type=int, default=150); s.set_defaults(fn=cmd_steam)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    a = p.parse_args()
    asyncio.run(a.fn(a))


if __name__ == "__main__":
    main()
