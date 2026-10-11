"""Event Lineage: inferred related-event graph for one event (query-time view, read only)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_kb
from app.database.session import get_db
from app.repositories.queries import get_event_or_404
from app.schemas.lineage import LineageResponse
from app.services.lineage.config import get_lineage_config
from app.services.lineage.query import lineage_view
from app.services.relationships.knowledge_base import KnowledgeBase

router = APIRouter(prefix="/api/events", tags=["event lineage"])


@router.get("/{event_id}/lineage", response_model=LineageResponse)
def event_lineage(
    event_id: str,
    direction: Literal["ancestors", "descendants", "both"] = "ancestors",
    min_strength: float | None = Query(None, ge=0.0, le=1.0,
                                       description="Minimum multiplicative path strength (default from config: 0.10)"),
    max_depth: int | None = Query(None, ge=1, le=10, description="Maximum link depth (default from config: 6)"),
    as_of: datetime | None = Query(None, description="ISO-8601 timestamp; default now (UTC). Naive = UTC."),
    include_expired: bool = True,
    db: Session = Depends(get_db),
    kb: KnowledgeBase = Depends(get_kb),
) -> dict:
    """Related earlier (and/or later) events inferred from shared canonical graph nodes, with the
    merged Cytoscape graph (``graph.elements``). Links are inferred relationships, not causal claims."""
    cfg = get_lineage_config()
    event = get_event_or_404(db, event_id)
    return lineage_view(db, event, kb, cfg, direction=direction,
                        min_strength=cfg.paths.min_path_strength if min_strength is None else min_strength,
                        max_depth=cfg.paths.max_depth if max_depth is None else max_depth,
                        as_of=as_of, include_expired=include_expired)
