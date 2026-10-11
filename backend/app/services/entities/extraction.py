"""Entity extraction (LLM) followed by normalisation (deterministic) as separate stages."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain import EntityOrigin, NormalizationStatus
from app.schemas.llm import EntityExtraction
from app.services.entities.normalization import EntityNormalizer
from app.services.text import normalize_alias, verify_passage


@dataclass
class NormalizedMention:
    mention: str
    entity_type: str
    entity_id: str | None
    status: NormalizationStatus
    method: str | None
    candidates: list[str]
    passage: str | None
    passage_verified: bool
    confidence: float
    origin: EntityOrigin = EntityOrigin.ARTICLE


def normalize_extracted_entities(
    extraction: EntityExtraction, normalizer: EntityNormalizer, article_text: str
) -> list[NormalizedMention]:
    out: dict[tuple[str, str], NormalizedMention] = {}
    for e in extraction.entities:
        key = (normalize_alias(e.mention), e.entity_type.value)
        if key in out:
            continue
        res = normalizer.normalize(e.mention, e.entity_type)
        out[key] = NormalizedMention(
            mention=e.mention.strip()[:500],
            entity_type=e.entity_type.value,
            entity_id=res.entity_id,
            status=res.status,
            method=res.method,
            candidates=res.candidates,
            passage=e.passage,
            passage_verified=verify_passage(e.passage, article_text),
            confidence=e.confidence,
        )
    return list(out.values())
