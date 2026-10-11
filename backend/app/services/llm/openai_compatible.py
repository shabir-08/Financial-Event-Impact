"""Adapter for providers exposing an OpenAI-compatible ``/chat/completions`` endpoint.

One implementation serves several hosted/local models via presets:

* ``gemini`` - Google Gemini (OpenAI-compatibility endpoint, key from Google AI Studio)
* ``groq``   - Groq (open models such as Llama, very fast)
* ``xai``    - xAI Grok
* ``ollama`` - a local Ollama server (no key)

Structured output: the request asks for ``response_format=json_schema`` (best-effort, not strict)
and the JSON schema is also stated in the system prompt. If a provider/model rejects
``json_schema`` with HTTP 400, the adapter switches to ``json_object`` mode for the rest of the
process. Every response is re-validated with Pydantic and gets one corrective retry, exactly like
the Anthropic adapter. Article text is always treated as untrusted (see ``prompts``).
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
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
from app.services.http import request_with_retries
from app.services.llm import prompts

log = logging.getLogger(__name__)
M = TypeVar("M", bound=BaseModel)


@dataclass(frozen=True)
class Preset:
    base_url: str
    key_setting: str | None  # Settings attribute holding the API key (None = no key needed)
    model_setting: str
    label: str


PRESETS: dict[str, Preset] = {
    "gemini": Preset("https://generativelanguage.googleapis.com/v1beta/openai", "gemini_api_key", "gemini_model",
                     "Google Gemini"),
    "groq": Preset("https://api.groq.com/openai/v1", "groq_api_key", "groq_model", "Groq"),
    "xai": Preset("https://api.x.ai/v1", "xai_api_key", "xai_model", "xAI Grok"),
    "ollama": Preset("", None, "ollama_model", "Ollama (local)"),
}


def provider_key_present(name: str, settings: Settings) -> bool:
    preset = PRESETS[name]
    if preset.key_setting is None:
        return True
    secret = getattr(settings, preset.key_setting)
    return bool(secret and secret.get_secret_value())


def inline_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve local ``$ref``s into a self-contained schema (some providers reject ``$defs``)."""
    defs = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                target = defs[node["$ref"].split("/")[-1]]
                merged = {**copy.deepcopy(target), **{k: v for k, v in node.items() if k != "$ref"}}
                return resolve(merged)
            return {k: resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(x) for x in node]
        return node

    return resolve(schema)


