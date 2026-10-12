"""User-saved analyses: the "Save" button in the UI (shown on the Stored Analyses page)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_kb, get_visual_layers
from app.core.errors import AppError, InvalidRequestError, NotFoundError
from app.database.session import get_db
from app.models import AnalysisRun, Event
from app.models.saved import SavedAnalysis
from app.schemas.api import ErrorResponse
from app.schemas.saved import SaveAnalysisRequest, SavedAnalysisOut
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.reports import service as reports

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/saved-analyses", tags=["saved analyses"])
ERRORS = {404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
USABLE = ("COMPLETED", "PARTIAL")


def _out(s: SavedAnalysis, ev: Event, run: AnalysisRun, **extra) -> SavedAnalysisOut:
    return SavedAnalysisOut(
        id=s.id, event_id=ev.id, analysis_id=run.id, title=s.title, event_type=ev.event_type,
        is_simulated=ev.is_simulated or run.mode == "SIMULATED", mode=run.mode, run_status=run.status,
        finished_at=run.finished_at, graph_stats=run.graph_stats, report_id=s.report_id,
        report_status="STORED" if s.report_id else "UNAVAILABLE", note=s.note, saved_by=s.saved_by,
        saved_at=s.created_at, **extra)


@router.post("", response_model=SavedAnalysisOut, status_code=status.HTTP_201_CREATED, responses=ERRORS)
def save_analysis(req: SaveAnalysisRequest, response: Response, db: Session = Depends(get_db),
                  kb: KnowledgeBase = Depends(get_kb), layers: dict = Depends(get_visual_layers)) -> SavedAnalysisOut:
    """Save a finished analysis run and snapshot its 12-section report. Saving the same run again returns the
    existing entry (200, ``already_saved: true``) instead of creating a duplicate."""
    run = db.get(AnalysisRun, req.analysis_id)
    if run is None or run.event_id is None:
        raise NotFoundError(f"analysis run {req.analysis_id} not found")
    if run.status not in USABLE:
        raise InvalidRequestError(f"analysis run {run.id} is {run.status}; only COMPLETED or PARTIAL runs can be saved")
    ev = db.get(Event, run.event_id)
    existing = db.scalar(select(SavedAnalysis).where(SavedAnalysis.analysis_run_id == run.id))
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return _out(existing, ev, run, already_saved=True)

    report_id, reason = None, None
    try:  # the report service commits its own row; identical sources reuse the stored report
        report_id = reports.create_report(db, kb, layers, "event", run.id).report_id
    except AppError as exc:
        db.rollback()
        reason = exc.message
        log.warning("Saved analysis %s without report: %s", run.id, exc.message)

    saved = SavedAnalysis(event_id=ev.id, analysis_run_id=run.id, report_id=report_id, title=ev.title,
                          note=req.note, saved_by=(req.saved_by or None))
    db.add(saved)
    try:
        db.commit()
    except IntegrityError:  # a concurrent save of the same run won
        db.rollback()
        saved = db.scalar(select(SavedAnalysis).where(SavedAnalysis.analysis_run_id == run.id))
        response.status_code = status.HTTP_200_OK
        return _out(saved, ev, run, already_saved=True)
    return _out(saved, ev, run, report_unavailable_reason=reason)


@router.get("", response_model=list[SavedAnalysisOut])
def list_saved(analysis_id: str | None = None, limit: int = Query(100, ge=1, le=500),
               db: Session = Depends(get_db)) -> list[SavedAnalysisOut]:
    """Saved analyses, newest first (optionally only the one for ``analysis_id``)."""
    stmt = (select(SavedAnalysis, Event, AnalysisRun)
            .join(Event, Event.id == SavedAnalysis.event_id)
            .join(AnalysisRun, AnalysisRun.id == SavedAnalysis.analysis_run_id)
            .order_by(SavedAnalysis.created_at.desc()).limit(limit))
    if analysis_id:
        stmt = stmt.where(SavedAnalysis.analysis_run_id == analysis_id)
    return [_out(s, ev, run) for s, ev, run in db.execute(stmt).all()]


@router.delete("/{saved_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def remove_saved(saved_id: str, db: Session = Depends(get_db)) -> Response:
    """Remove a saved entry. The analysis run and its report stay stored."""
    s = db.get(SavedAnalysis, saved_id)
    if s is None:
        raise NotFoundError(f"saved analysis {saved_id} not found")
    db.delete(s)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
