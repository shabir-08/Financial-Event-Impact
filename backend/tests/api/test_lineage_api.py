"""GET /api/events/{event_id}/lineage: validation, statuses and response shape."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database.session import get_db
from app.main import create_app
from app.models import Event
from app.schemas.lineage import LineageResponse
from app.services.lineage.linker import LineageService
from tests.lineage_fixtures import A_PATHS, B_PATHS, lineage_test_config, make_event

NOISE = [(["variable:us_bank_nim", "asset:jpm"], 0.5)]


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
        yield c


@pytest.fixture
def linked(db, kb):
    events = [make_event(db, kb, "Noise", date(2026, 1, 2), NOISE, event_type="BANKING_CREDIT"),
              make_event(db, kb, "OPEC cut", date(2026, 1, 5), A_PATHS),
              make_event(db, kb, "India oil import bill", date(2026, 1, 10), B_PATHS)]
    svc = LineageService(db, kb, lineage_test_config())
    for e in events:
        svc.link_event(e.id)
    db.commit()
    return events


def test_unknown_event_is_404(client):
    assert client.get("/api/events/nope/lineage").status_code == 404


@pytest.mark.parametrize("query", ["min_strength=-0.1", "min_strength=2", "max_depth=0", "max_depth=99",
                                   "as_of=not-a-date", "direction=sideways", "include_expired=maybe"])
def test_invalid_parameters_are_422(client, linked, query):
    r = client.get(f"/api/events/{linked[2].id}/lineage?{query}")
    assert r.status_code == 422, r.text


def test_ok_response_shape(client, linked):
    _, a, b = linked
    r = client.get(f"/api/events/{b.id}/lineage", params={"as_of": "2026-02-01T00:00:00Z"})
    assert r.status_code == 200, r.text
    body = r.json()
    LineageResponse.model_validate(body)
    assert body["status"] == "ok" and body["reason"] is None
    assert set(body["graph"]) == {"elements"} and set(body["graph"]["elements"]) == {"nodes", "edges"}
    assert all("data" in n and "id" in n["data"] for n in body["graph"]["elements"]["nodes"])
    assert {e["id"] for e in body["events"]} == {a.id, b.id}
    link = body["links"][0]
    assert link["link_type"] == "PARENT" and link["shared_nodes"] and link["is_primary"]
    assert any("causation" in d for d in body["disclaimers"])
    assert body["parameters"] == {"direction": "ancestors", "min_strength": 0.1, "max_depth": 6,
                                  "include_expired": True}
    assert body["versions"]["method"] and body["versions"]["config_hash"]


def test_descendants_direction(client, linked):
    _, a, b = linked
    body = client.get(f"/api/events/{a.id}/lineage", params={"direction": "descendants",
                                                              "as_of": "2026-02-01T00:00:00"}).json()
    assert {e["id"]: e["relation"] for e in body["events"]} == {a.id: "focus", b.id: "descendant"}


def test_no_related_events(client, linked):
    noise = linked[0]
    body = client.get(f"/api/events/{noise.id}/lineage").json()
    assert body["status"] == "no_related_events" and body["events"] == [] or \
        [e["id"] for e in body["events"]] == [noise.id]
    assert body["status"] == "no_related_events" and body["reason"]


def test_missing_analysis_is_unavailable_not_demo(client, db):
    ev = Event(event_type="OTHER", title="Unanalysed", event_date=date(2026, 1, 1), extraction_version="t",
               llm_provider="t")
    db.add(ev)
    db.commit()
    body = client.get(f"/api/events/{ev.id}/lineage").json()
    assert body["status"] == "unavailable" and "no completed analysis" in body["reason"]
    assert body["events"] == [] and body["graph"]["elements"] == {"nodes": [], "edges": []}


def test_analysed_but_not_yet_computed_is_unavailable(client, db, kb):
    ev = make_event(db, kb, "Analysed, lineage not run", date(2026, 1, 3), A_PATHS)
    body = client.get(f"/api/events/{ev.id}/lineage").json()
    assert body["status"] == "unavailable" and "backfill" in body["reason"]
