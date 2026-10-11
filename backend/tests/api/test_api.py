"""REST API tests via FastAPI's TestClient (mock LLM, fixture news, no market provider)."""

from __future__ import annotations

import pytest
from pydantic import SecretStr
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.main import create_app
from app.services.llm.mock_provider import MockLLMProvider
from app.services.pipeline import AnalysisPipeline


@pytest.fixture
def client(db, session_factory, settings, kb):
    app = create_app(seed=False)

    def _db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_settings] = lambda: settings

    def job_factory():
        s = session_factory()
        return s, AnalysisPipeline(s, settings, kb, MockLLMProvider(kb), None)

    previous = deps.job_pipeline_factory
    deps.set_job_pipeline_factory(job_factory)
    with TestClient(app) as c:
        yield c
    deps.set_job_pipeline_factory(previous)


def ingest_and_process(client) -> dict:
    r = client.post("/api/articles/ingest", json={"provider": "fixture"})
    assert r.status_code == 200, r.text
    out = {}
    for aid in r.json()["article_ids"]:
        out[aid] = client.post(f"/api/articles/{aid}/process").json()
    return out


def oil_event_id(results: dict) -> str:
    return next(r["event_id"] for r in results.values() if r["event_id"] and r["merged_into_existing"])


class TestHealth:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200 and r.json()["database"] == "ok"

    def test_integrations_never_expose_secrets(self, client, settings):
        settings.finnhub_api_key = SecretStr("finnhub-secret-value")
        settings.news_provider = "finnhub"
        r = client.get("/api/health/integrations")
        body = r.text
        assert r.status_code == 200 and "finnhub-secret-value" not in body
        data = r.json()
        assert data["news"]["credentials_present"] is True
        assert data["llm"]["simulated"] is True and data["market_data"]["configured"] is False

    def test_openapi_docs(self, client):
        assert client.get("/docs").status_code == 200
        assert "/api/events/{event_id}/paths" in client.get("/openapi.json").json()["paths"]


class TestArticlesAndEvents:
    def test_ingest_list_filter_paginate(self, client):
        r = client.post("/api/articles/ingest", json={"provider": "fixture", "limit": 5})
        assert r.json()["inserted"] == 5
        again = client.post("/api/articles/ingest", json={"provider": "fixture"}).json()
        assert again["inserted"] == 0 and again["duplicates"] == 5
        page = client.get("/api/articles", params={"page_size": 2, "page": 2}).json()
        assert page["total"] == 5 and len(page["items"]) == 2
        sim = client.get("/api/articles", params={"simulated": True}).json()
        assert sim["total"] == 5 and all(a["is_simulated"] for a in sim["items"])

    def test_validation_errors_are_structured(self, client):
        r = client.post("/api/articles/ingest", json={"limit": 0})
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
        r = client.get("/api/articles", params={"page_size": 1000})
        assert r.status_code == 422

    def test_not_found(self, client):
        r = client.get("/api/events/nope")
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
        assert client.get("/api/analysis/nope").status_code == 404
        assert client.get("/api/assets/asset:nope/history").status_code == 404

    def test_event_detail_and_listing(self, client):
        results = ingest_and_process(client)
        statuses = sorted(r["status"] for r in results.values())
        assert statuses.count("FILTERED_OUT") == 1
        events = client.get("/api/events").json()
        assert events["total"] == 3
        eid = oil_event_id(results)
        detail = client.get(f"/api/events/{eid}").json()
        assert len(detail["articles"]) == 2 and detail["verification_status"] == "SIMULATED"
        assert {a["role"] for a in detail["articles"]} == {"PRIMARY", "SUPPORTING"}
        filtered = client.get("/api/events", params={"event_type": "TARIFF_TRADE"}).json()
        assert filtered["total"] == 1


class TestAnalysisViews:
    def test_graph_paths_evidence_entities(self, client):
        eid = oil_event_id(ingest_and_process(client))
        g = client.get(f"/api/events/{eid}/graph").json()
        assert g["elements"]["nodes"] and g["elements"]["edges"]
        edge = g["elements"]["edges"][0]["data"]
        assert {"source", "target", "status", "direction", "score_components", "evidence"} <= edge.keys()
        assert g["legend"]["edges_are_not_causal_claims"] is True and g["mode"] == "SIMULATED"
        assert g["graph_version"]["knowledge_base_version"]

        paths = client.get(f"/api/events/{eid}/paths", params={"limit": 10}).json()
        assert paths["paths"][0]["rank"] == 1 and "NOT probabilities" in paths["score_semantics"]
        assert paths["explanation"]["status"] == "VALID" and paths["explanation"]["simulated"] is True
        assets = {a["asset_id"]: a for a in paths["assets"]}
        assert assets["asset:usdinr"]["impact_direction"] == "POTENTIAL_UPWARD_PRESSURE"
        one = client.get(f"/api/events/{eid}/paths", params={"asset_id": "asset:jets"}).json()
        assert one["paths"] and all(p["target_asset_id"] == "asset:jets" for p in one["paths"])

        ev = client.get(f"/api/events/{eid}/evidence").json()
        assert len(ev["articles"]) == 2 and ev["claims"]
        assert any(c["passage_verified"] for c in ev["claims"])
        assert any(r["evidence_type"] == "KNOWLEDGE_BASE_RATIONALE" for r in ev["relationship_evidence"])

        ents = client.get(f"/api/events/{eid}/entities").json()
        assert ents["article_entities"] and ents["inferred_entities"]
        assert all(e["origin"] == "INFERRED" for e in ents["inferred_entities"])

    def test_analyze_stored_event_background_and_sync(self, client):
        eid = oil_event_id(ingest_and_process(client))
        r = client.post(f"/api/events/{eid}/analyze")
        assert r.status_code == 202
        run_id = r.json()["analysis_id"]
        # TestClient runs background tasks before returning control.
        a = client.get(f"/api/analysis/{run_id}").json()
        assert a["status"] == "COMPLETED" and a["mode"] == "SIMULATED" and a["top_assets"]
        assert "evidence_package" not in (a["explanation"] or {})
        full = client.get(f"/api/analysis/{run_id}", params={"include_evidence_package": True}).json()
        assert full["explanation"]["evidence_package"]["candidate_paths"]
        r2 = client.post(f"/api/events/{eid}/analyze", json={"wait": True})
        assert r2.status_code == 200 and r2.json()["status"] == "COMPLETED"

    def test_graph_before_analysis_is_404_with_hint(self, client, db, settings, kb):
        from app.services.events.processor import EventProcessor
        import asyncio

        aid = client.post("/api/articles/ingest", json={"provider": "fixture"}).json()["article_ids"][0]
        res = asyncio.run(EventProcessor(db, MockLLMProvider(kb), kb).process_article(aid))
        r = client.get(f"/api/events/{res.event_id}/graph")
        assert r.status_code == 404 and "analyze" in r.json()["error"]["details"]["hint"]


