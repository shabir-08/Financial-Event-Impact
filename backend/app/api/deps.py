"""FastAPI dependencies and a session-independent factory for background jobs."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_db, get_sessionmaker
from app.services.llm.base import LLMProvider
from app.services.llm.factory import build_llm_provider
from app.services.market_data.base import MarketDataProvider
from app.services.market_data.service import build_market_provider
from app.services.pipeline import AnalysisPipeline
from app.services.relationships.knowledge_base import KnowledgeBase, get_knowledge_base


def get_kb() -> KnowledgeBase:
    return get_knowledge_base()


def get_llm(settings: Settings = Depends(get_settings), kb: KnowledgeBase = Depends(get_kb)) -> LLMProvider:
    # Raises ConfigurationError (HTTP 503) when the configured provider lacks credentials.
    return build_llm_provider(settings, kb)


def get_market_provider(settings: Settings = Depends(get_settings)) -> MarketDataProvider | None:
    return build_market_provider(settings)


def get_pipeline(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings), kb: KnowledgeBase = Depends(get_kb),
    llm: LLMProvider = Depends(get_llm), market: MarketDataProvider | None = Depends(get_market_provider),
) -> AnalysisPipeline:
    return AnalysisPipeline(db, settings, kb, llm, market)


#: Overridable in tests: builds (session, pipeline) for work running after the response is sent.
def default_job_pipeline_factory() -> tuple[Session, AnalysisPipeline]:
    settings = get_settings()
    kb = get_knowledge_base()
    session = get_sessionmaker()()
    return session, AnalysisPipeline(session, settings, kb, build_llm_provider(settings, kb),
                                     build_market_provider(settings))


job_pipeline_factory: Callable[[], tuple[Session, AnalysisPipeline]] = default_job_pipeline_factory


def set_job_pipeline_factory(factory: Callable[[], tuple[Session, AnalysisPipeline]]) -> None:
    global job_pipeline_factory
    job_pipeline_factory = factory


async def run_analysis_job(run_id: str) -> None:
    session, pipeline = job_pipeline_factory()
    try:
        await pipeline.run(run_id)
    finally:
        session.close()


async def process_articles_job(article_ids: list[str], analyze: bool) -> None:
    session, pipeline = job_pipeline_factory()
    try:
        for aid in article_ids:
            await pipeline.process_article(aid, trigger="INGESTION", analyze=analyze)
    finally:
        session.close()