class OpenAICompatibleProvider:
    simulated = False

    def __init__(self, name: str, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if name not in PRESETS:
            raise ValueError(f"unknown OpenAI-compatible provider {name}")
        preset = PRESETS[name]
        self.name = name
        self.settings = settings
        self.model = getattr(settings, preset.model_setting) or None
        self.base_url = (settings.ollama_base_url if name == "ollama" else preset.base_url).rstrip("/")
        self._key = None
        if preset.key_setting:
            secret = getattr(settings, preset.key_setting)
            self._key = secret.get_secret_value() if secret else None
            if not self._key:
                raise ConfigurationError(f"{preset.label} selected but {preset.key_setting.upper()} is not set",
                                         details={"integration": "llm", "provider": name})
        if not self.model:
            raise ConfigurationError(f"{preset.label} selected but {preset.model_setting.upper()} is not set",
                                     details={"integration": "llm", "provider": name})
        self.json_mode = "json_schema"
        self._client = client

    # ------------------------------------------------------------------ tasks
    async def classify_event(self, article: ArticleForLLM) -> LLMResult[EventClassification]:
        return await self._structured(prompts.SYSTEM_EXTRACTION, prompts.classification_prompt(article),
                                      EventClassification)

    async def extract_entities(self, article: ArticleForLLM, event: EventClassification) -> LLMResult[EntityExtraction]:
        return await self._structured(prompts.SYSTEM_EXTRACTION, prompts.entity_prompt(article, event),
                                      EntityExtraction)

    async def extract_relationships(self, article: ArticleForLLM, event: EventClassification,
                                    entities: EntityExtraction) -> LLMResult[RelationshipExtraction]:
        return await self._structured(prompts.SYSTEM_EXTRACTION,
                                      prompts.relationship_prompt(article, event, entities), RelationshipExtraction)

    async def generate_explanation(self, evidence_package: dict[str, Any],
                                   feedback: str | None = None) -> LLMResult[Explanation]:
        return await self._structured(prompts.SYSTEM_EXPLANATION,
                                      prompts.explanation_prompt(evidence_package, feedback), Explanation)

    # --------------------------------------------------------------- plumbing
    async def _structured(self, system: str, user: str, schema: type[M]) -> LLMResult[M]:
        json_schema = inline_schema(schema.model_json_schema())
        system_full = (f"{system}\n\nRespond with ONE JSON object only (no prose, no code fences) that conforms "
                       f"to this JSON Schema:\n{json.dumps(json_schema)}")
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_full},
                                          {"role": "user", "content": user}]
        usage: dict[str, int] = {}
        request_ids: list[str] = []
        last_error = ""
        attempts = 0
        for attempt in range(1, self.settings.llm_max_validation_retries + 2):
            attempts = attempt
            data = await self._chat(messages, schema.__name__, json_schema)
            if data.get("id"):
                request_ids.append(str(data["id"]))
            for k_src, k_dst in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens")):
                usage[k_dst] = usage.get(k_dst, 0) + int((data.get("usage") or {}).get(k_src) or 0)
            choices = data.get("choices") or []
            if not choices:
                raise LLMOutputError(f"{self.name} returned no choices", details={"provider": self.name})
            choice = choices[0]
            finish = choice.get("finish_reason")
            if finish == "length":
                raise LLMOutputError(f"{self.name} output was truncated (max_tokens)",
                                     details={"provider": self.name,
                                              "max_tokens": self.settings.openai_compat_max_tokens})
            if finish == "content_filter":
                raise LLMOutputError(f"{self.name} declined the request (content filter)",
                                     details={"provider": self.name})
            text = _strip_fences((choice.get("message") or {}).get("content") or "")
            try:
                parsed = schema.model_validate_json(text)
                check = getattr(parsed, "check_ranges", None)
                if check:
                    check()
                return LLMResult[schema](  # type: ignore[valid-type]
                    output=parsed, provider=self.name, model=data.get("model") or self.model, simulated=False,
                    attempts=attempts, request_ids=request_ids, usage=usage)
            except (ValidationError, ValueError) as exc:
                last_error = str(exc)[:2000]
                log.warning("%s output failed validation (attempt %s): %s", self.name, attempt, last_error[:300])
                messages = [*messages, {"role": "assistant", "content": text},
                            {"role": "user", "content": f"That output failed validation: {last_error}. "
                                                        "Return a corrected JSON object only."}]
        raise LLMOutputError(f"{self.name} output failed schema validation after bounded retries",
                             details={"provider": self.name, "schema": schema.__name__, "attempts": attempts,
                                      "last_error": last_error})

    async def _chat(self, messages: list[dict[str, Any]], schema_name: str, json_schema: dict[str, Any]) -> dict:
        body: dict[str, Any] = {"model": self.model, "messages": messages,
                                "max_tokens": self.settings.openai_compat_max_tokens,
                                "temperature": self.settings.openai_compat_temperature}
        if self.name == "gemini" and self.settings.gemini_reasoning_effort:
            body["reasoning_effort"] = self.settings.gemini_reasoning_effort
        if self.json_mode == "json_schema":
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": schema_name, "schema": json_schema, "strict": False}}
        else:
            body["response_format"] = {"type": "json_object"}
        try:
            return await self._post(body)
        except ProviderError as exc:
            text = str(exc.details.get("body", "")).lower()
            if (exc.details.get("status") == 400 and self.json_mode == "json_schema"
                    and any(k in text for k in ("response_format", "json_schema", "schema"))):
                log.info("%s rejected json_schema output; switching to json_object mode", self.name)
                self.json_mode = "json_object"
                body["response_format"] = {"type": "json_object"}
                return await self._post(body)
            raise

    async def _post(self, body: dict[str, Any]) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        client = self._client or httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds)
        try:
            resp = await request_with_retries(
                client, "POST", f"{self.base_url}/chat/completions", provider=self.name, headers=headers,
                json=body, max_retries=self.settings.llm_http_max_retries,
                backoff_seconds=self.settings.http_backoff_seconds, max_retry_after=5.0)
        except RateLimitedError:
            raise
        except ProviderError as exc:
            status = exc.details.get("status")
            if status in (401, 403):
                raise ConfigurationError(f"{self.name} rejected the API key (HTTP {status})",
                                         details={"provider": self.name, "status": status}) from exc
            if status == 404:
                raise ConfigurationError(f"{self.name}: model '{self.model}' or endpoint not found",
                                         details={"provider": self.name, "status": 404}) from exc
            raise
        finally:
            if self._client is None:
                await client.aclose()
        try:
            return resp.json()
        except ValueError as exc:
            raise ProviderError(f"{self.name} returned non-JSON response", provider=self.name) from exc


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()
