"""Synthetic persisted events for lineage tests (no LLM): Event + AnalysisRun + graph rows + ranked paths."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.models import AnalysisRun, Event, GraphNode, ImpactPath, Relationship
from app.services.lineage.config import config_from_dict, load_lineage_config

# Chain used across tests: OIL (A) -> IMPORT BILL (B) -> RUPEE/OMC (C)
A_PATHS = [(["variable:opec_production", "variable:global_oil_supply", "variable:oil_supply_risk_premium",
             "asset:ongc_ns"], 0.6)]
B_PATHS = [(["variable:global_oil_supply", "variable:oil_supply_risk_premium", "variable:india_oil_import_bill",
             "asset:hpcl_ns"], 0.6),
           (["variable:opec_production", "variable:global_oil_supply", "variable:india_oil_import_bill",
             "asset:bpcl_ns"], 0.55),
           (["variable:india_oil_import_bill", "variable:india_omc_marketing_margins", "asset:bpcl_ns"], 0.5)]
C_PATHS = [(["variable:india_oil_import_bill", "variable:india_current_account_deficit", "asset:in_10y_gsec_yield"],
            0.6),
           (["variable:india_oil_import_bill", "variable:india_omc_marketing_margins", "asset:hpcl_ns"], 0.5)]


def lineage_test_config(**overrides):
    """Lineage config for tests: mock-LLM runs allowed (the suite never calls a real LLM)."""
    import json

    raw = json.loads(load_lineage_config().model_dump_json())
    raw["eligibility"]["exclude_simulated_runs"] = False
    for dotted, value in overrides.items():
        cur = raw
        *parents, leaf = dotted.split(".")
        for p in parents:
            cur = cur[p]
        cur[leaf] = value
    return config_from_dict(raw)


def make_event(db, kb, title: str, day: date, paths: list[tuple[list[str], float]], *, event_type="ENERGY_SUPPLY",
               extra_nodes: tuple[str, ...] = (), simulated=False, mode="LIVE", status="COMPLETED",
               directions: dict[tuple[str, str], str] | None = None, reported: datetime | None = None,
               event: Event | None = None) -> Event:
    """Create (or re-analyse, when ``event`` is given) an event whose graph is the given ranked paths."""
    if event is None:
        event = Event(event_type=event_type, title=title, event_date=day, is_simulated=simulated,
                      first_reported_at=reported or datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc),
                      extraction_version="test", llm_provider="test")
        db.add(event)
        db.flush()
    run = AnalysisRun(event_id=event.id, status=status, mode=mode, trigger="TEST", analysis_version="test",
                      knowledge_base_version=kb.version, llm_provider="test")
    db.add(run)
    db.flush()
    ev_node = f"event:{event.id}"
    node_ids = {ev_node} | {n for p, _ in paths for n in p} | set(extra_nodes)
    for nid in sorted(node_ids):
        db.add(GraphNode(analysis_run_id=run.id, node_id=nid, node_type="EVENT" if nid == ev_node else kb.node_type(nid),
                         label=title if nid == ev_node else kb.node_label(nid),
                         origin="ARTICLE", on_impact_path=nid != ev_node))
    rel_ids: dict[tuple[str, str], str] = {}
    directions = directions or {}
    for rank, (p, score) in enumerate(sorted(paths, key=lambda x: -x[1]), start=1):
        full = [ev_node, *p]
        for a, b in zip(full, full[1:]):
            if (a, b) not in rel_ids:
                r = Relationship(analysis_run_id=run.id, event_id=event.id, source_node_id=a, target_node_id=b,
                                 relationship_type="INCREASES", direction=directions.get((a, b), "POSITIVE"),
                                 status="INFERRED", origin="KNOWLEDGE_BASE", confidence=0.8, evidence_strength=0.7,
                                 economic_relevance=0.8, historical_support_status="NOT_APPLICABLE",
                                 applicability=1.0, score=score)
                db.add(r)
                db.flush()
                rel_ids[(a, b)] = r.id
        db.add(ImpactPath(analysis_run_id=run.id, event_id=event.id, rank=rank, target_asset_id=p[-1],
                          node_ids=full, relationship_ids=[rel_ids[(a, b)] for a, b in zip(full, full[1:])],
                          path_score=score, score_breakdown={}, net_sign=1,
                          impact_direction="POTENTIAL_UPWARD_PRESSURE", explanation="test"))
    if status in ("COMPLETED", "PARTIAL"):
        event.latest_analysis_id = run.id
    db.commit()
    return event
