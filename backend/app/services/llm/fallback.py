"""Fallback chain over several REAL LLM providers (LLM_PROVIDER=fallback).

Each call tries the providers in order. A provider is skipped for that call - and the next one is
tried - when it raises a provider error (outage, timeout, rate limit), a configuration error (bad
key, unknown model) or an output error (invalid/refused output after its own retries).

* Providers that hit a rate limit or outage are put on cooldown (LLM_FALLBACK_COOLDOWN_SECONDS);
  configuration errors put them on a long cooldown. Cooled-down providers are skipped quickly.
* Every result records which provider actually served it and the failover trail.
* The mock provider can never be part of a chain, so a real-provider failure is never silently
  replaced by simulated output. If every provider fails, the call fails with a structured error.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.core.errors import ConfigurationError, LLMOutputError, ProviderError
from app.schemas.llm import (
    ArticleForLLM,
    EntityExtraction,
    EventClassification,
    Explanation,
    LLMResult,
    RelationshipExtraction,
)
from app.services.llm.base import LLMProvider

log = logging.getLogger(__name__)

CONFIG_ERROR_COOLDOWN_SECONDS = 600.0


class FallbackLLMProvider:
    name = "fallback"
    simulated = False

    def __init__(self, providers: list[LLMProvider], cooldown_seconds: float = 60.0,
                 skipped: list[dict[str, str]] | None = None, clock=time.monotonic) -> None:
        if not providers:
            raise ConfigurationError("LLM fallback chain has no usable providers",
                                     details={"integration": "llm", "skipped": skipped or []})
        if any(p.simulated for p in providers):
            raise ValueError("simulated (mock) providers cannot be part of a fallback chain")
        self.providers = providers
        self.cooldown_seconds = cooldown_seconds
        self.skipped = skipped or []  # providers left out at build time (e.g. missing key)
        self._clock = clock
        self._cooldown_until: dict[str, float] = {}
        self.model = " > ".join(f"{p.name}:{p.model}" for p in providers)

    def _cool(self, provider: LLMProvider, seconds: float) -> None:
        self._cooldown_until[provider.name] = self._clock() + seconds

    async def _call(self, method: str, *args: Any, **kwargs: Any) -> LLMResult:
        trail: list[dict[str, Any]] = []
        now = self._clock()
        for p in self.providers:
            until = self._cooldown_until.get(p.name, 0.0)
            if until > now:
                trail.append({"provider": p.name, "model": p.model, "outcome": "skipped_cooldown",
                              "cooldown_remaining_s": round(until - now, 1)})
                continue
            try:
                result: LLMResult = await getattr(p, method)(*args, **kwargs)
            except (ProviderError, ConfigurationError, LLMOutputError) as exc:
                trail.append({"provider": p.name, "model": p.model, "outcome": "failed",
                              "error_code": exc.code, "message": exc.message[:300]})
                if isinstance(exc, ConfigurationError):
                    self._cool(p, CONFIG_ERROR_COOLDOWN_SECONDS)
                elif isinstance(exc, ProviderError):
                    self._cool(p, self.cooldown_seconds)
                log.warning("LLM provider %s failed for %s (%s); trying next", p.name, method, exc.code)
                continue
            if trail:
                log.info("LLM %s served by fallback provider %s after %s", method, p.name,
                         [t["provider"] for t in trail])
            return result.model_copy(update={"fallback_trail": trail})
        raise ProviderError("All LLM providers in the fallback chain failed", provider="fallback",
                            retryable=True, attempts=trail)

    async def classify_event(self, article: ArticleForLLM) -> LLMResult[EventClassification]:
        return await self._call("classify_event", article)

    async def extract_entities(self, article: ArticleForLLM, event: EventClassification) -> LLMResult[EntityExtraction]:
        return await self._call("extract_entities", article, event)

    async def extract_relationships(self, article: ArticleForLLM, event: EventClassification,
                                    entities: EntityExtraction) -> LLMResult[RelationshipExtraction]:
        return await self._call("extract_relationships", article, event, entities)

    async def generate_explanation(self, evidence_package: dict[str, Any],
                                   feedback: str | None = None) -> LLMResult[Explanation]:
        return await self._call("generate_explanation", evidence_package, feedback=feedback)

