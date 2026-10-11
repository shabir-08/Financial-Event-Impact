"""Black Swan simulation orchestrator.

validate request -> scenario graph (GraphBuilder.build_scenario + PathAnalyzer, reused from the event
pipeline) -> quantitative inference (scenario-conditional model, if inputs are supported and in domain)
-> evidence (KB rule ids, user assumptions, curated historical analogs) -> illustrative timeline ->
persisted, versioned result. Graph and predictions are kept separate: no return is derived from graph
weights, and a graph is returned even when no numerical prediction is available.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import InvalidRequestError, NotFoundError
from app.database.base import utcnow
from app.models import HistoricalEvent, SimulationRun
from app.services.graph.builder import GraphBuilder, ScenarioInput, ScenarioSeed
from app.services.graph.paths import PathAnalyzer
from app.services.patterns import service as patterns
from app.services.patterns.library import PatternLibrary
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.simulation import inference
from app.services.simulation.graph3d import serialize_scenario_graph
from app.services.simulation.scenarios import ScenarioCatalog, ValidatedScenario, validate_request

TIMELINE_STAGES = [
    (1, "event_trigger", "Event Trigger", "Scenario and initiating global actors"),
    (2, "commodity_and_macro_reaction", "Commodity & Macro Reaction", "Economic variables reached by the scenario"),
    (3, "sector_impact", "Sector Impact", "Sectors and sector conditions on impact pathways"),
    (4, "company_and_market_impact", "Company & Market Impact", "Indian companies, indices and other assets on impact pathways"),
    (5, "stabilization", "Stabilization", "Not modelled: no validated model of recovery dynamics exists"),
]


def _fmt(v: float, unit: str) -> str:
    return f"{v:+g}{'%' if unit == '%' else ' ' + unit}"


class SimulationOrchestrator:
    def __init__(self, session: Session, settings: Settings, kb: KnowledgeBase, catalog: ScenarioCatalog,
                 models: dict[str, inference.ModelArtifact], layers: dict, pattern_library: PatternLibrary | None = None) -> None:
        self.session, self.settings, self.kb, self.catalog = session, settings, kb, catalog
        self.models, self.layers, self.patterns = models, layers, pattern_library

    # ------------------------------------------------------------------ public
    def run(self, scenario_id: str, shocks: dict[str, float], horizon_days: int, max_depth: int | None) -> tuple[dict, bool]:
        v = validate_request(self.catalog, scenario_id, shocks, horizon_days)
        model = self.models.get(self.settings.simulation_scenario_model_id)
        versions = {"knowledge_base_version": self.kb.version,
                    "scenario_catalog_version": f"{self.catalog.version}+{self.catalog.content_hash}",
                    "model_version": model.model_version if model else None,
                    "pattern_library_version": self.patterns.version if self.patterns else None}
        req = {"scenario_id": scenario_id, "shocks": dict(sorted(v.shocks.items())), "horizon_days": horizon_days,
               "max_depth": max_depth}
        rhash = hashlib.sha256(json.dumps({**req, **versions}, sort_keys=True).encode()).hexdigest()
        cached = self.session.scalar(select(SimulationRun).where(SimulationRun.request_hash == rhash))
        if cached is not None:
            return {**cached.result, "cached": True}, True
        result = self._simulate(v, max_depth, versions)
        sim_id = "sim_" + uuid.uuid4().hex[:16]
        result = {"simulation_id": sim_id, "created_at": utcnow().isoformat(), "request": req, "cached": False, **result}
        self.session.add(SimulationRun(
            id=sim_id, scenario_id=scenario_id, request_hash=rhash, request=req, status=result["status"],
            prediction_status=result["predictions"]["status"], horizon_days=horizon_days,
            model_version=versions["model_version"], knowledge_base_version=versions["knowledge_base_version"],
            scenario_catalog_version=versions["scenario_catalog_version"], result=result))
        self.session.commit()
        return result, False

    def get(self, simulation_id: str) -> dict:
        run = self.session.get(SimulationRun, simulation_id)
        if run is None:
            raise NotFoundError(f"simulation {simulation_id} not found")
        return run.result

    # ----------------------------------------------------------------- private
    def _seeds(self, v: ValidatedScenario) -> tuple[list[ScenarioSeed], list[dict]]:
        seeds, notes = [], []
        for name, value in v.shocks.items():
            p = self.catalog.parameters[name]
            if value == 0:
                notes.append({"code": "zero_parameter_ignored_in_graph", "parameter": name,
                              "message": f"{name}=0 implies no change; it adds no graph pathway."})
                continue
            sign = 1 if value > 0 else -1
            for sd in p.graph_seeds:
                seeds.append(ScenarioSeed(sd.node_id, sign * sd.sign_multiplier, name, value, p.unit,
                                          f"User assumption: {p.label} {_fmt(value, p.unit)} over {v.horizon_days} trading sessions"))
        return seeds, notes

    def _simulate(self, v: ValidatedScenario, max_depth: int | None, versions: dict) -> dict:
        sc = v.scenario
        settings = self.settings.model_copy(update={"path_max_depth": max_depth}) if max_depth else self.settings
        seeds, warnings = self._seeds(v)
        build = GraphBuilder(self.kb, settings).build_scenario(ScenarioInput(
            sc.id, sc.display_name, sc.event_type.value, sc.initiating_entities, sc.context_entities, seeds))
        analysis = PathAnalyzer(self.kb, settings).analyze(build)
        inf = inference.evaluate(v, self.catalog, self.models, self.settings.simulation_scenario_model_id)
        warnings += inf.warnings
        preds_by_asset = {a["kb_asset_id"]: a for a in inf.assets if a.get("kb_asset_id")}
        graph = serialize_scenario_graph(build, analysis, self.kb, self.layers, preds_by_asset)
        if not graph["paths"]:
            warnings.append({"code": "no_impact_paths", "message": "No knowledge-base pathway connects this scenario to a tradable asset."})
        for ex in build.excluded:
            if ex.get("kind") in ("seed_variable_not_in_kb", "scenario_entity_not_in_kb"):
                warnings.append({"code": ex["kind"], "detail": ex})
        prediction_status = inf.status
        if inf.assets and inf.status.startswith("available"):
            graph_assets = {n["id"] for n in graph["nodes"] if n["is_asset"]}
            missing = [a["symbol"] for a in inf.assets if a["kb_asset_id"] is None]
            if missing:
                warnings.append({"code": "model_targets_not_in_graph", "symbols": missing,
                                 "message": "These model targets have no knowledge-graph node; they appear only in predictions.assets."})
            not_reached = [a["symbol"] for a in inf.assets if a["kb_asset_id"] and a["kb_asset_id"] not in graph_assets]
            if not_reached:
                warnings.append({"code": "model_targets_not_on_scenario_graph", "symbols": not_reached,
                                 "message": "Estimated by the model but not reached by this scenario's graph pathways."})
        return {
            "scenario": {"id": sc.id, "display_name": sc.display_name, "category": sc.category,
                         "description": sc.description, "is_hypothetical": True, "limitations": sc.limitations},
            "status": "completed",
            "assumptions": [{"parameter": k, "value": val, "unit": self.catalog.parameters[k].unit,
                             "definition": self.catalog.parameters[k].definition, "source": "user_assumption"}
                            for k, val in v.shocks.items()],
            "graph": {**graph, "stats": build.stats, "layers": self.layers["layer_list"],
                      "excluded": [x for x in build.excluded if x.get("kind") != "rule_not_applicable"][:50]},
            "predictions": {"status": prediction_status, "horizon_trading_days": v.horizon_days,
                            "model": inf.model, "model_compatibility": inf.model_compatibility,
                            "inputs": inf.inputs, "assets": inf.assets,
                            "disclaimer": ("Conditional historical association, not a forecast or causal estimate. "
                                           "Intervals are empirical out-of-sample residual ranges, not guarantees.")},
            "evidence": {"historical_analogs": self._analogs(sc.historical_analog_event_ids),
                         "note": "Analogs are curated reference events for context; they are not used to compute the estimates."},
            "historical_patterns": self._historical_patterns(v),
            "timeline": self._timeline(graph),
            "warnings": warnings,
            "versions": versions,
        }

    def _historical_patterns(self, v: ValidatedScenario) -> dict:
        """Historical analogue weeks for the scenario's shocks (+ latest observed conditions). Observations only."""
        if self.patterns is None:
            return {"status": "unavailable", "reason": "pattern library not built"}
        try:
            res = patterns.search(self.patterns, self.catalog, "scenario", v.shocks, "latest", None, None, 15, v.horizon_days)
        except InvalidRequestError as exc:
            return {"status": "unavailable", "reason": exc.message, "details": exc.details}
        return {"status": "available", "kind": "historical_observations", **res}

    def _analogs(self, ids: list[str]) -> list[dict]:
        rows = {h.id: h for h in self.session.scalars(select(HistoricalEvent).where(HistoricalEvent.id.in_(ids)))}
        out = []
        for hid in ids:
            h = rows.get(hid)
            spec = next((x for x in self.kb.historical_events if x.id == hid), None)
            if h is None and spec is None:
                continue
            out.append({"id": hid, "title": h.title if h else spec.title,
                        "event_date": str(h.event_date) if h else spec.event_date,
                        "event_type": h.event_type if h else spec.event_type.value,
                        "source_type": h.source_type if h else "CURATED_REFERENCE",
                        "verification_note": h.verification_note if h else "Hand-curated reference event; verify before relying on it."})
        return out

    @staticmethod
    def _timeline(graph: dict) -> dict:
        on_path = [n for n in graph["nodes"] if n["on_impact_path"] or n["origin"] == "SCENARIO"]
        stages = []
        for layer, key, title, desc in TIMELINE_STAGES:
            ids = [n["id"] for n in on_path if n["layer"] == layer] if layer < 5 else []
            stages.append({"order": layer, "key": key, "title": title, "description": desc, "node_ids": ids,
                           "duration_trading_days": None})
        return {"mode": "illustrative",
                "note": ("Stages order the graph pathway by layer for display. They are not validated reaction times; "
                         "the only quantitative horizon is the model's 5-trading-day window."),
                "stages": stages}


