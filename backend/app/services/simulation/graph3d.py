"""Frontend (3D) graph serialisation: layered nodes, edges with stable ids, and impact paths.

Graph semantics are preserved: edge scores are support scores (not probabilities); reachability is
reported separately from model predictions; layers are visualization metadata only. The frontend
computes 3D positions.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.domain import EdgeStatus, EntityOrigin
from app.services.graph.builder import SCENARIO_PREFIX, EdgeSpec, GraphBuild
from app.services.graph.paths import PathAnalysis
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.simulation.scenarios import ScenarioCatalog

EVIDENCE_STATUS = {EdgeStatus.REPORTED: "reported", EdgeStatus.OBSERVED: "observed", EdgeStatus.INFERRED: "inferred",
                   EdgeStatus.UNVERIFIED: "unverified", EdgeStatus.ASSUMED: "assumed"}
NODE_EVIDENCE = {EntityOrigin.ARTICLE: "reported", EntityOrigin.INFERRED: "inferred", EntityOrigin.SCENARIO: "assumed"}


@lru_cache
def load_layers(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sector_condition_variables"] = set(data["sector_condition_variables"])
    data["layer_list"] = [{"layer": int(k), "name": v} for k, v in sorted(data["layers"].items(), key=lambda kv: int(kv[0]))]
    return data


def layer_for(node_id: str, node_type: str, layers: dict) -> int | None:
    if node_id in layers["sector_condition_variables"]:
        return 3
    return layers["by_type"].get(node_type)


def edge_id(e: EdgeSpec, used: set[str]) -> str:
    if e.source.startswith(SCENARIO_PREFIX) and e.status == EdgeStatus.ASSUMED:
        base = f"{'seed' if e.traversable else 'involves'}:{e.source[len(SCENARIO_PREFIX):]}:{e.target}"
    else:
        base = e.kb_rule_id or f"edge:{e.source}->{e.target}"
    eid, k = base, 2
    while eid in used:  # a rule id can only appear once per graph, but keep ids unique regardless
        eid, k = f"{base}#{k}", k + 1
    used.add(eid)
    return eid


def _edge_json(eid: str, e: EdgeSpec, on_path: bool) -> dict:
    return {"id": eid, "source": e.source, "target": e.target, "relationship_type": e.relationship_type,
            "direction": e.direction.value, "sign": e.sign, "status": e.status.value,
            "evidence_status": EVIDENCE_STATUS.get(e.status, "unknown"), "origin": e.origin.value,
            "mechanism": e.mechanism, "time_horizon": e.time_horizon, "traversable": e.traversable,
            "on_impact_path": on_path,
            "support_score": {"value": e.score.score, "is_probability": False,
                              "components": {"confidence": e.score.confidence, "evidence_strength": e.score.evidence_strength,
                                             "economic_relevance": e.score.economic_relevance,
                                             "applicability": e.score.applicability}},
            "evidence_ids": [r.reference for r in e.evidence if r.reference],
            "evidence": [{"type": r.evidence_type, "reference": r.reference, "summary": r.passage} for r in e.evidence],
            "conditions_note": (e.conditions or {}).get("note")}


def serialize_scenario_graph(build: GraphBuild, analysis: PathAnalysis, kb: KnowledgeBase, layers: dict,
                             predictions_by_asset: dict[str, dict]) -> dict:
    used: set[str] = set()
    ids = {key: edge_id(e, used) for key, e in build.edges.items()}
    on_path_edges = {(a, b) for p in analysis.paths for a, b in zip(p.nodes, p.nodes[1:])}
    on_path_nodes = {n for p in analysis.paths for n in p.nodes}
    asset_signal = {a.asset_id: a for a in analysis.assets}
    nodes = []
    for n in build.nodes.values():
        origin = n.origin if isinstance(n.origin, EntityOrigin) else EntityOrigin(n.origin)
        is_asset = kb.is_asset(n.node_id)
        sig = asset_signal.get(n.node_id)
        pred = predictions_by_asset.get(n.node_id)
        nodes.append({
            "id": n.node_id, "label": n.label, "type": n.node_type, "layer": layer_for(n.node_id, n.node_type, layers),
            "origin": origin.value, "evidence_status": NODE_EVIDENCE.get(origin, "unknown"),
            "is_asset": is_asset, "on_impact_path": n.node_id in on_path_nodes,
            "graph_signal": ({"reachable_from_scenario": True, "impact_direction": sig.impact_direction.value,
                              "best_path_score": sig.best_score, "n_paths": len(sig.paths),
                              "note": "Graph-derived potential direction from knowledge-base pathways; not a quantitative prediction."}
                             if sig else {"reachable_from_scenario": n.node_id in on_path_nodes or n.node_id == build.event_node,
                                          "impact_direction": None, "best_path_score": None, "n_paths": 0}),
            "prediction": pred if pred else {"status": "not_a_model_target" if is_asset else "not_applicable",
                                             "estimated_return_pct": None, "horizon_trading_days": None},
            "evidence_ids": [], "metadata": n.metadata,
        })
    edges = [_edge_json(ids[k], e, k in on_path_edges) for k, e in build.edges.items()]
    paths = []
    for p in analysis.paths:
        paths.append({"id": f"path:{p.rank}", "rank": p.rank, "target_asset_id": p.target, "node_ids": p.nodes,
                      "edge_ids": [ids[(a, b)] for a, b in zip(p.nodes, p.nodes[1:])],
                      "path_score": p.score, "score_is_probability": False, "net_sign": p.net_sign,
                      "impact_direction": p.impact_direction.value, "explanation": p.explanation,
                      "uncertainties": p.uncertainties, "edge_statuses": [e.status.value for e in p.edges]})
    return {"nodes": nodes, "edges": edges, "paths": paths}


def full_knowledge_graph(kb: KnowledgeBase, catalog: ScenarioCatalog, layers: dict) -> dict:
    """Initial 3D graph: every knowledge-base relationship plus the scenario catalog as layer-1 nodes."""
    nodes: dict[str, dict] = {}

    def add(nid: str, origin: str = "KNOWLEDGE_BASE") -> None:
        if nid not in nodes:
            ntype = kb.node_type(nid)
            nodes[nid] = {"id": nid, "label": kb.node_label(nid), "type": ntype, "layer": layer_for(nid, ntype, layers),
                          "origin": origin, "is_asset": kb.is_asset(nid), "evidence_status": "knowledge_base"}

    edges = []
    for r in kb.rules.values():
        add(r.source)
        add(r.target)
        edges.append({"id": r.id, "source": r.source, "target": r.target, "relationship_type": r.relationship_type.value,
                      "sign": r.effect_sign, "status": "INFERRED", "evidence_status": "knowledge_base",
                      "evidence_basis": r.evidence_basis, "kind": r.kind, "mechanism": r.mechanism,
                      "support_score": {"reliability": r.reliability, "economic_relevance": r.economic_relevance,
                                        "is_probability": False},
                      "evidence_ids": [r.id]})
    for s in catalog.scenarios:
        sid = SCENARIO_PREFIX + s.id
        nodes[sid] = {"id": sid, "label": s.display_name, "type": "EVENT", "layer": 1, "origin": "SCENARIO",
                      "is_asset": False, "evidence_status": "scenario_definition", "category": s.category}
        for e in s.initiating_entities:
            add(e)
            edges.append({"id": f"involves:{s.id}:{e}", "source": sid, "target": e, "relationship_type": "ASSOCIATED_WITH",
                          "sign": 0, "status": "SCENARIO_DEFINITION", "evidence_status": "scenario_definition",
                          "mechanism": "Initiating entity of the scenario", "evidence_ids": []})
        seeds = sorted({sd.node_id for p in s.parameters for sd in catalog.parameters[p].graph_seeds})
        for nid in seeds:
            add(nid)
            edges.append({"id": f"param:{s.id}:{nid}", "source": sid, "target": nid, "relationship_type": "SCENARIO_PARAMETER",
                          "sign": 0, "status": "SCENARIO_DEFINITION", "evidence_status": "scenario_definition",
                          "mechanism": "Variable the scenario's shock parameters act on (direction set by the user's values)",
                          "evidence_ids": []})
    return {"nodes": list(nodes.values()), "edges": edges,
            "layers": layers["layer_list"], "knowledge_base_version": kb.version, "scenario_catalog_version": catalog.version}
