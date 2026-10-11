"""News provider abstraction and the common normalised article schema."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field, field_validator


class NormalizedArticle(BaseModel):
    provider: str
    provider_article_id: str | None = None
    headline: str = Field(min_length=1)
    description: str | None = None
    content: str | None = None
    source_name: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    language: str | None = None
    source_country: str | None = None
    is_simulated: bool = False
    metadata: dict[str, Any] = {}

    @field_validator("headline")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("headline is empty")
        return v


class FetchResult(BaseModel):
    articles: list[NormalizedArticle]
    #: Raw items the adapter could not normalise (missing headline, malformed fields...).
    invalid_count: int = 0
    query: str | None = None


class NewsProvider(Protocol):
    name: str
    #: Whether the provider delivers article bodies or only headline/summary.
    provides_full_text: bool

    async def fetch(self, query: str | None = None, limit: int = 25) -> FetchResult: ...
