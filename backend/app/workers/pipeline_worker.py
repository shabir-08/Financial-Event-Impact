"""Automated ingestion + event detection + analysis loop.

    python -m app.workers.pipeline_worker --once              # one cycle
    python -m app.workers.pipeline_worker --interval 900      # every 15 minutes
    python -m app.workers.pipeline_worker --once --no-analyze --query '"crude oil"'

Uses NEWS_PROVIDER / LLM_PROVIDER / MARKET_DATA_PROVIDER from the environment.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.database.session import get_sessionmaker
from app.models import Article
from app.services.catalog_seed import seed_catalog
from app.services.llm.factory import build_llm_provider
from app.services.market_data.service import build_market_provider
from app.services.news.ingestion import IngestionService, build_news_provider
from app.services.pipeline import AnalysisPipeline
from app.services.relationships.knowledge_base import get_knowledge_base

log = logging.getLogger("worker")


async def run_cycle(query: str | None, limit: int, analyze: bool, max_process: int) -> dict:
    settings = get_settings()
    kb = get_knowledge_base()
    with get_sessionmaker()() as session:
        seed_catalog(session, kb)
        summary = {"ingested": 0, "duplicates": 0, "processed": {}, "errors": []}
        try:
            ing = await IngestionService(session, build_news_provider(settings)).ingest(query=query, limit=limit)
            summary["ingested"], summary["duplicates"] = ing.inserted, ing.duplicates
        except AppError as exc:
            summary["errors"].append(exc.to_dict())
            log.error("Ingestion failed: %s", exc.message)
        pipeline = AnalysisPipeline(session, settings, kb, build_llm_provider(settings, kb),
                                    build_market_provider(settings))
        pending = session.scalars(select(Article.id).where(Article.processing_status == "PENDING")
                                  .order_by(Article.published_at.desc().nullslast()).limit(max_process)).all()
        for aid in pending:
            result, run = await pipeline.process_article(aid, trigger="WORKER", analyze=analyze)
            key = result.status.value
            summary["processed"][key] = summary["processed"].get(key, 0) + 1
            if run is not None:
                log.info("Event %s analysed: run %s %s", result.event_id, run.id, run.status)
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=int, default=900, help="seconds between cycles")
    p.add_argument("--query", default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--max-process", type=int, default=25)
    p.add_argument("--no-analyze", action="store_true")
    args = p.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level, settings.secret_values())
    limit = args.limit or settings.news_max_articles

    async def loop() -> None:
        while True:
            summary = await run_cycle(args.query, limit, not args.no_analyze, args.max_process)
            log.info("Cycle complete: %s", summary)
            if args.once:
                return
            await asyncio.sleep(args.interval)

    asyncio.run(loop())


if __name__ == "__main__":
    main()
