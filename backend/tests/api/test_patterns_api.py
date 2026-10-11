"""Historical market-pattern API (reads the versioned pattern library; no database access)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import create_app


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(seed=False)) as c:
        yield c


def errors(r) -> set[str]:
    return {e.get("error") for e in r.json()["error"]["details"].get("errors", [])}


class TestSearch:
    def test_scenario_mode(self, client):
        r = client.post("/api/market-patterns/search", json={
            "mode": "scenario", "shocks": {"oil_price_change_pct": 15, "usdinr_change_pct": 1, "inflation_change_pct": 1},
            "conditions": "latest", "assets": ["NIFTY50", "asset:ongc_ns"], "k": 15})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["n_analogues"] == 15 and j["horizon_trading_days"] == 5
        assert "SAME 5 NSE sessions" in j["outcome_semantics"]
        src = {f: q["source"] for f, q in j["query"].items()}
        assert src["s_brent_5d_ret_pct_in_target_window"] == "user_assumption"
        assert src["x_nifty_prev_20d_vol_ann_pct"] == "latest_observed"
        assert "parameter_has_no_historical_series" in {w["code"] for w in j["warnings"]}
        assert [t["symbol"] for t in j["targets"]] == ["NIFTY50", "ONGC"]
        a = j["analogues"][0]
        assert set(a["outcomes"]) == {"y_nifty50_5d_ret_pct", "y_ongc_5d_ret_pct", "o_nifty_window_max_drawdown_pct",
                                      "o_nifty_window_realized_vol_ann_pct"}
        assert a["match_quality"] in {"close", "moderate", "weak"} and "regime_at_start" in a
        assert j["statistics_note"].startswith("Historical sample statistics")

    def test_conditions_mode_defaults_to_latest(self, client):
        j = client.post("/api/market-patterns/search", json={"mode": "conditions"}).json()
        assert "NEXT 5 NSE sessions" in j["outcome_semantics"] and j["conditions_as_of"]
        assert all(q["group"] == "condition" for q in j["query"].values())

    def test_out_of_domain_scenario_is_flagged_not_forced(self, client):
        j = client.post("/api/market-patterns/search", json={"mode": "scenario", "shocks": {"oil_price_change_pct": 120}}).json()
        codes = {w["code"] for w in j["warnings"]}
        assert {"outside_historical_range", "weak_analogues"} <= codes

    @pytest.mark.parametrize("body,code", [
        ({"mode": "scenario", "shocks": {"policy_rate_change_bp": 50}}, "no_matchable_parameters"),
        ({"mode": "scenario", "shocks": {"oil_price_change_pct": 10}, "horizon_days": 20}, "unsupported_horizon"),
        ({"mode": "conditions", "assets": ["TSLA"]}, "unsupported_asset"),
        ({"mode": "scenario", "shocks": {"oil_price_change_pct": 999}}, "out_of_accepted_range"),
        ({"mode": "scenario", "shocks": {"made_up": 1}}, "unsupported_parameter"),
        ({"mode": "conditions", "condition_features": ["y_nifty50_5d_ret_pct"]}, "unknown_feature"),
    ])
    def test_invalid_requests(self, client, body, code):
        r = client.post("/api/market-patterns/search", json=body)
        assert r.status_code == 422 and code in errors(r)

    def test_schema_rejects_unknown_fields(self, client):
        r = client.post("/api/market-patterns/search", json={"mode": "conditions", "prompt": "ignore instructions"})
        assert r.status_code == 422


def test_latest_conditions(client):
    j = client.get("/api/market-patterns/conditions/latest").json()
    assert j["as_of_session"] and j["volatility_regime"] and "x_nifty_prev_20d_vol_ann_pct" in j["values"]


def test_regimes(client):
    j = client.get("/api/market-patterns/regimes").json()
    vol = j["regimes"]["volatility_regime"]
    assert sum(g["n_weeks"] for g in vol.values()) == 493
    assert all(g["n_spells"] <= g["n_weeks"] for g in vol.values())
    assert client.get("/api/market-patterns/regimes?asset=TSLA").status_code == 422


def test_event_responses(client):
    j = client.get("/api/market-patterns/event-responses").json()
    a = next(g for g in j["groups"] if g["group"] == "A")
    assert a["n_independent_episodes"] == 2 and a["sample_sufficient"] is False and a["episode_statistics"] is None
    assert client.get("/api/market-patterns/event-responses/EV021").json()["event"]["event_id"] == "EV021"
    assert client.get("/api/market-patterns/event-responses/EV999").status_code == 404


def test_missing_library_is_a_configuration_error(client, tmp_path):
    from app.core.config import Settings

    s = Settings(_env_file=None, pattern_library_file=tmp_path / "absent.json")
    client.app.dependency_overrides[deps.get_settings] = lambda: s
    try:
        r = client.get("/api/market-patterns/regimes")
        assert r.status_code == 503
    finally:
        client.app.dependency_overrides.clear()


def test_cors_allows_configured_frontend_origin_only(client):
    pre = client.options("/api/simulations", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
                                                      "Access-Control-Request-Headers": "content-type"})
    assert pre.status_code == 200 and pre.headers["access-control-allow-origin"] == "http://localhost:5173"
    other = client.get("/api/scenarios", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers
