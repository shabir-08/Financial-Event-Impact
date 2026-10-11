"""Analysis report endpoints: 12-section reports for event analyses and Black Swan simulations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_kb, get_visual_layers
from app.database.session import get_db
from app.schemas.api import ErrorResponse
from app.schemas.report import CreateReportRequest, Report, ReportListItem
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.reports import service

router = APIRouter(prefix="/api/reports", tags=["reports"])
ERRORS = {404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


@router.post("", response_model=Report, status_code=status.HTTP_201_CREATED, responses=ERRORS)
def create_report(req: CreateReportRequest, db: Session = Depends(get_db), kb: KnowledgeBase = Depends(get_kb),
                  layers: dict = Depends(get_visual_layers)) -> Report:
    """Assemble and store a report from a stored analysis run (kind=event) or simulation (kind=simulation).
    Identical source and versions return the stored report (`cached: true`)."""
    return service.create_report(db, kb, layers, req.kind, req.source_id)


@router.get("", response_model=list[ReportListItem])
def list_reports(source_id: str | None = None, limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)) -> list[ReportListItem]:
    return [ReportListItem(report_id=r.id, kind=r.kind, source_id=r.source_id, title=r.title, created_at=r.created_at.isoformat())
            for r in service.list_reports(db, source_id, limit)]


@router.get("/{report_id}", response_model=Report, responses=ERRORS)
def get_report(report_id: str, db: Session = Depends(get_db)) -> Report:
    return service.get_report(db, report_id)
