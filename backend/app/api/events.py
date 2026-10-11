from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_pipeline, run_analysis_job
from app.database.session import get_db
from app.models import Article, Event, EventArticle
from app.repositories.queries import get_event_or_404, paginate
from app.schemas.api import (
    AnalysisAccepted,
    AnalyzeRequest,
    ArticleOut,
    EventArticleOut,
    EventDetail,
    EventSummary,
    ManualEventRequest,
    Page,
)
from app.services.news.base import NormalizedArticle
from app.services.news.ingestion import store_articles
from app.services.pipeline import AnalysisPipeline

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=Page[EventSummary])
def list_events(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    event_type: str | None = None, verification_status: str | None = None,
    simulated: bool | None = None, country: str | None = None,
) -> Page[EventSummary]:
    stmt = select(Event).order_by(Event.first_reported_at.desc().nullslast(), Event.created_at.desc())
    if event_type:
        stmt = stmt.where(Event.event_type == event_type.upper())
    if verification_status:
        stmt = stmt.where(Event.verification_status == verification_status.upper())
    if simulated is not None:
        stmt = stmt.where(Event.is_simulated == simulated)
    items, total = paginate(db, stmt, page, page_size)
    if country:  # JSON list filter applied in Python for portability across databases
        items = [e for e in items if country.lower() in {c.lower() for c in e.countries}]
    return Page[EventSummary](items=[EventSummary.model_validate(e) for e in items], page=page,
                              page_size=page_size, total=total)


@router.get("/{event_id}", response_model=EventDetail)
def get_event(event_id: str, db: Session = Depends(get_db)) -> EventDetail:
    ev = get_event_or_404(db, event_id)
    links = db.scalars(select(EventArticle).where(EventArticle.event_id == ev.id)).all()
    detail = EventDetail.model_validate(ev)
    detail.articles = [EventArticleOut(article=ArticleOut.model_validate(db.get(Article, l.article_id)), role=l.role,
                                       supporting_passages=l.supporting_passages,
                                       association_reason=l.association_reason) for l in links]
    return detail


@router.post("/analyze", response_model=AnalysisAccepted,
             responses={202: {"model": AnalysisAccepted}, 200: {"model": AnalysisAccepted}})
async def analyze_supplied_text(req: ManualEventRequest, background: BackgroundTasks, response: Response,
                                db: Session = Depends(get_db),
                                pipeline: AnalysisPipeline = Depends(get_pipeline)) -> AnalysisAccepted:
    """Analyse an explicitly supplied article/scenario.

    This is a controlled-input path, separate from automated news ingestion: the text is stored
    with ``input_origin=USER_SUPPLIED`` (and ``is_simulated`` if requested) and the resulting event
    is labelled USER_SUPPLIED or SIMULATED - never presented as provider-sourced news.
    """
    na = NormalizedArticle(
        provider="manual_input", provider_article_id=None, headline=req.headline, content=req.body or None,
        source_name=req.source_name or "User-supplied input", url=str(req.url) if req.url else None,
        published_at=req.published_at or datetime.now(timezone.utc), is_simulated=req.simulated,
        metadata={"submitted_via": "POST /api/events/analyze"},
    )
    _, _, ids = store_articles(db, [na], input_origin="USER_SUPPLIED")
    article_id = ids[0]
    if not req.wait:
        result, _ = await pipeline.process_article(article_id, trigger="API_SUPPLIED_TEXT",
                                                   skip_prefilter=req.skip_prefilter, analyze=False)
        if result.event_id is None:
            return AnalysisAccepted(analysis_id=None, event_id=None, article_id=article_id,
                                    status=result.status.value, detail=result.reason)
        run = pipeline.create_run(result.event_id, trigger="API_SUPPLIED_TEXT", article_id=article_id)
        background.add_task(run_analysis_job, run.id)
        response.status_code = status.HTTP_202_ACCEPTED
        return AnalysisAccepted(analysis_id=run.id, event_id=result.event_id, article_id=article_id, status="PENDING")
    result, run = await pipeline.process_article(article_id, trigger="API_SUPPLIED_TEXT",
                                                 skip_prefilter=req.skip_prefilter, analyze=True)
    return AnalysisAccepted(analysis_id=run.id if run else None, event_id=result.event_id, article_id=article_id,
                            status=run.status if run else result.status.value, detail=result.reason)


@router.post("/{event_id}/analyze", response_model=AnalysisAccepted, status_code=status.HTTP_202_ACCEPTED)
async def analyze_event(event_id: str, background: BackgroundTasks, response: Response,
                        req: AnalyzeRequest | None = None, db: Session = Depends(get_db),
                        pipeline: AnalysisPipeline = Depends(get_pipeline)) -> AnalysisAccepted:
    """Run (or schedule) a new analysis for a stored event. Poll GET /api/analysis/{analysis_id}."""
    get_event_or_404(db, event_id)
    run = pipeline.create_run(event_id, trigger="API_ANALYZE_EVENT")
    if req and req.wait:
        run = await pipeline.run(run.id)
        response.status_code = status.HTTP_200_OK
        return AnalysisAccepted(analysis_id=run.id, event_id=event_id, status=run.status)
    background.add_task(run_analysis_job, run.id)
    return AnalysisAccepted(analysis_id=run.id, event_id=event_id, status="PENDING")
