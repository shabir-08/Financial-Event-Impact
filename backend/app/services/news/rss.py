"""Publisher RSS / Atom feeds (Hindustan Times, BBC, Economic Times, Mint, Bloomberg, ...). No API key.

Publishers provide these feeds for machine reading: headline, short summary, link and publication time
(not full article text; Bloomberg articles themselves are paywalled). Articles keep the publisher name
and link for attribution. Feed XML is untrusted input: parsed with defusedxml (no entity expansion /
external entities), size-capped, and HTML in summaries is stripped to plain text.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from itertools import zip_longest

import httpx
from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ConfigurationError, ProviderError
from app.services.http import get_with_retries
from app.services.news.base import FetchResult, NormalizedArticle

log = logging.getLogger(__name__)

MAX_FEED_BYTES = 5_000_000
ATOM = "{http://www.w3.org/2005/Atom}"
MEDIA = "{http://search.yahoo.com/mrss/}"
TAG_RE = re.compile(r"<[^>]+>")
KEY_RE = re.compile(r"^[a-z0-9_]{2,40}$")


@dataclass(frozen=True)
class Feed:
    key: str
    name: str
    url: str


def parse_feed_config(entries: list[str]) -> list[Feed]:
    """RSS_FEEDS entries: 'key|Display name|https://url' (comma-separated in .env)."""
    feeds, bad = [], []
    for e in entries:
        parts = [p.strip() for p in e.split("|")]
        if len(parts) != 3 or not KEY_RE.match(parts[0]) or not parts[2].startswith("https://"):
            bad.append(e)
            continue
        feeds.append(Feed(*parts))
    if bad:
        raise ConfigurationError("Invalid RSS_FEEDS entries (expected key|Name|https://url)", details={"entries": bad})
    keys = [f.key for f in feeds]
    if len(keys) != len(set(keys)):
        raise ConfigurationError("Duplicate keys in RSS_FEEDS")
    return feeds


def _text(el, tag: str) -> str | None:
    child = el.find(tag)
    return child.text.strip() if child is not None and child.text else None


def _plain(s: str | None, limit: int = 2000) -> str | None:
    if not s:
        return None
    t = " ".join(html.unescape(TAG_RE.sub(" ", s)).split())
    return t[:limit] or None


def _date(s: str | None) -> datetime | None:
    if not s:
        return None
    for parse in (parsedate_to_datetime, lambda v: datetime.fromisoformat(v.replace("Z", "+00:00"))):
        try:
            d = parse(s.strip())
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, IndexError):
            continue
    return None


def _image(it) -> str | None:
    """Publisher-supplied image: media:content / media:thumbnail / image enclosure (https only)."""
    for el in (*it.findall(f"{MEDIA}content"), *it.findall(f"{MEDIA}thumbnail"), *it.findall("enclosure")):
        url = el.get("url") or ""
        kind = el.get("type") or el.get("medium") or ""
        if url.startswith("https://") and (not kind or kind.startswith("image")):
            return url
    return None


def parse_feed(xml_bytes: bytes, feed: Feed) -> tuple[list[NormalizedArticle], int]:
    """Parse RSS 2.0 or Atom into normalised articles. Returns (articles, invalid_item_count)."""
    try:
        root = SafeET.fromstring(xml_bytes)
    except (SafeET.ParseError, DefusedXmlException) as exc:
        raise ProviderError(f"{feed.name}: feed is not valid/safe XML ({type(exc).__name__})", provider="rss") from exc
    items = root.findall("./channel/item") or root.findall(f"{ATOM}entry")
    out, invalid = [], 0
    for it in items:
        try:
            if it.tag == f"{ATOM}entry":
                link_el = it.find(f"{ATOM}link[@rel='alternate']")
                if link_el is None:  # elements without children are falsy: never use `or` here
                    link_el = it.find(f"{ATOM}link")
                link = link_el.get("href") if link_el is not None else None
                headline = _plain(_text(it, f"{ATOM}title"), 500)
                summary = _plain(_text(it, f"{ATOM}summary") or _text(it, f"{ATOM}content"))
                published = _date(_text(it, f"{ATOM}published") or _text(it, f"{ATOM}updated"))
                guid = _text(it, f"{ATOM}id")
                cats = [c.get("term") for c in it.findall(f"{ATOM}category") if c.get("term")]
            else:
                link = _text(it, "link")
                headline = _plain(_text(it, "title"), 500)
                summary = _plain(_text(it, "description"))
                published = _date(_text(it, "pubDate"))
                guid = _text(it, "guid")
                cats = [c.text.strip() for c in it.findall("category") if c.text]
            out.append(NormalizedArticle(
                provider="rss", provider_article_id=guid or link, headline=headline or "", description=summary,
                source_name=feed.name, url=link if link and link.startswith(("https://", "http://")) else None,
                published_at=published, language="en",
                metadata={"feed": feed.key, "feed_url": feed.url, "categories": cats[:10], "full_text_available": False,
                          "attribution": f"{feed.name} (publisher RSS feed)", "image_url": _image(it)}))
        except (ValidationError, AttributeError, TypeError, ValueError):
            invalid += 1
    return out, invalid


class RSSNewsProvider:
    name = "rss"
    provides_full_text = False

    def __init__(self, settings: Settings, feeds: list[str] | None = None, client: httpx.AsyncClient | None = None) -> None:
        all_feeds = parse_feed_config(settings.rss_feeds)
        if not all_feeds:
            raise ConfigurationError("NEWS_PROVIDER=rss but RSS_FEEDS is empty", details={"integration": "news", "provider": "rss"})
        if feeds:
            unknown = sorted(set(feeds) - {f.key for f in all_feeds})
            if unknown:
                raise ConfigurationError("Unknown RSS feed keys", details={"unknown": unknown, "available": [f.key for f in all_feeds]})
        self.feeds = [f for f in all_feeds if not feeds or f.key in feeds]
        self.settings = settings
        self._client = client

    async def _fetch_one(self, client: httpx.AsyncClient, feed: Feed) -> tuple[list[NormalizedArticle], int]:
        resp = await get_with_retries(client, feed.url, provider=f"rss:{feed.key}",
                                      headers={"User-Agent": "financial-impact-graph RSS reader (research)"},
                                      max_retries=1, backoff_seconds=self.settings.http_backoff_seconds)
        if len(resp.content) > MAX_FEED_BYTES:
            raise ProviderError(f"{feed.name}: feed larger than {MAX_FEED_BYTES} bytes", provider="rss")
        return parse_feed(resp.content, feed)

    async def fetch(self, query: str | None = None, limit: int = 25) -> FetchResult:
        """``query``: optional keyword filter (case-insensitive, any word) on headline + summary."""
        client = self._client or httpx.AsyncClient(timeout=self.settings.http_timeout_seconds, follow_redirects=True)
        try:
            results = await asyncio.gather(*(self._fetch_one(client, f) for f in self.feeds), return_exceptions=True)
        finally:
            if self._client is None:
                await client.aclose()
        per_feed, invalid, notes = [], 0, []
        words = [w.lower() for w in (query or "").split() if w.strip()]
        for feed, res in zip(self.feeds, results):
            if isinstance(res, BaseException):
                notes.append(f"{feed.name}: {getattr(res, 'message', type(res).__name__)}")
                log.warning("RSS feed %s failed: %s", feed.key, type(res).__name__)
                continue
            arts, bad = res
            invalid += bad
            if words:
                arts = [a for a in arts if any(w in f"{a.headline} {a.description or ''}".lower() for w in words)]
            arts.sort(key=lambda a: a.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            per_feed.append(arts)
        if len(notes) == len(self.feeds):
            raise ProviderError("All RSS feeds failed", provider="rss", feeds=notes)
        # newest first, interleaved across publishers so one busy feed does not crowd out the others
        merged = [a for group in zip_longest(*per_feed) for a in group if a is not None][:limit]
        return FetchResult(articles=merged, invalid_count=invalid, query=query, notes=notes)
