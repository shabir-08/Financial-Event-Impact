"""News and market-data adapters: normalisation, malformed payloads, HTTP failures (respx-mocked)."""

from datetime import date

import httpx
import pytest
import respx

from app.core.config import Settings
from app.core.errors import ConfigurationError, ProviderError, RateLimitedError
from app.services.http import get_with_retries
from app.services.market_data.alphavantage import AlphaVantageProvider
from app.services.market_data.yahoo_chart import YahooChartProvider
from app.services.news.finnhub import FinnhubNewsProvider
from app.services.news.fixture import FixtureNewsProvider
from app.services.news.gdelt import GDELT_URL, GDELTNewsProvider
from app.services.news.ingestion import dedup_key


def S(**kw) -> Settings:
    return Settings(_env_file=None, http_backoff_seconds=0.0, http_max_retries=2, **kw)


class TestHttpRetries:
    @respx.mock
    async def test_retries_then_succeeds(self):
        route = respx.get("https://x.test/a").mock(side_effect=[httpx.Response(503), httpx.Response(200, json={})])
        async with httpx.AsyncClient() as c:
            r = await get_with_retries(c, "https://x.test/a", provider="t", backoff_seconds=0)
        assert r.status_code == 200 and route.call_count == 2

    @respx.mock
    async def test_timeout_exhaustion_raises_retryable_error(self):
        respx.get("https://x.test/a").mock(side_effect=httpx.ReadTimeout("slow"))
        async with httpx.AsyncClient() as c:
            with pytest.raises(ProviderError) as ei:
                await get_with_retries(c, "https://x.test/a", provider="t", max_retries=1, backoff_seconds=0)
        assert ei.value.retryable

    @respx.mock
    async def test_rate_limit_honours_retry_after_then_raises(self):
        respx.get("https://x.test/a").mock(return_value=httpx.Response(429, headers={"retry-after": "0"}))
        async with httpx.AsyncClient() as c:
            with pytest.raises(RateLimitedError):
                await get_with_retries(c, "https://x.test/a", provider="t", max_retries=1, backoff_seconds=0)

    @respx.mock
    async def test_client_error_not_retried(self):
        route = respx.get("https://x.test/a").mock(return_value=httpx.Response(401))
        async with httpx.AsyncClient() as c:
            with pytest.raises(ProviderError):
                await get_with_retries(c, "https://x.test/a", provider="t", backoff_seconds=0)
        assert route.call_count == 1


class TestNews:
    def test_gdelt_normalisation_and_missing_fields(self):
        payload = {"articles": [
            {"url": "https://a.com/1", "title": "Oil jumps", "seendate": "20261005T064500Z", "domain": "a.com",
             "language": "English", "sourcecountry": "India"},
            {"url": "https://a.com/2", "title": "", "seendate": "bad"},  # no headline -> invalid
            {"url": "https://a.com/3", "title": "No date"},
            "garbage",
        ]}
        res = GDELTNewsProvider(S()).normalize(payload)
        assert [a.headline for a in res.articles] == ["Oil jumps", "No date"]
        assert res.invalid_count == 2
        assert res.articles[0].published_at.isoformat() == "2026-10-05T06:45:00+00:00"
        assert res.articles[1].published_at is None

    @respx.mock
    async def test_gdelt_non_json_is_provider_error(self):
        respx.get(GDELT_URL).mock(return_value=httpx.Response(200, text="Your query was too short"))
        with pytest.raises(ProviderError, match="non-JSON"):
            await GDELTNewsProvider(S()).fetch("x")

    def test_finnhub_requires_key_and_normalises(self):
        with pytest.raises(ConfigurationError):
            FinnhubNewsProvider(S(finnhub_api_key=None))
        p = FinnhubNewsProvider(S(finnhub_api_key="k"))
        res = p.normalize([{"id": 1, "headline": "Fed hikes", "summary": "s", "source": "X", "url": "https://x.com/1",
                            "datetime": 1791000000}, {"id": 2, "headline": None}])
        assert len(res.articles) == 1 and res.invalid_count == 1

    @respx.mock
    async def test_finnhub_token_sent_as_header_not_url(self):
        route = respx.get("https://finnhub.io/api/v1/news").mock(return_value=httpx.Response(200, json=[]))
        await FinnhubNewsProvider(S(finnhub_api_key="secret-token")).fetch()
        req = route.calls[0].request
        assert "secret-token" not in str(req.url) and req.headers["X-Finnhub-Token"] == "secret-token"

    async def test_fixture_articles_are_simulated(self):
        res = await FixtureNewsProvider().fetch()
        assert res.articles and all(a.is_simulated for a in res.articles)

    def test_dedup_key_same_url_across_providers(self):
        from app.services.news.base import NormalizedArticle
        a = NormalizedArticle(provider="gdelt", headline="h", url="https://www.x.com/a?utm_source=1")
        b = NormalizedArticle(provider="finnhub", headline="other", url="https://x.com/a")
        assert dedup_key(a) == dedup_key(b)


class TestMarketProviders:
    def test_yahoo_parse(self):
        payload = {"chart": {"result": [{"meta": {"currency": "INR", "exchangeTimezoneName": "Asia/Kolkata"},
                                         "timestamp": [1791000000, 1791086400],
                                         "indicators": {"quote": [{"open": [1, 2], "high": [1, 2], "low": [1, 2],
                                                                   "close": [10.0, None], "volume": [5, 6]}]}}],
                             "error": None}}
        s = YahooChartProvider(S()).parse("X", payload)
        assert len(s.frame) == 1 and s.currency == "INR"  # null close dropped, never filled

    def test_yahoo_error_payload_is_empty_series(self):
        s = YahooChartProvider(S()).parse("BAD", {"chart": {"result": None, "error": {"code": "Not Found"}}})
        assert s.empty and "provider error" in s.notes[0]

    def test_alphavantage_rate_limit_notice(self):
        p = AlphaVantageProvider(S(market_data_api_key="k"))
        with pytest.raises(RateLimitedError):
            p.parse("IBM", {"Note": "Thank you for using Alpha Vantage! Our standard API rate limit is..."},
                    date(2026, 1, 1), date(2026, 2, 1))

    def test_alphavantage_parse(self):
        p = AlphaVantageProvider(S(market_data_api_key="k"))
        payload = {"Time Series (Daily)": {"2026-01-05": {"1. open": "1", "2. high": "1", "3. low": "1",
                                                          "4. close": "1.5", "5. volume": "10"}}}
        s = p.parse("IBM", payload, date(2026, 1, 1), date(2026, 2, 1))
        assert float(s.frame.loc[date(2026, 1, 5), "close"]) == 1.5

    def test_alphavantage_requires_key(self):
        with pytest.raises(ConfigurationError):
            AlphaVantageProvider(S(market_data_api_key=None))
