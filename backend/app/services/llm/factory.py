from __future__ import annotations

from app.core.config import Settings
from app.services.llm.base import LLMProvider
from app.services.relationships.knowledge_base import KnowledgeBase


def build_llm_provider(settings: Settings, kb: KnowledgeBase) -> LLMProvider:
    """Construct the configured provider. Raises ConfigurationError if credentials are missing;
    never substitutes the mock provider for a misconfigured real one."""
    if settings.llm_provider == "mock":
        from app.services.llm.mock_provider import MockLLMProvider

        return MockLLMProvider(kb)
    if settings.llm_provider == "fallback":
        return build_fallback_chain(settings)
    return build_real_provider(settings.llm_provider, settings)


def build_real_provider(name: str, settings: Settings) -> LLMProvider:
    if name == "anthropic":
        from app.services.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings)
    if name in ("gemini", "groq", "xai", "ollama"):
        from app.services.llm.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider(name, settings)
    raise ValueError(f"Unsupported LLM provider {name}")


def build_fallback_chain(settings: Settings) -> LLMProvider:
    """Build the chain from LLM_FALLBACK_CHAIN, skipping (and recording) members that are not configured."""
    from app.core.errors import ConfigurationError
    from app.services.llm.fallback import FallbackLLMProvider

    providers, skipped = [], []
    for name in settings.llm_fallback_chain:
        try:
            providers.append(build_real_provider(name, settings))
        except ConfigurationError as exc:
            skipped.append({"provider": name, "reason": exc.message})
    if not providers:
        raise ConfigurationError("LLM_PROVIDER=fallback but no provider in LLM_FALLBACK_CHAIN is configured",
                                 details={"integration": "llm", "skipped": skipped})
    return FallbackLLMProvider(providers, settings.llm_fallback_cooldown_seconds, skipped)
