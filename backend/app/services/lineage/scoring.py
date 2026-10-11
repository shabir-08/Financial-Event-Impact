"""Deterministic lineage math (no database access): TF-IDF similarity, link gates, decay, paths.

Every quantity here is a heuristic. Similarity measures overlap of canonical graph nodes; it does
not establish that one event caused another. Impact/relevance are rankings, not probabilities.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.services.lineage.config import LineageConfig

PARENT, DUPLICATE, ANALOGUE = "PARENT", "DUPLICATE", "ANALOGUE"
DAY = 86400.0


@dataclass(frozen=True)
class NodeRec:
    node_id: str
    label: str
    node_type: str
    role: str  # trigger | intermediate | asset | context
    weight: float | None  # None: no path support -> excluded from scoring (never coerced to 0)
    role_source: str = "derived"


@dataclass
class EventProfile:
    event_id: str
    run_id: str
    event_time: datetime
    first_reported_at: datetime | None
    category: str
    impact: float
    half_life_days: float | None
    nodes: dict[str, NodeRec]
    title: str = ""

    @property
    def key(self) -> tuple:
        return ordering_key(self.event_time, self.first_reported_at, self.event_id)

    def scored(self) -> dict[str, NodeRec]:
        return {k: n for k, n in self.nodes.items() if n.weight is not None and n.role != "context"}


@dataclass
class Comparison:
    score: float
    shared: list[dict]  # per shared node: id, label, roles, weights, idf, hub, informative, contribution
    shared_count: int
    informative_count: int


@dataclass
class Decision:
    parent_id: str
    link_type: str | None  # PARENT | DUPLICATE | ANALOGUE | None (rejected)
    score: float
    gap_days: float
    effective_strength: float | None
    reason: str | None
    comparison: Comparison
    parent_run_id: str = ""
    rank: int | None = None
    is_primary: bool = False


@dataclass
class AncestorPath:
    event_id: str
    strength: float
    depth: int
    via: list[str] = field(default_factory=list)  # event ids from focus (exclusive) to this ancestor


# ------------------------------------------------------------------- time
def as_utc(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def ordering_key(event_time: datetime, first_reported_at: datetime | None, event_id: str) -> tuple:
    """Total order (event_time, first_reported_at, id): parents must be strictly smaller -> acyclic."""
    et = as_utc(event_time)
    return (et, as_utc(first_reported_at) if first_reported_at else et, event_id)


def gap_days(child_time: datetime, parent_time: datetime) -> float:
    return (as_utc(child_time) - as_utc(parent_time)).total_seconds() / DAY


# ------------------------------------------------------------- similarity
def idf(n_events: int, df: int) -> float:
    """idf(n) = ln((N + 1) / (df(n) + 1)); 0 for a node present in every event."""
    return math.log((n_events + 1) / (df + 1))


def document_frequencies(profiles: Iterable[EventProfile]) -> tuple[int, dict[str, int]]:
    n, df = 0, {}
    for p in profiles:
        n += 1
        for node_id in p.scored():
            df[node_id] = df.get(node_id, 0) + 1
    return n, df


def vector(p: EventProfile, idf_map: Mapping[str, float], cfg: LineageConfig, cold_start: bool) -> dict[str, float]:
    s = cfg.similarity
    hubs = set(s.hub_nodes)
    out = {}
    for node_id, n in sorted(p.scored().items()):
        w = idf_map.get(node_id, 0.0) * s.role_weights.get(n.role, 0.0) * n.weight
        if node_id in hubs:
            w *= 0.0 if cold_start else s.hub_weight
        if w > 0:
            out[node_id] = w
    return out


def compare(child: EventProfile, parent: EventProfile, idf_map: Mapping[str, float], cfg: LineageConfig,
            cold_start: bool) -> Comparison:
    """Cosine similarity of the two TF-IDF vectors, with each shared node's additive contribution."""
    a, b = vector(child, idf_map, cfg, cold_start), vector(parent, idf_map, cfg, cold_start)
    na, nb = math.sqrt(sum(v * v for v in a.values())), math.sqrt(sum(v * v for v in b.values()))
    hubs = set(cfg.similarity.hub_nodes)
    shared_ids = sorted(set(child.scored()) & set(parent.scored()))
    shared, informative = [], 0
    for nid in shared_ids:
        cn, pn = child.nodes[nid], parent.nodes[nid]
        contrib = (a.get(nid, 0.0) * b.get(nid, 0.0) / (na * nb)) if na and nb else 0.0
        is_hub = nid in hubs
        is_informative = (not is_hub and idf_map.get(nid, 0.0) > 0
                          and cn.role != "asset" and pn.role != "asset")
        informative += is_informative
        shared.append({"node_id": nid, "label": cn.label, "node_type": cn.node_type,
                       "child_role": cn.role, "parent_role": pn.role,
                       "child_weight": round(cn.weight, 6), "parent_weight": round(pn.weight, 6),
                       "idf": round(idf_map.get(nid, 0.0), 6), "hub": is_hub, "informative": is_informative,
                       "contribution": round(contrib, 6)})
    score = sum(x["contribution"] for x in shared) if na and nb else 0.0
    shared.sort(key=lambda x: (-x["contribution"], x["node_id"]))
    return Comparison(round(min(score, 1.0), 6), shared, len(shared), informative)


