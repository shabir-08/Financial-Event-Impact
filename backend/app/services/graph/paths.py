"""Impact propagation: bounded directed path discovery and transparent path ranking.

Path score (a ranking heuristic, NOT a probability):

    path_score = geometric_mean(edge scores) * length_decay^(edges - 1) * direction_factor

* geometric mean keeps one weak link visible without letting long paths collapse to ~0 the way a
  raw product would; the weakest link is reported separately
* length_decay (default 0.9) prefers shorter, more direct mechanisms
* direction_factor = 0.85 when any edge is context-dependent (the net direction is then unknown)
Net direction = product of edge signs (any 0 -> uncertain). Reachability alone never labels an
asset a winner or loser.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import islice

import networkx as nx

from app.core.config import Settings
from app.domain import EdgeStatus, ImpactDirection
from app.services.graph.builder import EdgeSpec, GraphBuild
from app.services.relationships.knowledge_base import KnowledgeBase

CONTEXT_DEPENDENT_FACTOR = 0.85
PATH_FORMULA = "geometric_mean(edge_scores) * length_decay^(n_edges-1) * direction_factor"


@dataclass
class RankedPath:
    nodes: list[str]
    edges: list[EdgeSpec]
    score: float
    breakdown: dict
    net_sign: int
    impact_direction: ImpactDirection
    explanation: str
    uncertainties: list[str]
    rank: int = 0

    @property
    def target(self) -> str:
        return self.nodes[-1]


@dataclass
class AssetCandidate:
    asset_id: str
    paths: list[RankedPath]
    impact_direction: ImpactDirection
    best_score: float
    mechanism: str
    uncertainty: list[str] = field(default_factory=list)


@dataclass
class PathAnalysis:
    paths: list[RankedPath]
    assets: list[AssetCandidate]
    centrality: dict[str, float]
    stats: dict


class PathAnalyzer:
    def __init__(self, kb: KnowledgeBase, settings: Settings) -> None:
        self.kb = kb
        self.settings = settings

    def analyze(self, build: GraphBuild) -> PathAnalysis:
        g = build.traversable_graph()
        source = build.event_node
        reachable = nx.descendants(g, source) if source in g else set()
        targets = sorted(n for n in reachable if self.kb.is_asset(n))
        per_asset_cap = self.settings.path_max_per_asset
        enumerate_cap = per_asset_cap * 10
        all_paths: list[RankedPath] = []
        truncated_assets = []
        for target in targets:
            gen = nx.all_simple_paths(g, source, target, cutoff=self.settings.path_max_depth)
            found = [self.rank_path(p, build) for p in islice(gen, enumerate_cap + 1)]
            if len(found) > enumerate_cap:
                truncated_assets.append(target)
                found = found[:enumerate_cap]
            found.sort(key=lambda p: (-p.score, len(p.nodes)))
            all_paths.extend(found[:per_asset_cap])
        all_paths.sort(key=lambda p: (-p.score, len(p.nodes)))
        all_paths = all_paths[: self.settings.path_max_total]
        for i, p in enumerate(all_paths, start=1):
            p.rank = i
        assets = self.aggregate_assets(all_paths)
        centrality = nx.betweenness_centrality(g) if g.number_of_nodes() <= 400 else {}
        stats = {"reachable_nodes": len(reachable), "candidate_assets": len(targets),
                 "paths_returned": len(all_paths), "path_enumeration_truncated_for": truncated_assets,
                 "max_depth": self.settings.path_max_depth, "formula": PATH_FORMULA,
                 "length_decay": self.settings.path_length_decay}
        return PathAnalysis(all_paths, assets, centrality, stats)

    def rank_path(self, nodes: list[str], build: GraphBuild) -> RankedPath:
        edges = [build.edges[(a, b)] for a, b in zip(nodes, nodes[1:])]
        scores = [max(e.score.score, 1e-6) for e in edges]
        gmean = math.exp(sum(math.log(s) for s in scores) / len(scores))
        decay = self.settings.path_length_decay ** (len(edges) - 1)
        has_ctx = any(e.sign == 0 for e in edges)
        dfac = CONTEXT_DEPENDENT_FACTOR if has_ctx else 1.0
        score = round(gmean * decay * dfac, 4)
        net = 0 if has_ctx else math.prod(e.sign for e in edges)
        weakest = min(edges, key=lambda e: e.score.score)
        breakdown = {
            "formula": PATH_FORMULA, "geometric_mean_edge_score": round(gmean, 4), "length_factor": round(decay, 4),
            "direction_factor": dfac, "n_edges": len(edges),
            "weakest_link": {"source": weakest.source, "target": weakest.target, "score": weakest.score.score},
            "edge_scores": [e.score.score for e in edges],
            "n_reported": sum(1 for e in edges if e.status == EdgeStatus.REPORTED),
            "n_inferred": sum(1 for e in edges if e.status == EdgeStatus.INFERRED),
            "n_unverified": sum(1 for e in edges if e.status == EdgeStatus.UNVERIFIED),
            "historical_support_on_path": [e.score.historical_support for e in edges if e.score.historical_support is not None],
            "is_probability": False,
        }
        return RankedPath(nodes, edges, score, breakdown, net, ImpactDirection.from_sign(net),
                          self._explain(nodes, edges, build), self._uncertainties(edges, net))

    def _explain(self, nodes: list[str], edges: list[EdgeSpec], build: GraphBuild) -> str:
        parts = [f"Event '{build.nodes[nodes[0]].label}'"]
        running = 1  # cumulative sign: the direction of pressure on each successive node
        for e in edges:
            running = running * e.sign
            effect = {1: "potential upward pressure on", -1: "potential downward pressure on"}.get(
                running, "an effect of uncertain direction on")
            tag = {"REPORTED": "reported in sources", "INFERRED": "inferred from knowledge base",
                   "UNVERIFIED": "claimed, passage not verified", "OBSERVED": "observed",
                   "ASSUMED": "scenario assumption"}[e.status.value]
            parts.append(f"{effect} {self.kb.node_label(e.target)} [{tag}: {e.mechanism or e.relationship_type}]")
        return " -> ".join(parts) + "."

    @staticmethod
    def _uncertainties(edges: list[EdgeSpec], net: int) -> list[str]:
        out = []
        if net == 0:
            out.append("At least one link is context-dependent, so the net direction cannot be determined.")
        for e in edges:
            note = (e.conditions or {}).get("note")
            if note:
                out.append(f"{e.source} -> {e.target}: {note}")
            if e.status == EdgeStatus.UNVERIFIED:
                out.append(f"{e.source} -> {e.target}: supporting passage could not be verified in the article.")
            if (e.conditions or {}).get("conflicting_directions"):
                out.append(f"{e.source} -> {e.target}: sources report conflicting directions.")
            if e.score.applicability < 1.0:
                out.append(f"{e.source} -> {e.target}: applicability reduced (context entities not mentioned).")
        if len(edges) >= 5:
            out.append("Long transmission chain: each additional link adds uncertainty.")
        return list(dict.fromkeys(out))

    def aggregate_assets(self, paths: list[RankedPath]) -> list[AssetCandidate]:
        by_asset: dict[str, list[RankedPath]] = defaultdict(list)
        for p in paths:
            by_asset[p.target].append(p)
        out = []
        for asset, ps in by_asset.items():
            signs = {p.net_sign for p in ps if p.net_sign != 0}
            if len(signs) > 1:
                direction = ImpactDirection.MIXED_SIGNALS
            elif signs:
                direction = ImpactDirection.from_sign(signs.pop())
            else:
                direction = ImpactDirection.DIRECTION_UNCERTAIN
            best = max(ps, key=lambda p: p.score)
            unc = list(dict.fromkeys(u for p in ps for u in p.uncertainties))[:8]
            if direction == ImpactDirection.MIXED_SIGNALS:
                unc.insert(0, "Different candidate paths imply opposite directions for this asset.")
            out.append(AssetCandidate(asset, sorted(ps, key=lambda p: -p.score), direction, best.score,
                                      best.explanation, unc))
        return sorted(out, key=lambda a: -a.best_score)
