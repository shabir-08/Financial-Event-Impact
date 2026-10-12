"""/api/saved-analyses: save (with report snapshot), idempotency, listing, removal, validation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import get_settings
from app.database.session import get_db
from app.main import create_app
from app.models import AnalysisReport, AnalysisRun, Event
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


@pytest.fixture
def run_id(client, db) -> str:
    r = client.post("/api/articles/ingest", json={"provider": "fixture"})
    assert r.status_code == 200, r.text
    for aid in r.json()["article_ids"]:
        client.post(f"/api/articles/{aid}/process")
    db.expire_all()
    ev = next(e for e in db.query(Event).all() if e.latest_analysis_id)
    return ev.latest_analysis_id


def test_save_snapshots_report_and_is_idempotent(client, db, run_id):
    r = client.post("/api/saved-analyses", json={"analysis_id": run_id, "saved_by": "test", "note": "for the judges"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["analysis_id"] == run_id and body["already_saved"] is False
    assert body["report_status"] == "STORED" and body["report_id"]
    assert body["saved_by"] == "test" and body["note"] == "for the judges"
    assert body["is_simulated"] is True  # fixture articles + mock LLM: labelled, not hidden
    assert db.get(AnalysisReport, body["report_id"]) is not None

    again = client.post("/api/saved-analyses", json={"analysis_id": run_id})
    assert again.status_code == 200 and again.json()["already_saved"] is True and again.json()["id"] == body["id"]
    listed = client.get("/api/saved-analyses").json()
    assert [x["id"] for x in listed] == [body["id"]]


def test_filter_by_analysis_and_remove(client, run_id):
    saved = client.post("/api/saved-analyses", json={"analysis_id": run_id}).json()
    assert len(client.get("/api/saved-analyses", params={"analysis_id": run_id}).json()) == 1
    assert client.get("/api/saved-analyses", params={"analysis_id": "other-run"}).json() == []
    assert client.delete(f"/api/saved-analyses/{saved['id']}").status_code == 204
    assert client.get("/api/saved-analyses").json() == []
    assert client.delete(f"/api/saved-analyses/{saved['id']}").status_code == 404


def test_report_kept_after_unsave(client, db, run_id):
    saved = client.post("/api/saved-analyses", json={"analysis_id": run_id}).json()
    client.delete(f"/api/saved-analyses/{saved['id']}")
    db.expire_all()
    assert db.get(AnalysisReport, saved["report_id"]) is not None and db.get(AnalysisRun, run_id) is not None


def test_unknown_and_invalid_requests(client, db, run_id):
    assert client.post("/api/saved-analyses", json={"analysis_id": "does-not-exist"}).status_code == 404
    assert client.post("/api/saved-analyses", json={"analysis_id": "bad id!"}).status_code == 422
    assert client.post("/api/saved-analyses", json={"analysis_id": run_id, "extra": 1}).status_code == 422
    run = db.get(AnalysisRun, run_id)
    run.status = "RUNNING"
    db.commit()
    assert client.post("/api/saved-analyses", json={"analysis_id": run_id}).status_code == 422
