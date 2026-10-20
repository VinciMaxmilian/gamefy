"""Level 1: turn behaviour into a preference profile.

Profile = {feature_key: weight in [-1, 1]} where keys look like 'genre:rpg', 'tag:story-rich',
'feature:single-player'. Pure functions — easy to test and to replace with an ML model later.
"""
import math
from dataclasses import dataclass
from datetime import datetime, timezone

# Signal strengths (positive = interest, negative = disinterest).
SIGNAL = {
    "view": 0.10,
    "wishlist": 0.50,
    "library": 0.30,
    "ignore": -0.90,
    "search": 0.15,
}
MAX_PLAYTIME_BONUS = 0.80       # reached at PLAYTIME_FULL_HOURS
PLAYTIME_FULL_HOURS = 20.0
SATURATION = 1.5                # larger = slower to saturate towards +-1


@dataclass
class Interaction:
    kind: str                          # view|wishlist|library|ignore|search|rating|playtime
    features: list[str]                # feature keys of the game (or matched from query)
    at: datetime
    value: float | None = None         # rating score (1..10) or hours played


def game_features(genres: list[str], tags: list[str], features: list[str]) -> list[str]:
    return ([f"genre:{g}" for g in genres] + [f"tag:{t}" for t in tags] + [f"feature:{f}" for f in features])


def _strength(i: Interaction) -> float:
    if i.kind == "rating" and i.value is not None:
        return (i.value - 5.5) / 4.5             # 1..10 -> -1..1
    if i.kind == "playtime" and i.value is not None:
        return MAX_PLAYTIME_BONUS * min(1.0, i.value / PLAYTIME_FULL_HOURS)
    return SIGNAL.get(i.kind, 0.0)


def build_profile(interactions: list[Interaction], explicit: dict[str, float] | None = None,
                  half_life_days: float = 45.0, now: datetime | None = None) -> dict[str, float]:
    now = now or datetime.now(timezone.utc)
    acc: dict[str, float] = {}
    for it in interactions:
        age_days = max(0.0, (now - it.at).total_seconds() / 86400)
        decay = 0.5 ** (age_days / half_life_days)
        s = _strength(it) * decay
        if not s or not it.features:
            continue
        share = s / math.sqrt(len(it.features))      # many tags must not drown a few strong ones
        for f in it.features:
            acc[f] = acc.get(f, 0.0) + share
    for k, v in (explicit or {}).items():
        acc[k] = acc.get(k, 0.0) + max(-1.0, min(1.0, float(v))) * 2.0   # explicit statements weigh a lot
    prof = {k: round(math.tanh(v / SATURATION), 3) for k, v in acc.items()}
    return {k: v for k, v in prof.items() if abs(v) >= 0.02}


def top_features(profile: dict[str, float], n: int = 8) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    items = sorted(profile.items(), key=lambda kv: kv[1], reverse=True)
    return [kv for kv in items if kv[1] > 0][:n], [kv for kv in reversed(items) if kv[1] < 0][:n]
