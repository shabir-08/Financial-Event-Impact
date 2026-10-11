"""Dynamic, event-specific knowledge-graph construction (NetworkX, in memory).

Procedure for one event:
1. event node + nodes for entities the articles explicitly mention (origin ARTICLE)
2. article-supported edges from extracted claims (REPORTED if the passage verified, else UNVERIFIED)
3. event-trigger rules whose conditions match the event (INFERRED, origin EVENT_TRIGGER)
4. bounded BFS expansion over knowledge-base rules from the nodes the event reaches, keeping only
   rules whose applicability conditions hold (INFERRED, origin KNOWLEDGE_BASE)
5. pruning of inferred dead ends that lead to no asset
6. scoring of every edge
The graph therefore differs per event; nothing is loaded as a prebuilt result.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import networkx as nx

from app.core.config import Settings
from app.domain import EdgeDirection, EdgeStatus, EntityOrigin, EntityType, RelationshipOrigin, RelationshipType
from app.services.relationships.applicability import EventContext, evaluate_rule, evaluate_trigger
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.relationships.scoring import ScoreResult, score_article_claims, score_kb_rule, score_trigger

EVENT_PREFIX = "event:"


@dataclass
class ClaimRecord:
    id: str
    article_id: str
    source_entity_id: str | None  # "EVENT" for the event itself
    target_entity_id: str | None
    source_mention: str
    target_mention: str
    relationship_type: str
    effect_sign: int
    mechanism: str | None
    passage: str | None
    passage_verified: bool
    confidence: float
    is_primary_effect: bool
    source_domain: str | None
    published_at: datetime | None


@dataclass
class MentionRecord:
    entity_id: str | None
    mention_text: str
    entity_type: str


@dataclass
class EventInput:
    event_id: str
    event_type: str
    title: str
    mentions: list[MentionRecord]
    claims: list[ClaimRecord]


@dataclass
class EvidenceRef:
    evidence_type: str  # ARTICLE_PASSAGE | KNOWLEDGE_BASE_RATIONALE | EVENT_TRIGGER_RULE | HISTORICAL_COMPARISON
    article_id: str | None = None
    passage: str | None = None
    reference: str | None = None
    verified: bool = False


@dataclass
class EdgeSpec:
    source: str
    target: str
    relationship_type: str
    sign: int
    status: EdgeStatus
    origin: RelationshipOrigin
    mechanism: str | None
    score: ScoreResult
    evidence: list[EvidenceRef]
    kb_rule_id: str | None = None
    claim_ids: list[str] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)
    time_horizon: str | None = None
    reported_at: datetime | None = None
    #: Involvement edges (event -> mentioned entity) are shown but never used for impact paths.
    traversable: bool = True

    @property
    def direction(self) -> EdgeDirection:
        return EdgeDirection.from_sign(self.sign)


@dataclass
class NodeSpec:
    node_id: str
    node_type: str
    label: str
    origin: EntityOrigin | str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphBuild:
    graph: nx.DiGraph
    nodes: dict[str, NodeSpec]
    edges: dict[tuple[str, str], EdgeSpec]
    event_node: str
    context: EventContext
    excluded: list[dict[str, Any]]
    stats: dict[str, Any]

    def traversable_graph(self) -> nx.DiGraph:
        g = nx.DiGraph()
        g.add_nodes_from(self.graph.nodes)
        g.add_edges_from((s, t) for (s, t), e in self.edges.items() if e.traversable)
        return g


class GraphBuilder:
    def __init__(self, kb: KnowledgeBase, settings: Settings) -> None:
        self.kb = kb
        self.settings = settings
        self.weights = settings.scoring_weights

    def build(self, data: EventInput) -> GraphBuild:
        event_node = EVENT_PREFIX + data.event_id
        nodes: dict[str, NodeSpec] = {
            event_node: NodeSpec(event_node, EntityType.EVENT.value, data.title[:255], EntityOrigin.ARTICLE,
                                 {"event_type": data.event_type})
        }
        edges: dict[tuple[str, str], EdgeSpec] = {}
        excluded: list[dict[str, Any]] = []

        # 1. explicitly mentioned entities
        mentioned: set[str] = set()
        for m in data.mentions:
            if m.entity_id and self.kb.node_exists(m.entity_id):
                mentioned.add(m.entity_id)
                self._add_node(nodes, m.entity_id, EntityOrigin.ARTICLE)
            elif not m.entity_id:
                excluded.append({"kind": "unresolved_entity", "mention": m.mention_text, "entity_type": m.entity_type})
        primary = self._primary_effect_signs(data.claims)
        ctx = EventContext(
            event_type=data.event_type,
            entity_ids=mentioned | {v for e in mentioned if (v := self.kb.effect_variable(e))},
            primary_effects=primary,
        )

        # 2. article-supported edges
        grouped: dict[tuple[str, str], list[ClaimRecord]] = defaultdict(list)
        for c in data.claims:
            if not c.source_entity_id or not c.target_entity_id:
                excluded.append({"kind": "claim_unresolved_endpoint", "claim_id": c.id,
                                 "source": c.source_mention, "target": c.target_mention})
                continue
            src = event_node if c.source_entity_id == "EVENT" else c.source_entity_id
            if (src != event_node and not self.kb.node_exists(src)) or not self.kb.node_exists(c.target_entity_id):
                excluded.append({"kind": "claim_unknown_node", "claim_id": c.id})
                continue
            grouped[(src, c.target_entity_id)].append(c)
        for (src, tgt), claims in grouped.items():
            self._add_node(nodes, src, EntityOrigin.ARTICLE)
            self._add_node(nodes, tgt, EntityOrigin.ARTICLE)
            edges[(src, tgt)] = self._claim_edge(src, tgt, claims)

        # 2b. involvement edges for mentioned entities without a stated relationship (display only)
        for ent in sorted(mentioned):
            if (event_node, ent) not in edges and not any(t == ent for (_, t) in edges):
                edges[(event_node, ent)] = EdgeSpec(
                    event_node, ent, RelationshipType.ASSOCIATED_WITH.value, 0, EdgeStatus.REPORTED,
                    RelationshipOrigin.ARTICLE, "Entity is mentioned in the event's source article(s).",
                    score_article_claims(confidences=[0.5], verified=[True], source_domains=[None],
                                         is_primary_effect=False, kb=self.kb, weights=self.weights),
                    [], traversable=False)

        # 3. event triggers
        for trig in self.kb.triggers:
            decision = evaluate_trigger(trig, ctx)
            if not decision.applicable:
                continue
            if (event_node, trig.target) in edges and edges[(event_node, trig.target)].traversable:
                edges[(event_node, trig.target)].evidence.append(
                    EvidenceRef("EVENT_TRIGGER_RULE", reference=trig.id, passage=trig.mechanism))
                continue
            self._add_node(nodes, trig.target, EntityOrigin.INFERRED)
            edges[(event_node, trig.target)] = EdgeSpec(
                event_node, trig.target, trig.relationship_type.value, decision.sign, EdgeStatus.INFERRED,
                RelationshipOrigin.EVENT_TRIGGER, trig.mechanism,
                score_trigger(trig.reliability, trig.economic_relevance, self.weights),
                [EvidenceRef("EVENT_TRIGGER_RULE", reference=trig.id, passage=trig.mechanism)],
                kb_rule_id=trig.id, conditions={"reasons": decision.reasons})

        # 4. bounded knowledge-base expansion from what the event reaches
        self._expand(event_node, nodes, edges, ctx, excluded)

        # 5. prune inferred dead ends
        g = self._to_graph(nodes, edges)
        removed = self._prune(g, nodes, edges, event_node)

        stats = {
            "nodes": g.number_of_nodes(),
            "edges": g.number_of_edges(),
            "reported_edges": sum(1 for e in edges.values() if e.status == EdgeStatus.REPORTED and e.traversable),
            "unverified_edges": sum(1 for e in edges.values() if e.status == EdgeStatus.UNVERIFIED),
            "inferred_edges": sum(1 for e in edges.values() if e.status == EdgeStatus.INFERRED),
            "involvement_edges": sum(1 for e in edges.values() if not e.traversable),
            "asset_nodes": sum(1 for n in nodes if self.kb.is_asset(n)),
            "pruned_nodes": removed,
            "excluded_items": len(excluded),
            "knowledge_base_version": self.kb.version,
            "limits": {"kb_expansion_depth": self.settings.graph_kb_expansion_depth,
                       "max_nodes": self.settings.graph_max_nodes},
        }
        return GraphBuild(g, nodes, edges, event_node, ctx, excluded, stats)

    # ------------------------------------------------------------------ helpers
    def _add_node(self, nodes: dict[str, NodeSpec], node_id: str, origin: EntityOrigin) -> None:
        if node_id in nodes:
            if origin == EntityOrigin.ARTICLE:
                nodes[node_id].origin = EntityOrigin.ARTICLE
            return
        meta: dict[str, Any] = {}
        if self.kb.is_asset(node_id):
            a = self.kb.assets[node_id]
            meta = {"asset_type": a.asset_type.value, "is_asset": True, "quote_semantics": a.quote_semantics,
                    "currency": a.currency}
        nodes[node_id] = NodeSpec(node_id, self.kb.node_type(node_id), self.kb.node_label(node_id), origin, meta)

    @staticmethod
    def _primary_effect_signs(claims: list[ClaimRecord]) -> dict[str, int]:
        signs: dict[str, set[int]] = defaultdict(set)
        for c in claims:
            if c.source_entity_id == "EVENT" and c.target_entity_id and c.passage_verified:
                signs[c.target_entity_id].add(c.effect_sign)
        return {k: (next(iter(v)) if len(v) == 1 else 0) for k, v in signs.items()}

    def _claim_edge(self, src: str, tgt: str, claims: list[ClaimRecord]) -> EdgeSpec:
        verified = [c for c in claims if c.passage_verified]
        basis = verified or claims
        signs = {c.effect_sign for c in basis}
        conflict = len(signs) > 1
        sign = 0 if conflict else next(iter(signs))
        rtypes = {c.relationship_type for c in basis}
        rtype = next(iter(rtypes)) if len(rtypes) == 1 else RelationshipType.INFLUENCES.value
        score = score_article_claims(
            confidences=[c.confidence for c in claims], verified=[c.passage_verified for c in claims],
            source_domains=[c.source_domain for c in claims],
            is_primary_effect=any(c.is_primary_effect for c in claims), kb=self.kb, weights=self.weights,
        )
        if conflict:
            score.details["conflicting_evidence"] = "articles report different directions for this relationship"
        mechanisms = [c.mechanism for c in basis if c.mechanism]
        return EdgeSpec(
            src, tgt, rtype, sign, EdgeStatus.REPORTED if verified else EdgeStatus.UNVERIFIED,
            RelationshipOrigin.ARTICLE, mechanisms[0] if mechanisms else None, score,
            [EvidenceRef("ARTICLE_PASSAGE", article_id=c.article_id, passage=c.passage, verified=c.passage_verified)
             for c in claims],
            claim_ids=[c.id for c in claims],
            conditions={"conflicting_directions": sorted(signs)} if conflict else {},
            reported_at=min((c.published_at for c in claims if c.published_at), default=None),
        )

    def _expand(self, event_node: str, nodes: dict[str, NodeSpec], edges: dict[tuple[str, str], EdgeSpec],
                ctx: EventContext, excluded: list[dict[str, Any]]) -> None:
        max_depth, max_nodes = self.settings.graph_kb_expansion_depth, self.settings.graph_max_nodes
        out_existing: dict[str, list[str]] = defaultdict(list)
        for (s, t), e in edges.items():
            if e.traversable:
                out_existing[s].append(t)
        queue: deque[tuple[str, int]] = deque((t, 1) for t in out_existing[event_node])
        visited = {event_node}
        rejected_rules: set[str] = set()
        while queue:
            node, depth = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            for nxt in out_existing.get(node, []):  # continue along article-reported edges
                queue.append((nxt, depth + 1))
            if depth > max_depth:
                continue
            for rule in self.kb.outgoing(node):
                app = evaluate_rule(rule, ctx)
                if not app.applicable:
                    if rule.id not in rejected_rules:
                        rejected_rules.add(rule.id)
                        excluded.append({"kind": "rule_not_applicable", "rule_id": rule.id, "reasons": app.reasons})
                    continue
                key = (node, rule.target)
                ev = EvidenceRef("KNOWLEDGE_BASE_RATIONALE", reference=rule.id,
                                 passage=f"{rule.mechanism} Rationale: {rule.rationale}".strip())
                if key in edges:
                    edges[key].evidence.append(ev)  # reported edge corroborated by a known mechanism
                    if edges[key].kb_rule_id is None:
                        edges[key].kb_rule_id = rule.id
                    continue
                if rule.target not in nodes and len(nodes) >= max_nodes:
                    excluded.append({"kind": "node_limit_reached", "rule_id": rule.id, "limit": max_nodes})
                    continue
                self._add_node(nodes, rule.target, EntityOrigin.INFERRED)
                edges[key] = EdgeSpec(
                    node, rule.target, rule.relationship_type.value, rule.effect_sign, EdgeStatus.INFERRED,
                    RelationshipOrigin.KNOWLEDGE_BASE, rule.mechanism, score_kb_rule(rule, app.factor, self.weights),
                    [ev], kb_rule_id=rule.id,
                    conditions={**rule.conditions.model_dump(mode="json"), "applicability_reasons": app.reasons},
                    time_horizon=rule.time_horizon,
                )
                if rule.target not in visited:
                    queue.append((rule.target, depth + 1))

    @staticmethod
    def _to_graph(nodes: dict[str, NodeSpec], edges: dict[tuple[str, str], EdgeSpec]) -> nx.DiGraph:
        g = nx.DiGraph()
        for n in nodes.values():
            g.add_node(n.node_id, node_type=n.node_type, label=n.label, origin=str(n.origin))
        for (s, t), e in edges.items():
            g.add_edge(s, t, spec=e, score=e.score.score, sign=e.sign, traversable=e.traversable)
        return g

    def _prune(self, g: nx.DiGraph, nodes: dict[str, NodeSpec], edges: dict[tuple[str, str], EdgeSpec],
               event_node: str) -> int:
        removed = 0
        changed = True
        while changed:
            changed = False
            for n in list(g.nodes):
                if n == event_node or self.kb.is_asset(n) or nodes[n].origin == EntityOrigin.ARTICLE:
                    continue
                if not any(g.edges[n, t]["traversable"] for t in g.successors(n)):
                    for p in list(g.predecessors(n)):
                        edges.pop((p, n), None)
                    for t in list(g.successors(n)):
                        edges.pop((n, t), None)
                    g.remove_node(n)
                    nodes.pop(n, None)
                    removed += 1
                    changed = True
        return removed
