"""Serialise a persisted analysis graph into Cytoscape.js-compatible JSON (rebuilt from DB rows)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AnalysisRun, GraphNode, Relationship


def graph_payload(session: Session, run: AnalysisRun, *, include_involvement: bool = True,
                  min_score: float = 0.0) -> dict[str, Any]:
    nodes = session.scalars(select(GraphNode).where(GraphNode.analysis_run_id == run.id)).all()
    rels = session.scalars(
        select(Relationship).where(Relationship.analysis_run_id == run.id)
        .options(selectinload(Relationship.evidence))
    ).all()
    edges = []
    for r in rels:
        traversable = r.conditions.get("traversable", True)
        if (not include_involvement and not traversable) or r.score < min_score:
            continue
        edges.append({"data": {
            "id": r.id, "source": r.source_node_id, "target": r.target_node_id,
            "relationship_type": r.relationship_type, "direction": r.direction, "status": r.status,
            "origin": r.origin, "kb_rule_id": r.kb_rule_id, "mechanism": r.mechanism,
            "time_horizon": r.time_horizon, "traversable": traversable,
            "score": r.score, "score_components": {
                "confidence": r.confidence, "evidence_strength": r.evidence_strength,
                "economic_relevance": r.economic_relevance, "historical_support": r.historical_support,
                "historical_support_status": r.historical_support_status, "applicability": r.applicability},
            "score_details": r.score_details, "conditions": r.conditions,
            "reported_at": r.reported_at.isoformat() if r.reported_at else None,
            "evidence": [{"id": e.id, "type": e.evidence_type, "article_id": e.article_id, "passage": e.passage,
                          "reference": e.reference, "verified": e.verified} for e in r.evidence],
        }})
    return {
        "analysis_id": run.id,
        "event_id": run.event_id,
        "mode": run.mode,
        "generated_at": run.graph_generated_at.isoformat() if run.graph_generated_at else None,
        "graph_version": {"analysis_version": run.analysis_version,
                          "knowledge_base_version": run.knowledge_base_version, "config": run.config},
        "stats": run.graph_stats,
        "elements": {
            "nodes": [{"data": {"id": n.node_id, "label": n.label, "type": n.node_type, "origin": n.origin,
                                "on_impact_path": n.on_impact_path, "centrality": n.centrality,
                                "metadata": n.extra}} for n in nodes],
            "edges": edges,
        },
        "legend": {
            "status": {"REPORTED": "stated in a source article (passage verified)",
                       "OBSERVED": "measured in market data", "INFERRED": "from the economic knowledge base",
                       "UNVERIFIED": "claimed by extraction but the passage could not be verified"},
            "score": "heuristic support score in [0,1]; not a probability of any price move",
            "edges_are_not_causal_claims": True,
        },
    }
