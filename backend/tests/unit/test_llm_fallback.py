"""OpenAI-compatible adapter (Gemini/Groq/xAI/Ollama) and the fallback chain - no real API calls."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from pydantic import SecretStr

from app.core.config import Settings
from app.core.errors import ConfigurationError, LLMOutputError, ProviderError, RateLimitedError
from app.schemas.llm import ArticleForLLM, EntityExtraction, LLMResult
from app.services.llm.factory import build_llm_provider
from app.services.llm.fallback import FallbackLLMProvider
from app.services.llm.openai_compatible import OpenAICompatibleProvider, inline_schema

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
ART = ArticleForLLM(article_id="a", headline="Brent crude jumps after OPEC+ cut", text="Brent crude rose 6%.")
VALID = {"is_financial_event": True, "event_type": "ENERGY_SUPPLY", "title": "t", "summary": "s",
         "event_date": None, "countries": [], "reported_figures": [], "primary_effects": [],
         "financial_relevance": 0.8, "relevance_rationale": "r", "supporting_passages": []}


def S(**kw) -> Settings:
    base = dict(gemini_api_key=SecretStr("gem-secret"), groq_api_key=SecretStr("groq-secret"),
                http_backoff_seconds=0.0, llm_http_max_retries=0)
    return Settings(_env_file=None, **{**base, **kw})


def completion(content, finish="stop", model="gemini-2.5-flash"):
    return httpx.Response(200, json={"id": "c1", "model": model, "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                                     "choices": [{"message": {"role": "assistant", "content": content},
                                                  "finish_reason": finish}]})


class TestOpenAICompatible:
    def test_schema_is_self_contained(self):
        from app.schemas.llm import EventClassification

        flat = json.dumps(inline_schema(EventClassification.model_json_schema()))
        assert "$ref" not in flat and "$defs" not in flat

    def test_missing_key_or_model_is_configuration_error(self):
        with pytest.raises(ConfigurationError):
            OpenAICompatibleProvider("gemini", S(gemini_api_key=None))
        with pytest.raises(ConfigurationError, match="XAI_MODEL"):
            OpenAICompatibleProvider("xai", S(xai_api_key=SecretStr("k"), xai_model=""))

    @respx.mock
    async def test_request_shape_and_parse(self):
        route = respx.post(GEMINI_URL).mock(return_value=completion(json.dumps(VALID)))
        res = await OpenAICompatibleProvider("gemini", S()).classify_event(ART)
        assert res.provider == "gemini" and not res.simulated and res.usage["input_tokens"] == 10
        req = route.calls[0].request
        assert req.headers["Authorization"] == "Bearer gem-secret" and "gem-secret" not in str(req.url)
        body = json.loads(req.content)
        assert body["model"] == "gemini-2.5-flash" and body["temperature"] == 0.0
        assert body["response_format"]["type"] == "json_schema"
        assert body["messages"][0]["role"] == "system" and "untrusted" in body["messages"][0]["content"]
        assert "<article>" in body["messages"][1]["content"]

    @respx.mock
    async def test_code_fences_tolerated_and_invalid_output_retried(self):
        respx.post(GROQ_URL).mock(side_effect=[completion("not json"),
                                              completion("```json\n" + json.dumps(VALID) + "\n```")])
        res = await OpenAICompatibleProvider("groq", S()).classify_event(ART)
        assert res.attempts == 2

    @respx.mock
    async def test_json_schema_rejected_falls_back_to_json_object(self):
        route = respx.post(GROQ_URL).mock(side_effect=[
            httpx.Response(400, json={"error": {"message": "response_format json_schema is not supported by this model"}}),
            completion(json.dumps(VALID))])
        p = OpenAICompatibleProvider("groq", S())
        await p.classify_event(ART)
        assert json.loads(route.calls[1].request.content)["response_format"] == {"type": "json_object"}
        assert p.json_mode == "json_object"

    @respx.mock
    async def test_truncation_auth_rate_limit_and_not_found(self):
        respx.post(GEMINI_URL).mock(return_value=completion('{"is_fin', finish="length"))
        with pytest.raises(LLMOutputError, match="truncated"):
            await OpenAICompatibleProvider("gemini", S()).classify_event(ART)
        respx.post(GEMINI_URL).mock(return_value=httpx.Response(401, json={"error": "bad key"}))
        with pytest.raises(ConfigurationError, match="API key"):
            await OpenAICompatibleProvider("gemini", S()).classify_event(ART)
        respx.post(GEMINI_URL).mock(return_value=httpx.Response(429))
        with pytest.raises(RateLimitedError):
            await OpenAICompatibleProvider("gemini", S()).classify_event(ART)
        respx.post(GEMINI_URL).mock(return_value=httpx.Response(404, json={"error": "model"}))
        with pytest.raises(ConfigurationError, match="not found"):
            await OpenAICompatibleProvider("gemini", S()).classify_event(ART)

    @respx.mock
    async def test_ollama_needs_no_key(self):
        route = respx.post("http://localhost:11434/v1/chat/completions").mock(
            return_value=completion(json.dumps({"entities": []})))
        from app.schemas.llm import EventClassification

        await OpenAICompatibleProvider("ollama", S()).extract_entities(ART, EventClassification(**VALID))
        assert "Authorization" not in route.calls[0].request.headers


# ------------------------------------------------------------------ fallback
class Stub:
    simulated = False

    def __init__(self, name, error=None):
        self.name, self.model, self.error, self.calls = name, f"{name}-model", error, 0

    async def extract_entities(self, article, event):
        self.calls += 1
        if self.error:
            raise self.error
        return LLMResult[EntityExtraction](output=EntityExtraction(entities=[]), provider=self.name,
                                           model=self.model, simulated=False)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class TestFallbackChain:
    async def test_primary_rate_limited_secondary_serves_with_trail(self):
        clock = Clock()
        gem = Stub("gemini", RateLimitedError("gemini rate limit exceeded", provider="gemini", retryable=True))
        groq = Stub("groq")
        chain = FallbackLLMProvider([gem, groq], cooldown_seconds=60, clock=clock)
        res = await chain.extract_entities(ART, None)
        assert res.provider == "groq"
        assert res.fallback_trail[0]["provider"] == "gemini" and res.fallback_trail[0]["error_code"] == "rate_limited"
        # within cooldown the primary is skipped without being called
        res2 = await chain.extract_entities(ART, None)
        assert gem.calls == 1 and res2.fallback_trail[0]["outcome"] == "skipped_cooldown"
        # after cooldown it is tried again
        clock.t = 61
        gem.error = None
        res3 = await chain.extract_entities(ART, None)
        assert res3.provider == "gemini" and res3.fallback_trail == []

    async def test_invalid_output_fails_over_without_cooldown(self):
        gem = Stub("gemini", LLMOutputError("bad output"))
        chain = FallbackLLMProvider([gem, Stub("groq")])
        assert (await chain.extract_entities(ART, None)).provider == "groq"
        assert "gemini" not in chain._cooldown_until

    async def test_all_fail_is_structured_error_not_mock(self):
        chain = FallbackLLMProvider([Stub("gemini", ProviderError("down", provider="gemini")),
                                     Stub("groq", ConfigurationError("bad key"))])
        with pytest.raises(ProviderError) as ei:
            await chain.extract_entities(ART, None)
        assert [a["provider"] for a in ei.value.details["attempts"]] == ["gemini", "groq"]

    def test_mock_cannot_join_chain(self, mock_llm):
        with pytest.raises(ValueError):
            FallbackLLMProvider([Stub("groq"), mock_llm])
        with pytest.raises(Exception):
            Settings(_env_file=None, llm_fallback_chain="gemini,mock")

    def test_factory_skips_unconfigured_members(self, kb):
        p = build_llm_provider(S(llm_provider="fallback", llm_fallback_chain="gemini,groq,xai", gemini_api_key=None), kb)
        assert [m.name for m in p.providers] == ["groq"]
        assert {s["provider"] for s in p.skipped} == {"gemini", "xai"}
        with pytest.raises(ConfigurationError):
            build_llm_provider(S(llm_provider="fallback", gemini_api_key=None, groq_api_key=None), kb)


def test_list_settings_accept_comma_separated_env(monkeypatch):
    """LLM_FALLBACK_CHAIN / CORS_ALLOWED_ORIGINS are documented as comma-separated env values."""
    from app.core.config import Settings

    monkeypatch.setenv("LLM_FALLBACK_CHAIN", "groq, gemini")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5199, https://app.example/")
    s = Settings(_env_file=None)
    assert s.llm_fallback_chain == ["groq", "gemini"]
    assert s.cors_allowed_origins == ["http://localhost:5199", "https://app.example"]


def test_env_example_loads_without_errors(tmp_path):
    """A .env copied from .env.example must load (list settings are comma-separated there)."""
    from pathlib import Path

    from app.core.config import Settings

    env = tmp_path / ".env"
    env.write_text((Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    s = Settings(_env_file=env)
    assert s.market_event_windows == [1, 3, 5, 20] and s.llm_fallback_chain == ["gemini", "groq"]


class FlakyStub(Stub):
    """Rate-limited for the first `fail_times` calls, then succeeds."""

    def __init__(self, name, fail_times):
        super().__init__(name)
        self.fail_times = fail_times

    async def extract_entities(self, article, event):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RateLimitedError(f"{self.name} rate limit exceeded", provider=self.name, retryable=True)
        return LLMResult[EntityExtraction](output=EntityExtraction(entities=[]), provider=self.name,
                                           model=self.model, simulated=False)


class TestWaitForRateLimits:
    async def _chain(self, providers, max_wait):
        from app.schemas.llm import EventClassification

        clock, slept = Clock(), []

        async def fake_sleep(s):
            slept.append(s)
            clock.t += s

        chain = FallbackLLMProvider(providers, cooldown_seconds=60, clock=clock, max_wait_seconds=max_wait, sleep=fake_sleep)
        return chain, slept, EventClassification(**VALID)

    async def test_waits_when_all_rate_limited_then_succeeds(self):
        gem, groq = FlakyStub("gemini", 1), FlakyStub("groq", 1)
        chain, slept, ev = await self._chain([gem, groq], max_wait=90)
        r = await chain.extract_entities(ART, ev)
        assert r.provider == "gemini" and slept and 55 <= slept[0] <= 62  # waited for the 60 s cooldown
        assert any(t["outcome"] == "waited_for_rate_limit" for t in r.fallback_trail)

    async def test_no_wait_for_non_rate_limit_failures(self):
        chain, slept, ev = await self._chain([Stub("gemini", ProviderError("down", provider="gemini")),
                                              Stub("groq", LLMOutputError("bad json"))], max_wait=90)
        with pytest.raises(ProviderError):
            await chain.extract_entities(ART, ev)
        assert slept == []

    async def test_wait_is_capped(self):
        chain, slept, ev = await self._chain([FlakyStub("gemini", 99), FlakyStub("groq", 99)], max_wait=30)
        with pytest.raises(ProviderError) as ei:
            await chain.extract_entities(ART, ev)
        assert slept == [] and ei.value.details["attempts"]  # 60 s cooldown > 30 s cap -> fail without waiting
