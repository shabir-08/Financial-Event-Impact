"""Turn LLM-extracted primary effects and relationships into article-backed claims.

Claims keep the article's own wording (mentions, passage) plus resolved node ids. A claim is
only usable as a REPORTED graph edge if both endpoints resolve and its passage is verified
verbatim against the article text.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain import EdgeDirection, EntityType, MoveDirection, RELATIONSHIP_DEFAULT_SIGN, RelationshipType
from app.schemas.llm import EventClassification, RelationshipExtraction
from app.services.entities.extraction import NormalizedMention
from app.services.entities.normalization import EntityNormalizer
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.text import normalize_alias, verify_passage

EVENT = "EVENT"
#: Confidence assigned to primary effects (the classification schema carries no per-effect confidence).
PRIMARY_EFFECT_CONFIDENCE = 0.85


@dataclass
class ClaimDraft:
    source_mention: str
    target_mention: str
    source_entity_id: str | None
    target_entity_id: str | None
    relationship_type: RelationshipType
    effect_sign: int
    mechanism: str | None
    passage: str | None
    passage_verified: bool
    confidence: float
    is_primary_effect: bool


class ClaimBuilder:
    def __init__(self, kb: KnowledgeBase, normalizer: EntityNormalizer) -> None:
        self.kb = kb
        self.normalizer = normalizer

    def _resolve(self, mention: str, lookup: dict[str, NormalizedMention], type_hint: EntityType | None) -> str | None:
        if mention == EVENT:
            return EVENT
        m = lookup.get(normalize_alias(mention))
        node = m.entity_id if m else None
        if node is None and type_hint is not None:
            node = self.normalizer.normalize(mention, type_hint).entity_id
        if node is None:
            return None
        # An event moves the *level/price* of a commodity, currency, institution's rate, etc.
        return self.kb.effect_variable(node) or node

    def build(
        self,
        classification: EventClassification,
        relationships: RelationshipExtraction,
        mentions: list[NormalizedMention],
        article_text: str,
    ) -> list[ClaimDraft]:
        lookup = {normalize_alias(m.mention): m for m in mentions}
        drafts: dict[tuple[str, str], ClaimDraft] = {}

        for eff in classification.primary_effects:
            if eff.direction == MoveDirection.UNCHANGED:
                continue
            target = self._resolve(eff.target_mention, lookup, eff.target_type)
            sign = eff.direction.sign
            rtype = {1: RelationshipType.INCREASES, -1: RelationshipType.REDUCES}.get(sign, RelationshipType.INFLUENCES)
            d = ClaimDraft(EVENT, eff.target_mention, EVENT, target, rtype, sign,
                           f"Article reports {eff.target_mention} moving {eff.direction.value}.",
                           eff.passage, verify_passage(eff.passage, article_text), PRIMARY_EFFECT_CONFIDENCE, True)
            drafts[(EVENT, target or f"?{eff.target_mention}")] = d

        for r in relationships.relationships:
            source = self._resolve(r.source_mention, lookup, None)
            target = self._resolve(r.target_mention, lookup, None)
            sign = r.direction.sign
            implied = RELATIONSHIP_DEFAULT_SIGN.get(r.relationship_type)
            mechanism = r.mechanism
            if implied is not None and sign != 0 and implied != sign:
                sign = 0  # contradictory type vs direction: do not pick one
                mechanism = f"{mechanism} [direction conflicts with relationship type; treated as context-dependent]"
            key = (source or f"?{r.source_mention}", target or f"?{r.target_mention}")
            if key[0] == key[1]:
                continue
            draft = ClaimDraft(r.source_mention, r.target_mention, source, target, r.relationship_type, sign,
                               mechanism, r.passage, verify_passage(r.passage, article_text), r.confidence,
                               r.source_mention == EVENT)
            existing = drafts.get(key)
            if existing is None or draft.confidence > existing.confidence:
                if existing and existing.is_primary_effect:
                    draft.is_primary_effect = True
                drafts[key] = draft
        return list(drafts.values())


def direction_label(sign: int) -> str:
    return EdgeDirection.from_sign(sign).value
