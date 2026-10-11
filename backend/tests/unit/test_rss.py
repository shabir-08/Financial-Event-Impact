"""Publisher RSS/Atom provider: parsing, safety, partial failures, selection (respx-mocked HTTP)."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.core.config import Settings
from app.core.errors import ConfigurationError, ProviderError
from app.services.news.ingestion import build_news_provider
from app.services.news.rss import Feed, RSSNewsProvider, parse_feed, parse_feed_config

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title><![CDATA[RBI hikes repo rate by 50 bps]]></title><link>https://pub.example/a1</link>
<description><![CDATA[<p>The central bank <b>raised</b> rates &amp; signalled more.</p>]]></description>
<pubDate>Sun, 11 Oct 2026 16:48:54 +0530</pubDate><guid>a1</guid><category>Economy</category></item>
<item><title>Oil jumps after OPEC cut</title><link>https://pub.example/a2</link><pubDate>Sat, 10 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title></title><link>https://pub.example/empty</link></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>A</title>
<entry><title>Rupee hits record low</title><link rel="alternate" href="https://atom.example/r1"/><id>tag:r1</id>
<updated>2026-10-11T09:00:00Z</updated><summary>The rupee fell past 90 per dollar.</summary></entry></feed>"""

BOMB = b"""<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">]>
<rss><channel><item><title>&lol2;</title></item></channel></rss>"""

FEEDS = ["pub_one|Publisher One|https://pub.example/rss", "pub_two|Publisher Two|https://atom.example/feed"]


def S(**kw) -> Settings:
    return Settings(_env_file=None, http_backoff_seconds=0.0, rss_feeds=FEEDS, **kw)


def test_parse_rss_strips_html_and_keeps_attribution():
    arts, invalid = parse_feed(RSS, Feed("pub_one", "Publisher One", "https://pub.example/rss"))
    assert [a.headline for a in arts] == ["RBI hikes repo rate by 50 bps", "Oil jumps after OPEC cut"] and invalid == 1
    a = arts[0]
    assert a.description == "The central bank raised rates & signalled more."
    assert a.source_name == "Publisher One" and a.url == "https://pub.example/a1" and a.provider == "rss"
    assert a.published_at.isoformat() == "2026-10-11T16:48:54+05:30"
    assert a.metadata["feed"] == "pub_one" and a.metadata["full_text_available"] is False


def test_parse_atom():
    arts, _ = parse_feed(ATOM, Feed("pub_two", "Publisher Two", "https://atom.example/feed"))
    assert arts[0].headline == "Rupee hits record low" and arts[0].url == "https://atom.example/r1"
    assert arts[0].published_at.isoformat() == "2026-10-11T09:00:00+00:00"


def test_entity_expansion_is_rejected():
    with pytest.raises(ProviderError, match="not valid/safe XML"):
        parse_feed(BOMB, Feed("x_feed", "X", "https://x.example/rss"))


@respx.mock
async def test_partial_failure_and_interleaving():
    respx.get("https://pub.example/rss").mock(return_value=httpx.Response(200, content=RSS))
    respx.get("https://atom.example/feed").mock(return_value=httpx.Response(503))
    r = await RSSNewsProvider(S()).fetch(limit=10)
    assert [a.source_name for a in r.articles] == ["Publisher One", "Publisher One"]
    assert r.notes and "Publisher Two" in r.notes[0]


@respx.mock
async def test_all_feeds_failing_is_an_error():
    respx.get("https://pub.example/rss").mock(return_value=httpx.Response(503))
    respx.get("https://atom.example/feed").mock(return_value=httpx.Response(503))
    with pytest.raises(ProviderError, match="All RSS feeds failed"):
        await RSSNewsProvider(S()).fetch()


@respx.mock
async def test_keyword_filter_and_feed_selection():
    respx.get("https://pub.example/rss").mock(return_value=httpx.Response(200, content=RSS))
    atom = respx.get("https://atom.example/feed").mock(return_value=httpx.Response(200, content=ATOM))
    r = await RSSNewsProvider(S(), feeds=["pub_one"]).fetch(query="opec")
    assert [a.headline for a in r.articles] == ["Oil jumps after OPEC cut"] and atom.call_count == 0


def test_config_validation():
    with pytest.raises(ConfigurationError):
        parse_feed_config(["bad entry"])
    with pytest.raises(ConfigurationError):
        parse_feed_config(["k1|Name|http://insecure.example/rss"])  # https only
    with pytest.raises(ConfigurationError, match="Unknown RSS feed keys"):
        RSSNewsProvider(S(), feeds=["nope"])
    assert isinstance(build_news_provider(S(), "rss"), RSSNewsProvider)


def test_rss_feeds_env_is_comma_separated(monkeypatch):
    monkeypatch.setenv("RSS_FEEDS", "a_feed|A|https://a.example/rss, b_feed|B|https://b.example/rss")
    s = Settings(_env_file=None)
    assert [f.key for f in parse_feed_config(s.rss_feeds)] == ["a_feed", "b_feed"]
