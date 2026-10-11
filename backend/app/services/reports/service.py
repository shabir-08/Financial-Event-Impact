"""Create, persist and fetch analysis reports (shared envelope for event and simulation reports)."""

from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import InvalidRequestError, NotFoundError
from app.database.base import utcnow
from app.models import AnalysisRun, SimulationRun
from app.models.report import AnalysisReport
from app.schemas.report import Report
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.reports.common import GENERATOR
from app.services.reports.event_report import assemble_event_report
from app.services.reports.simulation_report import assemble_simulation_report


def create_report(session: Session, kb: KnowledgeBase, layers: dict, kind: str, source_id: str) -> Report:
    if kind == "event":
        run = session.get(AnalysisRun, source_id)
        if run is None:
            raise NotFoundError(f"analysis run {source_id} not found", details={"hint": "use an event's latest_analysis_id"})
        if run.status not in ("COMPLETED", "PARTIAL"):
            raise InvalidRequestError(f"analysis run {source_id} is {run.status}; reports need a COMPLETED or PARTIAL run",
                                      details={"errors": [{"field": "source_id", "error": "analysis_not_finished", "status": run.status}]})
        body = assemble_event_report(session, run, kb, layers)
    else:
        sim = session.get(SimulationRun, source_id)
        if sim is None:
            raise NotFoundError(f"simulation {source_id} not found")
        body = assemble_simulation_report(sim.result)
    versions = {**body["versions"], "generator": GENERATOR}
    content_hash = hashlib.sha256(json.dumps({"kind": kind, "source_id": source_id, "versions": versions},
                                             sort_keys=True, default=str).encode()).hexdigest()
    existing = session.scalar(select(AnalysisReport).where(AnalysisReport.content_hash == content_hash))
    if existing is not None:
        return Report.model_validate({**existing.report, "cached": True})
    rid = "rep_" + uuid.uuid4().hex[:16]
    report = Report(report_id=rid, kind=kind, source_id=source_id, title=body["title"], is_simulated_data=body["is_simulated_data"],
                    is_hypothetical=body["is_hypothetical"], sections=body["sections"], versions=versions,
                    created_at=utcnow().isoformat(), generator=GENERATOR)
    session.add(AnalysisReport(id=rid, kind=kind, source_id=source_id, title=report.title, content_hash=content_hash,
                               versions=versions, report=report.model_dump(mode="json")))
    try:
        session.commit()
    except IntegrityError:  # a concurrent identical request stored it first (unique content_hash)
        session.rollback()
        stored = session.scalar(select(AnalysisReport).where(AnalysisReport.content_hash == content_hash))
        return Report.model_validate({**stored.report, "cached": True})
    return report


def get_report(session: Session, report_id: str) -> Report:
    r = session.get(AnalysisReport, report_id)
    if r is None:
        raise NotFoundError(f"report {report_id} not found")
    return Report.model_validate(r.report)


def list_reports(session: Session, source_id: str | None, limit: int) -> list[AnalysisReport]:
    stmt = select(AnalysisReport).order_by(AnalysisReport.created_at.desc()).limit(limit)
    if source_id:
        stmt = stmt.where(AnalysisReport.source_id == source_id)
    return list(session.scalars(stmt))