# --------------------------------------------------------- impact & decay
def impact_score(path_scores: Iterable[float], cfg: LineageConfig) -> float:
    """I_e = clip(mean(top-k path scores) / S_ref, 0, 1); 0 when the event has no scored paths."""
    top = sorted((s for s in path_scores if s is not None and s >= 0), reverse=True)[: cfg.impact.top_k_paths]
    if not top:
        return 0.0
    return round(max(0.0, min(1.0, (sum(top) / len(top)) / cfg.impact.s_ref)), 6)


def half_life(category: str, impact: float, cfg: LineageConfig) -> float | None:
    """HL_e = HL_category * (1 + alpha * I_e); None when the category has no configured half-life."""
    base = cfg.half_life_for(category)
    return None if base is None else round(base * (1 + cfg.impact.alpha * impact), 6)


def effective_strength(similarity: float, gap: float, parent_half_life: float | None) -> float | None:
    """similarity * 2^(-gap / HL_parent). None (not a guess) when the half-life is missing/invalid."""
    if parent_half_life is None or not math.isfinite(parent_half_life) or parent_half_life <= 0 or gap < 0:
        return None
    return round(similarity * 2 ** (-gap / parent_half_life), 6)


def reinforced_anchor(event_time: datetime, child_links: Iterable[tuple[datetime, float]],
                      as_of: datetime) -> datetime:
    """t_anchor += strength * (t_child - t_anchor) over accepted child links (child time <= as_of),
    in child-time order. Derived at query time; nothing is stored or incremented."""
    anchor = as_utc(event_time)
    for t_child, strength in sorted(((as_utc(t), s) for t, s in child_links), key=lambda x: x[0]):
        if t_child > as_utc(as_of) or t_child <= anchor or not strength or strength <= 0:
            continue
        anchor = anchor + (t_child - anchor) * min(strength, 1.0)
    return anchor


def relevance(impact: float, half_life_days: float | None, anchor: datetime, t: datetime) -> float | None:
    """r_e(t) = I_e * 2^(-(t - t_anchor) / HL_e). Not a probability of anything."""
    if half_life_days is None or half_life_days <= 0:
        return None
    age = max(0.0, gap_days(t, anchor))
    return round(impact * 2 ** (-age / half_life_days), 6)


def is_live(impact: float, half_life_days: float | None, anchor: datetime, t: datetime, cfg: LineageConfig) -> bool:
    """Live iff relevance >= epsilon AND age since the (reinforced) anchor <= max_lifetime * HL."""
    r = relevance(impact, half_life_days, anchor, t)
    if r is None:
        return False
    age = gap_days(t, anchor)
    return r >= cfg.relevance.expiry_epsilon and age <= cfg.relevance.max_lifetime_half_lives * half_life_days


