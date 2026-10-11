"""Report endpoints: 12-section envelope for event analyses and simulations (test database only)."""

from __future__ import annotations

import json
import re

import pytest

from app.schemas.report import SECTION_KEYS
from tests.api.test_api import client, ingest_and_process, oil_event_id  # noqa: F401  (fixture reuse)

KEYS = [k for k, _ in SECTION_KEYS]
PCT = re.compile(r"([+-]?\d+(?:\.\d+)?)%")


def check_envelope(rep: dict, kind: str) -> None:
    assert rep["kind"] == kind and rep["report_id"].startswith("rep_")
    assert [s["key"] for s in rep["sections"]] == KEYS
    for s in rep["sections"]:
        assert s["status"] in ("available", "partial", "unavailable")
        if s["status"] == "unavailable":
            assert s["unavailable_reason"], s["key"]
        # every percentage in a narrative must exist in that section's own data (nothing invented)
        blob = json.dumps(s["data"])
        for m in PCT.finditer(s["narrative"] or ""):
            v = float(m.group(1))
            assert any(abs(v - float(x)) < 0.006 for x in re.findall(r"-?\d+\.?\d*", blob)), (s["key"], m.group(0))


class TestEventReport:
    def test_event_report(self, client):
        res = ingest_and_process(client)
        eid = oil_event_id(res)
        run_id = client.get(f"/api/events/{eid}").json()["latest_analysis_id"]
        r = client.post("/api/reports", json={"kind": "event", "source_id": run_id})
        assert r.status_code == 201, r.text
        rep = r.json()
        check_envelope(rep, "event")
        sec = {s["key"]: s for s in rep["sections"]}
        assert rep["is_simulated_data"] is True and rep["is_hypothetical"] is False
        # no market provider in tests -> explicit unavailable, never invented observations
        assert sec["historical_market_behaviour"]["status"] == "unavailable"
        assert "MARKET_DATA_PROVIDER=none" in sec["historical_market_behaviour"]["unavailable_reason"]
        assert sec["ml_predictions"]["status"] == "unavailable"
        # citations point at real package refs / urls
        arts = sec["evidence_and_sources"]["data"]["articles"]
        refs = {a["ref"] for a in arts}
        assert {c["ref"] for c in sec["evidence_and_sources"]["citations"] if c["kind"] == "article"} <= refs
        assert sec["impact_pathways"]["status"] == "available" and sec["impact_pathways"]["data"]["paths"]
        # persisted, retrievable, and identical requests reuse the stored report
        got = client.get(f"/api/reports/{rep['report_id']}").json()
        assert got["sections"] == rep["sections"]
        again = client.post("/api/reports", json={"kind": "event", "source_id": run_id}).json()
        assert again["cached"] is True and again["report_id"] == rep["report_id"]
        assert any(x["report_id"] == rep["report_id"] for x in client.get(f"/api/reports?source_id={run_id}").json())


class TestSimulationReport:
    def test_available_estimates(self, client):
        sim = client.post("/api/simulations", json={"scenario_id": "global_oil_supply_shock",
                                                    "shocks": {"oil_price_change_pct": 15, "usdinr_change_pct": 1}}).json()
        rep = client.post("/api/reports", json={"kind": "simulation", "source_id": sim["simulation_id"]}).json()
        check_envelope(rep, "simulation")
        sec = {s["key"]: s for s in rep["sections"]}
        assert rep["is_hypothetical"] is True
        assert sec["ml_predictions"]["status"] == "available"
        assert sec["historical_market_behaviour"]["status"] in ("available", "partial")
        assert sec["timeline"]["data"]["mode"] == "illustrative"
        assert "user assumptions" in " ".join(sec["executive_summary"]["limitations"])

    def test_out_of_domain_has_no_numbers(self, client):
        sim = client.post("/api/simulations", json={"scenario_id": "global_oil_supply_shock",
                                                    "shocks": {"oil_price_change_pct": 60}}).json()
        rep = client.post("/api/reports", json={"kind": "simulation", "source_id": sim["simulation_id"]}).json()
        ml = next(s for s in rep["sections"] if s["key"] == "ml_predictions")
        assert ml["status"] == "unavailable" and "out_of_domain" in ml["unavailable_reason"]
        assert all(a["estimated_return_pct"] is None for a in ml["data"]["assets"])


@pytest.mark.parametrize("body,code", [
    ({"kind": "event", "source_id": "no-such-run"}, 404),
    ({"kind": "simulation", "source_id": "sim_0000000000000000"}, 404),
    ({"kind": "event", "source_id": "bad id!"}, 422),
    ({"kind": "chart", "source_id": "x123"}, 422),
    ({"kind": "event", "source_id": "x123", "extra": 1}, 422),
])
def test_report_errors(client, body, code):
    assert client.post("/api/reports", json=body).status_code == code


def test_unknown_report(client):
    assert client.get("/api/reports/rep_0000000000000000").status_code == 404


def test_concurrent_identical_requests_store_one_report(client, session_factory):
    """Two simultaneous identical requests (e.g. React StrictMode double effects) must not store duplicates."""
    from concurrent.futures import ThreadPoolExecutor

    from app.models.report import AnalysisReport

    sim = client.post("/api/simulations", json={"scenario_id": "global_oil_supply_shock", "shocks": {"oil_price_change_pct": 12}}).json()
    with ThreadPoolExecutor(4) as ex:
        reps = list(ex.map(lambda _: client.post("/api/reports", json={"kind": "simulation", "source_id": sim["simulation_id"]}).json(), range(4)))
    assert len({r["report_id"] for r in reps}) == 1
    with session_factory() as s:
        assert s.query(AnalysisReport).filter_by(source_id=sim["simulation_id"]).count() == 1
