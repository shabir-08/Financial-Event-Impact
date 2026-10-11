from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, new_id, utcnow
from app.domain import RunStatus


class ExtractedClaim(TimestampMixin, Base):
    """A relationship stated in (or claimed from) a source article.

    Claims are extraction output; they become graph relationships only during analysis.
    ``source_mention`` may be the literal ``EVENT`` meaning "the event itself".
    """

    __tablename__ = "extracted_claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    source_mention: Mapped[str] = mapped_column(String(500), nullable=False)
    target_mention: Mapped[str] = mapped_column(String(500), nullable=False)
    source_entity_id: Mapped[str | None] = mapped_column(String(120))
    target_entity_id: Mapped[str | None] = mapped_column(String(120))
    relationship_type: Mapped[str] = mapped_column(String(40), nullable=False)
    effect_sign: Mapped[int] = mapped_column(Integer, nullable=False)
    mechanism: Mapped[str | None] = mapped_column(Text)
    passage: Mapped[str | None] = mapped_column(Text)
    passage_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extraction_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    is_primary_effect: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(40), nullable=False)

    event: Mapped["Event"] = relationship(back_populates="claims")  # noqa: F821


class AnalysisRun(TimestampMixin, Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    article_id: Mapped[str | None] = mapped_column(ForeignKey("articles.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.PENDING, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # RunMode
    trigger: Mapped[str] = mapped_column(String(30), nullable=False)
    analysis_version: Mapped[str] = mapped_column(String(40), nullable=False)
    knowledge_base_version: Mapped[str | None] = mapped_column(String(64))
    llm_provider: Mapped[str] = mapped_column(String(40), nullable=False)
    llm_model: Mapped[str | None] = mapped_column(String(100))
    market_data_provider: Mapped[str | None] = mapped_column(String(40))
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graph_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graph_stats: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    explanation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    explanation_status: Mapped[str | None] = mapped_column(String(30))

    relationships: Mapped[list["Relationship"]] = relationship(
        back_populates="analysis_run", cascade="all, delete-orphan"
    )
    nodes: Mapped[list["GraphNode"]] = relationship(cascade="all, delete-orphan")
    paths: Mapped[list["ImpactPath"]] = relationship(cascade="all, delete-orphan", order_by="ImpactPath.rank")
    asset_impacts: Mapped[list["AssetImpact"]] = relationship(cascade="all, delete-orphan")
    observations: Mapped[list["MarketObservation"]] = relationship(cascade="all, delete-orphan")


class GraphNode(Base):
    __tablename__ = "graph_nodes"
    __table_args__ = (UniqueConstraint("analysis_run_id", "node_id", name="uq_graph_nodes_run_node"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_id: Mapped[str] = mapped_column(String(120), nullable=False)
    node_type: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    origin: Mapped[str] = mapped_column(String(20), nullable=False)
    on_impact_path: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    centrality: Mapped[float | None] = mapped_column(Float)
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)


class Relationship(TimestampMixin, Base):
    """A scored, directed graph edge produced for one analysis run."""

    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "source_node_id", "target_node_id", name="uq_relationships_run_edge"),
        Index("ix_relationships_event", "event_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    source_node_id: Mapped[str] = mapped_column(String(120), nullable=False)
    target_node_id: Mapped[str] = mapped_column(String(120), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(40), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # EdgeDirection
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # EdgeStatus
    origin: Mapped[str] = mapped_column(String(20), nullable=False)  # RelationshipOrigin
    kb_rule_id: Mapped[str | None] = mapped_column(String(120))
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("extracted_claims.id", ondelete="SET NULL"))
    mechanism: Mapped[str | None] = mapped_column(Text)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    time_horizon: Mapped[str | None] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_strength: Mapped[float] = mapped_column(Float, nullable=False)
    economic_relevance: Mapped[float] = mapped_column(Float, nullable=False)
    historical_support: Mapped[float | None] = mapped_column(Float)
    historical_support_status: Mapped[str] = mapped_column(String(30), nullable=False)
    applicability: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    score_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="relationships")
    evidence: Mapped[list["RelationshipEvidence"]] = relationship(
        back_populates="relationship", cascade="all, delete-orphan"
    )


class RelationshipEvidence(Base):
    __tablename__ = "relationship_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    relationship_id: Mapped[str] = mapped_column(
        ForeignKey("relationships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ARTICLE_PASSAGE | KNOWLEDGE_BASE_RATIONALE | HISTORICAL_COMPARISON
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False)
    article_id: Mapped[str | None] = mapped_column(ForeignKey("articles.id", ondelete="SET NULL"))
    passage: Mapped[str | None] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    relationship: Mapped[Relationship] = relationship(back_populates="evidence")


class ImpactPath(Base):
    __tablename__ = "impact_paths"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    target_asset_id: Mapped[str] = mapped_column(String(120), nullable=False)
    node_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    relationship_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    path_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    net_sign: Mapped[int] = mapped_column(Integer, nullable=False)
    impact_direction: Mapped[str] = mapped_column(String(40), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    uncertainties: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class AssetImpact(Base):
    __tablename__ = "asset_impacts"
    __table_args__ = (UniqueConstraint("analysis_run_id", "asset_id", name="uq_asset_impacts_run_asset"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(120), nullable=False)
    impact_direction: Mapped[str] = mapped_column(String(40), nullable=False)
    best_path_score: Mapped[float] = mapped_column(Float, nullable=False)
    path_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    uncertainty: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    market_data_status: Mapped[str] = mapped_column(String(30), nullable=False)
    market_data_reason_code: Mapped[str | None] = mapped_column(String(40))  # quality.LimitationCode
    historical_comparison: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class MarketData(Base):
    """Cached daily bars from a market-data provider (never fabricated)."""

    __tablename__ = "market_data"
    __table_args__ = (
        UniqueConstraint("asset_id", "provider", "trade_date", name="uq_market_data_bar"),
        Index("ix_market_data_asset_date", "asset_id", "trade_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(10))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MarketObservation(Base):
    """Event-window return for one asset around one (current or historical) event."""

    __tablename__ = "market_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[str] = mapped_column(String(120), nullable=False)
    # CURRENT_EVENT observations are the observed reaction; HISTORICAL_EVENT ones feed
    # historical support. They are kept distinct on purpose.
    observation_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    historical_event_id: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(40))  # quality.LimitationCode
    provider: Mapped[str | None] = mapped_column(String(40))
    symbol: Mapped[str | None] = mapped_column(String(80))
    anchor_date: Mapped[date | None] = mapped_column(Date)
    reference_date: Mapped[date | None] = mapped_column(Date)
    reference_close: Mapped[float | None] = mapped_column(Float)
    windows: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
