from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, new_id


class Entity(TimestampMixin, Base):
    """Canonical entity registry. ``id`` is a stable typed identifier such as
    ``commodity:crude_oil`` or ``asset:usdinr``; it is also the graph node id."""

    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_name: Mapped[str | None] = mapped_column(String(255))
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    external_ids: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    country: Mapped[str | None] = mapped_column(String(80))
    # Variable node that represents "the level/price of" this entity (e.g. crude oil -> crude oil price).
    effect_variable: Mapped[str | None] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(40), default="KNOWLEDGE_BASE", nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)


class EventEntity(TimestampMixin, Base):
    """An entity mention extracted for an event, before/after normalisation."""

    __tablename__ = "event_entities"
    __table_args__ = (
        UniqueConstraint("event_id", "article_id", "mention_text", "entity_type", name="uq_event_entities_mention"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    article_id: Mapped[str | None] = mapped_column(ForeignKey("articles.id", ondelete="SET NULL"), index=True)
    entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    mention_text: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    origin: Mapped[str] = mapped_column(String(20), nullable=False)  # EntityOrigin
    normalization_status: Mapped[str] = mapped_column(String(20), nullable=False)
    normalization_method: Mapped[str | None] = mapped_column(String(80))
    candidate_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence_passage: Mapped[str | None] = mapped_column(Text)
    passage_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    extraction_version: Mapped[str] = mapped_column(String(40), nullable=False)

    event: Mapped["Event"] = relationship(back_populates="entity_mentions")  # noqa: F821
    entity: Mapped[Entity | None] = relationship()


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(ForeignKey("entities.id"), primary_key=True)
    asset_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(10))
    country: Mapped[str | None] = mapped_column(String(80))
    exchange: Mapped[str | None] = mapped_column(String(80))
    exchange_timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    # For yield instruments a +1% move is a yield rise, i.e. a bond PRICE fall.
    quote_semantics: Mapped[str | None] = mapped_column(Text)

    symbols: Mapped[list["AssetSymbol"]] = relationship(back_populates="asset", cascade="all, delete-orphan")


class AssetSymbol(Base):
    """Provider-specific symbol for an internal asset id (one per provider)."""

    __tablename__ = "asset_symbols"
    __table_args__ = (
        UniqueConstraint("provider", "symbol", name="uq_asset_symbols_provider_symbol"),
        UniqueConstraint("asset_id", "provider", name="uq_asset_symbols_asset_provider"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="symbols")
