"""IGDB (Twitch) importer. Auth: client-credentials OAuth token from id.twitch.tv; queries use the
Apicalypse body format. Credentials come only from the environment."""
import datetime as dt
import re
import time

from ..config import get_settings
from ..security.sanitize import clean_text
from . import mapping
from .allowlist import classify_url, safe_image_url
from .http import Throttled

FIELDS = (
    "name,slug,summary,storyline,first_release_date,total_rating,total_rating_count,"
    "genres.name,themes.name,keywords.name,game_modes.name,player_perspectives.name,platforms.name,"
    "cover.image_id,screenshots.image_id,websites.url,involved_companies.developer,involved_companies.company.name"
)
IMG = "https://images.igdb.com/igdb/image/upload"


class IGDB:
    def __init__(self) -> None:
        s = get_settings()
        if not (s.igdb_client_id and s.igdb_client_secret):
            raise RuntimeError("IGDB_CLIENT_ID / IGDB_CLIENT_SECRET are not set")
        self._id, self._secret = s.igdb_client_id, s.igdb_client_secret
        self._token: tuple[str, float] | None = None
        self._auth = Throttled("https://id.twitch.tv", 0.5)
        self._api = Throttled("https://api.igdb.com/v4", 0.30)   # limit is 4 req/s

    async def aclose(self) -> None:
        await self._auth.aclose(); await self._api.aclose()

    async def _headers(self) -> dict:
        if not self._token or self._token[1] < time.time() + 60:
            r = await self._auth.request("POST", "/oauth2/token", params={
                "client_id": self._id, "client_secret": self._secret, "grant_type": "client_credentials"})
            r.raise_for_status()
            d = r.json()
            self._token = (d["access_token"], time.time() + int(d.get("expires_in", 3600)))
        return {"Client-ID": self._id, "Authorization": f"Bearer {self._token[0]}", "Accept": "application/json"}

    async def games(self, *, limit: int = 100, offset: int = 0, min_ratings: int = 100) -> list[dict]:
        where = f"version_parent = null & parent_game = null & total_rating_count >= {int(min_ratings)} & platforms != null"
        body = f"fields {FIELDS}; where {where}; sort total_rating_count desc; limit {min(int(limit), 500)}; offset {int(offset)};"
        r = await self._api.request("POST", "/games", content=body, headers=await self._headers())
        r.raise_for_status()
        return r.json()


def _names(items: list[dict] | None) -> list[str]:
    return [clean_text(i.get("name"), 80) for i in (items or []) if i.get("name")]


def to_game(raw: dict) -> dict | None:
    """Map one IGDB record to our schema; returns None when it must not be imported."""
    themes = _names(raw.get("themes"))
    if any(t.lower() in mapping.EXCLUDED_THEMES for t in themes):
        return None
    slug = mapping.slugify(raw.get("slug") or raw.get("name") or "", 100)
    title = clean_text(raw.get("name"), 200)
    if not slug or not title or not raw.get("id"):
        return None
    genres = mapping.map_genres(_names(raw.get("genres")))
    if "horror" in [t.lower() for t in themes] and "horror" not in genres:
        genres.append("horror")
    if "survival" in [t.lower() for t in themes] and "survival" not in genres:
        genres.append("survival")
    tags = mapping.uniq(
        [mapping.THEME.get(t.lower()) or mapping.slugify(t) for t in themes if t.lower() not in ("horror", "survival")]
        + [mapping.slugify(p) for p in _names(raw.get("player_perspectives"))]
        + [mapping.slugify(k) for k in _names(raw.get("keywords"))[:6]]
    )[:14]
    summary = clean_text(raw.get("summary"), 600)
    story = clean_text(raw.get("storyline"), 2000)
    dev = next((clean_text(c["company"]["name"], 80) for c in (raw.get("involved_companies") or []) if c.get("developer") and c.get("company")), None)
    released = dt.datetime.fromtimestamp(raw["first_release_date"], dt.timezone.utc).date() if raw.get("first_release_date") else None

    links, steam_appid = [], None
    for w in raw.get("websites") or []:
        if (c := classify_url(w.get("url"))) and c[0] not in ("cheapshark",):
            links.append({"store": c[0], "url": c[1], "source": "igdb"})
            if c[0] == "steam" and (m := re.search(r"/app/(\d+)", c[1])):
                steam_appid = int(m.group(1))
    shot = (raw.get("screenshots") or [{}])[0].get("image_id")
    cover = (raw.get("cover") or {}).get("image_id")
    cover_url = safe_image_url(f"{IMG}/t_screenshot_big/{shot}.jpg") if shot else (safe_image_url(f"{IMG}/t_cover_big/{cover}.jpg") if cover else None)
    rating = raw.get("total_rating")
    return {
        "game": {
            "igdb_id": int(raw["id"]), "slug": slug, "title": title, "summary": summary,
            "description": (summary + ("\n\n" + story if story else ""))[:8000], "developer": dev, "release_date": released,
            "platforms": mapping.map_platforms(_names(raw.get("platforms"))), "genres": genres, "tags": tags,
            "features": mapping.map_modes(_names(raw.get("game_modes"))),
            "rating": round(rating) if rating is not None else None, "rating_count": int(raw.get("total_rating_count") or 0),
            "cover_url": cover_url, "steam_appid": steam_appid, "source": "igdb",
        },
        "links": links,
    }
