"""Provider-independent LLM interface. Business logic depends only on this protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.schemas.llm import (
    ArticleForLLM,
    EntityExtraction,
    EventClassification,
    Explanation,
    LLMResult,
    RelationshipExtraction,
)


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str | None
    #: True for providers that do not call a real model; results must be labelled SIMULATED.
    simulated: bool

    async def classify_event(self, article: ArticleForLLM) -> LLMResult[EventClassification]: ...

    async def extract_entities(
        self, article: ArticleForLLM, event: EventClassification
    ) -> LLMResult[EntityExtraction]: ...

    async def extract_relationships(
        self, article: ArticleForLLM, event: EventClassification, entities: EntityExtraction
    ) -> LLMResult[RelationshipExtraction]: ...

    async def generate_explanation(
        self, evidence_package: dict[str, Any], feedback: str | None = None
    ) -> LLMResult[Explanation]: ...