class TestManualAnalysis:
    def test_supplied_text_is_labelled_user_supplied(self, client):
        r = client.post("/api/events/analyze", json={
            "headline": "Reserve Bank of India raises repo rate by 50 basis points",
            "body": "The Reserve Bank of India raised the repo rate by 50 basis points to curb inflation. "
                    "Indian bond yields rose after the decision.",
            "source_name": "Analyst scenario"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "COMPLETED" and body["event_id"]
        ev = client.get(f"/api/events/{body['event_id']}").json()
        assert ev["verification_status"] == "USER_SUPPLIED"
        assert ev["articles"][0]["article"]["input_origin"] == "USER_SUPPLIED"
        paths = client.get(f"/api/events/{body['event_id']}/paths").json()
        assert any(a["asset_id"] == "asset:in_10y_gsec_yield" for a in paths["assets"])

    def test_simulated_flag_and_background_mode(self, client):
        r = client.post("/api/events/analyze", json={
            "headline": "US Federal Reserve cuts interest rates by 25 basis points",
            "body": "The Federal Reserve cut the federal funds rate by 25 basis points.", "simulated": True,
            "wait": False})
        assert r.status_code == 202, r.text
        a = client.get(f"/api/analysis/{r.json()['analysis_id']}").json()
        assert a["status"] == "COMPLETED"
        ev = client.get(f"/api/events/{r.json()['event_id']}").json()
        assert ev["verification_status"] == "SIMULATED" and ev["is_simulated"]

    def test_non_financial_text_does_not_create_event(self, client):
        r = client.post("/api/events/analyze", json={"headline": "Local cricket club wins regional championship",
                                                     "body": "A celebration followed the cricket final."})
        assert r.status_code == 200 and r.json()["event_id"] is None and r.json()["status"] == "NOT_EVENT"


class TestAssetsAndConfig:
    def test_asset_list_and_unavailable_history(self, client):
        assets = client.get("/api/assets").json()
        usdinr = next(a for a in assets if a["id"] == "asset:usdinr")
        assert usdinr["symbols"]["yahoo_chart"] == "INR=X"
        h = client.get("/api/assets/asset:usdinr/history").json()
        assert h["status"] == "UNAVAILABLE" and h["bars"] == [] and "no market-data provider" in h["reason"]

    def test_history_with_provider(self, client, kb, settings):
        from tests.conftest import FakeMarketProvider

        client.app.dependency_overrides[deps.get_market_provider] = lambda: FakeMarketProvider()
        h = client.get("/api/assets/asset:usdinr/history",
                       params={"start": "2026-09-01", "end": "2026-09-30"}).json()
        assert h["status"] == "AVAILABLE" and h["simulated"] is True and h["bars"]
        assert h["bars"][1]["daily_return_pct"] == pytest.approx(0.1, rel=1e-3)
        again = client.get("/api/assets/asset:usdinr/history", params={"start": "2026-09-01", "end": "2026-09-30"}).json()
        assert again["retrieved_from_cache"] is True

    def test_missing_llm_credentials_return_503_but_reads_work(self, client, settings):
        settings.llm_provider = "anthropic"
        settings.anthropic_api_key = None
        r = client.post("/api/events/analyze", json={"headline": "Brent crude jumps after OPEC+ cut", "body": "x"})
        assert r.status_code == 503 and r.json()["error"]["code"] == "configuration_error"
        assert client.get("/api/events").status_code == 200
        assert client.get("/api/health/integrations").json()["llm"]["configured"] is False


def test_integrations_show_fallback_chain_without_secrets(client, settings):
    settings.llm_provider = "fallback"
    settings.llm_fallback_chain = ["gemini", "groq"]
    settings.gemini_api_key = SecretStr("gemini-secret-value")
    settings.groq_api_key = None
    r = client.get("/api/health/integrations")
    assert "gemini-secret-value" not in r.text
    llm = r.json()["llm"]
    assert llm["provider"] == "fallback" and llm["configured"] is True
    assert [(m["provider"], m["configured"]) for m in llm["chain"]] == [("gemini", True), ("groq", False)]
    assert llm["chain"][1]["problem"] == "GROQ_API_KEY missing"
