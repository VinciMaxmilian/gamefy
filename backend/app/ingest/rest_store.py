"""Write the catalog through Supabase's REST API (PostgREST, HTTPS/443) instead of a direct Postgres connection.

Use when the machine running the import cannot reach the database port (corporate networks, sandboxes).
Auth: the project's *secret* key (server-side only; it bypasses RLS, so it must never reach a browser)."""
import json
from collections import defaultdict

from ..config import get_settings
from ..tlsutil import client_verify  # noqa: F401  (kept so the verify policy is shared by every outbound client)
from .http import Throttled
from .store import clean_links


class RestError(RuntimeError):
    pass


class Rest:
    def __init__(self) -> None:
        s = get_settings()
        if not (s.supabase_url and s.supabase_secret_key):
            raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
        self.http = Throttled(f"{s.supabase_url}/rest/v1", 0.05, timeout=60,
                              headers={"apikey": s.supabase_secret_key, "Content-Type": "application/json"})

    async def aclose(self) -> None:
        await self.http.aclose()

    @staticmethod
    def _ok(r) -> None:
        if r.status_code >= 400:
            raise RestError(f"HTTP {r.status_code}: {r.text[:300]}")

    async def select(self, table: str, params: dict) -> list[dict]:
        r = await self.http.request("GET", f"/{table}", params=params)
        self._ok(r)
        return r.json()

    async def select_all(self, table: str, params: dict, page: int = 1000) -> list[dict]:
        out: list[dict] = []
        while True:
            chunk = await self.select(table, {**params, "limit": str(page), "offset": str(len(out))})
            out += chunk
            if len(chunk) < page:
                return out

    async def upsert(self, table: str, rows: list[dict], on_conflict: str, returning: bool = True) -> list[dict]:
        """Bulk upsert. PostgREST needs identical keys per request, so rows are grouped by key set."""
        out: list[dict] = []
        groups: dict[frozenset, list[dict]] = defaultdict(list)
        for row in rows:
            groups[frozenset(row)].append(row)
        for group in groups.values():
            r = await self.http.request(
                "POST", f"/{table}", params={"on_conflict": on_conflict}, content=json.dumps(group, default=str),
                headers={"Prefer": "resolution=merge-duplicates," + ("return=representation" if returning else "return=minimal")})
            self._ok(r)
            if returning:
                out += r.json()
        return out

    async def patch(self, table: str, params: dict, values: dict) -> None:
        r = await self.http.request("PATCH", f"/{table}", params=params, content=json.dumps(values, default=str), headers={"Prefer": "return=minimal"})
        self._ok(r)

    async def delete(self, table: str, params: dict) -> None:
        r = await self.http.request("DELETE", f"/{table}", params=params, headers={"Prefer": "return=minimal"})
        self._ok(r)


def game_row(g: dict) -> dict:
    """None values are dropped so a re-import never blanks fields filled by another source (e.g. Steam covers)."""
    row = {k: v for k, v in g.items() if v is not None}
    if "release_date" in row:
        row["release_date"] = row["release_date"].isoformat()
    return row


async def upsert_games(rest: Rest, mapped: list[dict]) -> dict[int, str]:
    """Returns igdb_id -> game uuid. Falls back to one-by-one if a batch hits a constraint (e.g. duplicate slug)."""
    rows = [game_row(m["game"]) for m in mapped]
    try:
        res = await rest.upsert("games", rows, on_conflict="igdb_id")
    except RestError:
        res = []
        for row in rows:
            try:
                res += await rest.upsert("games", [row], on_conflict="igdb_id")
            except RestError as exc:
                print(f"! {row['slug']}: {str(exc)[:120]}")
    return {int(r["igdb_id"]): r["id"] for r in res if r.get("igdb_id") is not None}


async def replace_links(rest: Rest, game_id: str, source: str, links: list[dict]) -> int:
    clean = clean_links(game_id, source, links)
    await rest.delete("store_links", {"game_id": f"eq.{game_id}", "source": f"eq.{source}"})
    if clean:
        keys = ("game_id", "store", "source", "url", "price_cents", "normal_price_cents", "currency", "external_id")
        await rest.upsert("store_links", [{k: l[k] for k in keys if l.get(k) is not None} for l in clean],
                          on_conflict="game_id,store,source", returning=False)
    return len(clean)


async def recompute_best_price(rest: Rest, game_id: str) -> None:
    rows = await rest.select("store_links", {"select": "price_cents", "game_id": f"eq.{game_id}", "price_cents": "not.is.null", "currency": "eq.USD"})
    if rows:
        await rest.patch("games", {"id": f"eq.{game_id}"}, {"price_cents": min(r["price_cents"] for r in rows)})


async def embed_games(rest: Rest, provider, batch: int = 50) -> tuple[int, int, int]:
    """(Re)embed games whose semantic document or provider changed, writing through the REST API.
    pgvector accepts the textual form '[0.1,0.2,...]'. Returns (games embedded, tokens, cost in micro-USD)."""
    from ..ai.semantic_doc import build_semantic_doc, doc_hash
    games = await rest.select_all("games", {"select": "id,slug,title,genres,tags,features,platforms,avg_duration_hours,difficulty,summary,description", "order": "id"})
    have = {e["game_id"]: e["doc_hash"] for e in await rest.select_all("game_embeddings", {"select": "game_id,doc_hash", "order": "game_id"})}
    todo = []
    for g in games:
        doc, flagged = build_semantic_doc(g)
        if flagged:
            print(f"! {g['slug']}: suspicious free text dropped from semantic doc")
        h = doc_hash(doc, provider.name)
        if have.get(g["id"]) != h:
            todo.append((g["id"], h, doc))
    tokens = cost = done = 0
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        res = await provider.embed([d for _, _, d in chunk], task="document")
        tokens += res.tokens_in; cost += res.cost_micro_usd
        await rest.upsert("game_embeddings", [
            {"game_id": gid, "embedding": "[" + ",".join(f"{x:.6f}" for x in vec) + "]", "doc_hash": h, "model": res.model}
            for (gid, h, _), vec in zip(chunk, res.vectors)], on_conflict="game_id", returning=False)
        done += len(chunk)
        print(f"embedded {done}/{len(todo)}")
    return done, tokens, cost
