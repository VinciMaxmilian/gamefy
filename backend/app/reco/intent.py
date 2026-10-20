"""Rule-based intent parser (PT/EN). Turns a free-text request into structured constraints
WITHOUT an LLM. The generative layer (post-MVP) can produce the same `ParsedQuery` for harder
phrasing, but the backend still validates and executes — the LLM never runs the search.
"""
import re
from dataclasses import dataclass, field

from ..security.sanitize import clean_text
from .engine import Intent

GENRE_WORDS = {
    "rpg": "rpg", "action": "action", "ação": "action", "acao": "action", "aventura": "adventure", "adventure": "adventure",
    "estratégia": "strategy", "estrategia": "strategy", "strategy": "strategy", "puzzle": "puzzle", "quebra-cabeça": "puzzle",
    "terror": "horror", "horror": "horror", "corrida": "racing", "racing": "racing", "esporte": "sports", "esportes": "sports",
    "sports": "sports", "simulação": "simulation", "simulacao": "simulation", "simulation": "simulation", "indie": "indie",
    "plataforma": "platformer", "platformer": "platformer", "tiro": "shooter", "fps": "shooter", "shooter": "shooter",
    "roguelike": "roguelike", "souls-like": "soulslike", "soulslike": "soulslike", "luta": "fighting", "fighting": "fighting",
    "sobrevivência": "survival", "sobrevivencia": "survival", "survival": "survival",
}
TAG_WORDS = {
    "difficult": "difficult", "hard": "difficult", "história": "story-rich", "historia": "story-rich", "story": "story-rich", "narrativa": "story-rich",
    "mundo aberto": "open-world", "open world": "open-world", "exploração": "exploration", "exploracao": "exploration",
    "exploration": "exploration", "relaxante": "relaxing", "relaxing": "relaxing", "cozy": "cozy", "difícil": "difficult",
    "dificil": "difficult", "challenging": "difficult", "atmosférico": "atmospheric", "atmospheric": "atmospheric",
    "fantasia": "fantasy", "fantasy": "fantasy", "sci-fi": "sci-fi", "ficção científica": "sci-fi", "pixel": "pixel-art",
    "construção": "building", "building": "building", "furtividade": "stealth", "stealth": "stealth",
}
FEATURE_WORDS = {
    "single player": "single-player", "singleplayer": "single-player", "um jogador": "single-player", "solo": "single-player",
    "coop": "co-op", "co-op": "co-op", "cooperativo": "co-op", "multiplayer": "multiplayer", "multijogador": "multiplayer",
    "controle": "controller-support", "controller": "controller-support",
}
PLATFORM_WORDS = {"pc": "pc", "windows": "pc", "ps5": "ps5", "playstation": "ps5", "xbox": "xbox", "switch": "switch",
                  "nintendo": "switch", "mac": "mac", "linux": "linux", "steam deck": "linux"}
SHORT = re.compile(r"\b(curto|curta|pequeno|rápido|rapido|short|small|quick|menor)\b", re.I)
LONG = re.compile(r"\b(longo|longa|enorme|long|huge|épico|epico)\b", re.I)
NOT_LONG = re.compile(r"\b(não|nao|sem|nem|not|no|without|avoid|evitar)\b.{0,25}\b(100|longo|long|horas|hours)\b", re.I)
HOURS = re.compile(r"(?:até|ate|under|menos de|less than|<=?|no máximo|max)\s*(\d{1,3})\s*(?:h|horas|hours)\b", re.I)
PRICE = re.compile(r"(?:até|ate|under|menos de|less than|<=?|no máximo|max|abaixo de)\s*(?:r\$|\$|us\$)?\s*(\d{1,4}(?:[.,]\d{1,2})?)", re.I)
FREE = re.compile(r"\b(grátis|gratis|free|gratuito)\b", re.I)
SIMILAR = re.compile(r"(?:parecid[oa]s? com|similar(?:es)? a|tipo|como|like|similar to|inspired by)\s+(?:o |a |the )?([^,.;]+?)(?=\s+(?:mas|porém|but|and|e|que|with|com|sem|without)\b|[,.;]|$)", re.I)


@dataclass
class ParsedQuery:
    text: str
    intent: Intent = field(default_factory=Intent)
    similar_titles: list[str] = field(default_factory=list)
    avoid_features: set[str] = field(default_factory=set)


def _scan(table: dict[str, str], text: str) -> set[str]:
    return {v for k, v in table.items() if re.search(rf"(?<![\w-]){re.escape(k)}(?![\w-])", text)}


def parse_query(raw: str, max_len: int = 300) -> ParsedQuery:
    text = clean_text(raw, max_len)
    low = text.lower()
    it = Intent(genres=_scan(GENRE_WORDS, low), tags=_scan(TAG_WORDS, low), features=_scan(FEATURE_WORDS, low),
                platforms=_scan(PLATFORM_WORDS, low))
    if m := PRICE.search(low):
        it.max_price_cents = int(float(m.group(1).replace(",", ".")) * 100)
    if FREE.search(low):
        it.max_price_cents = 0
    if m := HOURS.search(low):
        it.max_duration_hours = float(m.group(1))
    elif NOT_LONG.search(low) or SHORT.search(low):
        it.max_duration_hours = 30.0
    elif LONG.search(low):
        it.min_duration_hours = 40.0
    titles = [clean_text(m.group(1), 80) for m in SIMILAR.finditer(text)]
    # "A e B" lists: "gostei de Witcher 3 e Skyrim"
    for m in re.finditer(r"(?:gostei (?:muito )?de|i (?:really )?(?:liked|loved)|adorei)\s+([^,.;]+)", text, re.I):
        titles += [clean_text(t, 80) for t in re.split(r"\s+(?:e|and|&)\s+|,", m.group(1)) if t.strip()]
    titles = list(dict.fromkeys(t for t in titles if len(t) >= 2))[:5]
    return ParsedQuery(text=text, intent=it, similar_titles=titles)
