from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, new_id, utcnow
from app.domain import ArticleStatus


class Article(TimestampMixin, Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("provider", "provider_article_id", name="uq_articles_provider_article"),
        Index("ix_articles_status_published", "processing_status", "published_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_article_id: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(Text)
    # Hash of the normalised URL (or of provider+headline when no URL) used for deduplication.
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(255))
    source_domain: Mapped[str | None] = mapped_column(String(255), index=True)
    source_country: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str | None] = mapped_column(String(20))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(20), default=ArticleStatus.PENDING, nullable=False)
    filter_reason: Mapped[str | None] = mapped_column(Text)
    prefilter_score: Mapped[float | None] = mapped_column(Float)
    # True for fixture/demo articles; such articles must never be presented as real news.
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # USER_SUPPLIED articles come from POST /api/events/analyze rather than a news provider.
    input_origin: Mapped[str] = mapped_column(String(20), default="NEWS_PROVIDER", nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    event_links: Mapped[list["EventArticle"]] = relationship(back_populates="article")  # noqa: F821

    @property
    def text_for_analysis(self) -> str:
        parts = [self.headline, self.description or "", self.content or ""]
        return "\n\n".join(p for p in parts if p)


class IngestionRun(Base):
    """One invocation of news ingestion (for auditability of what was fetched when)."""

    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    query: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="RUNNING", nullable=False)
    fetched_count: Mapped[int] = mapped_column(default=0)
    inserted_count: Mapped[int] = mapped_column(default=0)
    duplicate_count: Mapped[int] = mapped_column(default=0)
    invalid_count: Mapped[int] = mapped_column(default=0)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
