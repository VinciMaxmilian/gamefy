import hashlib

from ..security.sanitize import clean_text, looks_like_injection


def build_semantic_doc(g: dict) -> tuple[str, bool]:
    """Build the text that is embedded for a game. Returns (document, flagged).

    All fields are sanitised (they may come from imports/third parties). Free-text fields
    that look like prompt injection are dropped from the document and `flagged` is set so
    the record can be reviewed — the embedding model would only see inert data, but the same
    document may later be shown to an LLM, so we keep it clean at the source."""
    flagged = False

    def safe(field: str, n: int) -> str:
        nonlocal flagged
        text = clean_text(g.get(field), n)
        if text and looks_like_injection(text):
            flagged = True
            return ""
        return text

    def lst(field: str) -> str:
        return ", ".join(clean_text(x, 40) for x in (g.get(field) or [])[:20])

    hours = g.get("avg_duration_hours")
    parts = [
        f"Title: {clean_text(g.get('title'), 200)}",
        f"Genres: {lst('genres')}",
        f"Tags (gameplay, narrative, atmosphere): {lst('tags')}",
        f"Modes and features: {lst('features')}",
        f"Platforms: {lst('platforms')}",
        f"Duration: about {hours:g} hours" if hours else "",
        f"Difficulty: {g['difficulty']} out of 5" if g.get("difficulty") else "",
        f"Summary: {safe('summary', 600)}",
        f"Description: {safe('description', 1500)}",
    ]
    return "\n".join(p for p in parts if p and not p.endswith(": ")), flagged


def doc_hash(doc: str, model: str) -> str:
    return hashlib.sha256(f"{model}\n{doc}".encode()).hexdigest()
