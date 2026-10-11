"""GET /api/events/{id}/market and the enriched /api/assets/{id}/history."""

from __future__ import annotations

import pytest

from app.api import deps
from tests.api.test_api import client, ingest_and_process, oil_event_id  # noqa: F401 - fixture reuse
from tests.conftest import FakeMarketProvider


def _process_with_market(client, provider):  # noqa: F811
    client.app.dependency_overrides[deps.get_market_provider] = lambda: provider
    return oil_event_id(ingest_and_process(client))


class TestNoProvider:
    def test_unconfigured_integration_is_explained_and_no_fake_chart(self, client):  # noqa: F811
        eid = oil_event_id(ingest_and_process(client))
        r = client.get(f"/api/events/{eid}/market")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["market_data_provider"] is None and body["assets"]
        assert set(body["window_definitions"]) >= {"anchor_date", "reference_close", "window_k", "return_pct"}
        assert {c["code"] for c in body["limitation_codes"]} >= {"NOT_CONFIGURED", "NO_PROVIDER_COVERAGE"}
        for a in body["assets"]:
            assert a["availability"]["status"] == "UNAVAILABLE"
            assert a["availability"]["limitation"]["code"] == "NOT_CONFIGURED"
            assert a["availability"]["limitation"]["source"] == "integration"
            assert a["chart"]["bars"] == [] and a["latest_observation"] is None
            assert a["returns"]["windows"] == [] and a["returns"]["computed_in_analysis"] is False
            assert a["freshness"]["usable_as_current_price"] is False

    def test_404_before_analysis_and_for_unknown_event(self, client):  # noqa: F811
        assert client.get("/api/events/nope/market").status_code == 404


