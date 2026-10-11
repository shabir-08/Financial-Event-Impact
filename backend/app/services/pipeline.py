"""End-to-end analysis orchestration for one event, with a persisted, step-by-step run record.

article -> (EventProcessor) event/entities/claims -> graph build -> path ranking -> market data
& historical comparison -> re-scoring with historical support -> persistence -> evidence package
-> grounded explanation. Optional integrations (market data, explanation) degrade the run to
PARTIAL instead of failing it; nothing is silently replaced with simulated output.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, time as dtime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.database.base import utcnow
from app.domain import DataAvailability, EdgeStatus, RelationshipOrigin, RelationshipType, RunMode, RunStatus
from app.models import AnalysisRun, Article, Event, EventEntity, ExtractedClaim, HistoricalEvent, MarketObservation
from app.services.events.processor import EventProcessor, ProcessResult
from app.services.explanations.evidence_package import build_evidence_package
from app.services.explanations.explainer import explain
from app.services.graph.builder import (
    ClaimRecord,
    EdgeSpec,
    EvidenceRef,
    EventInput,
    GraphBuild,
    GraphBuilder,
    MentionRecord,
)
from app.services.graph.paths import PathAnalyzer
from app.services.graph.persistence import persist_graph
from app.services.llm.base import LLMProvider
from app.services.market_data.base import MarketDataProvider
from app.services.market_data.quality import LimitationCode
from app.services.market_data.service import MarketDataService
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.relationships.scoring import combine

log = logging.getLogger(__name__)
ANALYSIS_VERSION = "analysis-v1"


class AnalysisPipeline:
    def __init__(self, session: Session, settings: Settings, kb: KnowledgeBase, llm: LLMProvider,
                 market_provider: MarketDataProvider | None) -> None:
        self.session = session
        self.settings = settings
        self.kb = kb
        self.llm = llm
        self.market_provider = market_provider

    # --------------------------------------------------------------- entry points
    async def process_article(self, article_id: str, *, trigger: str = "INGESTION",
                              skip_prefilter: bool = False, analyze: bool = True) -> tuple[ProcessResult, AnalysisRun | None]:
        result = await EventProcessor(self.session, self.llm, self.kb).process_article(
            article_id, skip_prefilter=skip_prefilter)
        if result.event_id is None or not analyze:
            return result, None
        run = self.create_run(result.event_id, trigger=trigger, article_id=article_id)
        return result, await self.run(run.id)

    def create_run(self, event_id: str, *, trigger: str, article_id: str | None = None) -> AnalysisRun:
        event = self.session.get(Event, event_id)
        if event is None:
            raise NotFoundError(f"event {event_id} not found")
        simulated = self.llm.simulated or event.is_simulated
        run = AnalysisRun(
            event_id=event_id, article_id=article_id, status=RunStatus.PENDING,
            mode=RunMode.SIMULATED if simulated else RunMode.LIVE, trigger=trigger,
            analysis_version=ANALYSIS_VERSION, knowledge_base_version=self.kb.version,
            llm_provider=self.llm.name, llm_model=self.llm.model,
            market_data_provider=self.market_provider.name if self.market_provider else None,
            config=self._config_snapshot(),
        )
        self.session.add(run)
        self.session.commit()
        return run

    async def run(self, run_id: str) -> AnalysisRun:
        run = self.session.get(AnalysisRun, run_id)
        if run is None:
            raise NotFoundError(f"analysis {run_id} not found")
        run.status, run.started_at = RunStatus.RUNNING, utcnow()
        self.session.commit()
        steps: list[dict[str, Any]] = []
        warnings: list[str] = []
        degraded = False
        try:
            event = self.session.get(Event, run.event_id)
            t = self._step_start()
            build = GraphBuilder(self.kb, self.settings).build(self._event_input(event))
            steps.append(self._step_end("graph_build", t, "COMPLETED", build.stats))

            t = self._step_start()
            analyzer = PathAnalyzer(self.kb, self.settings)
            analysis = analyzer.analyze(build)
            steps.append(self._step_end("path_analysis", t, "COMPLETED", analysis.stats))

            t = self._step_start()
            asset_market, market_warnings, market_errors = await self._market_step(run, event, build, analysis)
            warnings += market_warnings
            degraded |= market_errors
            if self.market_provider is None:
                steps.append(self._step_end("market_analysis", t, "SKIPPED", {"reason": "MARKET_DATA_PROVIDER=none"}))
            else:
                steps.append(self._step_end("market_analysis", t, "PARTIAL" if market_errors else "COMPLETED",
                                            {"assets_analysed": len(asset_market)}))
                analysis = analyzer.analyze(build)  # re-rank after historical support updated edge scores
                steps.append(self._step_end("rescoring_with_historical_support", self._step_start(), "COMPLETED",
                                            analysis.stats))

            t = self._step_start()
            for a in analysis.assets:
                asset_market.setdefault(a.asset_id, {
                    "status": "NOT_REQUESTED",
                    "reason": f"outside top {self.settings.market_max_assets} assets"
                    if self.market_provider else "no market-data provider configured",
                    "reason_code": LimitationCode.NOT_REQUESTED if self.market_provider
                    else LimitationCode.NOT_CONFIGURED})
            persist_graph(self.session, run, build, analysis, asset_market)
            run.graph_generated_at = utcnow()
            run.graph_stats = {**build.stats, "paths": analysis.stats, "excluded": build.excluded[:200]}
            self.session.flush()
            steps.append(self._step_end("persistence", t, "COMPLETED", {}))

            t = self._step_start()
            package = build_evidence_package(self.session, run, self.kb)
            outcome = await explain(self.llm, package)
            run.explanation = {"status": outcome.status, "simulated": outcome.simulated, "provider": outcome.provider,
                               "model": outcome.model, "fallback_trail": outcome.fallback_trail or [],
                               "content": outcome.explanation, "issues": outcome.issues,
                               "evidence_package": package}
            run.explanation_status = outcome.status
            ok = outcome.status in ("VALID", "VALID_AFTER_RETRY", "SANITIZED")
            if not ok:
                degraded = True
                warnings.append(f"explanation {outcome.status}: {outcome.issues[:3]}")
            steps.append(self._step_end("explanation", t, "COMPLETED" if ok else "FAILED", {"status": outcome.status}))

            self._register_historical(event)
            event.latest_analysis_id = run.id
            run.status = RunStatus.PARTIAL if degraded else RunStatus.COMPLETED
        except Exception as exc:  # noqa: BLE001 - any failure must be recorded on the run
            log.exception("Analysis run %s failed", run_id)
            self.session.rollback()
            run = self.session.get(AnalysisRun, run_id)
            run.status = RunStatus.FAILED
            run.error = exc.to_dict() if isinstance(exc, AppError) else {"code": type(exc).__name__, "message": str(exc)[:500]}
            steps.append({"step": "error", "status": "FAILED", "detail": run.error})
        run.steps, run.warnings, run.finished_at = steps, warnings, utcnow()
        self.session.commit()
        return run

    # ------------------------------------------------------------------ helpers
    def _event_input(self, event: Event) -> EventInput:
        claims = self.session.scalars(select(ExtractedClaim).where(ExtractedClaim.event_id == event.id)).all()
        arts = {a.id: a for a in self.session.scalars(
            select(Article).where(Article.id.in_({c.article_id for c in claims}))).all()}
        return EventInput(
            event_id=event.id, event_type=event.event_type, title=event.title,
            mentions=[MentionRecord(m.entity_id, m.mention_text, m.entity_type)
                      for m in self._article_mentions(event.id)],
            claims=[ClaimRecord(
                c.id, c.article_id, c.source_entity_id, c.target_entity_id, c.source_mention, c.target_mention,
                c.relationship_type, c.effect_sign, c.mechanism, c.passage, c.passage_verified,
                c.extraction_confidence, c.is_primary_effect,
                arts[c.article_id].source_domain if c.article_id in arts else None,
                arts[c.article_id].published_at if c.article_id in arts else None) for c in claims],
        )

    async def _market_step(self, run: AnalysisRun, event: Event, build: GraphBuild, analysis) -> tuple[dict, list[str], bool]:
        if self.market_provider is None:
            return {}, ["Market data provider not configured; historical analysis UNAVAILABLE."], False
        service = MarketDataService(self.session, self.market_provider, self.kb, self.settings)
        hist = self.session.scalars(select(HistoricalEvent)).all()
        info_time: datetime | Any = event.first_reported_at or (
            datetime.combine(event.event_date, dtime.min, tzinfo=timezone.utc) if event.event_date else utcnow())
        out: dict[str, dict] = {}
        warnings: list[str] = []
        errors = False
        for cand in analysis.assets[: self.settings.market_max_assets]:
            current, sr, comparison = await service.analyze_asset(cand.asset_id, info_time, cand.paths, hist, event.id)
            if sr.status_reason and sr.status_reason.startswith("provider error"):
                errors = True
                warnings.append(f"{cand.asset_id}: {sr.status_reason}")
            simulated = bool(sr.series is not None and sr.series.simulated)
            self.session.add(MarketObservation(
                analysis_run_id=run.id, asset_id=cand.asset_id, observation_kind="CURRENT_EVENT",
                status=current.status.value, reason_code=(sr.reason_code or current.reason_code),
                provider=self.market_provider.name, symbol=sr.symbol, anchor_date=current.anchor_date, reference_date=current.reference_date,
                reference_close=current.reference_close, windows=current.to_json(), is_simulated=simulated,
                notes=list(dict.fromkeys(current.notes + ([sr.status_reason] if sr.status_reason else [])))))
            for row in comparison.comparisons:
                self.session.add(MarketObservation(
                    analysis_run_id=run.id, asset_id=cand.asset_id, observation_kind="HISTORICAL_EVENT",
                    historical_event_id=row["historical_event_id"], status=row["status"],
                    reason_code=row.get("reason_code"),
                    provider=self.market_provider.name, symbol=sr.symbol,
                    anchor_date=datetime.fromisoformat(row["event_date"]).date(),
                    reference_date=datetime.fromisoformat(row["reference_date"]).date() if row["reference_date"] else None,
                    windows=[{"window_trading_days": 5, "return_pct": row["return_pct"],
                              "predicted_sign": row["predicted_sign"], "consistency": row.get("consistency")}],
                    is_simulated=simulated, notes=row["notes"]))
            self._apply_historical_support(build, cand, comparison)
            self._add_observed_edge(build, cand.asset_id, current)
            out[cand.asset_id] = {"status": current.status.value, "symbol": sr.symbol, "provider": self.market_provider.name,
                                  "observed_windows": current.to_json(), "historical": comparison.to_json(),
                                  "reason": sr.status_reason,
                                  "reason_code": sr.reason_code or current.reason_code}
        self.session.flush()
        return out, warnings, errors

    def _apply_historical_support(self, build: GraphBuild, cand, comparison) -> None:
        final_edges = {(p.nodes[-2], p.nodes[-1]) for p in cand.paths}
        for key in final_edges:
            e = build.edges.get(key)
            if e is None or e.origin == RelationshipOrigin.ARTICLE:
                continue
            e.score = combine(
                confidence=e.score.confidence, evidence=e.score.evidence_strength, relevance=e.score.economic_relevance,
                historical=comparison.support, historical_status=comparison.status,
                applicability=e.score.applicability, weights=self.settings.scoring_weights,
                notes={k: v for k, v in e.score.details.items() if k.startswith("evidence")}
                | {"historical_comparison_events": [c["historical_event_id"] for c in comparison.comparisons]},
            )
            if comparison.status == "AVAILABLE":
                e.evidence.append(EvidenceRef("HISTORICAL_COMPARISON", reference=",".join(
                    c["historical_event_id"] for c in comparison.comparisons),
                    passage=f"Directional consistency with {len(comparison.comparisons)} comparable past event(s): "
                            f"{comparison.support}"))

    def _add_observed_edge(self, build: GraphBuild, asset_id: str, current) -> None:
        if current.status == DataAvailability.UNAVAILABLE:
            return
        first = next((w for w in current.windows if w.return_pct is not None), None)
        if first is None:
            return
        key = (build.event_node, asset_id)
        text = (f"Observed {first.return_pct:+.2f}% over {first.window} trading day(s) after the event "
                f"(reference close {current.reference_date}). Co-movement only; not causal attribution.")
        if key in build.edges:
            build.edges[key].evidence.append(EvidenceRef("MARKET_OBSERVATION", passage=text))
            return
        sign = 1 if first.return_pct > 0 else -1 if first.return_pct < 0 else 0
        build.edges[key] = EdgeSpec(
            build.event_node, asset_id, RelationshipType.OBSERVED_TO_MOVE_WITH.value, sign, EdgeStatus.OBSERVED,
            RelationshipOrigin.MARKET_DATA, text,
            combine(confidence=1.0, evidence=0.9, relevance=0.5, historical=None, historical_status="NOT_APPLICABLE",
                    applicability=1.0, weights=self.settings.scoring_weights,
                    notes={"evidence_source": "market_data_observation"}),
            [EvidenceRef("MARKET_OBSERVATION", passage=text)], traversable=False)
        build.graph.add_edge(build.event_node, asset_id, traversable=False)

    def _register_historical(self, event: Event) -> None:
        """Make analysed real events available as future comparison points (SYSTEM_DETECTED)."""
        if event.is_simulated or not event.event_date:
            return
        hid = f"sys.{event.id}"
        if self.session.get(HistoricalEvent, hid):
            return
        effects = [{"variable": e["node_id"], "direction": e["direction"]} for e in event.primary_effects
                   if e.get("node_id") and e.get("passage_verified") and e.get("direction") in ("UP", "DOWN")]
        self.session.add(HistoricalEvent(
            id=hid, event_type=event.event_type, title=event.title, event_date=event.event_date,
            entity_ids=sorted({m.entity_id for m in self._article_mentions(event.id) if m.entity_id}),
            primary_effects=effects, source_type="SYSTEM_DETECTED", event_id=event.id,
            verification_note=f"Detected by this system ({event.verification_status}).",
        ))

    def _article_mentions(self, event_id: str) -> list[EventEntity]:
        # Explicit query: relationship collections can be stale with expire_on_commit=False.
        return list(self.session.scalars(select(EventEntity).where(EventEntity.event_id == event_id,
                                                                    EventEntity.origin == "ARTICLE")))

    def _config_snapshot(self) -> dict[str, Any]:
        s = self.settings
        return {"scoring_weights": s.scoring_weights.model_dump(), "weights_are_heuristic": True,
                "graph_kb_expansion_depth": s.graph_kb_expansion_depth, "graph_max_nodes": s.graph_max_nodes,
                "path_max_depth": s.path_max_depth, "path_max_total": s.path_max_total,
                "path_max_per_asset": s.path_max_per_asset, "path_length_decay": s.path_length_decay,
                "market_max_assets": s.market_max_assets, "market_event_windows": s.market_event_windows,
                "historical_min_comparisons": s.historical_min_comparisons, "llm_effort": s.llm_effort}

    @staticmethod
    def _step_start() -> tuple[float, str]:
        return time.perf_counter(), utcnow().isoformat()

    @staticmethod
    def _step_end(name: str, start: tuple[float, str], status: str, detail: dict) -> dict:
        return {"step": name, "status": status, "started_at": start[1],
                "duration_ms": round((time.perf_counter() - start[0]) * 1000, 1), "detail": detail}
