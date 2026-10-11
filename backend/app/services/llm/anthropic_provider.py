"""Anthropic Claude adapter using the official ``anthropic`` SDK with structured outputs.

Each task sends a JSON schema derived from the Pydantic output model via
``output_config.format``; the response text is then re-validated with Pydantic here, so a
refusal or truncated answer is detected from ``stop_reason`` instead of surfacing as an
opaque parse error. Invalid outputs get a bounded number of corrective retries.
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import ConfigurationError, LLMOutputError, ProviderError, RateLimitedError
from app.schemas.llm import (
    ArticleForLLM,
    EntityExtraction,
    EventClassification,
    Explanation,
    LLMResult,
    RelationshipExtraction,
)
from app.services.llm import prompts

log = logging.getLogger(__name__)
M = TypeVar("M", bound=BaseModel)

# Server-side refusal fallback (see Claude API docs, "refusals and fallback"): on a policy
# decline the API re-runs the request on a fallback model chosen by refusal category.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"
    simulated = False

    def __init__(self, settings: Settings, client: anthropic.AsyncAnthropic | None = None) -> None:
        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
        if client is None and not key:
            raise ConfigurationError(
                "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set",
                details={"integration": "llm", "provider": "anthropic"},
            )
        self.model = settings.llm_model
        self.settings = settings
        self.client = client or anthropic.AsyncAnthropic(
            api_key=key, timeout=settings.llm_timeout_seconds, max_retries=2
        )

    # ------------------------------------------------------------------ tasks
    async def classify_event(self, article: ArticleForLLM) -> LLMResult[EventClassification]:
        return await self._structured(
            prompts.SYSTEM_EXTRACTION, prompts.classification_prompt(article), EventClassification
        )

    async def extract_entities(
        self, article: ArticleForLLM, event: EventClassification
    ) -> LLMResult[EntityExtraction]:
        return await self._structured(
            prompts.SYSTEM_EXTRACTION, prompts.entity_prompt(article, event), EntityExtraction
        )

    async def extract_relationships(
        self, article: ArticleForLLM, event: EventClassification, entities: EntityExtraction
    ) -> LLMResult[RelationshipExtraction]:
        return await self._structured(
            prompts.SYSTEM_EXTRACTION,
            prompts.relationship_prompt(article, event, entities),
            RelationshipExtraction,
        )

    async def generate_explanation(
        self, evidence_package: dict[str, Any], feedback: str | None = None
    ) -> LLMResult[Explanation]:
        return await self._structured(
            prompts.SYSTEM_EXPLANATION, prompts.explanation_prompt(evidence_package, feedback), Explanation
        )

    # --------------------------------------------------------------- plumbing
    async def _structured(self, system: str, user: str, schema: type[M]) -> LLMResult[M]:
        output_config: dict[str, Any] = {
            "effort": self.settings.llm_effort,
            "format": {"type": "json_schema", "schema": anthropic.transform_schema(schema.model_json_schema())},
        }
        messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
        request_ids: list[str] = []
        usage: dict[str, int] = {}
        last_error = ""
        attempts = 0
        for attempt in range(1, self.settings.llm_max_validation_retries + 2):
            attempts = attempt
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": self.settings.llm_max_tokens,
                "system": system,
                "messages": messages,
                "output_config": output_config,
            }
            if self.settings.llm_use_server_fallbacks:
                kwargs["betas"] = [FALLBACK_BETA]
                kwargs["fallbacks"] = "default"
            response = await self._call(**kwargs)
            if getattr(response, "_request_id", None):
                request_ids.append(response._request_id)
            for k in ("input_tokens", "output_tokens"):
                usage[k] = usage.get(k, 0) + int(getattr(response.usage, k, 0) or 0)

            if response.stop_reason == "refusal":
                category = getattr(getattr(response, "stop_details", None), "category", None)
                raise LLMOutputError(
                    "The model declined the request", details={"stop_reason": "refusal", "category": category}
                )
            if response.stop_reason == "max_tokens":
                raise LLMOutputError(
                    "Model output was truncated at max_tokens", details={"max_tokens": self.settings.llm_max_tokens}
                )

            text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
            try:
                parsed = schema.model_validate_json(text)
                check = getattr(parsed, "check_ranges", None)
                if check:
                    check()
                return LLMResult[schema](  # type: ignore[valid-type]
                    output=parsed, provider=self.name, model=getattr(response, "model", self.model),
                    simulated=False, attempts=attempts, request_ids=request_ids, usage=usage,
                )
            except (ValidationError, ValueError) as exc:
                last_error = str(exc)[:2000]
                log.warning("LLM output failed validation (attempt %s): %s", attempt, last_error[:300])
                # Append-only correction turn: echo the assistant content unchanged, then ask for a fix.
                messages = [
                    *messages,
                    {"role": "assistant", "content": [b.to_dict() for b in response.content]},
                    {"role": "user", "content": f"That output failed validation: {last_error}. "
                                                "Return a corrected JSON object only."},
                ]
        raise LLMOutputError(
            "LLM output failed schema validation after bounded retries",
            details={"schema": schema.__name__, "attempts": attempts, "last_error": last_error},
        )

    async def _call(self, **kwargs: Any) -> Any:
        try:
            return await self.client.beta.messages.create(**kwargs)
        except anthropic.AuthenticationError as exc:
            raise ConfigurationError("Anthropic rejected the API key", details={"status": 401}) from exc
        except anthropic.PermissionDeniedError as exc:
            raise ConfigurationError("Anthropic API key lacks permission", details={"status": 403}) from exc
        except anthropic.NotFoundError as exc:
            raise ConfigurationError(f"Unknown model or endpoint: {self.model}", details={"status": 404}) from exc
        except anthropic.RateLimitError as exc:
            raise RateLimitedError("Anthropic rate limit exceeded", provider=self.name, retryable=True) from exc
        except anthropic.BadRequestError as exc:
            raise ProviderError(f"Anthropic rejected the request: {exc.message}", provider=self.name) from exc
        except anthropic.APITimeoutError as exc:
            raise ProviderError("Anthropic request timed out", provider=self.name, retryable=True) from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("Could not connect to Anthropic", provider=self.name, retryable=True) from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(
                f"Anthropic API error {exc.status_code}", provider=self.name, retryable=exc.status_code >= 500
            ) from exc