# ------------------------------------------------------------ link gates
def decide(child: EventProfile, parent: EventProfile, cmp: Comparison, parent_live: bool,
           cfg: LineageConfig) -> Decision:
    """Classify one (child, earlier candidate) pair. Order: ordering -> duplicate -> gates -> parent/analogue."""
    gap = gap_days(child.event_time, parent.event_time)
    d = Decision(parent.event_id, None, cmp.score, round(gap, 6), None, None, cmp, parent.run_id)
    if parent.event_id == child.event_id:
        d.reason = "self"
        return d
    if not parent.key < child.key:
        d.reason = "not_earlier"
        return d
    s = cfg.similarity
    if cmp.score >= cfg.duplicate.min_similarity and gap <= cfg.duplicate.max_gap_days \
            and cmp.shared_count >= s.min_shared_nodes:
        d.link_type = DUPLICATE
        return d
    if cmp.shared_count < s.min_shared_nodes:
        d.reason = "too_few_shared_nodes"
    elif cmp.informative_count < s.min_informative_shared_nodes:
        d.reason = "no_informative_shared_node"  # hub-only / terminal-asset-only overlap
    elif cmp.score < s.min_similarity:
        d.reason = "below_min_similarity"
    if d.reason:
        return d
    if not parent_live:
        if cmp.score >= cfg.analogue.min_similarity:
            d.link_type = ANALOGUE
        else:
            d.reason = "parent_not_live"
        return d
    strength = effective_strength(cmp.score, gap, parent.half_life_days)
    if strength is None:
        d.reason = "parent_half_life_unavailable"
        return d
    d.link_type, d.effective_strength = PARENT, strength
    return d


def select_parents(decisions: list[Decision], cfg: LineageConfig) -> list[Decision]:
    """Keep at most max_parent_links PARENT decisions by effective strength; the first is primary.
    Ties: higher similarity, then smaller gap, then parent id (deterministic)."""
    parents = sorted((d for d in decisions if d.link_type == PARENT),
                     key=lambda d: (-d.effective_strength, -d.score, d.gap_days, d.parent_id))
    keep = parents[: cfg.similarity.max_parent_links]
    for d in parents[cfg.similarity.max_parent_links:]:
        d.link_type, d.reason = None, "exceeds_max_parent_links"
    for i, d in enumerate(keep, start=1):
        d.rank, d.is_primary = i, i == 1
    return keep


# ------------------------------------------------------------------ paths
def strongest_paths(start: str, edges: Mapping[str, list[tuple[str, float]]], *, min_strength: float,
                    max_depth: int) -> dict[str, AncestorPath]:
    """Max-product path from ``start`` to every reachable node with depth <= max_depth.

    Exact layered DP (best product per (depth, node)); strengths are in (0, 1] so products only
    shrink. Zero/None strengths are skipped. Path strength is a product, never a sum.
    """
    best: dict[str, AncestorPath] = {}
    frontier = {start: AncestorPath(start, 1.0, 0, [])}
    for depth in range(1, max_depth + 1):
        nxt: dict[str, AncestorPath] = {}
        for u in sorted(frontier):
            pu = frontier[u]
            for v, w in sorted(edges.get(u, []), key=lambda x: (-x[1], x[0])):
                if not w or w <= 0 or v == start or v in pu.via:
                    continue
                s = round(pu.strength * min(w, 1.0), 9)
                if s < min_strength:
                    continue
                cur = nxt.get(v)
                if cur is None or s > cur.strength or (s == cur.strength and pu.via + [v] < cur.via):
                    nxt[v] = AncestorPath(v, s, depth, pu.via + [v])
        for v, p in nxt.items():
            cur = best.get(v)
            if cur is None or p.strength > cur.strength:
                best[v] = p
        frontier = nxt
        if not frontier:
            break
    return best
