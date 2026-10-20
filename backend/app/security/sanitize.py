"""Untrusted-text handling. Everything that is not our own code (reviews, game
descriptions, tags, imported metadata, user messages, RAG hits) is DATA, never instructions.

Used today when building semantic documents; the generative layer (chat, post-MVP)
must pass any such text through `wrap_untrusted` and keep it out of the system prompt.
"""
import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁠-⁤﻿]")
_INLINE = re.compile(r"</?(?:b|i|em|strong|u|span|a|font|small|sub|sup|mark)\b[^>]{0,200}>", re.I)
_TAGS = re.compile(r"<[^>]{0,200}>")
_WS = re.compile(r"\s+")

# Heuristic detector. It does NOT make text safe (isolation does); it flags content
# for logging, quarantine from LLM context and moderation.
_INJECTION = [
    r"ignore (all|any|the|your)?\s*(previous|prior|above|earlier)\s*(instructions|prompts?|rules)",
    r"disregard (all|any|the|your)?\s*(previous|prior|above)",
    r"ignore (todas )?as instru[cç][õo]es",
    r"you are now\b",
    r"\bnew (system )?instructions?\b",
    r"(reveal|show|print|repeat|leak).{0,40}(system prompt|instructions|credentials|api[ _-]?key|secret|password|token)",
    r"(system|developer)\s*(prompt|message)\s*:",
    r"</?\s*(system|assistant|tool|instructions?)\s*>",
    r"\bjailbreak\b|\bDAN mode\b",
    r"act as (an? )?(admin|administrator|root|developer)",
    r"mostre (o )?(seu )?(system )?prompt",
    r"(database|db|service[_ ]role|supabase).{0,20}(credential|password|key|secret)",
]
_INJECTION_RE = re.compile("|".join(f"(?:{p})" for p in _INJECTION), re.IGNORECASE | re.DOTALL)


def clean_text(value: str | None, max_len: int = 2000, strip_markup: bool = True) -> str:
    """Normalise to NFKC, drop control/zero-width/bidi characters and markup, collapse whitespace."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = _CONTROL.sub("", text)
    if strip_markup:
        text = _TAGS.sub(" ", _INLINE.sub("", text))
    return _WS.sub(" ", text).strip()[:max_len]


def looks_like_injection(value: str) -> bool:
    return bool(_INJECTION_RE.search(unicodedata.normalize("NFKC", value or "")))


def wrap_untrusted(label: str, value: str, max_len: int = 1500) -> str:
    """Render untrusted text as an inert, clearly delimited data block for an LLM prompt.
    The delimiter text is neutralised inside the payload so content cannot close the block."""
    safe = clean_text(value, max_len).replace("<<", "‹‹").replace(">>", "››")
    flag = ' flagged="true"' if looks_like_injection(safe) else ""
    return f'<<untrusted_data source="{clean_text(label, 40)}"{flag}>>{safe}<</untrusted_data>>'
