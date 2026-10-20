"""Level 1+2 ranking:  Score = Σ weight_i · component_i  (weights configurable).

Every component is normalised so the final score is explainable and tunable. The engine is a
pure function over `Candidate`s — swap `rank()` for an ML ranker later without touching routers.
"""
from dataclasses import dataclass, field

from ..config import RecoWeights
from .hardware import Compat


@dataclass
class Candidate:
    slug: str
    genres: list[str]
    tags: list[str]
    features: list[str]
    platforms: list[str]
    price_cents: int | None
    rating: int | None
    avg_duration_hours: float | None
    similarity: float = 0.0           # cosine similarity in [0, 1] (0 if unknown)
    compat: Compat | None = None


@dataclass
class Intent:
    """What the user asked for right now (structured), independent of long-term taste."""
    genres: set[str] = field(default_factory=set)
    tags: set[str] = field(default_factory=set)
    features: set[str] = field(default_factory=set)
    platforms: set[str] = field(default_factory=set)
    max_price_cents: int | None = None
    max_duration_hours: float | None = None
    min_duration_hours: float | None = None


@dataclass
class Scored:
    candidate: Candidate
    score: float
    breakdown: dict[str, float]
    reasons: list[str]


def _pref(profile: dict[str, float], keys: list[str]) -> float:
    vals = [profile[k] for k in keys if k in profile]
    if not vals:
        return 0.0
    # Strongest signal dominates, the rest nudge it.
    vals.sort(key=abs, reverse=True)
    return max(-1.0, min(1.0, vals[0] + 0.25 * sum(vals[1:])))


def _overlap(wanted: set[str], have: list[str]) -> float:
    return len(wanted & set(have)) / len(wanted) if wanted else 0.0


def _price_match(price: int | None, cap: int | None) -> float:
    if cap is None or price is None:
        return 0.5                      # no budget stated / unknown price: neutral
    if price <= cap:
        return 1.0
    return max(0.0, 1.0 - (price - cap) / max(cap, 1))


def _duration_match(hours: float | None, lo: float | None, hi: float | None) -> float:
    if hours is None or (lo is None and hi is None):
        return 0.5
    if hi is not None and hours > hi:
        return max(0.0, 1.0 - (hours - hi) / max(hi, 1))
    if lo is not None and hours < lo:
        return max(0.0, 1.0 - (lo - hours) / max(lo, 1))
    return 1.0


def _platform(c: Candidate, intent: Intent) -> float:
    plat = _overlap(intent.platforms, c.platforms) if intent.platforms else 0.5
    if c.compat is None:
        return plat
    return 0.5 * plat + 0.5 * c.compat.score if intent.platforms else c.compat.score


def score_candidate(c: Candidate, profile: dict[str, float], intent: Intent, w: RecoWeights) -> Scored:
    comps = {
        "semantic_similarity": max(0.0, min(1.0, c.similarity)),
        "user_preference": _pref(profile, [f"genre:{g}" for g in c.genres] + [f"tag:{t}" for t in c.tags] + [f"feature:{f}" for f in c.features]),
        "genre_match": max(_overlap(intent.genres, c.genres), max(0.0, _pref(profile, [f"genre:{g}" for g in c.genres]))),
        "tag_match": max(_overlap(intent.tags, c.tags), max(0.0, _pref(profile, [f"tag:{t}" for t in c.tags]))),
        "gameplay_match": max(_overlap(intent.features, c.features), max(0.0, _pref(profile, [f"feature:{f}" for f in c.features]))),
        "rating": (c.rating or 0) / 100,
        "platform_compatibility": _platform(c, intent),
        "price_match": _price_match(c.price_cents, intent.max_price_cents),
        "duration_match": _duration_match(c.avg_duration_hours, intent.min_duration_hours, intent.max_duration_hours),
    }
    weights = w.model_dump()
    total = sum(weights[k] * v for k, v in comps.items())
    if c.compat and c.compat.verdict == "below_minimum":
        total *= 0.4           # still visible, but clearly demoted: it will not run on this PC
    return Scored(c, round(total, 4), {k: round(v, 3) for k, v in comps.items()}, _reasons(c, profile, intent, comps))


def _reasons(c: Candidate, profile: dict[str, float], intent: Intent, comps: dict[str, float]) -> list[str]:
    """Deterministic, factual explanations (an LLM may later *rephrase* these, never invent them)."""
    out: list[str] = []
    liked = sorted(((profile[k], k) for k in [f"genre:{g}" for g in c.genres] + [f"tag:{t}" for t in c.tags] if profile.get(k, 0) > 0.3), reverse=True)
    if liked:
        out.append("Matches your taste: " + ", ".join(k.split(":", 1)[1] for _, k in liked[:3]))
    if intent.genres & set(c.genres):
        out.append("Genre you asked for: " + ", ".join(sorted(intent.genres & set(c.genres))))
    if comps["semantic_similarity"] > 0.55:
        out.append("Very similar to what you described")
    if intent.max_duration_hours and c.avg_duration_hours and c.avg_duration_hours <= intent.max_duration_hours:
        out.append(f"About {c.avg_duration_hours:g}h to finish")
    if intent.max_price_cents is not None and c.price_cents is not None and c.price_cents <= intent.max_price_cents:
        out.append("Within your budget")
    if c.compat and c.compat.verdict == "recommended":
        out.append("Runs well on your PC")
    elif c.compat and c.compat.verdict == "below_minimum":
        out.append("Below minimum requirements for your PC")
    if (c.rating or 0) >= 90:
        out.append("Highly rated")
    return out[:4]


def rank(cands: list[Candidate], profile: dict[str, float], intent: Intent, w: RecoWeights, limit: int = 20) -> list[Scored]:
    scored = [score_candidate(c, profile, intent, w) for c in cands]
    scored.sort(key=lambda s: (s.score, s.candidate.rating or 0), reverse=True)
    return scored[:limit]
