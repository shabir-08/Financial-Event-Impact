"""Fixture news provider: loads SIMULATED demo articles from ``data/fixtures/articles.json``.

Every article it returns is marked ``is_simulated=True``; it exists for tests and offline demos.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.core.config import DATA_DIR
from app.services.news.base import FetchResult, NormalizedArticle


class FixtureNewsProvider:
    name = "fixture"
    provides_full_text = True

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DATA_DIR / "fixtures" / "articles.json"

    async def fetch(self, query: str | None = None, limit: int = 25) -> FetchResult:
        raw = json.loads(self.path.read_text(encoding="utf-8"))["articles"]
        out, invalid = [], 0
        for item in raw:
            if query and query.lower() not in (item.get("headline", "") + item.get("content", "")).lower():
                continue
            try:
                out.append(NormalizedArticle(provider=self.name, is_simulated=True,
                                             metadata={"simulated": True}, **item))
            except ValidationError:
                invalid += 1
        return FetchResult(articles=out[:limit], invalid_count=invalid, query=query)
