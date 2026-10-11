"""Canonical node extraction from an event's PERSISTED graph (graph_nodes + impact_paths).

Roles are not stored by the graph builder, so they are derived deterministically from topology:

* asset        - the node is a knowledge-base asset (terminal of impact paths)        [derived:kb_asset]
* trigger      - first node after the event node on at least one ranked impact path [derived:path_position]
* intermediate - any other node on a ranked impact path                             [derived:path_position]
* context      - persisted but on no ranked path (e.g. a mentioned country)         [derived:not_on_ranked_path]

Weight (normalised importance) = max score of the ranked paths through the node / the event's best
path score, so the event's own strongest mechanism is the reference (1.0). Context nodes have no
path support: weight NULL, excluded from similarity (never silently set to 0).
Node ids are the existing canonical knowledge-base ids; nothing is merged by label.
"""

from __future__ import annotations

from datetime import datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalysisRun, Event, GraphNode, ImpactPath
from app.services.graph.builder import EVENT_PREFIX
from app.services.lineage.scoring import NodeRec
from app.services.relationships.knowledge_base import KnowledgeBase


def event_time(event: Event) -> datetime | None:
    """event_date at 00:00 UTC (day precision), else first_reported_at; None if neither is known."""
    if event.event_date:
        return datetime.combine(event.event_date, time.min, tzinfo=timezone.utc)
    if event.first_reported_at:
        t = event.first_reported_at
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    return None


def extract_nodes(session: Session, run: AnalysisRun, kb: KnowledgeBase) -> tuple[list[NodeRec], list[float]]:
    """Returns (canonical nodes, path scores) for one analysis run."""
    gnodes = session.scalars(select(GraphNode).where(GraphNode.analysis_run_id == run.id)).all()
    paths = session.scalars(select(ImpactPath).where(ImpactPath.analysis_run_id == run.id)
                            .order_by(ImpactPath.rank)).all()
    best = max((p.path_score for p in paths), default=0.0)
    path_weight: dict[str, float] = {}
    first_hop: set[str] = set()
    for p in paths:
        for i, nid in enumerate(p.node_ids):
            if nid.startswith(EVENT_PREFIX):
                continue
            path_weight[nid] = max(path_weight.get(nid, 0.0), p.path_score)
            if i == 1:
                first_hop.add(nid)
    out = []
    for g in sorted(gnodes, key=lambda g: g.node_id):
        if g.node_id.startswith(EVENT_PREFIX) or g.node_type == "EVENT":
            continue
        on_path = g.node_id in path_weight
        if kb.is_asset(g.node_id) or (g.extra or {}).get("is_asset"):
            role, source = "asset", "derived:kb_asset"
        elif g.node_id in first_hop:
            role, source = "trigger", "derived:path_position"
        elif on_path:
            role, source = "intermediate", "derived:path_position"
        else:
            role, source = "context", "derived:not_on_ranked_path"
        weight = round(path_weight[g.node_id] / best, 6) if on_path and best > 0 else None
        if role == "asset" and not on_path:
            source = "derived:kb_asset_not_on_ranked_path"
        out.append(NodeRec(g.node_id, g.label, g.node_type, role, weight, source))
    return out, [p.path_score for p in paths]
