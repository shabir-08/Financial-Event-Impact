"""Scenario catalog (data/simulation/scenarios.json) and simulation-request validation.

Scenarios are HYPOTHETICAL definitions, kept separate from historical events. They only reference
entities, variables and curated analog events that already exist in the knowledge base; the loader
fails fast otherwise. Request validation never clamps: out-of-range or unsupported inputs are rejected.
"""

from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.core.errors import InvalidRequestError, NotFoundError
from app.domain import EventType
from app.services.relationships.knowledge_base import KnowledgeBase


class SeedDef(BaseModel):
    node_id: str
    sign_multiplier: Literal[-1, 1]


class ParameterDef(BaseModel):
    label: str
    unit: str
    input_range: tuple[float, float]
    definition: str
    graph_seeds: list[SeedDef]
    model_feature: str | None


class ScenarioParamUse(BaseModel):
    required: bool = False


class ScenarioDef(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]{3,64}$")
    display_name: str
    category: str
    description: str
    event_type: EventType
    initiating_entities: list[str]
    context_entities: list[str]
    parameters: dict[str, ScenarioParamUse]
    supported_horizons_trading_days: list[int]
    historical_analog_event_ids: list[str]
    limitations: list[str]


class ScenarioCatalog(BaseModel):
    version: str
    parameters: dict[str, ParameterDef]
    scenarios: list[ScenarioDef]
    content_hash: str = ""

    def get(self, scenario_id: str) -> ScenarioDef:
        for s in self.scenarios:
            if s.id == scenario_id:
                return s
        raise NotFoundError(f"unknown scenario '{scenario_id}'",
                            details={"code": "unknown_scenario", "available": [s.id for s in self.scenarios]})

    def validate_against(self, kb: KnowledgeBase) -> None:
        problems = []
        for name, p in self.parameters.items():
            if p.input_range[0] >= p.input_range[1]:
                problems.append(f"parameter {name}: empty input_range")
            problems += [f"parameter {name}: seed {s.node_id} not in KB" for s in p.graph_seeds if not kb.node_exists(s.node_id)]
        hist_ids = {h.id for h in kb.historical_events}
        for s in self.scenarios:
            problems += [f"{s.id}: entity {e} not in KB" for e in [*s.initiating_entities, *s.context_entities] if not kb.node_exists(e)]
            problems += [f"{s.id}: unknown parameter {p}" for p in s.parameters if p not in self.parameters]
            problems += [f"{s.id}: analog {h} not in KB historical events" for h in s.historical_analog_event_ids if h not in hist_ids]
        ids = [s.id for s in self.scenarios]
        if len(ids) != len(set(ids)):
            problems.append("duplicate scenario ids")
        if problems:
            raise ValueError("Invalid scenario catalog:\n" + "\n".join(problems))


@lru_cache
def load_scenario_catalog(path: Path, kb: KnowledgeBase) -> ScenarioCatalog:
    raw = path.read_bytes()
    data = json.loads(raw)
    data.pop("_comment", None)
    cat = ScenarioCatalog.model_validate({**data, "content_hash": hashlib.sha256(raw).hexdigest()[:12]})
    cat.validate_against(kb)
    return cat


class ValidatedScenario(BaseModel):
    scenario: ScenarioDef
    shocks: dict[str, float]
    horizon_days: int


def validate_request(catalog: ScenarioCatalog, scenario_id: str, shocks: dict[str, float],
                     horizon_days: int) -> ValidatedScenario:
    sc = catalog.get(scenario_id)
    errors: list[dict] = []
    if horizon_days not in sc.supported_horizons_trading_days:
        errors.append({"field": "horizon_days", "error": "unsupported_horizon", "value": horizon_days,
                       "supported": sc.supported_horizons_trading_days})
    for name in shocks:
        if name not in sc.parameters:
            errors.append({"field": f"shocks.{name}", "error": "unsupported_parameter",
                           "supported": sorted(sc.parameters)})
    for name, use in sc.parameters.items():
        if use.required and name not in shocks:
            errors.append({"field": f"shocks.{name}", "error": "required_parameter_missing"})
    for name, value in shocks.items():
        if name not in sc.parameters:
            continue
        if value is None or not math.isfinite(value):
            errors.append({"field": f"shocks.{name}", "error": "not_a_finite_number"})
            continue
        lo, hi = catalog.parameters[name].input_range
        if not lo <= value <= hi:
            errors.append({"field": f"shocks.{name}", "error": "out_of_accepted_range", "value": value,
                           "accepted_range": [lo, hi], "unit": catalog.parameters[name].unit})
    if not shocks:
        errors.append({"field": "shocks", "error": "no_parameters", "detail": "supply at least one shock parameter"})
    elif all(v == 0 for v in shocks.values() if v is not None):
        errors.append({"field": "shocks", "error": "all_parameters_zero", "detail": "at least one shock must be non-zero"})
    if errors:
        raise InvalidRequestError("Invalid simulation request", details={"errors": errors, "scenario_id": scenario_id})
    return ValidatedScenario(scenario=sc, shocks=dict(shocks), horizon_days=horizon_days)
