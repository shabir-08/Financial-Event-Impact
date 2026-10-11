"""Deterministic MOCK LLM provider (``LLM_PROVIDER=mock``).

It never calls a model. It derives outputs from the article text with keyword rules and the
entity catalog, so the downstream graph still depends on the actual article - but every result
carries ``simulated=True`` and analysis runs using it are recorded with mode SIMULATED.
It is only used when explicitly configured; it is never a silent fallback for a failed provider.
"""

from __future__ import annotations

import re
from typing import Any

from app.domain import EdgeDirection, EntityType, EventType, MoveDirection, RelationshipType
from app.schemas.llm import (
    ArticleForLLM,
    AssetExplanation,
    EntityExtraction,
    EventClassification,
    Explanation,
    ExtractedEntity,
    ExtractedRelationship,
    LLMResult,
    MechanismExplanation,
    PrimaryEffect,
    RelationshipExtraction,
    ReportedFigure,
)
from app.services.entities.normalization import EntityNormalizer
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.text import split_sentences

_UP = r"\b(rise|rises|rose|risen|rising|jump\w*|surg\w*|soar\w*|climb\w*|gain\w*|hike\w*|raise[sd]?|raising|increas\w*|higher|strengthen\w*|rall\w*|spik\w*|impos\w*|widen\w*|escalat\w*)\b"
_DOWN = r"\b(fall|falls|fell|fallen|falling|drop\w*|slump\w*|plung\w*|declin\w*|cut|cuts|cutting|lower\w*|weaken\w*|slid\w*|slide|reduc\w*|tumbl\w*|sank|sink\w*|eas(e|ed|es|ing)|narrow\w*)\b"
_POS_LINK = r"(raising|lifting|boosting|pushing up|driving up|supporting|adding to|increasing)"
_NEG_LINK = r"(weighing on|hurting|pressuring|pressure on|dragging|squeezing|denting|hitting)"
_FIGURE = re.compile(r"(\$?\d[\d,.]*\s?(%|percent|per cent|basis points|bps|bp|billion|million|a barrel|per barrel))", re.I)
_COMPANY_LIKE = re.compile(r"\b([A-Z][A-Za-z&]+(?:\s[A-Z][A-Za-z&]+){0,3}\s(?:Ltd|Limited|Inc|Corp|Corporation|Holdings|Group|Airways|Airlines|Petroleum|Bank))\b")


