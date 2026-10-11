"""Finnhub market-news adapter (requires FINNHUB_API_KEY).

Uses the general ``/news`` endpoint; Finnhub supplies headline + summary, not full text.
The API key is sent as the ``X-Finnhub-Token`` header so it never appears in URLs or logs.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ConfigurationError, ProviderError
from app.services.http import get_with_retries
from app.services.news.base import FetchResult, NormalizedArticle

FINNHUB_URL = "https://finnhub.io/api/v1/news"


class FinnhubNewsProvider:
    name = "finnhub"
    provides_full_text = False

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if not settings.finnhub_api_key or not settings.finnhub_api_key.get_secret_value():
            raise ConfigurationError(
                "NEWS_PROVIDER=finnhub but FINNHUB_API_KEY is not set",
                details={"integration": "news", "provider": "finnhub"},
            )
        self.settings = settings
        self._client = client

    async def fetch(self, query: str | None = None, limit: int = 25) -> FetchResult:
        category = query or "general"
        client = self._client or httpx.AsyncClient(timeout=self.settings.http_timeout_seconds)
        try:
            resp = await get_with_retries(
                client, FINNHUB_URL, provider=self.name, params={"category": category},
                headers={"X-Finnhub-Token": self.settings.finnhub_api_key.get_secret_value()},
                max_retries=self.settings.http_max_retries, backoff_seconds=self.settings.http_backoff_seconds,
            )
        finally:
            if self._client is None:
                await client.aclose()
        try:
            payload = resp.json()
        except ValueError as exc:
            raise ProviderError("Finnhub returned non-JSON response", provider=self.name) from exc
        return self.normalize(payload, limit=limit, query=category)

    def normalize(self, payload: list, limit: int = 25, query: str | None = None) -> FetchResult:
        if not isinstance(payload, list):
            raise ProviderError("Finnhub payload is not a list", provider=self.name)
        out, invalid = [], 0
        for item in payload[:limit]:
            try:
                ts = item.get("datetime")
                out.append(
                    NormalizedArticle(
                        provider=self.name,
                        provider_article_id=str(item["id"]) if item.get("id") is not None else None,
                        headline=item.get("headline") or "",
                        description=item.get("summary") or None,
                        source_name=item.get("source"),
                        url=item.get("url"),
                        published_at=datetime.fromtimestamp(ts, tz=timezone.utc) if isinstance(ts, (int, float)) else None,
                        metadata={"category": item.get("category"), "related": item.get("related"),
                                  "full_text_available": False},
                    )
                )
            except (ValidationError, AttributeError, TypeError, ValueError, OSError):
                invalid += 1
        return FetchResult(articles=out, invalid_count=invalid, query=query)
