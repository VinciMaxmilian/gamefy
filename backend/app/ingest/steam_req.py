"""Parse Steam's HTML system requirements into our deterministic tiers. Input is untrusted HTML:
we never render it — tags are stripped and only numbers / hardware names are extracted."""
import re

from ..reco.hardware import cpu_tier, gpu_tier
from ..security.sanitize import clean_text

_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.I | re.S)
_SPLIT_ALT = re.compile(r"\s*(?:/|\bor\b|,|\|)\s*", re.I)


def _gb(text: str) -> int | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:[A-Za-z]{2,5}\s+)?(TB|GB|MB)\b", text, re.I)   # tolerates "60 SSD GB"
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    unit = m.group(2).upper()
    gb = n * 1024 if unit == "TB" else n if unit == "GB" else n / 1024
    return max(1, round(gb))


def _tier(text: str, fn) -> int | None:
    tiers = [t for alt in _SPLIT_ALT.split(text) if (t := fn(alt)) is not None]
    return min(tiers) if tiers else None      # any listed alternative is acceptable => the weakest one gates


def parse_block(html: str | None) -> dict:
    out: dict[str, int] = {}
    for li in _LI.findall(html or ""):
        m = re.match(r"\s*<strong>(.*?):?\s*</strong>\s*(.*)", li, re.I | re.S)
        if not m:
            continue
        key, val = clean_text(m.group(1), 40).lower().rstrip(":"), clean_text(m.group(2), 200)
        if key.startswith("processor") and (t := _tier(val, cpu_tier)):
            out["cpu_tier"] = t
        elif key.startswith("memory") and (g := _gb(val)):
            out["ram_gb"] = g
        elif key.startswith("graphics"):
            if t := _tier(val, gpu_tier):
                out["gpu_tier"] = t
            if (v := re.search(r"(\d+)\s*GB\s*(?:of\s*)?(?:dedicated\s*)?(?:VRAM|video)", val, re.I)):
                out["vram_gb"] = int(v.group(1))
        elif key.startswith(("storage", "hard drive", "disk")) and (g := _gb(val)):
            out["storage_gb"] = g
        elif key.startswith("additional") and (v := re.search(r"VRAM\s*:?\s*(\d+)\s*GB|(\d+)\s*GB\s*(?:of\s*)?VRAM", val, re.I)):
            out["vram_gb"] = int(v.group(1) or v.group(2))
    return out


def parse_requirements(pc_requirements) -> dict:
    """pc_requirements is {'minimum': html, 'recommended': html}, or [] when absent."""
    if not isinstance(pc_requirements, dict):
        return {}
    req = {}
    if mn := parse_block(pc_requirements.get("minimum")):
        req["min"] = mn
    if rc := parse_block(pc_requirements.get("recommended")):
        req["rec"] = rc
    return req