class MockLLMProvider:
    name = "mock"
    model = "mock-deterministic-v1"
    simulated = True

    def __init__(self, kb: KnowledgeBase) -> None:
        self.kb = kb
        self.normalizer = EntityNormalizer(kb)

    def _result(self, output: Any) -> LLMResult:
        return LLMResult(output=output, provider=self.name, model=self.model, simulated=True)

    # ---------------------------------------------------------------- classify
    async def classify_event(self, article: ArticleForLLM) -> LLMResult[EventClassification]:
        text = f"{article.headline}\n{article.text}"
        low = text.lower()
        head = article.headline.lower()
        scores: dict[str, float] = {}
        for cat, meta in self.kb.categories["categories"].items():
            s = 0.0
            for kw in meta["keywords"]:
                if kw in low:
                    s += 1 + (1.5 if kw in head else 0)
            scores[cat] = s
        best = max(scores, key=lambda c: scores[c])
        fin_terms = sum(1 for t in self.kb.categories["financial_terms"] if t in low)
        noise = any(t in low for t in self.kb.categories["noise_terms"])
        # Provider feeds such as GDELT carry headlines only; require less corroborating vocabulary there.
        headline_only = article.text.startswith("(no article body available")
        is_event = scores[best] >= 2 and fin_terms >= (1 if headline_only else 2) and not noise
        sentences = split_sentences(text)
        mentions = self.normalizer.find_mentions(text)
        countries = sorted({self.kb.entities[m.entity_id].name for m in mentions
                            if m.entity_id in self.kb.entities and self.kb.entities[m.entity_id].type == EntityType.COUNTRY})
        figures = []
        for s in sentences:
            for m in _FIGURE.finditer(s):
                figures.append(ReportedFigure(label="figure reported in article", value=m.group(1).strip(), passage=s))
        effects = self._primary_effects(text)
        out = EventClassification(
            is_financial_event=is_event,
            event_type=EventType(best) if is_event else EventType.OTHER,
            title=article.headline.strip(),
            summary=" ".join(sentences[:2])[:600],
            event_date=(article.published_at or "")[:10] or None,
            countries=countries,
            reported_figures=figures[:6],
            primary_effects=effects,
            financial_relevance=round(min(1.0, 0.2 + 0.1 * scores[best] + 0.03 * fin_terms), 2) if is_event else 0.1,
            relevance_rationale=f"[SIMULATED] keyword score {scores[best]:.1f} for {best}; {fin_terms} financial terms.",
            supporting_passages=sentences[:2],
        )
        return self._result(out)

    def _primary_effects(self, text: str) -> list[PrimaryEffect]:
        effects: list[PrimaryEffect] = []
        seen: set[str] = set()
        for sentence in split_sentences(text)[:4]:
            for m in self.normalizer.find_mentions(sentence):
                node = m.entity_id
                target = self.kb.effect_variable(node) or node
                etype = self.normalizer.entity_type_of(target)
                if etype not in (EntityType.ECONOMIC_VARIABLE,) or target in seen:
                    continue
                window = sentence[m.end : m.end + 70].lower()
                before = sentence[max(0, m.start - 40) : m.start].lower()
                direction = None
                up, down = re.search(_UP, window), re.search(_DOWN, window)
                if up and (not down or up.start() < down.start()):
                    direction = MoveDirection.UP
                elif down:
                    direction = MoveDirection.DOWN
                elif re.search(_UP, before):
                    direction = MoveDirection.UP
                elif re.search(_DOWN, before):
                    direction = MoveDirection.DOWN
                if direction is None:
                    continue
                seen.add(target)
                effects.append(PrimaryEffect(target_mention=m.text, target_type=self.normalizer.entity_type_of(node),
                                             direction=direction, passage=sentence))
            if len(effects) >= 3:
                break
        return effects

    # ---------------------------------------------------------------- entities
    async def extract_entities(self, article: ArticleForLLM, event: EventClassification) -> LLMResult[EntityExtraction]:
        text = f"{article.headline}\n{article.text}"
        sentences = split_sentences(text)
        out: dict[tuple[str, str], ExtractedEntity] = {}
        for s in sentences:
            for m in self.normalizer.find_mentions(s):
                etype = self.normalizer.entity_type_of(m.entity_id)
                key = (m.text.lower(), etype.value)
                out.setdefault(key, ExtractedEntity(mention=m.text, entity_type=etype, passage=s, confidence=0.9))
            for cm in _COMPANY_LIKE.finditer(s):
                key = (cm.group(1).lower(), EntityType.COMPANY.value)
                if not any(k[0] == key[0] for k in out):
                    out.setdefault(key, ExtractedEntity(mention=cm.group(1), entity_type=EntityType.COMPANY,
                                                        passage=s, confidence=0.6))
        return self._result(EntityExtraction(entities=list(out.values())))

    # ----------------------------------------------------------- relationships
    async def extract_relationships(
        self, article: ArticleForLLM, event: EventClassification, entities: EntityExtraction
    ) -> LLMResult[RelationshipExtraction]:
        rels: list[ExtractedRelationship] = []
        for eff in event.primary_effects:
            up = eff.direction == MoveDirection.UP
            if eff.direction not in (MoveDirection.UP, MoveDirection.DOWN):
                continue
            rels.append(ExtractedRelationship(
                source_mention="EVENT", target_mention=eff.target_mention,
                relationship_type=RelationshipType.INCREASES if up else RelationshipType.REDUCES,
                direction=EdgeDirection.POSITIVE if up else EdgeDirection.NEGATIVE,
                mechanism=f"[SIMULATED] The article reports {eff.target_mention} moving {'up' if up else 'down'}.",
                passage=eff.passage, confidence=0.8))
        text = f"{article.headline}\n{article.text}"
        for s in split_sentences(text):
            ms = self.normalizer.find_mentions(s)
            if len(ms) < 2:
                continue
            for pattern, sign in ((_POS_LINK, 1), (_NEG_LINK, -1)):
                link = re.search(pattern, s, re.I)
                if not link:
                    continue
                before = [m for m in ms if m.end <= link.start()]
                after = [m for m in ms if m.start >= link.end()]
                if before and after:
                    src, tgt = before[-1], after[0]
                    rels.append(ExtractedRelationship(
                        source_mention=src.text, target_mention=tgt.text,
                        relationship_type=RelationshipType.INCREASES if sign > 0 else RelationshipType.REDUCES,
                        direction=EdgeDirection.from_sign(sign),
                        mechanism=f"[SIMULATED] Sentence links {src.text} to {tgt.text} ('{link.group(0)}').",
                        passage=s, confidence=0.6))
        return self._result(RelationshipExtraction(relationships=rels))

    # ------------------------------------------------------------- explanation
    async def generate_explanation(self, evidence_package: dict[str, Any], feedback: str | None = None) -> LLMResult[Explanation]:
        ev = evidence_package.get("event", {})
        paths = evidence_package.get("candidate_paths", [])[:3]
        assets = evidence_package.get("candidate_assets", [])[:5]
        obs = evidence_package.get("market_observations", [])
        articles = evidence_package.get("articles", [])
        mechanisms = []
        for p in paths:
            rel_refs = [r for r in p.get("relationship_refs", [])]
            mechanisms.append(MechanismExplanation(
                path_ref=p["ref"],
                explanation="[SIMULATED] " + " -> ".join(p.get("node_labels", [])),
                evidence_refs=rel_refs,
                status_note=f"Edge statuses along the path: {', '.join(p.get('edge_statuses', []))}.",
            ))
        asset_expl = []
        for a in assets:
            asset_expl.append(AssetExplanation(
                asset_ref=a["asset_id"],
                explanation=f"[SIMULATED] Reached via {len(a.get('path_refs', []))} candidate path(s).",
                direction_statement=f"Heuristic direction label: {a.get('impact_direction')} (not a prediction).",
                evidence_refs=a.get("path_refs", [])[:3],
            ))
        available = [o for o in obs if o.get("status") != "UNAVAILABLE"]
        hist = (
            f"[SIMULATED] {len(available)} market observation(s) available in the package; see M* references."
            if available else "Historical market data is unavailable for the candidate assets in this analysis."
        )
        out = Explanation(
            event_summary=f"[SIMULATED EXPLANATION] {ev.get('title', '')}",
            financial_relevance=str(ev.get("relevance_rationale") or ""),
            direct_entities=[e["name"] for e in evidence_package.get("entities", []) if e.get("origin") == "ARTICLE"][:10],
            mechanisms=mechanisms,
            affected_assets=asset_expl,
            historical_context=hist,
            reported_vs_inferred=(
                f"{sum(1 for r in evidence_package.get('relationships', []) if r.get('status') == 'REPORTED')} relationship(s) "
                f"are reported by {len(articles)} source article(s); the rest are INFERRED from the knowledge base."
            ),
            uncertainties=list(evidence_package.get("known_limitations", []))[:6],
            missing_data=list(evidence_package.get("missing_data", []))[:6],
            limitations="Mock provider output: template text, not model reasoning. Scores are heuristic, not probabilities.",
        )
        return self._result(out)
