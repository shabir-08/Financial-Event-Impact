from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__
from app.api.deps import get_kb
from app.core.config import Settings, get_settings
from app.database.session import check_database
from app.schemas.api import HealthResponse, IntegrationStatus, IntegrationsResponse
from app.services.relationships.knowledge_base import KnowledgeBase

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    ok, err = check_database()
    return HealthResponse(status="ok" if ok else "degraded", version=__version__, app_env=settings.app_env,
                          database="ok" if ok else "unavailable", database_error=err)


def _has(secret) -> bool:
    return bool(secret and secret.get_secret_value())


def _llm_member(name: str, settings: Settings) -> dict:
    """Configuration state of one real LLM provider (never includes key values)."""
    if name == "anthropic":
        has, model, key_name = _has(settings.anthropic_api_key), settings.llm_model, "ANTHROPIC_API_KEY"
    else:
        from app.services.llm.openai_compatible import PRESETS, provider_key_present

        preset = PRESETS[name]
        has = provider_key_present(name, settings)
        model = getattr(settings, preset.model_setting) or None
        key_name = preset.key_setting.upper() if preset.key_setting else None
    problem = None
    if not has:
        problem = f"{key_name} missing"
    elif not model:
        problem = f"{name.upper()}_MODEL not set"
    return {"provider": name, "model": model, "credentials_present": has if key_name else None,
            "configured": problem is None, "problem": problem}


@router.get("/integrations", response_model=IntegrationsResponse)
def integrations(settings: Settings = Depends(get_settings), kb: KnowledgeBase = Depends(get_kb)) -> IntegrationsResponse:
    """Configuration/availability of each integration. Never returns credential values."""
    if settings.llm_provider == "mock":
        llm = IntegrationStatus(provider="mock", configured=True, simulated=True, model="mock-deterministic-v1",
                                notes=["MOCK provider: outputs are SIMULATED and labelled as such."])
    elif settings.llm_provider == "fallback":
        chain = [_llm_member(name, settings) for name in settings.llm_fallback_chain]
        usable = [m for m in chain if m["configured"]]
        llm = IntegrationStatus(
            provider="fallback", configured=bool(usable), credentials_present=bool(usable),
            model=" > ".join(f"{m['provider']}:{m['model']}" for m in usable) or None, chain=chain,
            notes=[f"Tried in order: {' > '.join(settings.llm_fallback_chain)}; unconfigured members are skipped; "
                   "the mock provider is never used as a fallback."]
            + ([] if usable else ["No chain member is configured: LLM-dependent endpoints return 503."]))
    else:
        m = _llm_member(settings.llm_provider, settings)
        llm = IntegrationStatus(provider=m["provider"], configured=m["configured"],
                                credentials_present=m["credentials_present"], model=m["model"],
                                notes=[] if m["configured"] else [f"{m['problem']}: LLM-dependent endpoints return 503."])
    if settings.news_provider == "finnhub":
        has = _has(settings.finnhub_api_key)
        news = IntegrationStatus(provider="finnhub", configured=has, credentials_present=has,
                                 notes=["Headline + summary only (no full text)."])
    elif settings.news_provider == "gdelt":
        news = IntegrationStatus(provider="gdelt", configured=True, credentials_present=None,
                                 notes=["No API key required. Headlines/metadata only (no full text)."])
    else:
        news = IntegrationStatus(provider="fixture", configured=True, simulated=True,
                                 notes=["Fixture articles are SIMULATED demo content."])
    if settings.market_data_provider == "none":
        md = IntegrationStatus(provider="none", configured=False,
                               notes=["Historical market analysis returns UNAVAILABLE."])
    elif settings.market_data_provider == "alphavantage":
        has = _has(settings.market_data_api_key)
        md = IntegrationStatus(provider="alphavantage", configured=has, credentials_present=has,
                               notes=["Free tier: ~100 most recent sessions; US equities/ETFs and FX."])
    else:
        md = IntegrationStatus(provider="yahoo_chart", configured=True, credentials_present=None,
                               notes=["Unofficial endpoint; research/demo use only - verify licensing."])
    ok, err = check_database()
    db = IntegrationStatus(provider="postgresql" if settings.database_url.startswith("postgresql") else "sqlite",
                           configured=ok, notes=[] if ok else [f"connection failed: {err}"])
    return IntegrationsResponse(llm=llm, news=news, market_data=md, database=db, knowledge_base={
        "version": kb.version, "relationship_rules": len(kb.rules), "event_triggers": len(kb.triggers),
        "entities": len(kb.entities), "assets": len(kb.assets),
        "reference_historical_events": len(kb.historical_events)})
