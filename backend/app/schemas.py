import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{1,100}$")]
Token = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9 +&'.-]{0,39}$", to_lower=True)]
Platform = Literal["pc", "ps5", "ps4", "xbox", "switch", "mac", "linux"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ------------------------------------------------------------------ games
class GameCard(BaseModel):
    slug: str
    title: str
    summary: str
    cover_url: str | None
    price_cents: int | None
    currency: str
    genres: list[str]
    tags: list[str]
    platforms: list[str]
    rating: int | None
    avg_duration_hours: float | None
    release_date: date | None


class GameDetail(GameCard):
    description: str
    developer: str | None
    features: list[str]
    difficulty: int | None
    rating_count: int
    req: dict


class Reason(BaseModel):
    """Language-neutral explanation: the frontend renders `code` + `args` in the user's language."""
    code: str
    args: list[str] = []


class Compatibility(BaseModel):
    verdict: str
    reasons: list[Reason]


class Recommendation(BaseModel):
    game: GameCard
    score: float
    reasons: list[Reason]
    breakdown: dict[str, float] | None = None
    compatibility: Compatibility | None = None


class Page(BaseModel):
    items: list[GameCard]
    total: int
    limit: int
    offset: int


# -------------------------------------------------------------------- auth
def _normalize_email(v: str) -> str:
    from email_validator import EmailNotValidError, validate_email
    try:
        return validate_email(v, check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise ValueError("Invalid email") from exc


class Credentials(Strict):
    email: Annotated[str, StringConstraints(max_length=254)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    _email = field_validator("email")(_normalize_email)


class EmailOnly(Strict):
    email: Annotated[str, StringConstraints(max_length=254)]
    _email = field_validator("email")(_normalize_email)


class ResetPassword(Strict):
    """Exactly one credential: `token_hash` (from our e-mail template; consumed only on submit, so mail
    scanners that pre-open links cannot burn it) or `access_token` (legacy #access_token redirect)."""
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    access_token: Annotated[str, StringConstraints(min_length=20, max_length=4096)] | None = None
    token_hash: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_\-]{8,200}$")] | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "ResetPassword":
        if (self.access_token is None) == (self.token_hash is None):
            raise ValueError("Provide exactly one of access_token or token_hash")
        return self


class ConfirmEmail(Strict):
    token_hash: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_\-]{8,200}$")]


# ----------------------------------------------------------------- user data
class LibraryIn(Strict):
    status: Literal["owned", "playing", "completed", "dropped"] = "owned"
    playtime_minutes: int = Field(0, ge=0, le=600_000)


class RatingIn(Strict):
    score: int = Field(ge=1, le=10)
    review: str | None = Field(None, max_length=2000)


class EventIn(Strict):
    type: Literal["view", "ignore"]
    slug: Slug


class HardwareIn(Strict):
    cpu: str | None = Field(None, max_length=80)
    gpu: str | None = Field(None, max_length=80)
    ram_gb: int | None = Field(None, ge=1, le=1024)
    vram_gb: int | None = Field(None, ge=0, le=256)
    storage_gb: int | None = Field(None, ge=0, le=100_000)
    os: Literal["windows", "linux", "macos"] | None = None

    @field_validator("cpu", "gpu")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        if v is None:
            return None
        from .security.sanitize import clean_text
        return clean_text(v, 80) or None


class ExplicitPrefsIn(Strict):
    likes: list[Token] = Field(default_factory=list, max_length=20)
    dislikes: list[Token] = Field(default_factory=list, max_length=20)

    @field_validator("likes", "dislikes")
    @classmethod
    def _tokens(cls, v: list[str]) -> list[str]:
        return [re.sub(r"\s+", "-", t) for t in v]
