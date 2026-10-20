"""Steam: `appdetails` (storefront, unofficial but widely used) for price/requirements, and the
official Web API IStoreService/GetAppList (needs a key) to discover apps changed since a timestamp."""
from collections.abc import AsyncIterator

from ..config import get_settings
from ..security.sanitize import clean_text
from .allowlist import safe_image_url
from .http import Throttled
from .steam_req import parse_requirements


class Steam:
    def __init__(self) -> None:
        # appdetails is aggressively rate limited (~200 req / 5 min): one request per 1.6 s.
        self.store = Throttled("https://store.steampowered.com", 1.6)
        self.api = Throttled("https://api.steampowered.com", 0.5)

    async def aclose(self) -> None:
        await self.store.aclose(); await self.api.aclose()

    async def app_details(self, appid: int) -> dict | None:
        cc = get_settings().store_country
        data = await self.store.get_json("/api/appdetails", params={"appids": appid, "cc": cc, "l": "en"})
        entry = data.get(str(appid)) or {}
        return entry.get("data") if entry.get("success") else None

    async def modified_apps(self, since_ts: int) -> AsyncIterator[dict]:
        key = get_settings().steam_web_api_key
        if not key:
            raise RuntimeError("STEAM_WEB_API_KEY is not set")
        last = 0
        while True:
            d = await self.api.get_json("/IStoreService/GetAppList/v1/", params={
                "key": key, "if_modified_since": since_ts, "last_appid": last, "max_results": 5000, "include_games": "true"})
            resp = d.get("response", {})
            for app in resp.get("apps", []):
                yield app
            if not resp.get("have_more_results"):
                return
            last = resp.get("last_appid", 0)


def to_enrichment(appid: int, d: dict) -> dict:
    """Extract only what we use from an appdetails payload."""
    po = d.get("price_overview") or {}
    price = {"price_cents": 0, "normal_price_cents": 0, "currency": "USD"} if d.get("is_free") else (
        {"price_cents": int(po["final"]), "normal_price_cents": int(po.get("initial", po["final"])), "currency": str(po.get("currency", "USD"))[:3].upper()}
        if "final" in po else None)
    return {
        "summary": clean_text(d.get("short_description"), 600),
        "cover_url": safe_image_url(d.get("header_image")),
        "req": parse_requirements(d.get("pc_requirements")),
        "price": price,
        "url": f"https://store.steampowered.com/app/{int(appid)}/",
    }
