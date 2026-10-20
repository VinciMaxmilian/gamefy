"""Deterministic hardware compatibility. No LLM involved: an LLM may only *explain* the verdict."""
import re
from dataclasses import dataclass

# (regex, tier 1..10) — first match wins, so list specific models before generic ones.
_GPU = [
    (r"rtx\s*50[89]0|rx\s*9070|rtx\s*4090|rtx\s*4080", 10),
    (r"rtx\s*50[67]0|rtx\s*4070\s*ti|rx\s*7900|rtx\s*3090|rtx\s*3080", 9),
    (r"rtx\s*4070|rtx\s*3070|rx\s*7800|rx\s*6800|rx\s*7700|rtx\s*5060", 8),
    (r"rtx\s*4060|rtx\s*3060\s*ti|rx\s*6700|rx\s*7600|rx\s*6650|arc\s*b580|rtx\s*2080|rtx\s*2070", 7),
    (r"rtx\s*3060|rtx\s*2060|gtx\s*1080|gtx\s*1070|rx\s*6600|rx\s*5700|arc\s*a750", 6),
    (r"gtx\s*1660|gtx\s*1060|rx\s*5[78]0|rx\s*5500|gtx\s*980|arc\s*a380", 5),
    (r"gtx\s*1650|gtx\s*1050|gtx\s*970|rx\s*560|rx\s*470|gtx\s*960", 4),
    (r"gtx\s*750|gtx\s*950|gtx\s*1030|rx\s*550|gt\s*1030|rx\s*460", 3),
    (r"radeon\s*(780m|680m|graphics)|vega\s*[0-9]+|iris\s*xe|uhd\s*(graphics)?\s*7|m[1-4]\s*(pro|max|ultra)?", 3),
    (r"intel\s*(uhd|hd)|integrated|igpu|gt\s*7[0-9]0|gt\s*6[0-9]0", 2),
]
_CPU = [
    (r"i9-1[3-5]\d{3}|ryzen\s*9\s*[79]\d{3}|ryzen\s*7\s*[79]\d{3}|core\s*ultra\s*[79]", 10),
    (r"i7-1[2-4]\d{3}|i5-1[3-4]\d{3}|ryzen\s*7\s*5\d{3}|ryzen\s*5\s*[79]\d{3}|m[2-4]", 8),
    (r"i7-(9|10|11)\d{3}|i5-1[0-2]\d{3}|ryzen\s*5\s*[35]\d{3}|ryzen\s*7\s*[23]\d{3}|m1", 7),
    (r"i5-[89]\d{3}|i7-[78]\d{3}|ryzen\s*5\s*[12]\d{3}|ryzen\s*7\s*1\d{3}", 6),
    (r"i5-[67]\d{3}|i7-[46]\d{3}|i3-1\d{4}|ryzen\s*3", 5),
    (r"i3-[6-9]\d{3}|i5-[45]\d{3}|i[357]-[23]\d{3}|fx-?\d+|athlon", 4),
    (r"i3|pentium|celeron|core\s*2", 2),
]


def _match(table: list[tuple[str, int]], text: str | None) -> int | None:
    if not text:
        return None
    t = text.lower()
    t = re.sub(r"\s+", " ", t)
    for pattern, tier in table:
        if re.search(pattern, t):
            return tier
    return None


def gpu_tier(name: str | None) -> int | None:
    return _match(_GPU, name)


def cpu_tier(name: str | None) -> int | None:
    return _match(_CPU, name)


@dataclass
class Hardware:
    gpu_tier: int | None = None
    cpu_tier: int | None = None
    ram_gb: int | None = None
    vram_gb: int | None = None
    storage_gb: int | None = None


@dataclass
class Compat:
    verdict: str  # 'recommended' | 'minimum' | 'below_minimum' | 'unknown'
    score: float  # 0..1, used by the ranking engine
    reasons: list[dict]   # [{'code': ..., 'args': [...]}] rendered by the client in the user's language


_FIELDS = [("gpu_tier", "gpu"), ("cpu_tier", "cpu"), ("ram_gb", "ram"), ("vram_gb", "vram"), ("storage_gb", "storage")]


def check_compat(hw: Hardware, req: dict | None) -> Compat:
    req = req or {}
    minimum, rec = req.get("min") or {}, req.get("rec") or {}
    if not minimum and not rec:
        return Compat("unknown", 0.5, [{"code": "no_req_data", "args": []}])
    below, below_rec, unknown = [], [], []
    checked = 0
    for field, label in _FIELDS:                       # label is a stable key: gpu, cpu, ram, vram, storage
        have = getattr(hw, field)
        need_min, need_rec = minimum.get(field), rec.get(field) or minimum.get(field)
        if need_min is None and need_rec is None:
            continue
        if have is None:
            unknown.append(label)
            continue
        checked += 1
        if need_min is not None and have < need_min:
            below.append({"code": "below_min_field", "args": [label]})
        elif need_rec is not None and have < need_rec:
            below_rec.append({"code": "below_rec_field", "args": [label]})
    if below:
        return Compat("below_minimum", 0.0, below)
    if checked == 0:
        return Compat("unknown", 0.5, [{"code": "add_hardware", "args": []}])
    if below_rec:
        return Compat("minimum", 0.65, below_rec)
    if unknown:                      # nothing fails, but we cannot vouch for what we do not know
        return Compat("partial", 0.75, [{"code": "add_fields", "args": list(unknown)}])
    return Compat("recommended", 1.0, [{"code": "meets_rec", "args": []}])
