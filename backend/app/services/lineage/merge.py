"""Query-time merged graph over the focus event and its lineage events (render-only view).

Built from the existing persisted per-event graphs; nothing is copied or modified. Node glow and
edge thickness are bounded, time-decayed cumulative support:

    G(n, t) = sum over LIVE events e containing n of relevance(e, t) * weight(e, n)
    glow(n) = 1 - exp(-G(n, t) / k)

Edge thickness uses the same form with the persisted edge score (in [0,1]) as the weight. Edges are
merged only when (source, target, relationship_type) match; opposing directions are never summed
(direction_conflict = true, per-direction support kept). These values are for rendering only and
are never fed back into similarity, impact or any model.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EventNode, GraphNode, Relationship
from app.services.graph.builder import EVENT_PREFIX
from app.services.lineage.config import LineageConfig

OPPOSING = {"POSITIVE", "NEGATIVE"}


def _sat(g: float, k: float) -> float:
    return round(1 - math.exp(-g / k), 6) if g > 0 else 0.0


def merged_graph(session: Session, members: list[dict[str, Any]], lineage_links: list[dict[str, Any]],
                 cfg: LineageConfig) -> dict[str, Any]:
    """``members``: [{event_id, run_id, relevance, live}], ``lineage_links``: links shown as event->event edges."""
    k = cfg.render.glow_k
    runs = {m["run_id"]: m for m in members}
    if not runs:
        return {"elements": {"nodes": [], "edges": []}, "truncated": False, "stats": {}}
    gnodes = session.scalars(select(GraphNode).where(GraphNode.analysis_run_id.in_(runs))).all()
    rels = session.scalars(select(Relationship).where(Relationship.analysis_run_id.in_(runs))).all()
    weights = {(r.analysis_run_id, r.node_id): r.weight for r in session.scalars(
        select(EventNode).where(EventNode.analysis_run_id.in_(runs)))}

    nodes: dict[str, dict[str, Any]] = {}
    for g in sorted(gnodes, key=lambda g: (g.node_id, g.analysis_run_id)):
        m = runs[g.analysis_run_id]
        is_event_node = g.node_id.startswith(EVENT_PREFIX)
        w = 1.0 if is_event_node else weights.get((g.analysis_run_id, g.node_id))
        n = nodes.setdefault(g.node_id, {"id": g.node_id, "label": g.label, "type": g.node_type, "roles": {},
                                         "contributing_event_ids": [], "per_event_weights": {}, "support": 0.0,
                                         "is_event_node": is_event_node})
        if m["event_id"] not in n["contributing_event_ids"]:
            n["contributing_event_ids"].append(m["event_id"])
        n["per_event_weights"][m["event_id"]] = w
        if w is not None and m["live"] and m["relevance"]:
            n["support"] += m["relevance"] * w
    roles = {(r.analysis_run_id, r.node_id): r.role for r in session.scalars(
        select(EventNode).where(EventNode.analysis_run_id.in_(runs)))}
    for g in gnodes:
        role = roles.get((g.analysis_run_id, g.node_id))
        if role:
            nodes[g.node_id]["roles"][runs[g.analysis_run_id]["event_id"]] = role

    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in sorted(rels, key=lambda r: (r.source_node_id, r.target_node_id, r.relationship_type, r.analysis_run_id)):
        m = runs[r.analysis_run_id]
        key = (r.source_node_id, r.target_node_id, r.relationship_type)
        e = edges.setdefault(key, {"id": "merged:" + "|".join(key), "source": key[0], "target": key[1],
                                   "relationship_type": key[2], "contributing_event_ids": [],
                                   "per_event": {}, "support_by_direction": defaultdict(float)})
        if m["event_id"] not in e["contributing_event_ids"]:
            e["contributing_event_ids"].append(m["event_id"])
        e["per_event"][m["event_id"]] = {"relationship_id": r.id, "direction": r.direction, "status": r.status,
                                         "score": r.score, "mechanism": r.mechanism}
        if m["live"] and m["relevance"]:
            e["support_by_direction"][r.direction] += m["relevance"] * r.score

    out_nodes = []
    for n in nodes.values():
        role_values = sorted(set(n["roles"].values()))
        out_nodes.append({"data": {
            "id": n["id"], "label": n["label"], "type": n["type"],
            "role": role_values[0] if len(role_values) == 1 else (role_values or None),
            "roles_by_event": n["roles"], "contributing_event_ids": n["contributing_event_ids"],
            "per_event_weights": n["per_event_weights"], "cumulative_support": round(n["support"], 6),
            "glow": _sat(n["support"], k),
            "is_bridge": (not n["is_event_node"]) and len(n["contributing_event_ids"]) >= 2,
            "is_event_node": n["is_event_node"], "render_only": True}})
    out_edges = []
    for e in edges.values():
        dirs = {d for d in (v["direction"] for v in e["per_event"].values())}
        conflict = OPPOSING <= dirs
        by_dir = {d: round(v, 6) for d, v in sorted(e["support_by_direction"].items())}
        support = max(by_dir.values(), default=0.0) if conflict else sum(by_dir.values())
        out_edges.append({"data": {
            "id": e["id"], "source": e["source"], "target": e["target"], "relationship_type": e["relationship_type"],
            "kind": "event_graph", "direction": None if conflict else (next(iter(dirs)) if len(dirs) == 1 else "MIXED"),
            "direction_conflict": conflict,
            "direction_conflict_detail": ({d: [eid for eid, v in e["per_event"].items() if v["direction"] == d]
                                           for d in sorted(dirs)} if conflict else None),
            "contributing_event_ids": e["contributing_event_ids"], "per_event": e["per_event"],
            "support_by_direction": by_dir, "thickness": _sat(support, k),
            "thickness_by_direction": {d: _sat(v, k) for d, v in by_dir.items()} if conflict else None,
            "render_only": True}})
    for link in lineage_links:
        src, tgt = EVENT_PREFIX + link["parent_id"], EVENT_PREFIX + link["child_id"]
        out_edges.append({"data": {
            "id": f"lineage:{link['parent_id']}->{link['child_id']}", "source": src, "target": tgt,
            "relationship_type": f"LINEAGE_{link['link_type']}", "kind": "lineage", "status": "INFERRED",
            "score": link["score"], "effective_strength": link["effective_strength"],
            "is_primary": link["is_primary"], "thickness": link["effective_strength"] or 0.0,
            "note": "Inferred from overlapping graph nodes; not a causal claim.", "render_only": True}})

    truncated = False
    if len(out_nodes) > cfg.render.max_nodes:
        truncated = True
        ranked = sorted(out_nodes, key=lambda n: (not n["data"]["is_event_node"], -n["data"]["glow"], n["data"]["id"]))
        out_nodes = ranked[: cfg.render.max_nodes]
    present = {n["data"]["id"] for n in out_nodes}
    out_edges = [e for e in out_edges if e["data"]["source"] in present and e["data"]["target"] in present]
    out_nodes.sort(key=lambda n: n["data"]["id"])
    out_edges.sort(key=lambda e: e["data"]["id"])
    return {"elements": {"nodes": out_nodes, "edges": out_edges}, "truncated": truncated,
            "stats": {"nodes": len(out_nodes), "edges": len(out_edges), "total_nodes_before_cap": len(nodes),
                      "bridge_nodes": sum(1 for n in out_nodes if n["data"]["is_bridge"]),
                      "direction_conflicts": sum(1 for e in out_edges if e["data"].get("direction_conflict")),
                      "render_cap": cfg.render.max_nodes, "glow_k": k}}
