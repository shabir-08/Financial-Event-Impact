from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_pipeline, process_articles_job
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.database.session import get_db
from app.models import Article
from app.repositories.queries import paginate
from app.schemas.api import ArticleOut, IngestRequest, IngestResponse, Page, ProcessArticleResponse
from app.services.news.ingestion import IngestionService, build_news_provider
from app.services.pipeline import AnalysisPipeline

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("", response_model=Page[ArticleOut])
def list_articles(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    processing_status: str | None = Query(None, alias="status"),
    provider: str | None = None, simulated: bool | None = None,
    q: str | None = Query(None, max_length=200, description="Case-insensitive headline/description search"),
) -> Page[ArticleOut]:
    stmt = select(Article).order_by(Article.published_at.desc().nullslast(), Article.retrieved_at.desc())
    if processing_status:
        stmt = stmt.where(Article.processing_status == processing_status.upper())
    if provider:
        stmt = stmt.where(Article.provider == provider)
    if simulated is not None:
        stmt = stmt.where(Article.is_simulated == simulated)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Article.headline.ilike(like), Article.description.ilike(like)))
    items, total = paginate(db, stmt, page, page_size)
    return Page[ArticleOut](items=[ArticleOut.model_validate(a) for a in items], page=page, page_size=page_size, total=total)


@router.get("/news-sources")
def news_sources(settings: Settings = Depends(get_settings)) -> dict:
    """News sources the backend can ingest from (no credentials are returned)."""
    from app.services.news.rss import parse_feed_config

    feeds = parse_feed_config(settings.rss_feeds)
    finnhub_ok = bool(settings.finnhub_api_key and settings.finnhub_api_key.get_secret_value())
    return {"default_provider": settings.news_provider, "providers": [
        {"id": "rss", "name": "Publisher RSS feeds", "configured": bool(feeds), "needs_key": False,
         "live": True, "note": "Headline, summary and link from each publisher's official feed; no API key.",
         "feeds": [{"key": f.key, "name": f.name, "url": f.url} for f in feeds]},
        {"id": "gdelt", "name": "GDELT (global news index)", "configured": True, "needs_key": False, "live": True,
         "note": "Free; limited to one request every 5 seconds per IP and may throttle for longer."},
        {"id": "finnhub", "name": "Finnhub market news", "configured": finnhub_ok, "needs_key": True, "live": True,
         "note": "Requires FINNHUB_API_KEY." if not finnhub_ok else "Configured."},
    ]}


@router.get("/{article_id}", response_model=ArticleOut)
def get_article(article_id: str, db: Session = Depends(get_db)) -> ArticleOut:
    art = db.get(Article, article_id)
    if art is None:
        raise NotFoundError(f"article {article_id} not found")
    return ArticleOut.model_validate(art)


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_200_OK)
async def ingest(req: IngestRequest, background: BackgroundTasks, db: Session = Depends(get_db),
                 settings: Settings = Depends(get_settings)) -> IngestResponse:
    """Fetch from the configured (or requested) news provider, normalise, deduplicate and store."""
    provider = build_news_provider(settings, req.provider, feeds=req.feeds)
    summary = await IngestionService(db, provider).ingest(query=req.query, limit=req.limit)
    processing = "not_requested"
    if req.process and summary.inserted:
        new_ids = [i for i in summary.article_ids
                   if db.get(Article, i) is not None and db.get(Article, i).processing_status == "PENDING"]
        background.add_task(process_articles_job, new_ids, req.analyze)
        processing = "scheduled"
    return IngestResponse(ingestion_run_id=summary.ingestion_run_id, provider=summary.provider,
                          fetched=summary.fetched, inserted=summary.inserted, duplicates=summary.duplicates,
                          invalid=summary.invalid, article_ids=summary.article_ids, processing=processing,
                          notes=summary.notes or [])


@router.post("/{article_id}/process", response_model=ProcessArticleResponse)
async def process_article(article_id: str, analyze: bool = True, db: Session = Depends(get_db),
                          pipeline: AnalysisPipeline = Depends(get_pipeline)) -> ProcessArticleResponse:
    """Run event detection (and optionally analysis) for one stored article, synchronously."""
    if db.get(Article, article_id) is None:
        raise NotFoundError(f"article {article_id} not found")
    result, run = await pipeline.process_article(article_id, trigger="API_PROCESS_ARTICLE", analyze=analyze)
    return ProcessArticleResponse(article_id=result.article_id, status=result.status.value, event_id=result.event_id,
                                  merged_into_existing=result.merged_into_existing, reason=result.reason,
                                  analysis_id=run.id if run else None)
