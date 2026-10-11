"""Structured-output schemas for every LLM task.

These models are sent to the provider as JSON schemas (structured outputs) and every
response is re-validated with Pydantic before it can touch the database or the graph.
Numeric ranges are validated after parsing (``check_ranges``) rather than encoded in the
schema, because not every provider's structured-output mode supports numeric bounds.
"""

from __future__ import annotations

from datetime import date
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain import EdgeDirection, EntityType, EventType, MoveDirection, RelationshipType

EXTRACTION_VERSION = "extract-v1"
EXPLANATION_VERSION = "explain-v1"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArticleForLLM(_Strict):
    article_id: str
    headline: str
    text: str
    source_name: str | None = None
    published_at: str | None = None


# ----------------------------------------------------------------- classification
class ReportedFigure(_Strict):
    label: str = Field(description="What the number measures, e.g. 'Brent crude price change'")
    value: str = Field(description="The figure exactly as written in the article, e.g. '8%' or '$92 a barrel'")
    passage: str = Field(description="Verbatim sentence from the article containing the figure")


class PrimaryEffect(_Strict):
    target_mention: str = Field(description="The variable/entity the event directly moved, as named in the article")
    target_type: EntityType
    direction: MoveDirection
    passage: str = Field(description="Verbatim sentence from the article stating this effect")


class EventClassification(_Strict):
    is_financial_event: bool = Field(description="True only if the article reports a concrete, financially relevant event")
    event_type: EventType
    title: str
    summary: str = Field(description="Two to three sentence factual summary of what the article reports")
    event_date: str | None = Field(description="YYYY-MM-DD date of the event if stated or clearly implied, else null")
    countries: list[str] = Field(description="Countries directly involved in the event")
    reported_figures: list[ReportedFigure]
    primary_effects: list[PrimaryEffect] = Field(
        description="Direct effects the article itself reports (not your own inferences)"
    )
    financial_relevance: float = Field(description="0.0-1.0: how financially material the event is")
    relevance_rationale: str
    supporting_passages: list[str] = Field(description="Verbatim sentences from the article that report the event")

    @field_validator("event_date")
    @classmethod
    def _iso_date(cls, v: str | None) -> str | None:
        if v in (None, "", "null"):
            return None
        date.fromisoformat(v)
        return v

    def check_ranges(self) -> None:
        if not 0.0 <= self.financial_relevance <= 1.0:
            raise ValueError("financial_relevance must be within [0, 1]")


# ----------------------------------------------------------------------- entities
class ExtractedEntity(_Strict):
    mention: str = Field(description="Entity name exactly as it appears in the article")
    entity_type: EntityType
    passage: str = Field(description="Verbatim sentence from the article where the entity appears")
    confidence: float = Field(description="0.0-1.0 confidence that this mention is correctly typed")


class EntityExtraction(_Strict):
    entities: list[ExtractedEntity]

    def check_ranges(self) -> None:
        for e in self.entities:
            if not 0.0 <= e.confidence <= 1.0:
                raise ValueError("entity confidence must be within [0, 1]")
            if e.entity_type == EntityType.EVENT:
                raise ValueError("EVENT is not an extractable entity type")


# ------------------------------------------------------------------ relationships
class ExtractedRelationship(_Strict):
    source_mention: str = Field(description="An extracted entity mention, or the literal 'EVENT' for the event itself")
    target_mention: str = Field(description="An extracted entity mention")
    relationship_type: RelationshipType
    direction: EdgeDirection = Field(
        description="POSITIVE if source rising pushes target up, NEGATIVE if down, CONTEXT_DEPENDENT if unclear"
    )
    mechanism: str = Field(description="Short economic mechanism as stated or clearly implied by the article")
    passage: str = Field(description="Verbatim sentence(s) from the article that state this relationship")
    confidence: float = Field(description="0.0-1.0 confidence that the article states this relationship")


class RelationshipExtraction(_Strict):
    relationships: list[ExtractedRelationship]

    def check_ranges(self) -> None:
        for r in self.relationships:
            if not 0.0 <= r.confidence <= 1.0:
                raise ValueError("relationship confidence must be within [0, 1]")


# -------------------------------------------------------------------- explanation
class MechanismExplanation(_Strict):
    path_ref: str = Field(description="Reference id of a candidate path from the evidence package, e.g. PATH1")
    explanation: str
    evidence_refs: list[str] = Field(description="Reference ids (A*, P*, R*, M*) from the package supporting this")
    status_note: str = Field(description="Which links are REPORTED by sources vs INFERRED from the knowledge base")


class AssetExplanation(_Strict):
    asset_ref: str = Field(description="Asset id exactly as listed in the evidence package")
    explanation: str
    direction_statement: str = Field(description="Cautious statement of potential direction, or why it is uncertain")
    evidence_refs: list[str]


class Explanation(_Strict):
    event_summary: str
    financial_relevance: str
    direct_entities: list[str]
    mechanisms: list[MechanismExplanation]
    affected_assets: list[AssetExplanation]
    historical_context: str = Field(description="Only numbers present in the package; say so if none are available")
    reported_vs_inferred: str
    uncertainties: list[str]
    missing_data: list[str]
    limitations: str

    def check_ranges(self) -> None:  # no numeric fields
        return None


T = TypeVar("T", bound=BaseModel)


class LLMResult(BaseModel, Generic[T]):
    output: T
    provider: str
    model: str | None
    simulated: bool
    attempts: int = 1
    request_ids: list[str] = []
    usage: dict[str, int] = {}
    #: Providers tried (and why they failed) before the one that served this result.
    fallback_trail: list[dict] = []
