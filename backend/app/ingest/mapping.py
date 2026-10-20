"""IGDB / Steam vocabulary -> our controlled vocabulary (lowercase slugs)."""
import re

GENRE = {
    "role-playing (rpg)": ["rpg"], "adventure": ["adventure"], "shooter": ["shooter", "action"], "strategy": ["strategy"],
    "turn-based strategy (tbs)": ["strategy", "turn-based"], "real time strategy (rts)": ["strategy", "rts"],
    "simulator": ["simulation"], "sport": ["sports"], "racing": ["racing"], "puzzle": ["puzzle"], "platform": ["platformer"],
    "fighting": ["fighting", "action"], "hack and slash/beat 'em up": ["action"], "indie": ["indie"], "arcade": ["arcade"],
    "tactical": ["strategy", "tactical"], "point-and-click": ["adventure", "point-and-click"], "music": ["music"],
    "card & board game": ["card-game"], "visual novel": ["adventure", "visual-novel"], "quiz/trivia": ["trivia"],
    "moba": ["moba", "strategy"], "pinball": ["arcade"],
}
THEME = {
    "science fiction": "sci-fi", "fantasy": "fantasy", "horror": "horror", "survival": "survival", "open world": "open-world",
    "stealth": "stealth", "comedy": "humor", "historical": "historical", "sandbox": "sandbox", "4x (explore, expand, exploit, and exterminate)": "4x",
    "party": "party", "mystery": "mystery", "thriller": "thriller", "drama": "story-rich", "warfare": "war", "kids": "family",
}
MODE = {
    "single player": ["single-player"], "multiplayer": ["multiplayer"], "co-operative": ["co-op", "multiplayer"],
    "split screen": ["split-screen", "multiplayer"], "massively multiplayer online (mmo)": ["mmo", "multiplayer"],
    "battle royale": ["battle-royale", "multiplayer"],
}
EXCLUDED_THEMES = {"erotic"}   # adult content is not imported

PLATFORM_RULES = [  # (substring in lowercase IGDB name, our key)
    ("pc (microsoft windows)", "pc"), ("playstation 5", "ps5"), ("playstation 4", "ps4"), ("xbox series", "xbox"),
    ("xbox one", "xbox"), ("nintendo switch", "switch"), ("mac", "mac"), ("linux", "linux"),
]


def slugify(value: str, max_len: int = 40) -> str | None:
    s = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:max_len].strip("-")
    return s if re.fullmatch(r"[a-z0-9][a-z0-9-]*", s or "") else None


def uniq(items: list[str]) -> list[str]:
    return list(dict.fromkeys(i for i in items if i))


def map_genres(names: list[str]) -> list[str]:
    out: list[str] = []
    for n in names:
        out += GENRE.get(n.lower()) or [slugify(n)]
    return uniq(out)


def map_modes(names: list[str]) -> list[str]:
    out: list[str] = []
    for n in names:
        out += MODE.get(n.lower()) or [slugify(n)]
    return uniq(out)


def map_platforms(names: list[str]) -> list[str]:
    out = [key for n in names for sub, key in PLATFORM_RULES if sub in n.lower()]
    return uniq(out)
