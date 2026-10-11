"""News ingestion: fetch from a provider, normalise, deduplicate and persist articles."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.database.base import utcnow
from app.domain import ArticleStatus
from app.models import Article, IngestionRun
from app.services.news.base import NewsProvider, NormalizedArticle
from app.services.text import canonical_url, domain_of, normalize_text, sha256_hex

log = logging.getLogger(__name__)


def build_news_provider(settings: Settings, name: str | None = None) -> NewsProvider:
    name = name or settings.news_provider
    if name == "gdelt":
        from app.services.news.gdelt import GDELTNewsProvider

        return GDELTNewsProvider(settings)
    if name == "finnhub":
        from app.services.news.finnhub import FinnhubNewsProvider

        return FinnhubNewsProvider(settings)
    if name == "fixture":
        from app.services.news.fixture import FixtureNewsProvider

        return FixtureNewsProvider()
    raise ValueError(f"Unknown news provider {name}")


def dedup_key(article: NormalizedArticle) -> str:
    """Same URL (after canonicalisation) => same article, regardless of provider.
    Without a URL, fall back to provider + normalised headline + publication date."""
    if article.url:
        return sha256_hex("url:" + canonical_url(article.url))
    day = article.published_at.date().isoformat() if article.published_at else "nodate"
    return sha256_hex(f"headline:{article.provider}:{normalize_text(article.headline)}:{day}")


@dataclass
class IngestionSummary:
    ingestion_run_id: str
    provider: str
    fetched: int
    inserted: int
    duplicates: int
    invalid: int
    article_ids: list[str]


class IngestionService:
    def __init__(self, session: Session, provider: NewsProvider) -> None:
        self.session = session
        self.provider = provider

    async def ingest(self, query: str | None = None, limit: int = 25) -> IngestionSummary:
        run = IngestionRun(provider=self.provider.name, query=query)
        self.session.add(run)
        self.session.commit()
        try:
            result = await self.provider.fetch(query=query, limit=limit)
        except AppError as exc:
            run.status, run.finished_at, run.error = "FAILED", utcnow(), exc.to_dict()
            self.session.commit()
            raise
        inserted, dupes, ids = store_articles(self.session, result.articles)
        run.query = result.query
        run.fetched_count = len(result.articles)
        run.inserted_count = len(inserted)
        run.duplicate_count = dupes
        run.invalid_count = result.invalid_count
        run.status, run.finished_at = "COMPLETED", utcnow()
        self.session.commit()
        return IngestionSummary(run.id, self.provider.name, len(result.articles), len(inserted), dupes,
                                result.invalid_count, ids)


def store_articles(session: Session, articles: list[NormalizedArticle],
                   input_origin: str = "NEWS_PROVIDER") -> tuple[list[str], int, list[str]]:
    """Persist articles, skipping duplicates. Returns (inserted_ids, duplicate_count, all_ids)."""
    inserted: list[str] = []
    all_ids: list[str] = []
    dupes = 0
    for na in articles:
        key = dedup_key(na)
        existing = session.scalar(select(Article).where(Article.dedup_key == key))
        if existing is None and na.provider_article_id:
            existing = session.scalar(
                select(Article).where(
                    Article.provider == na.provider, Article.provider_article_id == na.provider_article_id
                )
            )
        if existing is not None:
            dupes += 1
            all_ids.append(existing.id)
            continue
        art = Article(
            provider=na.provider,
            provider_article_id=na.provider_article_id,
            url=na.url,
            dedup_key=key,
            headline=na.headline,
            description=na.description,
            content=na.content,
            source_name=na.source_name,
            source_domain=domain_of(na.url),
            source_country=na.source_country,
            language=na.language,
            published_at=na.published_at,
            processing_status=ArticleStatus.PENDING,
            is_simulated=na.is_simulated,
            input_origin=input_origin,
            extra=na.metadata,
        )
        try:
            with session.begin_nested():  # savepoint: a clash must not undo earlier inserts
                session.add(art)
        except IntegrityError:
            # Concurrent insert of the same article: treat as duplicate.
            dupes += 1
            continue
        inserted.append(art.id)
        all_ids.append(art.id)
    session.commit()
    return inserted, dupes, all_ids
