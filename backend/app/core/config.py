"""Application configuration loaded from environment variables / .env.

Secrets are held as ``SecretStr`` so they never appear in reprs, logs or API responses.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


class ScoringWeights(BaseSettings):
    """Heuristic weights for S = w_c*C + w_e*E + w_r*R + w_h*H (see README, "Scoring").

    These are hand-set heuristics, NOT empirically calibrated values.
    """

    model_config = SettingsConfigDict(env_prefix="SCORE_WEIGHT_", extra="ignore")

    confidence: float = 0.30
    evidence: float = 0.30
    relevance: float = 0.25
    historical: float = 0.15

    @model_validator(mode="after")
    def _non_negative(self) -> "ScoringWeights":
        for name in ("confidence", "evidence", "relevance", "historical"):
            if getattr(self, name) < 0:
                raise ValueError(f"score weight {name} must be >= 0")
        if self.confidence + self.evidence + self.relevance + self.historical <= 0:
            raise ValueError("at least one score weight must be positive")
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://fig:fig@localhost:5433/financial_impact_graph"

    # --- LLM -----------------------------------------------------------------
    llm_provider: Literal["anthropic", "gemini", "groq", "xai", "ollama", "fallback", "mock"] = "mock"
    #: Model for LLM_PROVIDER=anthropic (other providers use their own *_MODEL setting).
    llm_model: str = "claude-opus-5-5"
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    llm_max_tokens: int = 16000
    llm_timeout_seconds: float = 120.0
    llm_max_validation_retries: int = 1
    llm_use_server_fallbacks: bool = True
    anthropic_api_key: SecretStr | None = None

    # OpenAI-compatible providers (Gemini, Groq, xAI Grok, Ollama) - one adapter, per-provider settings.
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: SecretStr | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    xai_api_key: SecretStr | None = None
    xai_model: str = ""  # no default: set the Grok model your account has access to
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1"
    openai_compat_max_tokens: int = 8192
    openai_compat_temperature: float = 0.0
    #: Retries per provider before failing over (kept low so the fallback chain reacts quickly).
    llm_http_max_retries: int = 1

    # Fallback chain (LLM_PROVIDER=fallback): tried in order; members without credentials are skipped.
    llm_fallback_chain: list[str] = ["gemini", "groq"]
    #: After a rate limit / outage, skip that provider for this many seconds.
    llm_fallback_cooldown_seconds: float = 60.0

    # --- News ----------------------------------------------------------------
    news_provider: Literal["gdelt", "finnhub", "fixture"] = "gdelt"
    finnhub_api_key: SecretStr | None = None
    gdelt_default_query: str = (
        '(oil OR tariff OR "interest rate" OR inflation OR sanctions OR rupee OR "central bank")'
        " sourcelang:english"
    )
    news_max_articles: int = 25

    # --- Market data ---------------------------------------------------------
    market_data_provider: Literal["yahoo_chart", "alphavantage", "none"] = "none"
    market_data_api_key: SecretStr | None = None

    # --- HTTP ----------------------------------------------------------------
    http_timeout_seconds: float = 20.0
    http_max_retries: int = 3
    http_backoff_seconds: float = 1.0

    # --- Analysis bounds -----------------------------------------------------
    graph_kb_expansion_depth: int = Field(default=5, ge=1, le=8)
    graph_max_nodes: int = Field(default=150, ge=10, le=2000)
    path_max_depth: int = Field(default=7, ge=1, le=10)
    path_max_total: int = Field(default=60, ge=1, le=1000)
    path_max_per_asset: int = Field(default=5, ge=1, le=50)
    path_length_decay: float = Field(default=0.9, gt=0, le=1)
    market_max_assets: int = Field(default=8, ge=0, le=50)
    market_event_windows: list[int] = [1, 3, 5, 20]
    historical_min_comparisons: int = Field(default=2, ge=1)
    historical_max_comparisons: int = Field(default=5, ge=1)

    # --- Black Swan simulator ---------------------------------------------------
    simulation_scenarios_file: Path = DATA_DIR / "simulation" / "scenarios.json"
    simulation_layers_file: Path = DATA_DIR / "simulation" / "visual_layers.json"
    simulation_model_dir: Path = DATA_DIR / "models"
    simulation_scenario_model_id: str = "scenario_conditional_v1"
    simulation_forecast_model_id: str = "forecast_trailing_v1"

    @field_validator("llm_fallback_chain", mode="before")
    @classmethod
    def _parse_chain(cls, v: object) -> object:
        if isinstance(v, str):
            return [x.strip().lower() for x in v.split(",") if x.strip()]
        return v

    @field_validator("llm_fallback_chain")
    @classmethod
    def _check_chain(cls, v: list[str]) -> list[str]:
        allowed = {"anthropic", "gemini", "groq", "xai", "ollama"}
        bad = [x for x in v if x not in allowed]
        if bad:
            raise ValueError(f"unsupported providers in LLM_FALLBACK_CHAIN: {bad} (mock is never allowed)")
        if not v:
            raise ValueError("LLM_FALLBACK_CHAIN must name at least one provider")
        return v

    @field_validator("market_event_windows", mode="before")
    @classmethod
    def _parse_windows(cls, v: object) -> object:
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip()]
        return v

    @property
    def scoring_weights(self) -> ScoringWeights:
        return ScoringWeights()

    def secret_values(self) -> list[str]:
        """All configured secret strings, used by the log redaction filter."""
        out = []
        for s in (self.anthropic_api_key, self.finnhub_api_key, self.market_data_api_key, self.gemini_api_key,
                  self.groq_api_key, self.xai_api_key):
            if s is not None and s.get_secret_value():
                out.append(s.get_secret_value())
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
