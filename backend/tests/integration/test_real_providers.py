"""Optional smoke tests against REAL external providers.

Skipped by default. Enable with RUN_REAL_PROVIDER_TESTS=1. The Anthropic test additionally needs
ANTHROPIC_API_KEY and makes one small billed API call.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

from app.core.config import Settings

pytestmark = [
    pytest.mark.real_provider,
    pytest.mark.skipif(os.environ.get("RUN_REAL_PROVIDER_TESTS") != "1", reason="set RUN_REAL_PROVIDER_TESTS=1"),
]


async def test_gdelt_returns_real_articles():
    from app.services.news.gdelt import GDELTNewsProvider

    res = await GDELTNewsProvider(Settings(_env_file=None)).fetch('"crude oil" sourcelang:english', limit=5, timespan="7d")
    assert res.articles and all(a.url and not a.is_simulated for a in res.articles)


async def test_yahoo_chart_returns_real_prices():
    from app.services.market_data.yahoo_chart import YahooChartProvider

    end = date.today()
    s = await YahooChartProvider(Settings(_env_file=None)).fetch_daily("INR=X", end - timedelta(days=30), end)
    assert not s.empty and not s.simulated and (s.frame["close"] > 0).all()


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")
async def test_anthropic_classification_round_trip():
    from app.schemas.llm import ArticleForLLM
    from app.services.llm.anthropic_provider import AnthropicProvider

    s = Settings(_env_file=None, llm_provider="anthropic", anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
                 llm_effort="low")
    res = await AnthropicProvider(s).classify_event(ArticleForLLM(
        article_id="smoke", headline="Brent crude jumps 6% after OPEC+ announces output cut",
        text="Brent crude rose 6% to $90 a barrel after OPEC+ said it would reduce production."))
    assert res.output.is_financial_event and not res.simulated


@pytest.mark.parametrize("name,key_env", [("gemini", "GEMINI_API_KEY"), ("groq", "GROQ_API_KEY")])
async def test_openai_compatible_classification_round_trip(name, key_env):
    if not os.environ.get(key_env):
        pytest.skip(f"{key_env} not set")
    from app.schemas.llm import ArticleForLLM
    from app.services.llm.openai_compatible import OpenAICompatibleProvider

    s = Settings(_env_file=None, **{key_env.lower(): os.environ[key_env]})
    res = await OpenAICompatibleProvider(name, s).classify_event(ArticleForLLM(
        article_id="smoke", headline="Brent crude jumps 6% after OPEC+ announces output cut",
        text="Brent crude rose 6% to $90 a barrel after OPEC+ said it would reduce production."))
    assert res.output.is_financial_event and not res.simulated and res.provider == name