class TestWithProvider:
    def test_full_market_view(self, client):  # noqa: F811
        eid = _process_with_market(client, FakeMarketProvider(drift_by_symbol={"BZ=F": 0.004}))
        body = client.get(f"/api/events/{eid}/market").json()
        assert body["market_data_provider"] == "yahoo_chart"
        brent = next(a for a in body["assets"] if a["summary"]["asset_id"] == "asset:brent_futures")

        s = brent["summary"]
        assert s["symbol"] == "BZ=F" and s["exchange"] == "ICE" and s["currency"] == "USD"
        assert s["asset_type"] == "FUTURE" and s["provider"] == "yahoo_chart"

        chart = brent["chart"]
        assert chart["bars"] and chart["simulated"] is True  # test provider data is labelled simulated
        assert chart["latest_observation"]["date"] == chart["bars"][-1]["date"]
        kinds = {m["kind"] for m in chart["markers"]}
        assert {"EVENT", "REFERENCE", "WINDOW_END"} <= kinds
        event_marker = next(m for m in chart["markers"] if m["kind"] == "EVENT")
        assert event_marker["date"] == "2026-10-05"

        ret = brent["returns"]
        assert ret["computed_in_analysis"] and ret["reference_date"] == "2026-10-02"
        w = {x["window_trading_days"]: x for x in ret["windows"]}
        assert set(w) == {1, 3, 5, 20}
        assert w[1]["status"] == "AVAILABLE"
        assert w[1]["return_pct"] == pytest.approx(0.4, abs=1e-6)  # one session at +0.4% drift
        assert all(x["status"] in ("AVAILABLE", "NOT_YET_ELAPSED") for x in w.values())
        if any(x["status"] == "NOT_YET_ELAPSED" for x in w.values()):
            assert brent["availability"]["status"] == "PARTIALLY_AVAILABLE"
            assert brent["availability"]["limitation"]["code"] == "NOT_YET_ELAPSED"

        hc = brent["historical_context"]
        assert hc["status"] == "AVAILABLE" and hc["comparisons"]
        c = hc["comparisons"][0]
        assert c["relevant_asset"] == brent["summary"]["name"] and c["window_trading_days"] == 5
        assert c["observed_direction"] in ("UP", "DOWN", "FLAT") and c["path_implied_direction"] in ("UP", "DOWN")
        assert any("not proof of causation" in l or "not proof that" in l for l in hc["limitations"])
        assert any("hand-curated" in l for l in hc["limitations"])

    def test_asset_filter_and_bars_toggle(self, client):  # noqa: F811
        eid = _process_with_market(client, FakeMarketProvider())
        body = client.get(f"/api/events/{eid}/market",
                          params={"asset_id": "asset:usdinr", "include_bars": False}).json()
        assert [a["summary"]["asset_id"] for a in body["assets"]] == ["asset:usdinr"]
        assert body["assets"][0]["chart"]["bars"] == [] and body["assets"][0]["latest_observation"]

    def test_assets_outside_top_n_explained(self, client, settings):  # noqa: F811
        settings.market_max_assets = 1
        eid = _process_with_market(client, FakeMarketProvider())
        assets = client.get(f"/api/events/{eid}/market", params={"limit": 5}).json()["assets"]
        not_requested = [a for a in assets if not a["returns"]["computed_in_analysis"]]
        assert not_requested
        assert all(a["returns"]["limitation"]["code"] == "NOT_REQUESTED" for a in not_requested)
        assert all(a["chart"]["bars"] for a in not_requested)  # chart can still be shown

    def test_provider_outage_reported_as_provider_error(self, client):  # noqa: F811
        eid = _process_with_market(client, FakeMarketProvider(fail_symbols={"BZ=F"}))
        brent = next(a for a in client.get(f"/api/events/{eid}/market").json()["assets"]
                     if a["summary"]["asset_id"] == "asset:brent_futures")
        assert brent["availability"]["status"] == "UNAVAILABLE"
        assert brent["availability"]["limitation"]["code"] == "PROVIDER_ERROR"
        assert brent["chart"]["bars"] == []

    def test_cache_only_after_provider_removed(self, client):  # noqa: F811
        eid = _process_with_market(client, FakeMarketProvider())
        client.app.dependency_overrides[deps.get_market_provider] = lambda: None
        body = client.get(f"/api/events/{eid}/market").json()
        assert body["market_data_provider"] is None and body["market_data_provider_at_analysis"] == "yahoo_chart"
        analysed = next(a for a in body["assets"] if a["returns"]["computed_in_analysis"])
        assert analysed["chart"]["bars"] and analysed["chart"]["retrieved_from_cache"] is True


class TestHistoryEndpoint:
    def test_gaps_freshness_and_coverage(self, client):  # noqa: F811
        class HoleyProvider(FakeMarketProvider):
            async def fetch_daily(self, symbol, start, end):
                s = await super().fetch_daily(symbol, start, end)
                s.frame = s.frame.drop([d for d in s.frame.index if d.isoformat() in
                                        ("2026-09-14", "2026-09-15", "2026-09-16", "2026-09-22")])
                return s

        client.app.dependency_overrides[deps.get_market_provider] = lambda: HoleyProvider()
        h = client.get("/api/assets/asset:usdinr/history", params={"start": "2026-09-01", "end": "2026-09-30"}).json()
        assert h["status"] == "PARTIALLY_AVAILABLE" and h["limitation"]["code"] == "MISSING_OBSERVATIONS"
        gaps = {(g["from_date"], g["missing_sessions"], g["likely_holiday"]) for g in h["gaps"]}
        assert ("2026-09-11", 3, False) in gaps and ("2026-09-21", 1, True) in gaps
        after_gap = next(b for b in h["bars"] if b["date"] == "2026-09-17")
        assert after_gap["return_spans_gap"] is True
        assert h["freshness"]["latest_observation_date"] == "2026-09-30"
        assert h["freshness"]["is_stale"] is True  # old range: not a current price

        cov = client.get("/api/assets/asset:in_10y_gsec_yield/history").json()
        assert cov["status"] == "UNAVAILABLE" and cov["limitation"]["code"] == "NO_PROVIDER_COVERAGE"
        assert cov["limitation"]["source"] == "provider_coverage" and cov["bars"] == []
