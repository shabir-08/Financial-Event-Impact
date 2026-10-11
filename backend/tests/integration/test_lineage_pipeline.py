"""Lineage inside the real AnalysisPipeline (mock LLM, fixture articles, no market data)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import AnalysisRun, Event, EventImpact, EventNode, GraphNode, ImpactPath
from app.services.lineage.linker import LineageService
from app.services.news.fixture import FixtureNewsProvider
from app.services.news.ingestion import IngestionService
from app.services.pipeline import AnalysisPipeline
from tests.lineage_fixtures import lineage_test_config


async def analysed_events(db, pipe) -> list[Event]:
    summary = await IngestionService(db, FixtureNewsProvider()).ingest()
    for aid in summary.article_ids:
        await pipe.process_article(aid)
    return db.scalars(select(Event)).all()


def lineage_step(run: AnalysisRun) -> dict:
    return next(s for s in run.steps if s["step"] == "lineage")


async def test_simulated_fixture_events_are_skipped_by_the_lineage_step(db, settings, kb, mock_llm):
    pipe = AnalysisPipeline(db, settings, kb, mock_llm, None, lineage_config=lineage_test_config())
    events = await analysed_events(db, pipe)
    assert events and all(e.is_simulated for e in events)
    for e in events:
        step = lineage_step(db.get(AnalysisRun, e.latest_analysis_id))
        assert step["status"] == "SKIPPED" and "simulated" in step["detail"]["reason"]
    assert db.scalar(select(func.count()).select_from(EventImpact)) == 0


async def test_lineage_runs_after_persistence_on_real_pipeline_graphs(db, settings, kb, mock_llm):
    pipe = AnalysisPipeline(db, settings, kb, mock_llm, None, lineage_config=lineage_test_config())
    events = await analysed_events(db, pipe)
    for e in events:  # treat as non-simulated news to exercise linking on genuinely built graphs
        e.is_simulated = False
    db.commit()
    for e in sorted(events, key=lambda e: (e.event_date, e.id)):
        run = await pipe.run(pipe.create_run(e.id, trigger="TEST").id)
        step = lineage_step(run)
        assert step["status"] == "COMPLETED", step
        names = [s["step"] for s in run.steps]
        assert names.index("persistence") < names.index("lineage")
        nodes = db.scalars(select(EventNode).where(EventNode.analysis_run_id == run.id)).all()
        n_paths = db.scalar(select(func.count()).select_from(ImpactPath).where(ImpactPath.analysis_run_id == run.id))
        assert db.get(EventImpact, (e.id, run.id)) is not None
        if n_paths:
            assert any(n.weight == 1.0 for n in nodes)  # the best path is the normalisation reference
        graph_ids = set(db.scalars(select(GraphNode.node_id).where(GraphNode.analysis_run_id == run.id)))
        assert {n.node_id for n in nodes} <= graph_ids  # canonical ids reused, nothing invented


async def test_lineage_failure_never_breaks_the_analysis(db, settings, kb, mock_llm, monkeypatch):
    def boom(self, *a, **k):
        raise RuntimeError("lineage exploded")

    monkeypatch.setattr(LineageService, "link_event", boom)
    pipe = AnalysisPipeline(db, settings, kb, mock_llm, None, lineage_config=lineage_test_config())
    events = await analysed_events(db, pipe)
    run = db.get(AnalysisRun, events[0].latest_analysis_id)
    assert run.status in ("COMPLETED", "PARTIAL")
    assert lineage_step(run)["status"] == "FAILED"
    assert any("lineage" in w for w in run.warnings)
    assert db.scalar(select(func.count()).select_from(GraphNode).where(GraphNode.analysis_run_id == run.id)) > 0
