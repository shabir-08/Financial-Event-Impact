"""Persist an in-memory graph build + path analysis to PostgreSQL (the source of truth)."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.database.base import new_id
from app.domain import EntityOrigin, NormalizationStatus
from app.models import AnalysisRun, AssetImpact, EventEntity, GraphNode, ImpactPath, Relationship, RelationshipEvidence
from app.schemas.llm import EXTRACTION_VERSION
from app.services.graph.builder import EdgeSpec, GraphBuild
from app.services.graph.paths import PathAnalysis


def persist_graph(session: Session, run: AnalysisRun, build: GraphBuild, analysis: PathAnalysis,
                  asset_market: dict[str, dict]) -> dict[tuple[str, str], str]:
    """Write nodes, relationships (+evidence), ranked paths and asset impacts. Returns edge -> relationship id."""
    on_path = {n for p in analysis.paths for n in p.nodes}
    for n in build.nodes.values():
        session.add(GraphNode(
            analysis_run_id=run.id, node_id=n.node_id, node_type=n.node_type, label=n.label[:255],
            origin=str(n.origin.value if hasattr(n.origin, "value") else n.origin),
            on_impact_path=n.node_id in on_path, centrality=analysis.centrality.get(n.node_id),
            extra={**n.metadata, **({"market": asset_market[n.node_id]} if n.node_id in asset_market else {})},
        ))
    rel_ids: dict[tuple[str, str], str] = {}
    for key, e in build.edges.items():
        rid = new_id()
        rel_ids[key] = rid
        session.add(_relationship_row(rid, run, e))
        for ev in e.evidence:
            session.add(RelationshipEvidence(relationship_id=rid, evidence_type=ev.evidence_type,
                                             article_id=ev.article_id, passage=ev.passage,
                                             reference=ev.reference, verified=ev.verified))
    path_ids_by_asset: dict[str, list[str]] = {}
    for p in analysis.paths:
        pid = new_id()
        path_ids_by_asset.setdefault(p.target, []).append(pid)
        session.add(ImpactPath(
            id=pid, analysis_run_id=run.id, event_id=run.event_id, rank=p.rank, target_asset_id=p.target,
            node_ids=p.nodes, relationship_ids=[rel_ids[(a, b)] for a, b in zip(p.nodes, p.nodes[1:])],
            path_score=p.score, score_breakdown=p.breakdown, net_sign=p.net_sign,
            impact_direction=p.impact_direction.value, explanation=p.explanation, uncertainties=p.uncertainties,
        ))
    for a in analysis.assets:
        m = asset_market.get(a.asset_id, {})
        session.add(AssetImpact(
            analysis_run_id=run.id, event_id=run.event_id, asset_id=a.asset_id,
            impact_direction=a.impact_direction.value, best_path_score=a.best_score,
            path_ids=path_ids_by_asset.get(a.asset_id, []), mechanism=a.mechanism, uncertainty=a.uncertainty,
            market_data_status=m.get("status", "NOT_REQUESTED"), market_data_reason_code=m.get("reason_code"),
            historical_comparison=m.get("historical"),
        ))
    _store_inferred_entities(session, run, build)
    return rel_ids


def _relationship_row(rid: str, run: AnalysisRun, e: EdgeSpec) -> Relationship:
    return Relationship(
        id=rid, analysis_run_id=run.id, event_id=run.event_id, source_node_id=e.source, target_node_id=e.target,
        relationship_type=e.relationship_type, direction=e.direction.value, status=e.status.value,
        origin=e.origin.value, kb_rule_id=e.kb_rule_id, claim_id=e.claim_ids[0] if e.claim_ids else None,
        mechanism=e.mechanism, conditions={**e.conditions, "traversable": e.traversable,
                                           "claim_ids": e.claim_ids},
        time_horizon=e.time_horizon, confidence=e.score.confidence, evidence_strength=e.score.evidence_strength,
        economic_relevance=e.score.economic_relevance, historical_support=e.score.historical_support,
        historical_support_status=e.score.historical_support_status, applicability=e.score.applicability,
        score=e.score.score, score_details=e.score.details, reported_at=e.reported_at,
    )


def _store_inferred_entities(session: Session, run: AnalysisRun, build: GraphBuild) -> None:
    """Record entities introduced by economic inference, distinct from article mentions."""
    session.execute(delete(EventEntity).where(EventEntity.event_id == run.event_id,
                                              EventEntity.origin == EntityOrigin.INFERRED))
    for n in build.nodes.values():
        if n.origin == EntityOrigin.INFERRED:
            session.add(EventEntity(
                event_id=run.event_id, article_id=None, entity_id=n.node_id, mention_text=n.label[:500],
                entity_type=n.node_type, origin=EntityOrigin.INFERRED,
                normalization_status=NormalizationStatus.RESOLVED, normalization_method=f"inferred_in_run:{run.id}",
                candidate_ids=[], evidence_passage=None, passage_verified=False, extraction_confidence=None,
                extraction_version=EXTRACTION_VERSION,
            ))
