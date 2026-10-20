import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, REAL as Real, SmallInteger, String, Text, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBED_DIM = 768


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(40))
    plan: Mapped[str] = mapped_column(String, default="free")
    role: Mapped[str] = mapped_column(String, default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Game(Base):
    __tablename__ = "games"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    developer: Mapped[str | None] = mapped_column(String)
    release_date: Mapped[date | None] = mapped_column(Date)
    price_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String, default="USD")
    platforms: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    genres: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    features: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    avg_duration_hours: Mapped[float | None] = mapped_column(Real)
    difficulty: Mapped[int | None] = mapped_column(SmallInteger)
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    cover_url: Mapped[str | None] = mapped_column(Text)
    req: Mapped[dict] = mapped_column(JSONB, default=dict)
    source: Mapped[str] = mapped_column(String, default="seed")
    search = mapped_column(TSVECTOR, deferred=True)


class GameEmbedding(Base):
    __tablename__ = "game_embeddings"
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), primary_key=True)
    embedding = mapped_column(Vector(EMBED_DIM))
    doc_hash: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)


class Wishlist(Base):
    __tablename__ = "wishlist"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Library(Base):
    __tablename__ = "library"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String, default="owned")
    playtime_minutes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Rating(Base):
    __tablename__ = "ratings"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), primary_key=True)
    score: Mapped[int] = mapped_column(SmallInteger)
    review: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserEvent(Base):
    __tablename__ = "user_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    game_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String)
    query: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PreferenceProfile(Base):
    __tablename__ = "preference_profiles"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    weights: Mapped[dict] = mapped_column(JSONB, default=dict)
    explicit: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HardwareProfile(Base):
    __tablename__ = "hardware_profiles"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    cpu: Mapped[str | None] = mapped_column(String(80))
    gpu: Mapped[str | None] = mapped_column(String(80))
    cpu_tier: Mapped[int | None] = mapped_column(SmallInteger)
    gpu_tier: Mapped[int | None] = mapped_column(SmallInteger)
    ram_gb: Mapped[int | None] = mapped_column(SmallInteger)
    vram_gb: Mapped[int | None] = mapped_column(SmallInteger)
    storage_gb: Mapped[int | None] = mapped_column(Integer)
    os: Mapped[str | None] = mapped_column(String)


class UsageLog(Base):
    __tablename__ = "usage_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String)
    endpoint: Mapped[str | None] = mapped_column(String)
    provider: Mapped[str | None] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_micro_usd: Mapped[int] = mapped_column(Integer, default=0)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String)
    ip_hash: Mapped[str | None] = mapped_column(String)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
