from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class SimulationRun(TimestampMixin, Base):
    """One Black Swan simulator run: the user's hypothetical assumptions plus the versioned result.

    The result stores the scenario-specific subgraph (not the whole knowledge base) together with the
    model / knowledge-base / scenario-catalog versions that produced it. request_hash identifies identical
    requests under identical versions so they can be served from the stored result.
    """

    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    prediction_status: Mapped[str] = mapped_column(String(40), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(100))
    knowledge_base_version: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_catalog_version: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
