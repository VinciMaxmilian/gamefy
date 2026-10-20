from datetime import datetime, timedelta, timezone

from app.config import RecoWeights
from app.reco.engine import Candidate, Intent, rank
from app.reco.hardware import Hardware, check_compat, cpu_tier, gpu_tier
from app.reco.intent import parse_query
from app.reco.profile import Interaction, build_profile, game_features

NOW = datetime.now(timezone.utc)


def test_profile_positive_negative_and_decay():
    rpg = game_features(["rpg"], ["story-rich"], ["single-player"])
    sport = game_features(["sports"], ["competitive"], ["multiplayer"])
    p = build_profile([
        Interaction("wishlist", rpg, NOW), Interaction("rating", rpg, NOW, 10), Interaction("playtime", rpg, NOW, 40),
        Interaction("ignore", sport, NOW),
    ], now=NOW)
    assert p["genre:rpg"] > 0.6 and p["genre:sports"] < -0.2
    old = build_profile([Interaction("wishlist", rpg, NOW - timedelta(days=300))], now=NOW)
    new = build_profile([Interaction("wishlist", rpg, NOW)], now=NOW)
    assert abs(old.get("genre:rpg", 0)) < abs(new["genre:rpg"])


def test_profile_bounded_and_explicit():
    f = game_features(["rpg"], [], [])
    p = build_profile([Interaction("wishlist", f, NOW)] * 500, {"genre:horror": -1.0}, now=NOW)
    assert all(-1 <= v <= 1 for v in p.values()) and p["genre:horror"] < -0.5


def _c(slug, genres, price=2000, hours=20, rating=80, sim=0.5, plats=("pc",), compat=None):
    return Candidate(slug, genres, [], [], list(plats), price, rating, hours, sim, compat)


def test_ranking_prefers_taste_and_respects_constraints():
    profile = {"genre:rpg": 0.9, "genre:sports": -0.8}
    cands = [_c("sport", ["sports"], sim=0.5), _c("rpg-long", ["rpg"], hours=120), _c("rpg-short", ["rpg"], hours=20)]
    out = rank(cands, profile, Intent(max_duration_hours=30), RecoWeights())
    assert [s.candidate.slug for s in out][0] == "rpg-short" and out[-1].candidate.slug == "sport"
    assert out[0].reasons


def test_weights_are_configurable():
    cands = [_c("a", ["x"], sim=1.0, rating=10), _c("b", ["x"], sim=0.0, rating=100)]
    sem = rank(cands, {}, Intent(), RecoWeights(semantic_similarity=1, rating=0))
    rat = rank(cands, {}, Intent(), RecoWeights(semantic_similarity=0, rating=1))
    assert sem[0].candidate.slug == "a" and rat[0].candidate.slug == "b"


def test_hardware_deterministic():
    assert gpu_tier("NVIDIA GeForce RTX 3060") == 6 and gpu_tier("GTX 1650") == 4 and gpu_tier("potato") is None
    assert cpu_tier("Intel Core i5-12400") is not None
    req = {"min": {"gpu_tier": 4, "ram_gb": 8}, "rec": {"gpu_tier": 7, "ram_gb": 16}}
    assert check_compat(Hardware(gpu_tier=3, ram_gb=16), req).verdict == "below_minimum"
    assert check_compat(Hardware(gpu_tier=5, ram_gb=8), req).verdict == "minimum"
    assert check_compat(Hardware(gpu_tier=8), req).verdict == "partial"
    assert check_compat(Hardware(gpu_tier=8, ram_gb=16), req).verdict == "recommended"
    assert check_compat(Hardware(), req).verdict == "unknown"


def test_below_minimum_is_demoted():
    from app.reco.hardware import Compat
    bad = _c("bad", ["rpg"], compat=Compat("below_minimum", 0.0, []))
    ok = _c("ok", ["rpg"], compat=Compat("recommended", 1.0, []))
    assert rank([bad, ok], {}, Intent(), RecoWeights())[0].candidate.slug == "ok"


def test_intent_parser_pt_and_en():
    p = parse_query("Quero um RPG parecido com Skyrim, mas menor, com uma história boa e que rode no PC")
    assert "rpg" in p.intent.genres and "story-rich" in p.intent.tags and "pc" in p.intent.platforms
    assert p.intent.max_duration_hours == 30 and "Skyrim" in p.similar_titles
    q = parse_query("cozy co-op game under $20, less than 10 hours")
    assert q.intent.max_price_cents == 2000 and q.intent.max_duration_hours == 10 and "co-op" in q.intent.features
    r = parse_query("Gostei muito de Witcher 3 e Skyrim, mas não quero outro jogo de 100 horas")
    assert {"Witcher 3", "Skyrim"} <= set(r.similar_titles) and r.intent.max_duration_hours == 30
