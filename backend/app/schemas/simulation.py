"""Schemas for the Black Swan simulator API.

The request is strict (unknown fields rejected, numbers only, bounded sizes); scenario text is never
accepted, so user input cannot alter graph definitions or reach an LLM prompt. Range checks against the
scenario catalog happen in app.services.simulation.scenarios.validate_request (never clamped).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, field_validator

PARAM_NAME = r"^[a-z0-9_]{1,64}$"


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(pattern=r"^[a-z0-9_]{3,64}$", examples=["global_oil_supply_shock"])
    shocks: dict[str, StrictFloat | StrictInt] = Field(
        description="Hypothetical moves over the horizon, keyed by scenario parameter name (see GET /api/scenarios)",
        examples=[{"oil_price_change_pct": 25, "usdinr_change_pct": 2}])
    horizon_days: StrictInt = Field(5, description="Trading-day horizon; only values listed by the scenario are accepted")
    max_depth: StrictInt | None = Field(None, ge=1, le=7, description="Optional graph path-depth override")

    @field_validator("shocks")
    @classmethod
    def _shock_keys(cls, v: dict[str, float]) -> dict[str, float]:
        import re

        if len(v) > 20:
            raise ValueError("at most 20 shock parameters")
        bad = [k for k in v if not re.match(PARAM_NAME, k)]
        if bad:
            raise ValueError(f"invalid parameter names: {bad[:5]}")
        return {k: float(x) for k, x in v.items()}


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow", protected_namespaces=())


class ScenarioParameterOut(_Open):
    name: str
    label: str
    unit: str
    required: bool
    definition: str
    accepted_range: list[float]
    used_by_model: bool
    model_validated_range: list[float] | None
    typical_range_p01_p99: list[float] | None
    graph_variables: list[str]


class ScenarioOut(_Open):
    id: str
    display_name: str
    category: str
    description: str
    is_hypothetical: Literal[True]
    event_type: str
    initiating_entities: list[str]
    context_entities: list[str]
    parameters: list[ScenarioParameterOut]
    supported_horizons_trading_days: list[int]
    historical_analog_event_ids: list[str]
    limitations: list[str]


class ScenarioListResponse(BaseModel):
    scenario_catalog_version: str
    scenarios: list[ScenarioOut]
    model_compatibility: list[dict[str, Any]]


class GraphOut(_Open):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    paths: list[dict[str, Any]] = []


class PredictionsOut(_Open):
    status: Literal["available", "available_with_warnings", "out_of_domain", "no_supported_inputs",
                    "model_unavailable", "unsupported_horizon"]
    horizon_trading_days: int
    model: dict[str, Any] | None
    model_compatibility: list[dict[str, Any]]
    inputs: list[dict[str, Any]]
    assets: list[dict[str, Any]]
    disclaimer: str


class SimulationResponse(_Open):
    simulation_id: str
    created_at: str
    cached: bool
    request: dict[str, Any]
    scenario: dict[str, Any]
    status: Literal["completed"]
    assumptions: list[dict[str, Any]]
    graph: GraphOut
    predictions: PredictionsOut
    evidence: dict[str, Any]
    timeline: dict[str, Any]
    warnings: list[dict[str, Any]]
    versions: dict[str, Any]


class Graph3DResponse(_Open):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    layers: list[dict[str, Any]]
    knowledge_base_version: str
    scenario_catalog_version: str


class EntityResponse(_Open):
    id: str
    label: str
    type: str
    layer: int | None
    is_asset: bool
    is_model_target: bool
    outgoing_relationships: list[dict[str, Any]]
    incoming_relationships: list[dict[str, Any]]
