"""Full pipeline on the test database with the mock LLM and fixture (SIMULATED) articles."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select

from app.core.errors import ProviderError
from app.domain import ArticleStatus, RunMode, RunStatus
from app.models import (
    AnalysisRun,
    Article,
    AssetImpact,
    Event,
    EventEntity,
    GraphNode,
    HistoricalEvent,
    ImpactPath,
    IngestionRun,
    MarketData,
    MarketObservation,
    Relationship,
)
from app.services.graph.serialization import graph_payload
from app.services.news.fixture import FixtureNewsProvider
from app.services.news.ingestion import IngestionService
from app.services.pipeline import AnalysisPipeline
from tests.conftest import FakeMarketProvider


async def ingest_fixtures(db) -> list[str]:
    summary = await IngestionService(db, FixtureNewsProvider()).ingest()
    return summary.article_ids


async def process_all(pipeline: AnalysisPipeline, ids: list[str]) -> dict[str, Any]:
    out = {}
    for aid in ids:
        out[aid] = await pipeline.process_article(aid)
    return out


def headline_of(db, aid):
    return db.get(Article, aid).headline


class TestIngestion:
    def test_catalog_seeding_is_idempotent(self, db, kb):
        from app.services.catalog_seed import seed_catalog

        assert seed_catalog(db, kb) == {"entities": 0, "assets": 0, "symbols": 0, "historical_events": 0}

    async def test_dedup_across_runs(self, db):
        first = await IngestionService(db, FixtureNewsProvider()).ingest()
        second = await IngestionService(db, FixtureNewsProvider()).ingest()
        assert first.inserted == 5 and second.inserted == 0 and second.duplicates == 5
        assert db.scalar(select(func.count()).select_from(Article)) == 5

    async def test_provider_failure_recorded(self, db):
        class Broken:
            name, provides_full_text = "broken", False

            async def fetch(self, query=None, limit=25):
                raise ProviderError("outage", provider="broken", retryable=True)

        with pytest.raises(ProviderError):
            await IngestionService(db, Broken()).ingest()
        run = db.scalar(select(IngestionRun))
        assert run.status == "FAILED" and run.error["code"] == "provider_error"


class TestMockPipeline:
    async def test_end_to_end(self, db, settings, kb, mock_llm):
        pipe = AnalysisPipeline(db, settings, kb, mock_llm, None)
        ids = await ingest_fixtures(db)
        results = await process_all(pipe, ids)
        statuses = {headline_of(db, a): r[0].status for a, r in results.items()}
        assert statuses["Local cricket club wins regional championship"] == ArticleStatus.FILTERED_OUT

        # The two OPEC+ articles describe the same event and are merged into one.
        oil_ids = [a for a in ids if "OPEC+" in headline_of(db, a)]
        oil_events = {results[a][0].event_id for a in oil_ids}
        assert len(oil_events) == 1
        assert sum(1 for a in oil_ids if results[a][0].merged_into_existing) == 1
        # The tariff and Fed articles become separate events.
        assert db.scalar(select(func.count()).select_from(Event)) == 3

        event = db.get(Event, oil_events.pop())
        assert event.is_simulated and event.verification_status == "SIMULATED"
        run = db.get(AnalysisRun, event.latest_analysis_id)
        assert run.status == RunStatus.COMPLETED and run.mode == RunMode.SIMULATED
        assert [s["step"] for s in run.steps] == ["graph_build", "path_analysis", "market_analysis", "persistence",
                                                  "explanation", "lineage"]
        assert run.explanation_status == "VALID" and run.explanation["simulated"] is True

        # Graph persisted and reconstructable from DB rows.
        payload = graph_payload(db, run)
        node_ids = {n["data"]["id"] for n in payload["elements"]["nodes"]}
        assert {"variable:crude_oil_price", "asset:usdinr", "asset:jets"} <= node_ids
        statuses = {e["data"]["status"] for e in payload["elements"]["edges"]}
        assert {"REPORTED", "INFERRED"} <= statuses
        impacts = {a.asset_id: a for a in db.scalars(select(AssetImpact).where(AssetImpact.analysis_run_id == run.id))}
        assert impacts["asset:jets"].impact_direction == "POTENTIAL_DOWNWARD_PRESSURE"
        assert impacts["asset:usdinr"].impact_direction == "POTENTIAL_UPWARD_PRESSURE"
        # No market provider -> honest status, no observations, no fabricated numbers.
        assert all(a.market_data_status == "NOT_REQUESTED" for a in impacts.values())
        assert db.scalar(select(func.count()).select_from(MarketObservation)) == 0
        assert "Market data provider not configured" in run.warnings[0]
        # Inferred entities are recorded separately from article mentions.
        origins = set(db.scalars(select(EventEntity.origin).where(EventEntity.event_id == event.id)))
        assert origins == {"ARTICLE", "INFERRED"}
        # Simulated events are never registered as historical reference events.
        assert db.scalar(select(func.count()).select_from(HistoricalEvent)
                         .where(HistoricalEvent.source_type == "SYSTEM_DETECTED")) == 0

    async def test_tariff_event_uses_trigger_rules(self, db, settings, kb, mock_llm):
        pipe = AnalysisPipeline(db, settings, kb, mock_llm, None)
        ids = await ingest_fixtures(db)
        tariff = next(a for a in ids if "tariffs" in headline_of(db, a))
        result, run = await pipe.process_article(tariff)
        rels = db.scalars(select(Relationship).where(Relationship.analysis_run_id == run.id)).all()
        trig = [r for r in rels if r.origin == "EVENT_TRIGGER"]
        assert trig and trig[0].target_node_id == "variable:us_tariffs_on_china"
        assert any(p.target_asset_id == "asset:usdcny" for p in
                   db.scalars(select(ImpactPath).where(ImpactPath.analysis_run_id == run.id)))

    async def test_reanalysis_creates_new_run_and_keeps_old(self, db, settings, kb, mock_llm):
        pipe = AnalysisPipeline(db, settings, kb, mock_llm, None)
        ids = await ingest_fixtures(db)
        _, run1 = await pipe.process_article(ids[0])
        run2 = await pipe.run(pipe.create_run(run1.event_id, trigger="TEST").id)
        assert run2.id != run1.id and run2.status == RunStatus.COMPLETED
        n1 = db.scalar(select(func.count()).select_from(GraphNode).where(GraphNode.analysis_run_id == run1.id))
        n2 = db.scalar(select(func.count()).select_from(GraphNode).where(GraphNode.analysis_run_id == run2.id))
        assert n1 == n2 > 0


class FailingLLM:
    """Real-provider stand-in that fails: the pipeline must NOT fall back to mock output."""

    name, model, simulated = "anthropic", "claude-opus-5-5", False

    def __init__(self, inner=None, fail_on="classify"):
        self.inner, self.fail_on = inner, fail_on

    async def classify_event(self, article):
        if self.fail_on == "classify":
            raise ProviderError("Anthropic request timed out", provider="anthropic", retryable=True)
        return await self.inner.classify_event(article)

    async def extract_entities(self, article, event):
        return await self.inner.extract_entities(article, event)

    async def extract_relationships(self, article, event, entities):
        return await self.inner.extract_relationships(article, event, entities)

    async def generate_explanation(self, package, feedback=None):
        res = await self.inner.generate_explanation(package, feedback)
        bad = res.output.model_copy(update={"historical_context": "Airlines fell 37.5% after similar shocks."})
        return res.model_copy(update={"output": bad})


class TestFailureHandling:
    async def test_llm_failure_marks_article_failed_without_mock_substitution(self, db, settings, kb):
        pipe = AnalysisPipeline(db, settings, kb, FailingLLM(), None)
        ids = await ingest_fixtures(db)
        result, run = await pipe.process_article(ids[0])
        art = db.get(Article, ids[0])
        assert result.status == ArticleStatus.FAILED and run is None
        assert art.processing_status == "FAILED" and art.error["code"] == "provider_error"
        assert db.scalar(select(func.count()).select_from(Event)) == 0

    async def test_ungrounded_explanation_is_rejected_and_run_partial(self, db, settings, kb, mock_llm):
        llm = FailingLLM(inner=mock_llm, fail_on="explain")
        pipe = AnalysisPipeline(db, settings, kb, llm, None)
        ids = await ingest_fixtures(db)
        _, run = await pipe.process_article(ids[0])
        assert run.explanation_status == "FAILED_VALIDATION" and run.explanation["content"] is None
        assert any("37.5%" in i for i in run.explanation["issues"])
        assert run.status == RunStatus.PARTIAL


class TestMarketAnalysis:
    async def test_observations_and_historical_support(self, db, settings, kb, mock_llm):
        settings.market_max_assets = 4
        market = FakeMarketProvider(drift_by_symbol={"BZ=F": 0.004, "CL=F": 0.004})
        pipe = AnalysisPipeline(db, settings, kb, mock_llm, market)
        ids = await ingest_fixtures(db)
        _, run = await pipe.process_article(ids[0])
        assert run.status == RunStatus.COMPLETED
        assert [s["step"] for s in run.steps][2:4] == ["market_analysis", "rescoring_with_historical_support"]
        obs = db.scalars(select(MarketObservation).where(MarketObservation.analysis_run_id == run.id)).all()
        assert any(o.observation_kind == "CURRENT_EVENT" for o in obs)
        hist = [o for o in obs if o.observation_kind == "HISTORICAL_EVENT"]
        assert hist and all(o.is_simulated for o in obs)  # test data is labelled simulated
        brent = db.scalar(select(AssetImpact).where(AssetImpact.analysis_run_id == run.id,
                                                    AssetImpact.asset_id == "asset:brent_futures"))
        hc = brent.historical_comparison
        # Rising synthetic series vs. curated oil-UP / oil-DOWN reference events -> mixed consistency.
        assert hc["status"] == "AVAILABLE" and 0.0 <= hc["historical_support"] <= 1.0
        final = db.scalar(select(Relationship).where(Relationship.analysis_run_id == run.id,
                                                     Relationship.target_node_id == "asset:brent_futures",
                                                     Relationship.origin == "KNOWLEDGE_BASE"))
        assert final.historical_support == pytest.approx(hc["historical_support"])
        observed = db.scalars(select(Relationship).where(Relationship.analysis_run_id == run.id,
                                                         Relationship.status == "OBSERVED")).all()
        assert observed and all(not r.conditions["traversable"] for r in observed)
        assert db.scalar(select(func.count()).select_from(MarketData)) > 0  # cached

    async def test_provider_outage_degrades_to_partial(self, db, settings, kb, mock_llm):
        settings.market_max_assets = 3
        market = FakeMarketProvider(fail_symbols={"BZ=F", "CL=F", "XOM", "CVX", "XLE", "ONGC.NS"})
        pipe = AnalysisPipeline(db, settings, kb, mock_llm, market)
        ids = await ingest_fixtures(db)
        _, run = await pipe.process_article(ids[0])
        assert run.status == RunStatus.PARTIAL
        assert any("provider error" in w for w in run.warnings)
        assert run.graph_generated_at is not None  # graph still built without market data
        statuses = set(db.scalars(select(MarketObservation.status).where(MarketObservation.analysis_run_id == run.id)))
        assert statuses == {"UNAVAILABLE"}

    async def test_asset_without_symbol_is_unavailable(self, db, settings, kb, mock_llm):
        from app.services.market_data.service import MarketDataService

        svc = MarketDataService(db, FakeMarketProvider(), kb, settings)
        from datetime import date
        sr = await svc.get_series("asset:in_10y_gsec_yield", [(date(2026, 1, 1), date(2026, 2, 1))])
        assert sr.series is None and "no yahoo_chart symbol mapping" in sr.status_reason


@pytest.mark.postgres
def test_alembic_migrations_upgrade_and_downgrade(engine):
    from tests.conftest import IS_POSTGRES

    if not IS_POSTGRES:
        pytest.skip("requires PostgreSQL")
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, text

    admin = create_engine(engine.url.render_as_string(hide_password=False), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("DROP DATABASE IF EXISTS fig_migration_check"))
        c.execute(text("CREATE DATABASE fig_migration_check"))
    url = engine.url.set(database="fig_migration_check").render_as_string(hide_password=False)
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    try:
        command.upgrade(cfg, "head")
        eng = create_engine(url)
        tables = set(inspect(eng).get_table_names())
        assert {"articles", "events", "relationships", "relationship_evidence", "analysis_runs"} <= tables
        command.downgrade(cfg, "base")
        assert set(inspect(eng).get_table_names()) <= {"alembic_version"}
        eng.dispose()
    finally:
        with admin.connect() as c:
            c.execute(text("DROP DATABASE IF EXISTS fig_migration_check"))
        admin.dispose()


async def test_weekend_bars_dropped_for_weekday_markets(db, settings, kb):
    from datetime import date

    import pandas as pd

    from app.services.market_data.base import PriceSeries
    from app.services.market_data.service import MarketDataService

    class WeekendBarProvider:
        name, simulated = "yahoo_chart", True

        async def fetch_daily(self, symbol, start, end):
            idx = [date(2026, 10, 8), date(2026, 10, 9), date(2026, 10, 10)]  # Thu, Fri, Sat
            return PriceSeries(self.name, symbol, pd.DataFrame({"close": [1.0, 1.1, 1.2]}, index=idx), simulated=True)

    svc = MarketDataService(db, WeekendBarProvider(), kb, settings)
    sr = await svc.get_series("asset:usdinr", [(date(2026, 10, 1), date(2026, 10, 10))])
    assert date(2026, 10, 10) not in sr.series.frame.index
    assert any("weekend-dated" in n for n in sr.series.notes)


class TestFallbackPipeline:
    async def test_event_records_provider_that_actually_served(self, db, settings, kb, mock_llm):
        from app.services.llm.fallback import FallbackLLMProvider

        class Down:
            name, model, simulated = "gemini", "gemini-2.5-flash", False

            def __getattr__(self, method):
                async def fail(*a, **k):
                    raise ProviderError("gemini returned HTTP 503", provider="gemini", retryable=True)
                return fail

        class Working:
            """Stand-in for a real provider (delegates to the mock's logic but is NOT the mock)."""
            name, model, simulated = "groq", "llama-3.3-70b-versatile", False

            def __getattr__(self, method):
                async def call(*a, **k):
                    res = await getattr(mock_llm, method)(*a, **k)
                    return res.model_copy(update={"provider": "groq", "model": self.model, "simulated": False})
                return call

        chain = FallbackLLMProvider([Down(), Working()], cooldown_seconds=60)
        pipe = AnalysisPipeline(db, settings, kb, chain, None)
        ids = await ingest_fixtures(db)
        result, run = await pipe.process_article(ids[0])
        event = db.get(Event, result.event_id)
        assert event.llm_provider == "groq"
        served = event.processing_history[0]["llm_served_by"]["classification"]
        assert served["provider"] == "groq" and served["fallback_trail"][0]["provider"] == "gemini"
        assert run.llm_provider == "fallback" and run.explanation["provider"] == "groq"
        assert run.explanation["fallback_trail"][0]["outcome"] == "skipped_cooldown"
