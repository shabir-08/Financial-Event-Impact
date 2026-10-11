"""GDELT DOC 2.0 API adapter (no API key required).

GDELT returns article metadata (title, URL, domain, seen date, language, source country) but
NOT article bodies; analysis therefore runs on headlines unless another source supplies text.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ProviderError
from app.services.http import get_with_retries
from app.services.news.base import FetchResult, NormalizedArticle

log = logging.getLogger(__name__)

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
#: GDELT allows one request every 5 seconds per IP; keep a margin.
GDELT_MIN_INTERVAL_SECONDS = 6.0
GDELT_MAX_RETRIES = 1
_gdelt_lock = asyncio.Lock()
_gdelt_last_request = 0.0


async def _gdelt_spacing() -> None:
    """Process-wide: wait until GDELT_MIN_INTERVAL_SECONDS have passed since the previous GDELT request."""
    global _gdelt_last_request
    async with _gdelt_lock:
        wait = _gdelt_last_request + GDELT_MIN_INTERVAL_SECONDS - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        _gdelt_last_request = time.monotonic()


class GDELTNewsProvider:
    name = "gdelt"
    provides_full_text = False

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client

    async def fetch(self, query: str | None = None, limit: int = 25, timespan: str = "1d") -> FetchResult:
        q = query or self.settings.gdelt_default_query
        params = {"query": q, "mode": "artlist", "format": "json", "maxrecords": min(limit, 250),
                  "timespan": timespan, "sort": "datedesc"}
        client = self._client or httpx.AsyncClient(timeout=self.settings.http_timeout_seconds)
        try:
            await _gdelt_spacing()
            resp = await get_with_retries(
                client, GDELT_URL, provider=self.name, params=params,
                max_retries=min(self.settings.http_max_retries, GDELT_MAX_RETRIES),
                backoff_seconds=self.settings.http_backoff_seconds, min_rate_limit_wait=GDELT_MIN_INTERVAL_SECONDS,
            )
        finally:
            if self._client is None:
                await client.aclose()
        try:
            payload = resp.json()
        except ValueError as exc:
            # GDELT answers malformed queries with a plain-text message and HTTP 200.
            raise ProviderError(f"GDELT returned non-JSON response: {resp.text[:200]!r}", provider=self.name) from exc
        return self.normalize(payload, query=q)

    def normalize(self, payload: dict, query: str | None = None) -> FetchResult:
        items = payload.get("articles") or []
        if not isinstance(items, list):
            raise ProviderError("GDELT payload 'articles' is not a list", provider=self.name)
        out, invalid = [], 0
        for item in items:
            try:
                out.append(
                    NormalizedArticle(
                        provider=self.name,
                        provider_article_id=item.get("url"),
                        headline=item.get("title") or "",
                        description=None,
                        content=None,
                        source_name=item.get("domain"),
                        url=item.get("url"),
                        published_at=_parse_seendate(item.get("seendate")),
                        language=item.get("language"),
                        source_country=item.get("sourcecountry"),
                        metadata={"seendate": item.get("seendate"), "full_text_available": False},
                    )
                )
            except (ValidationError, AttributeError, TypeError):
                invalid += 1
        return FetchResult(articles=out, invalid_count=invalid, query=query)


def _parse_seendate(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
