"""Lineage on the test database with synthetic persisted events (no LLM, no market data)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import func, select

from app.models import EventImpact, EventLink, EventNode, GraphNode, ImpactPath, Relationship
from app.services.lineage import scoring as S
from app.services.lineage.linker import LineageService
from app.services.lineage.query import lineage_view
from tests.lineage_fixtures import A_PATHS, B_PATHS, C_PATHS, lineage_test_config, make_event

CFG = lineage_test_config()
NOISE = [(["variable:us_bank_nim", "asset:jpm"], 0.5)]
AS_OF = datetime(2026, 3, 1, tzinfo=timezone.utc)


def svc(db, kb, cfg=CFG):
    return LineageService(db, kb, cfg)


def link(db, kb, *events, cfg=CFG):
    out = [svc(db, kb, cfg).link_event(e.id) for e in events]
    db.commit()
    return out


def active_links(db, child_id=None):
    stmt = select(EventLink).where(EventLink.is_active.is_(True))
    if child_id:
        stmt = stmt.where(EventLink.child_event_id == child_id)
    return db.scalars(stmt).all()


@pytest.fixture
def chain(db, kb):
    noise = make_event(db, kb, "Bank margins", date(2026, 1, 2), NOISE, event_type="BANKING_CREDIT")
    a = make_event(db, kb, "OPEC cut", date(2026, 1, 5), A_PATHS)
    b = make_event(db, kb, "India oil import bill", date(2026, 1, 10), B_PATHS, event_type="COMMODITY_PRICE_CHANGE")
    c = make_event(db, kb, "Rupee and OMC pressure", date(2026, 1, 14), C_PATHS, event_type="CURRENCY_MARKET")
    link(db, kb, noise, a, b, c)
    return a, b, c


def view(db, kb, event, **kw):
    params = dict(direction="ancestors", min_strength=0.1, max_depth=6, as_of=AS_OF, include_expired=True) | kw
    return lineage_view(db, event, kb, CFG, **params)


def test_nodes_roles_weights_and_impact_materialised(db, kb, chain):
    _, b, _ = chain
    rows = {r.node_id: r for r in db.scalars(select(EventNode).where(EventNode.event_id == b.id))}
    assert rows["variable:global_oil_supply"].role == "trigger"
    assert rows["variable:india_oil_import_bill"].role == "trigger"  # first hop of B's third path
    assert rows["variable:oil_supply_risk_premium"].role == "intermediate"
    assert rows["asset:hpcl_ns"].role == "asset" and rows["asset:hpcl_ns"].weight == 1.0
    assert rows["variable:india_omc_marketing_margins"].weight == pytest.approx(0.5 / 0.6, abs=1e-6)
    assert all(not n.startswith("event:") for n in rows)
    imp = db.get(EventImpact, (b.id, b.latest_analysis_id))
    assert imp.impact == pytest.approx(min(1, (0.6 + 0.55 + 0.5) / 3 / 0.6), abs=1e-6)
    assert imp.half_life_days == pytest.approx(21 * (1 + imp.impact), abs=1e-5)


def test_chain_links_with_explanations(db, kb, chain):
    a, b, c = chain
    lb, lc = active_links(db, b.id), active_links(db, c.id)
    assert [(l.parent_event_id, l.link_type, l.is_primary) for l in lb] == [(a.id, "PARENT", True)]
    assert [(l.parent_event_id, l.link_type, l.is_primary) for l in lc] == [(b.id, "PARENT", True)]
    for l in lb + lc:
        assert l.shared_nodes and all({"node_id", "contribution", "idf", "informative"} <= set(x) for x in l.shared_nodes)
        assert l.effective_strength == pytest.approx(l.score * 2 ** (-l.gap_days / db.get(
            EventImpact, (l.parent_event_id, l.parent_analysis_run_id)).half_life_days), abs=1e-5)
        assert l.method_version and l.config_hash == CFG.config_hash and l.knowledge_base_version == kb.version


def test_lineage_view_ancestors_product_and_root(db, kb, chain):
    a, b, c = chain
    v = view(db, kb, c)
    assert v["status"] == "ok"
    ev = {e["id"]: e for e in v["events"]}
    assert set(ev) == {a.id, b.id, c.id}
    s_cb = next(l["effective_strength"] for l in v["links"] if l["child_id"] == c.id)
    s_ba = next(l["effective_strength"] for l in v["links"] if l["child_id"] == b.id)
    assert ev[a.id]["path_strength"] == pytest.approx(s_cb * s_ba, abs=1e-6) and ev[a.id]["depth"] == 2
    assert ev[a.id]["is_root"] and not ev[c.id]["is_root"]
    # depth and strength limits
    assert {e["id"] for e in view(db, kb, c, max_depth=1)["events"]} == {b.id, c.id}
    assert {e["id"] for e in view(db, kb, c, min_strength=s_cb * s_ba + 1e-3)["events"]} == {b.id, c.id}


def test_merged_graph_dedup_bridges_and_cytoscape_shape(db, kb, chain):
    _, b, c = chain
    g = view(db, kb, c)["graph"]
    assert set(g) == {"elements"} and set(g["elements"]) == {"nodes", "edges"}
    nodes = {n["data"]["id"]: n["data"] for n in g["elements"]["nodes"]}
    assert len(nodes) == len(g["elements"]["nodes"])  # deduplicated
    bill = nodes["variable:india_oil_import_bill"]
    assert bill["is_bridge"] and set(bill["contributing_event_ids"]) >= {b.id, c.id} and 0 < bill["glow"] < 1
    edge_ids = [e["data"]["id"] for e in g["elements"]["edges"]]
    assert len(edge_ids) == len(set(edge_ids))
    shared_edge = next(e["data"] for e in g["elements"]["edges"]
                       if e["data"]["source"] == "variable:india_oil_import_bill"
                       and e["data"]["target"] == "variable:india_omc_marketing_margins")
    assert set(shared_edge["contributing_event_ids"]) == {b.id, c.id} and not shared_edge["direction_conflict"]
    assert any(e["data"]["kind"] == "lineage" for e in g["elements"]["edges"])
    assert all(e["data"]["source"] in nodes and e["data"]["target"] in nodes for e in g["elements"]["edges"])


def test_direction_conflict_detected_not_summed(db, kb):
    noise = make_event(db, kb, "Noise", date(2026, 1, 1), NOISE, event_type="BANKING_CREDIT")
    edge = ("variable:oil_supply_risk_premium", "variable:india_oil_import_bill")
    p = [(["variable:global_oil_supply", "variable:oil_supply_risk_premium", "variable:india_oil_import_bill",
           "asset:hpcl_ns"], 0.6)]
    a = make_event(db, kb, "Up", date(2026, 1, 5), p)
    b = make_event(db, kb, "Down", date(2026, 1, 9), p, directions={edge: "NEGATIVE"})
    link(db, kb, noise, a, b)
    e = next(x["data"] for x in view(db, kb, b)["graph"]["elements"]["edges"]
             if (x["data"]["source"], x["data"]["target"]) == edge)
    assert e["direction_conflict"] and e["direction"] is None
    assert set(e["direction_conflict_detail"]) == {"POSITIVE", "NEGATIVE"}
    assert e["thickness"] == max(e["thickness_by_direction"].values())


def test_rerun_is_idempotent(db, kb, chain):
    a, b, c = chain
    before = db.scalar(select(func.count()).select_from(EventLink))
    link(db, kb, a, b, c)
    link(db, kb, c)
    assert db.scalar(select(func.count()).select_from(EventLink)) == before
    assert len(active_links(db, c.id)) == 1


def test_reanalysis_supersedes_old_links(db, kb, chain):
    a, b, c = chain
    old_run = c.latest_analysis_id
    make_event(db, kb, "", date(2026, 1, 14), A_PATHS, event=c)  # new run with A's mechanism
    link(db, kb, c)
    act = active_links(db, c.id)
    assert act and all(l.analysis_run_id == c.latest_analysis_id for l in act)
    old = db.scalars(select(EventLink).where(EventLink.analysis_run_id == old_run)).all()
    assert old and not any(l.is_active for l in old)  # kept for history, inactive
    pairs = [(l.child_event_id, l.parent_event_id) for l in active_links(db)]
    assert len(pairs) == len(set(pairs))


def test_out_of_order_event_triggers_reevaluation(db, kb):
    noise = make_event(db, kb, "Noise", date(2026, 1, 1), NOISE, event_type="BANKING_CREDIT")
    a = make_event(db, kb, "OPEC cut", date(2026, 1, 5), A_PATHS)
    c = make_event(db, kb, "Rupee", date(2026, 1, 14), C_PATHS, event_type="CURRENCY_MARKET")
    link(db, kb, noise, a, c)
    assert not [l for l in active_links(db, c.id) if l.link_type == "PARENT"]
    b = make_event(db, kb, "Import bill (reported late)", date(2026, 1, 10), B_PATHS, event_type="COMMODITY_PRICE_CHANGE")
    report = link(db, kb, b)[0]
    assert c.id in report.reevaluated
    assert [l.parent_event_id for l in active_links(db, c.id) if l.link_type == "PARENT"] == [b.id]


def test_simulated_events_and_runs_excluded(db, kb, chain):
    a, _, _ = chain
    sim = make_event(db, kb, "Simulated twin", date(2026, 1, 6), A_PATHS, simulated=True)
    r = link(db, kb, sim)[0]
    assert r.status == "skipped" and "simulated" in r.reason
    assert not db.scalars(select(EventLink).where(EventLink.parent_event_id == sim.id)).all()
    v = view(db, kb, sim)
    assert v["status"] == "unavailable" and "simulated" in v["reason"]
    mock_run = make_event(db, kb, "Mock-analysed", date(2026, 1, 7), A_PATHS, mode="SIMULATED")
    assert svc(db, kb, lineage_test_config(**{"eligibility.exclude_simulated_runs": True})).link_event(
        mock_run.id).status == "skipped"


def test_missing_path_weights_are_explicit(db, kb):
    e = make_event(db, kb, "No paths", date(2026, 1, 5), [], extra_nodes=("variable:global_oil_supply", "country:india"))
    link(db, kb, e)
    rows = db.scalars(select(EventNode).where(EventNode.event_id == e.id)).all()
    assert rows and all(r.weight is None and r.role == "context" for r in rows)
    imp = db.get(EventImpact, (e.id, e.latest_analysis_id))
    assert imp.impact == 0.0 and imp.details["impact_status"] == "NO_SCORED_PATHS"
    assert view(db, kb, e)["status"] == "no_related_events"


def test_as_of_reproduces_historical_view(db, kb, chain):
    a, b, c = chain
    early = datetime(2026, 1, 12, tzinfo=timezone.utc)
    assert view(db, kb, c, as_of=early)["status"] == "unavailable"
    d = view(db, kb, b, direction="descendants", as_of=early)
    assert c.id not in {e["id"] for e in d["events"]}
    d2 = view(db, kb, b, direction="descendants", as_of=AS_OF)
    assert c.id in {e["id"] for e in d2["events"]}
    r1, r2 = view(db, kb, c, as_of=AS_OF), view(db, kb, c, as_of=AS_OF)
    assert [(e["id"], e["relevance"]) for e in r1["events"]] == [(e["id"], e["relevance"]) for e in r2["events"]]


def test_expired_events_remain_viewable(db, kb, chain):
    a, b, c = chain
    far = datetime(2027, 6, 1, tzinfo=timezone.utc)
    v = view(db, kb, c, as_of=far)
    ev = {e["id"]: e for e in v["events"]}
    assert ev[a.id]["state"] == "expired" and a.id in ev  # still returned with include_expired=True
    v2 = view(db, kb, c, as_of=far, include_expired=False)
    assert {e["id"] for e in v2["events"]} == {c.id}


def test_original_graphs_unchanged(db, kb):
    a = make_event(db, kb, "OPEC cut", date(2026, 1, 5), A_PATHS)
    b = make_event(db, kb, "Import bill", date(2026, 1, 10), B_PATHS)

    def snapshot():
        return (sorted((n.analysis_run_id, n.node_id, n.label) for n in db.scalars(select(GraphNode))),
                sorted((r.id, r.score, r.direction) for r in db.scalars(select(Relationship))),
                sorted((p.id, p.path_score) for p in db.scalars(select(ImpactPath))))
    before = snapshot()
    link(db, kb, a, b)
    view(db, kb, b)
    assert snapshot() == before


def test_identical_events_without_other_corpus_do_not_link(db, kb):
    """With only the two events materialised every shared node has IDF 0: no information -> no link."""
    a = make_event(db, kb, "OPEC cut (wire 1)", date(2026, 1, 5), A_PATHS)
    a2 = make_event(db, kb, "OPEC cut (wire 2)", date(2026, 1, 6), A_PATHS)
    r = link(db, kb, a, a2)[1]
    assert not active_links(db) and r.rejected == {"no_informative_shared_node": 1}


def test_duplicate_link_not_in_parent_chain(db, kb):
    noise = make_event(db, kb, "Noise", date(2026, 1, 1), NOISE, event_type="BANKING_CREDIT")
    a = make_event(db, kb, "OPEC cut (wire 1)", date(2026, 1, 5), A_PATHS)
    a2 = make_event(db, kb, "OPEC cut (wire 2)", date(2026, 1, 6), A_PATHS)
    link(db, kb, noise, a, a2)
    ls = active_links(db, a2.id)
    assert [(l.parent_event_id, l.link_type) for l in ls] == [(a.id, S.DUPLICATE)]
    v = view(db, kb, a2)
    assert v["status"] == "ok" and not [e for e in v["events"] if e["relation"] == "ancestor"]
    assert [l["link_type"] for l in v["links"]] == ["DUPLICATE"]
