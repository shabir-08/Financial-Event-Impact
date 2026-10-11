"""Event Lineage tables: canonical nodes per analysis, impact/half-life parameters, inferred event links.

Links are inferred from overlapping graph nodes; they are not causal claims. The per-event graphs
(graph_nodes / relationships) stay the source of truth and are never copied or modified here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, new_id, utcnow

JSONType = JSON().with_variant(JSONB(), "postgresql")


class EventNode(Base):
    """A canonical graph node of one event analysis, with its derived role and normalised weight."""

    __tablename__ = "event_nodes"
    __table_args__ = (Index("ix_event_nodes_node_id", "node_id"),)

    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), primary_key=True)
    node_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    node_type: Mapped[str] = mapped_column(String(40), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # trigger | intermediate | asset | context
    role_source: Mapped[str] = mapped_column(String(40), nullable=False)
    # max path score through the node / the event's best path score; NULL when the node is on no ranked path
    weight: Mapped[float | None] = mapped_column(Float)


class EventImpact(Base):
    __tablename__ = "event_impact"

    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), primary_key=True)
    impact: Mapped[float] = mapped_column(Float, nullable=False)
    half_life_days: Mapped[float | None] = mapped_column(Float)  # NULL: category has no configured half-life
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    knowledge_base_version: Mapped[str | None] = mapped_column(String(64))
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class EventLink(Base):
    """An inferred relationship child -> earlier event (PARENT / DUPLICATE / ANALOGUE)."""

    __tablename__ = "event_links"
    __table_args__ = (
        UniqueConstraint("child_event_id", "parent_event_id", "analysis_run_id", name="uq_event_links_pair_run"),
        CheckConstraint("child_event_id <> parent_event_id", name="no_self_link"),
        Index("ix_event_links_child_active", "child_event_id", "is_active"),
        Index("ix_event_links_parent_active", "parent_event_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    parent_event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    # the child's analysis run that produced the link
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    parent_analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id", ondelete="SET NULL"))
    link_type: Mapped[str] = mapped_column(String(20), nullable=False)  # PARENT | DUPLICATE | ANALOGUE
    score: Mapped[float] = mapped_column(Float, nullable=False)
    effective_strength: Mapped[float | None] = mapped_column(Float)
    gap_days: Mapped[float] = mapped_column(Float, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    shared_nodes: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    knowledge_base_version: Mapped[str | None] = mapped_column(String(64))
    method_version: Mapped[str] = mapped_column(String(40), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow,
                                                 nullable=False)