def scenario_listing(catalog: ScenarioCatalog, models: dict[str, inference.ModelArtifact], model_id: str) -> list[dict[str, Any]]:
    m = models.get(model_id)
    feat_dom = m.domain if m else {}
    out = []
    for s in catalog.scenarios:
        params = []
        for name, use in s.parameters.items():
            p = catalog.parameters[name]
            dom = feat_dom.get(p.model_feature) if p.model_feature else None
            params.append({"name": name, "label": p.label, "unit": p.unit, "required": use.required,
                           "definition": p.definition, "accepted_range": list(p.input_range),
                           "used_by_model": bool(p.model_feature and dom),
                           "model_validated_range": [dom["min"], dom["max"]] if dom else None,
                           "typical_range_p01_p99": [dom["p01"], dom["p99"]] if dom else None,
                           "graph_variables": [sd.node_id for sd in p.graph_seeds]})
        out.append({"id": s.id, "display_name": s.display_name, "category": s.category, "description": s.description,
                    "is_hypothetical": True, "event_type": s.event_type.value,
                    "initiating_entities": s.initiating_entities, "context_entities": s.context_entities,
                    "parameters": params, "supported_horizons_trading_days": s.supported_horizons_trading_days,
                    "historical_analog_event_ids": s.historical_analog_event_ids,
                    "required_model_inputs": "at least one parameter with used_by_model=true for numerical estimates",
                    "limitations": s.limitations})
    return out
