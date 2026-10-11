"""Shared read queries used by the API layer."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import AnalysisRun, Event


def paginate(session: Session, stmt: Select, page: int, page_size: int) -> tuple[list[Any], int]:
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), int(total)


def get_event_or_404(session: Session, event_id: str) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise NotFoundError(f"event {event_id} not found")
    return event


def get_run_for_event(session: Session, event: Event, analysis_id: str | None = None,
                      *, require: bool = True) -> AnalysisRun | None:
    """The requested run, else the event's latest finished run (COMPLETED/PARTIAL)."""
    if analysis_id:
        run = session.get(AnalysisRun, analysis_id)
        if run is None or run.event_id != event.id:
            raise NotFoundError(f"analysis {analysis_id} not found for event {event.id}")
        return run
    run = session.get(AnalysisRun, event.latest_analysis_id) if event.latest_analysis_id else None
    if run is None:
        run = session.scalar(
            select(AnalysisRun).where(AnalysisRun.event_id == event.id,
                                      AnalysisRun.status.in_(["COMPLETED", "PARTIAL"]))
            .order_by(AnalysisRun.created_at.desc()).limit(1))
    if run is None and require:
        raise NotFoundError(f"event {event.id} has no completed analysis yet",
                            details={"hint": f"POST /api/events/{event.id}/analyze"})
    return run
