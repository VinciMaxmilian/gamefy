from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlanLimits(BaseModel):
    """Per-plan quotas. All numbers are configurable via the PLAN_LIMITS env var (JSON)."""

    requests_per_minute: int
    smart_search_per_day: int
    ai_chat_per_day: int
    ai_tokens_per_day: int


class RecoWeights(BaseModel):
    """Final-ranking weights (RECO_WEIGHTS env var, JSON). Need not sum to 1."""

    semantic_similarity: float = 0.30
    user_preference: float = 0.20
    genre_match: float = 0.10
    tag_match: float = 0.08
    gameplay_match: float = 0.07
    rating: float = 0.10
    platform_compatibility: float = 0.05
    price_match: float = 0.05
    duration_match: float = 0.05


def _default_plans() -> dict[str, PlanLimits]:
    return {
        "visitor": PlanLimits(requests_per_minute=60, smart_search_per_day=0, ai_chat_per_day=0, ai_tokens_per_day=0),
        "free": PlanLimits(requests_per_minute=120, smart_search_per_day=5, ai_chat_per_day=0, ai_tokens_per_day=0),
        "premium": PlanLimits(requests_per_minute=240, smart_search_per_day=200, ai_chat_per_day=100, ai_tokens_per_day=200_000),
        "admin": PlanLimits(requests_per_minute=1000, smart_search_per_day=5000, ai_chat_per_day=5000, ai_tokens_per_day=5_000_000),
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str = ""
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    supabase_jwt_secret: str = ""

    gemini_api_key: str = ""
    gemini_embed_model: str = "gemini-embedding-001"
    gemini_chat_model: str = "gemini-2.5-flash"
    embed_dim: int = 768
    # USD per 1M input tokens, used only for cost telemetry.
    embed_cost_per_mtok_usd: float = 0.15

    cors_origins: str = "http://localhost:5173"
    cookie_secure: bool = False
    max_body_bytes: int = 64 * 1024
    trusted_ip_header: str = "x-nf-client-connection-ip"

    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""

    plan_limits: dict[str, PlanLimits] = _default_plans()
    reco_weights: RecoWeights = RecoWeights()
    # Half-life (days) for behaviour signals in the preference profile.
    profile_half_life_days: float = 45.0
    # AI guard rails (used by the generative layer; chat is not enabled in the MVP).
    ai_max_message_chars: int = 1000
    ai_max_context_chars: int = 12_000
    ai_timeout_seconds: float = 12.0

    @property
    def is_prod(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        elif url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        return url

    def limits_for(self, plan: str) -> PlanLimits:
        return self.plan_limits.get(plan) or self.plan_limits["free"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
