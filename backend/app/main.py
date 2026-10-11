"""FastAPI application entry point: ``uvicorn app.main:app --reload``."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import (analysis, articles, assets, events, graphs, health, lineage, market, market_patterns, reports,
                     simulations)
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.database.session import get_sessionmaker
from app.services.catalog_seed import seed_catalog
from app.services.relationships.knowledge_base import get_knowledge_base

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level, settings.secret_values())
    kb = get_knowledge_base()  # fail fast on an invalid knowledge base
    if getattr(app.state, "seed_catalog", True):
        try:
            with get_sessionmaker()() as s:
                counts = seed_catalog(s, kb)
            log.info("Catalog seeded: %s", counts)
        except Exception as exc:  # noqa: BLE001 - DB may be down; health endpoint will report it
            log.warning("Catalog seeding skipped: %s", type(exc).__name__)
    yield


def create_app(seed: bool = True) -> FastAPI:
    app = FastAPI(
        title="Financial Event Market Impact Graph API",
        version=__version__,
        description=(
            "Detects financial events in news, builds event-specific knowledge graphs, traces potential "
            "propagation paths to assets with evidence, and reports historical market context. Scores are "
            "heuristic rankings, not probabilities; nothing here is investment advice."
        ),
        lifespan=lifespan,
    )
    app.state.seed_catalog = seed
    install_error_handlers(app)
    # Browser frontends on other origins (Vite dev server); no cookies/credentials are used by this API.
    app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_allowed_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])
    for r in (health.router, articles.router, events.router, graphs.router, market.router, assets.router,
              analysis.router, simulations.router, market_patterns.router, reports.router, lineage.router):
        app.include_router(r)
    return app


app = create_app()
