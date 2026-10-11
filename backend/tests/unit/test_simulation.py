"""Black Swan simulator: scenario validation, model inference and scenario-graph serialisation."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from app.core.errors import InvalidRequestError, NotFoundError
from app.services.graph.builder import GraphBuilder, ScenarioInput, ScenarioSeed
from app.services.graph.paths import PathAnalyzer
from app.services.simulation import inference
from app.services.simulation.graph3d import full_knowledge_graph, load_layers, serialize_scenario_graph
from app.services.simulation.scenarios import load_scenario_catalog, validate_request

OIL = "oil_price_change_pct"


@pytest.fixture
def catalog(settings, kb):
    return load_scenario_catalog(settings.simulation_scenarios_file, kb)


@pytest.fixture
def models(settings):
    return inference.load_models(settings.simulation_model_dir)


@pytest.fixture
def layers(settings):
    return load_layers(settings.simulation_layers_file)


def errors_of(exc: InvalidRequestError) -> set[str]:
    return {e["error"] for e in exc.details["errors"]}


# ------------------------------------------------------------------ validation
class TestValidation:
    def test_catalog_references_only_existing_kb_nodes(self, catalog, kb):
        assert len(catalog.scenarios) == 5
        for s in catalog.scenarios:
            assert all(kb.node_exists(e) for e in [*s.initiating_entities, *s.context_entities])

    def test_unknown_scenario_is_404(self, catalog):
        with pytest.raises(NotFoundError):
            validate_request(catalog, "made_up", {OIL: 5}, 5)

    def test_values_are_not_clamped(self, catalog):
        v = validate_request(catalog, "global_oil_supply_shock", {OIL: 149.5}, 5)
        assert v.shocks[OIL] == 149.5

    @pytest.mark.parametrize("shocks,horizon,code", [
        ({OIL: 400}, 5, "out_of_accepted_range"),
        ({OIL: -81}, 5, "out_of_accepted_range"),
        ({OIL: 5, "made_up_param": 1}, 5, "unsupported_parameter"),
        ({OIL: 5}, 20, "unsupported_horizon"),
        ({OIL: float("nan")}, 5, "not_a_finite_number"),
        ({OIL: float("inf")}, 5, "not_a_finite_number"),
        ({OIL: 0}, 5, "all_parameters_zero"),
        ({"usdinr_change_pct": 1}, 5, "required_parameter_missing"),
    ])
    def test_rejections(self, catalog, shocks, horizon, code):
        with pytest.raises(InvalidRequestError) as ei:
            validate_request(catalog, "global_oil_supply_shock", shocks, horizon)
        assert code in errors_of(ei.value)
        assert ei.value.status_code == 422

    def test_empty_shocks_rejected(self, catalog):
        with pytest.raises(InvalidRequestError) as ei:
            validate_request(catalog, "middle_east_geopolitical_crisis", {}, 5)
        assert "no_parameters" in errors_of(ei.value)


# ------------------------------------------------------------------- inference
class TestInference:
    def test_artifacts_load_and_declare_capabilities(self, models):
        sc, fc = models["scenario_conditional_v1"], models["forecast_trailing_v1"]
        assert sc.supports_hypothetical_shocks and not fc.supports_hypothetical_shocks
        assert sc.horizon == 5
        comp = {c["model_id"]: c for c in inference.compatibility(models)}
        assert comp["forecast_trailing_v1"]["used_for_simulation"] is False and comp["forecast_trailing_v1"]["reason"]

    def test_feature_order_and_units_match_catalog(self, models, catalog):
        m = models["scenario_conditional_v1"]
        mapped = {p.model_feature: (name, p.unit) for name, p in catalog.parameters.items() if p.model_feature}
        assert set(m.feature_order) == set(mapped)
        for f in m.raw["features"]:
            name, unit = mapped[f["column"]]
            assert f["scenario_parameter"] == name and f["unit"] == unit

    def test_prediction_equals_stored_linear_model(self, models, catalog):
        m = models["scenario_conditional_v1"]
        v = validate_request(catalog, "global_oil_supply_shock", {OIL: 10, "usdinr_change_pct": 1}, 5)
        res = inference.evaluate(v, catalog, models, "scenario_conditional_v1")
        assert res.status == "available"
        x = np.array([{"s_brent_5d_ret_pct_in_target_window": 10, "s_usdinr_5d_ret_pct_in_target_window": 1}.get(f, 0.0)
                      for f in m.raw["feature_order"]])
        W = np.array(m.raw["coefficients"]["weights_per_standardized_feature"])
        expected = (np.array(m.raw["coefficients"]["intercept"])
                    + ((x - np.array(m.raw["standardization"]["mean"])) / np.array(m.raw["standardization"]["sd"])) @ W)
        got = [a["estimated_return_pct"] for a in res.assets]
        assert np.allclose(got, np.round(expected, 3))
        for a in res.assets:
            lo, hi = a["interval_80_pct"]
            lo9, hi9 = a["interval_90_pct"]
            assert lo9 <= lo <= hi <= hi9 and all(math.isfinite(z) for z in (lo, hi, lo9, hi9))
            assert a["horizon_trading_days"] == 5 and a["reliability"]["n_oos_weeks"] > 0
        held = {i["parameter"] for i in res.inputs if i["source"] == "held_constant"}
        assert held == {"sp500_change_pct", "gold_change_pct", "us10y_change_bp"}
        assert "inputs_held_constant" in {w["code"] for w in res.warnings}

    def test_tail_value_warns(self, models, catalog):
        v = validate_request(catalog, "global_oil_supply_shock", {OIL: 25}, 5)  # p99 ~20.4, max ~33.8
        res = inference.evaluate(v, catalog, models, "scenario_conditional_v1")
        assert res.status == "available_with_warnings"
        assert "tail_extrapolation" in {w["code"] for w in res.warnings}

    def test_out_of_domain_declines_without_zero_fill(self, models, catalog):
        v = validate_request(catalog, "global_oil_supply_shock", {OIL: 60}, 5)  # accepted, but beyond training max
        res = inference.evaluate(v, catalog, models, "scenario_conditional_v1")
        assert res.status == "out_of_domain"
        assert res.assets and all(a["estimated_return_pct"] is None and a["interval_80_pct"] is None
                                  and a["status"] == "declined_out_of_domain" for a in res.assets)

    def test_graph_only_parameter_gives_no_estimates(self, models, catalog):
        v = validate_request(catalog, "us_interest_rate_shock", {"policy_rate_change_bp": 50}, 5)
        res = inference.evaluate(v, catalog, models, "scenario_conditional_v1")
        assert res.status == "no_supported_inputs"
        assert all(a["estimated_return_pct"] is None for a in res.assets)
        assert "parameter_not_used_by_model" in {w["code"] for w in res.warnings}

    def test_missing_model_is_explicit(self, catalog):
        v = validate_request(catalog, "global_oil_supply_shock", {OIL: 10}, 5)
        res = inference.evaluate(v, catalog, {}, "scenario_conditional_v1")
        assert res.status == "model_unavailable" and res.assets == []

    def test_inconsistent_artifact_rejected(self, settings, tmp_path):
        raw = json.loads((settings.simulation_model_dir / "scenario_conditional_v1.json").read_text(encoding="utf-8"))
        raw["standardization"]["sd"] = raw["standardization"]["sd"][:-1]
        p = tmp_path / "broken.json"
        p.write_text(json.dumps(raw), encoding="utf-8")
        with pytest.raises(ValueError):
            inference._load_artifact(p)


# ----------------------------------------------------------------------- graph
def scenario_graph(kb, settings, catalog, layers, scenario_id: str, shocks: dict[str, float]):
    sc = catalog.get(scenario_id)
    seeds = []
    for name, val in shocks.items():
        p = catalog.parameters[name]
        for sd in p.graph_seeds:
            seeds.append(ScenarioSeed(sd.node_id, (1 if val > 0 else -1) * sd.sign_multiplier, name, val, p.unit, "test"))
    build = GraphBuilder(kb, settings).build_scenario(ScenarioInput(
        sc.id, sc.display_name, sc.event_type.value, sc.initiating_entities, sc.context_entities, seeds))
    analysis = PathAnalyzer(kb, settings).analyze(build)
    return build, analysis, serialize_scenario_graph(build, analysis, kb, layers, {})


class TestScenarioGraph:
    def test_structure_ids_layers(self, kb, settings, catalog, layers):
        _, _, g = scenario_graph(kb, settings, catalog, layers, "global_oil_supply_shock", {OIL: 20})
        node_ids = [n["id"] for n in g["nodes"]]
        edge_ids = [e["id"] for e in g["edges"]]
        assert len(node_ids) == len(set(node_ids)) and len(edge_ids) == len(set(edge_ids))
        assert all(e["source"] in node_ids and e["target"] in node_ids for e in g["edges"])  # no dangling edges
        assert all(n["layer"] in (1, 2, 3, 4) for n in g["nodes"])
        assert g["paths"]
        for p in g["paths"]:
            assert set(p["edge_ids"]) <= set(edge_ids) and p["score_is_probability"] is False
            assert len(p["edge_ids"]) == len(p["node_ids"]) - 1
        seed = [e for e in g["edges"] if e["id"].startswith("seed:")]
        assert seed and all(e["status"] == "ASSUMED" and e["evidence_status"] == "assumed" for e in seed)
        assert all(e["evidence_ids"] for e in g["edges"] if e["status"] == "INFERRED")
        assert all(e["support_score"]["is_probability"] is False for e in g["edges"])

    def test_edge_ids_are_stable_across_runs(self, kb, settings, catalog, layers):
        a = scenario_graph(kb, settings, catalog, layers, "global_oil_supply_shock", {OIL: 20})[2]
        b = scenario_graph(kb, settings, catalog, layers, "global_oil_supply_shock", {OIL: 20})[2]
        assert [e["id"] for e in a["edges"]] == [e["id"] for e in b["edges"]]

    def test_direction_follows_shock_sign(self, kb, settings, catalog, layers):
        up = scenario_graph(kb, settings, catalog, layers, "global_oil_supply_shock", {OIL: 20})[1]
        down = scenario_graph(kb, settings, catalog, layers, "global_oil_supply_shock", {OIL: -20})[1]
        su = {a.asset_id: a.impact_direction.value for a in up.assets}
        sd = {a.asset_id: a.impact_direction.value for a in down.assets}
        flip = {"POTENTIAL_UPWARD_PRESSURE": "POTENTIAL_DOWNWARD_PRESSURE",
                "POTENTIAL_DOWNWARD_PRESSURE": "POTENTIAL_UPWARD_PRESSURE"}
        common = [k for k in su if k in sd and su[k] in flip]
        assert common, "expected directional assets in both runs"
        assert all(sd[k] == flip[su[k]] for k in common)

    def test_max_depth_respected(self, kb, settings, catalog, layers):
        s3 = settings.model_copy(update={"path_max_depth": 3})
        _, _, g = scenario_graph(kb, s3, catalog, layers, "global_oil_supply_shock", {OIL: 20})
        assert all(len(p["node_ids"]) - 1 <= 3 for p in g["paths"])

    def test_full_knowledge_graph(self, kb, catalog, layers):
        g = full_knowledge_graph(kb, catalog, layers)
        ids = {n["id"] for n in g["nodes"]}
        assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])
        assert len({e["id"] for e in g["edges"]}) == len(g["edges"])
        assert {f"scenario:{s.id}" for s in catalog.scenarios} <= ids
        assert [x["layer"] for x in g["layers"]] == [1, 2, 3, 4]
