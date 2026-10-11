"""Schemas for the historical market-pattern API (analogue search, regimes, event responses)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt

FEATURE_NAME = r"^[a-z0-9_]{1,80}$"


class PatternSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["scenario", "conditions"] = Field(
        description="scenario: match hypothetical shocks against historical same-week moves; "
                    "conditions: match start-of-week market conditions")
    shocks: dict[str, StrictFloat | StrictInt] | None = Field(
        None, description="Scenario parameters (GET /api/scenarios); only parameters with a historical series are matched",
        examples=[{"oil_price_change_pct": 15, "usdinr_change_pct": 1}])
    conditions: Literal["latest", "none"] | dict[str, StrictFloat | StrictInt] | None = Field(
        None, description="'latest' (most recent observed conditions), 'none', or explicit condition-feature values")
    condition_features: list[str] | None = Field(None, max_length=12, description="Condition features to match on")
    assets: list[str] | None = Field(None, max_length=18, description="Target symbols or knowledge-base asset ids")
    k: StrictInt = Field(15, ge=3, le=50, description="Number of analogue weeks")
    horizon_days: StrictInt = Field(5, description="Trading-day horizon; only 5 is supported")


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow", protected_namespaces=())


class PatternSearchResponse(_Open):
    mode: str
    horizon_trading_days: int
    outcome_semantics: str
    query: dict[str, Any]
    matching: dict[str, Any]
    analogues: list[dict[str, Any]]
    n_analogues: int
    n_independent_clusters: int
    sample_statistics: dict[str, Any] | None
    statistics_withheld_reason: str | None
    warnings: list[dict[str, Any]]
    library_version: str


class EventResponseGroups(_Open):
    group_by: str
    groups: list[dict[str, Any]]
    n_events: int
    n_independent_episodes: int
    library_version: str
