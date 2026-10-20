"""Outbound store links are an attack surface (phishing via imported data). Only https URLs on
these domains ever reach the database or the UI, and the check runs again when serving."""
from urllib.parse import urlsplit

# registrable domain -> canonical store key
DOMAIN_TO_STORE = {
    "store.steampowered.com": "steam",
    "store.epicgames.com": "epic",
    "epicgames.com": "epic",
    "gog.com": "gog",
    "humblebundle.com": "humble",
    "fanatical.com": "fanatical",
    "greenmangaming.com": "gmg",
    "store.playstation.com": "playstation",
    "xbox.com": "xbox",
    "microsoft.com": "microsoft",
    "nintendo.com": "nintendo",
    "itch.io": "itch",
    "cheapshark.com": "cheapshark",
}
STORE_NAMES = {
    "steam": "Steam", "epic": "Epic Games Store", "gog": "GOG", "humble": "Humble Store", "fanatical": "Fanatical",
    "gmg": "Green Man Gaming", "playstation": "PlayStation Store", "xbox": "Xbox", "microsoft": "Microsoft Store",
    "nintendo": "Nintendo eShop", "itch": "itch.io", "cheapshark": "CheapShark",
}
# Hosts we accept images from (cover art), exact or subdomain.
IMAGE_HOSTS = ("images.igdb.com", "shared.akamai.steamstatic.com", "cdn.akamai.steamstatic.com", "cdn.cloudflare.steamstatic.com")


def _host_ok(host: str, allowed: str) -> bool:
    return host == allowed or host.endswith("." + allowed)


def classify_url(url: str | None) -> tuple[str, str] | None:
    """Return (store_key, normalised_url) or None when the URL must not be shown."""
    if not url or len(url) > 500:
        return None
    try:
        parts = urlsplit(url.strip())
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        return None
    if parts.scheme != "https" or parts.username or parts.password or port not in (None, 443) or not host:
        return None
    if any(c in url for c in " \t\r\n<>\"'\\"):
        return None
    for domain, store in DOMAIN_TO_STORE.items():
        if _host_ok(host, domain):
            return store, parts._replace(fragment="").geturl()
    return None


def safe_image_url(url: str | None) -> str | None:
    try:
        parts = urlsplit((url or "").strip())
        host = (parts.hostname or "").lower()
    except ValueError:
        return None
    if parts.scheme == "https" and not parts.username and any(_host_ok(host, h) for h in IMAGE_HOSTS) and len(url or "") <= 500:
        return parts.geturl()
    return None
