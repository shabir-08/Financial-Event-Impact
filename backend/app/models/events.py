from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, new_id
from app.domain import VerificationStatus


class Event(TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_type_date", "event_type", "event_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    event_date: Mapped[date | None] = mapped_column(Date)
    # Earliest publication timestamp among associated articles: the information time
    # used to anchor market event windows.
    first_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    countries: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reported_figures: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    primary_effects: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    financial_relevance: Mapped[float | None] = mapped_column(Float)
    relevance_rationale: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(
        String(20), default=VerificationStatus.SINGLE_SOURCE, nullable=False
    )
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(40), nullable=False)
    llm_provider: Mapped[str] = mapped_column(String(40), nullable=False)
    llm_model: Mapped[str | None] = mapped_column(String(100))
    latest_analysis_id: Mapped[str | None] = mapped_column(String(36))
    processing_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    article_links: Mapped[list["EventArticle"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    entity_mentions: Mapped[list["EventEntity"]] = relationship(  # noqa: F821
        back_populates="event", cascade="all, delete-orphan"
    )
    claims: Mapped[list["ExtractedClaim"]] = relationship(  # noqa: F821
        back_populates="event", cascade="all, delete-orphan"
    )


class EventArticle(Base):
    __tablename__ = "event_articles"
    __table_args__ = (UniqueConstraint("event_id", "article_id", name="uq_event_articles_pair"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    article_id: Mapped[str] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="PRIMARY", nullable=False)
    supporting_passages: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    association_reason: Mapped[str | None] = mapped_column(Text)

    event: Mapped[Event] = relationship(back_populates="article_links")
    article: Mapped["Article"] = relationship(back_populates="event_links")  # noqa: F821


class HistoricalEvent(TimestampMixin, Base):
    """Reference events used for historical market-reaction comparisons.

    ``source_type`` is CURATED_REFERENCE for seeded well-known events, or SYSTEM_DETECTED
    for events this system analysed itself (linked via ``event_id``).
    """

    __tablename__ = "historical_events"
    __table_args__ = (Index("ix_historical_events_type_date", "event_type", "event_date"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    entity_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    primary_effects: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text)
    verification_note: Mapped[str | None] = mapped_column(Text)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
