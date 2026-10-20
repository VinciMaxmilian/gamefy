"""CheapShark: cross-store prices. Flow: games?steamAppID= -> gameID -> games?id= (deals per store).
Links use CheapShark's own redirect (https://www.cheapshark.com/redirect?dealID=…), which is how it
attributes referrals. Prices are USD. A descriptive User-Agent is mandatory (set in http.py)."""
import re

from .allowlist import classify_url
from .http import Throttled

# CheapShark storeName -> our store key (anything else is skipped rather than guessed)
STORE_BY_NAME = {
    "steam": "steam", "gog": "gog", "epic games store": "epic", "humblestore": "humble", "humble store": "humble",
    "fanatical": "fanatical", "greenmangaming": "gmg", "green man gaming": "gmg", "itch.io": "itch",
}
_DEAL_ID = re.compile(r"^[A-Za-z0-9%_\-+=.]{10,200}$")


class CheapShark:
    def __init__(self) -> None:
        self.http = Throttled("https://www.cheapshark.com/api/1.0", 1.1)   # stay well below documented limits
        self._stores: dict[str, str] | None = None

    async def aclose(self) -> None:
        await self.http.aclose()

    async def store_map(self) -> dict[str, str]:
        """storeID -> our store key, for active stores we know."""
        if self._stores is None:
            out = {}
            for s in await self.http.get_json("/stores"):
                key = STORE_BY_NAME.get(str(s.get("storeName", "")).lower())
                if key and str(s.get("isActive", "1")) == "1":
                    out[str(s["storeID"])] = key
            self._stores = out
        return self._stores

    async def game_id_for_steam_app(self, appid: int) -> str | None:
        rows = await self.http.get_json("/games", params={"steamAppID": appid})
        return str(rows[0]["gameID"]) if isinstance(rows, list) and rows else None

    async def deals_for(self, game_id: str) -> list[dict]:
        info = await self.http.get_json("/games", params={"id": game_id})
        return parse_deals(info, await self.store_map())


def _cents(v) -> int | None:
    try:
        return max(0, round(float(v) * 100))
    except (TypeError, ValueError):
        return None


def parse_deals(info: dict, stores: dict[str, str]) -> list[dict]:
    best: dict[str, dict] = {}
    for d in (info or {}).get("deals", []):
        store = stores.get(str(d.get("storeID")))
        deal_id = str(d.get("dealID", ""))
        price = _cents(d.get("price"))
        if not store or price is None or not _DEAL_ID.match(deal_id):
            continue
        link = classify_url(f"https://www.cheapshark.com/redirect?dealID={deal_id}")
        if not link:
            continue
        if store not in best or price < best[store]["price_cents"]:
            best[store] = {"store": store, "url": link[1], "source": "cheapshark", "price_cents": price,
                           "normal_price_cents": _cents(d.get("retailPrice")), "currency": "USD", "external_id": deal_id[:100]}
    return list(best.values())
