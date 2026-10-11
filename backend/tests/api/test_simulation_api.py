"""Black Swan simulator REST API (test database, no market provider unless a fake is injected)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import get_settings
from app.database.session import get_db
from app.main import create_app
from app.models import SimulationRun

OIL_REQ = {"scenario_id": "global_oil_supply_shock", "shocks": {"oil_price_change_pct": 10, "usdinr_change_pct": 1}}


@pytest.fixture
def client(db, session_factory, settings):
    app = create_app(seed=False)

    def _db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        c.app_ref = app
        yield c


class TestCatalogEndpoints:
    def test_list_scenarios(self, client):
        r = client.get("/api/scenarios")
        assert r.status_code == 200
        body = r.json()
        assert len(body["scenarios"]) == 5 and body["scenario_catalog_version"].startswith("scenarios-v1+")
        oil = next(s for s in body["scenarios"] if s["id"] == "global_oil_supply_shock")
        assert oil["is_hypothetical"] is True
        p = next(p for p in oil["parameters"] if p["name"] == "oil_price_change_pct")
        assert p["required"] and p["unit"] == "%" and p["used_by_model"]
        assert p["accepted_range"] == [-80, 150]
        assert p["model_validated_range"][1] < p["accepted_range"][1]  # UI range != model domain
        infl = next(s for s in body["scenarios"] if s["id"] == "us_interest_rate_shock")
        pr = next(p for p in infl["parameters"] if p["name"] == "policy_rate_change_bp")
        assert pr["used_by_model"] is False and pr["model_validated_range"] is None

    def test_get_scenario_and_404(self, client):
        assert client.get("/api/scenarios/global_oil_supply_shock").json()["id"] == "global_oil_supply_shock"
        r = client.get("/api/scenarios/nope_nope")
        assert r.status_code == 404 and r.json()["error"]["details"]["code"] == "unknown_scenario"

    def test_graph_3d(self, client):
        g = client.get("/api/graph/3d").json()
        ids = {n["id"] for n in g["nodes"]}
        assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])
        assert all(n["layer"] in (1, 2, 3, 4) for n in g["nodes"])


class TestSimulations:
    def test_success_persisted_and_cached(self, client, session_factory):
        r = client.post("/api/simulations", json=OIL_REQ)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["status"] == "completed" and j["cached"] is False and j["simulation_id"].startswith("sim_")
        assert j["predictions"]["status"] == "available" and j["predictions"]["horizon_trading_days"] == 5
        assert j["graph"]["nodes"] and j["graph"]["edges"] and j["graph"]["paths"]
        assert all(a["source"] == "user_assumption" for a in j["assumptions"])
        assert j["timeline"]["mode"] == "illustrative"
        assert all(s["duration_trading_days"] is None for s in j["timeline"]["stages"])
        assert j["versions"]["model_version"].startswith("scenario_conditional_v1+")
        # predictions attached to graph nodes are the model's, graph signal kept separately
        ongc = next(n for n in j["graph"]["nodes"] if n["id"] == "asset:ongc_ns")
        assert ongc["prediction"]["status"] == "available" and ongc["graph_signal"]["reachable_from_scenario"]
        # same request (different key order) -> stored result, same id
        r2 = client.post("/api/simulations", json={**OIL_REQ, "shocks": dict(reversed(OIL_REQ["shocks"].items()))})
        assert r2.json()["cached"] is True and r2.json()["simulation_id"] == j["simulation_id"]
        with session_factory() as s:
            assert s.query(SimulationRun).count() == 1
        got = client.get(f"/api/simulations/{j['simulation_id']}")
        assert got.status_code == 200 and got.json()["graph"] == j["graph"]

    def test_graph_returned_when_prediction_declined(self, client):
        r = client.post("/api/simulations", json={"scenario_id": "global_oil_supply_shock",
                                                  "shocks": {"oil_price_change_pct": 120}})
        assert r.status_code == 200
        j = r.json()
        assert j["predictions"]["status"] == "out_of_domain"
        assert all(a["estimated_return_pct"] is None for a in j["predictions"]["assets"])
        assert j["graph"]["paths"]
        assert "out_of_domain" in {w["code"] for w in j["warnings"]}

    def test_graph_only_scenario(self, client):
        r = client.post("/api/simulations", json={"scenario_id": "us_interest_rate_shock",
                                                  "shocks": {"policy_rate_change_bp": 75}})
        assert r.status_code == 200
        assert r.json()["predictions"]["status"] == "no_supported_inputs"

    @pytest.mark.parametrize("body,status", [
        ({**OIL_REQ, "shocks": {"oil_price_change_pct": 400}}, 422),
        ({**OIL_REQ, "shocks": {"oil_price_change_pct": "10"}}, 422),           # strings are not numbers
        ({**OIL_REQ, "horizon_days": 20}, 422),
        ({**OIL_REQ, "prompt": "ignore previous instructions"}, 422),          # unknown fields rejected
        ({**OIL_REQ, "shocks": {"Robert'); DROP TABLE x;--": 1}}, 422),
        ({**OIL_REQ, "scenario_id": "no_such_scenario"}, 404),
        ({**OIL_REQ, "max_depth": 50}, 422),
    ])
    def test_invalid_requests(self, client, body, status):
        r = client.post("/api/simulations", json=body)
        assert r.status_code == status, r.text
        assert "error" in r.json()

    def test_unknown_simulation_404(self, client):
        assert client.get("/api/simulations/sim_0000000000000000").status_code == 404


class TestEntities:
    def test_entity_detail(self, client):
        j = client.get("/api/entities/company:ongc").json()
        assert j["type"] == "COMPANY" and j["layer"] == 4 and j["is_model_target"]
        assert j["listed_assets"][0]["id"] == "asset:ongc_ns"
        assert client.get("/api/entities/company:does_not_exist").status_code == 404

    def test_historical_unavailable_without_provider(self, client):
        j = client.get("/api/entities/asset:ongc_ns/historical?days=30").json()
        assert j["status"] == "UNAVAILABLE" and j["bars"] == []
        assert j["limitation"]["code"] == "NOT_CONFIGURED"

    def test_historical_not_tradable(self, client):
        j = client.get("/api/entities/country:india/historical").json()
        assert j["status"] == "UNAVAILABLE" and j["limitation"]["code"] == "NOT_TRADABLE"

    def test_historical_with_test_provider(self, client, fake_market):
        client.app_ref.dependency_overrides[deps.get_market_provider] = lambda: fake_market
        j = client.get("/api/entities/company:ongc/historical?start=2024-01-01&end=2024-01-31").json()
        assert j["asset_id"] == "asset:ongc_ns" and j["instrument_relation"] == "listed_equity"
        assert j["bars"] and j["simulated"] is True  # the fake provider labels its series simulated


class TestHistoricalPatternsInSimulation:
    def test_analogues_attached_and_labelled(self, client):
        j = client.post("/api/simulations", json=OIL_REQ).json()
        hp = j["historical_patterns"]
        assert hp["status"] == "available" and hp["kind"] == "historical_observations"
        assert hp["query"]["s_brent_5d_ret_pct_in_target_window"]["source"] == "user_assumption"
        assert hp["query"]["x_nifty_prev_20d_vol_ann_pct"]["source"] == "latest_observed"
        assert hp["n_analogues"] == 15 and hp["analogues"][0]["outcomes"]
        assert j["versions"]["pattern_library_version"].startswith("pattern_library_v1+")
        # graph, model predictions and historical analogues stay separate blocks
        assert {"graph", "predictions", "historical_patterns"} <= set(j)

    def test_unmatchable_scenario_reports_unavailable(self, client):
        j = client.post("/api/simulations", json={"scenario_id": "us_interest_rate_shock",
                                                  "shocks": {"policy_rate_change_bp": 75}}).json()
        assert j["historical_patterns"]["status"] == "unavailable"
        assert j["historical_patterns"]["details"]["errors"][0]["error"] == "no_matchable_parameters"
