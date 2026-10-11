"""Pure lineage math: similarity, gates, decay, reinforcement, strongest paths (no database)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.services.lineage import scoring as S
from app.services.lineage.config import config_from_dict, load_lineage_config
from tests.lineage_fixtures import lineage_test_config

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
CFG = lineage_test_config()


def prof(eid: str, day: float, nodes: dict[str, tuple[str, float | None]], *, impact=1.0, hl: float | None = 42.0,
         category="ENERGY_SUPPLY") -> S.EventProfile:
    return S.EventProfile(eid, f"run-{eid}", T0 + timedelta(days=day), None, category, impact, hl,
                          {k: S.NodeRec(k, k, "ECONOMIC_VARIABLE", r, w) for k, (r, w) in nodes.items()}, eid)


OIL = {"variable:opec_production": ("trigger", 1.0), "variable:global_oil_supply": ("intermediate", 1.0),
       "variable:oil_supply_risk_premium": ("intermediate", 0.9), "asset:ongc_ns": ("asset", 1.0)}
OIL2 = {"variable:global_oil_supply": ("trigger", 1.0), "variable:oil_supply_risk_premium": ("intermediate", 1.0),
        "variable:opec_production": ("intermediate", 0.8), "variable:india_oil_import_bill": ("intermediate", 0.8),
        "asset:hpcl_ns": ("asset", 1.0)}
UNRELATED = {"variable:us_bank_nim": ("trigger", 1.0), "asset:jpm": ("asset", 1.0)}


def corpus_idf(*profiles):
    n, df = S.document_frequencies(profiles)
    return {k: S.idf(n, v) for k, v in df.items()}, n < CFG.similarity.cold_start_min_events


def run(child, parent, *others, live=True, cfg=CFG):
    idf_map, cold = corpus_idf(child, parent, *others)
    return S.decide(child, parent, S.compare(child, parent, idf_map, cfg, cold), live, cfg)


def test_idf_formula():
    assert S.idf(9, 2) == pytest.approx(math.log(10 / 3))
    assert S.idf(5, 5) == 0.0  # present everywhere -> carries no information


def test_meaningful_shared_drivers_link():
    a, b = prof("a", 0, OIL), prof("b", 5, OIL2)
    d = run(b, a, prof("x", 1, UNRELATED))
    assert d.link_type == S.PARENT and d.score >= CFG.similarity.min_similarity
    assert d.comparison.informative_count >= 1
    assert {x["node_id"] for x in d.comparison.shared} == {
        "variable:global_oil_supply", "variable:oil_supply_risk_premium", "variable:opec_production"}
    assert d.effective_strength == pytest.approx(d.score * 2 ** (-5 / 42), abs=1e-6)


def test_hub_only_overlap_never_links():
    hubs = {"variable:inr_value": ("intermediate", 1.0), "asset:usdinr": ("asset", 1.0),
            "commodity:crude_oil": ("trigger", 1.0), "institution:rbi": ("trigger", 1.0)}
    a = prof("a", 0, {**hubs, "variable:us_bank_nim": ("trigger", 1.0)})
    b = prof("b", 3, {**hubs, "variable:gold_price": ("trigger", 1.0)})
    for cold_threshold in (0, 1000):  # with and without cold start
        cfg = lineage_test_config(**{"similarity.cold_start_min_events": cold_threshold})
        d = run(b, a, prof("x", 1, UNRELATED), cfg=cfg)
        assert d.link_type is None and d.reason in ("no_informative_shared_node", "below_min_similarity")
        assert d.comparison.informative_count == 0


def test_terminal_asset_only_overlap_never_links():
    a = prof("a", 0, {"variable:us_bank_nim": ("trigger", 1.0), "asset:hpcl_ns": ("asset", 1.0), "asset:bpcl_ns": ("asset", 1.0)})
    b = prof("b", 2, {"variable:gold_price": ("trigger", 1.0), "asset:hpcl_ns": ("asset", 1.0), "asset:bpcl_ns": ("asset", 1.0)})
    d = run(b, a, prof("x", 1, UNRELATED))
    assert d.link_type is None and d.reason == "no_informative_shared_node"


def test_similarity_deterministic_and_contributions_sum_to_score():
    a, b, x = prof("a", 0, OIL), prof("b", 5, OIL2), prof("x", 1, UNRELATED)
    idf_map, cold = corpus_idf(a, b, x)
    c1, c2 = S.compare(b, a, idf_map, CFG, cold), S.compare(b, a, dict(reversed(list(idf_map.items()))), CFG, cold)
    assert c1.score == c2.score and c1.shared == c2.shared
    assert sum(x["contribution"] for x in c1.shared) == pytest.approx(c1.score, abs=1e-5)


def test_future_and_self_never_parents():
    a, b = prof("a", 0, OIL), prof("b", 5, OIL2)
    assert run(a, b).reason == "not_earlier"  # b is later than a
    same_time = prof("z", 0, OIL2)
    # equal event times fall back to first_reported_at, then the id: "z" sorts after "a", so it is later
    assert S.decide(a, same_time, S.compare(a, same_time, {}, CFG, True), True, CFG).reason == "not_earlier"
    assert S.decide(a, a, S.compare(a, a, {}, CFG, True), True, CFG).reason == "self"


def test_ordering_key_is_total_and_acyclic():
    a, b = prof("a", 0, OIL), prof("b", 0, OIL)
    assert (a.key < b.key) != (b.key < a.key)  # exactly one direction possible -> no cycles


def test_max_parents_and_primary_selection():
    child = prof("c", 10, OIL2)
    parents = [prof(f"p{i}", i, OIL2) for i in range(5)]
    idf_map, cold = corpus_idf(child, *parents, prof("x", 1, UNRELATED))
    ds = [S.decide(child, p, S.compare(child, p, idf_map, CFG, cold), True, CFG) for p in parents]
    kept = S.select_parents(ds, CFG)
    assert len(kept) == CFG.similarity.max_parent_links
    assert kept[0].is_primary and not any(d.is_primary for d in kept[1:])
    assert kept[0].effective_strength == max(d.effective_strength for d in ds if d.effective_strength)
    assert [d.parent_id for d in kept] == ["p4", "p3", "p2"]  # same similarity: the most recent decays least
    assert sum(1 for d in ds if d.reason == "exceeds_max_parent_links") == 2


def test_duplicate_is_not_a_parent():
    a, b = prof("a", 0, OIL), prof("b", 1, OIL)  # identical content one day apart
    d = run(b, a, prof("x", 1, UNRELATED))
    assert d.link_type == S.DUPLICATE and S.select_parents([d], CFG) == []


def test_analogue_when_parent_expired_and_not_in_chain():
    same_mechanism = {**{k: v for k, v in OIL.items() if k != "asset:ongc_ns"}, "asset:hpcl_ns": ("asset", 1.0)}
    a, b = prof("a", 0, OIL), prof("b", 400, same_mechanism)
    d = run(b, a, prof("x", 1, UNRELATED), live=False)
    assert d.score >= CFG.analogue.min_similarity and d.link_type == S.ANALOGUE and d.effective_strength is None
    assert S.select_parents([d], CFG) == []
    weak = run(b, a, prof("x", 1, UNRELATED), live=False,
               cfg=lineage_test_config(**{"analogue.min_similarity": 0.99}))
    assert weak.link_type is None and weak.reason == "parent_not_live"


def test_effective_strength_and_invalid_half_life():
    assert S.effective_strength(0.8, 21, 21) == pytest.approx(0.4)
    for bad in (None, 0, -3, float("nan")):
        assert S.effective_strength(0.8, 5, bad) is None


def test_impact_half_life_and_missing_paths():
    assert S.impact_score([], CFG) == 0.0
    assert S.impact_score([0.6, 0.3, 0.9, 0.1], CFG) == pytest.approx(min(1.0, (0.9 + 0.6 + 0.3) / 3 / 0.6))
    assert S.half_life("ENERGY_SUPPLY", 0.5, CFG) == pytest.approx(21 * 1.5)
    assert S.half_life("NOT_A_CATEGORY", 0.5, CFG) is None


def test_relevance_decay_and_expiry():
    t = T0 + timedelta(days=10)
    assert S.relevance(0.8, 10, T0, t) == pytest.approx(0.4)
    assert S.is_live(0.8, 10, T0, t, CFG)
    assert not S.is_live(0.8, 10, T0, T0 + timedelta(days=50), CFG)   # relevance 0.025 < 0.05
    assert not S.is_live(1.0, 10, T0, T0 + timedelta(days=41), CFG) or S.relevance(1.0, 10, T0, T0 + timedelta(days=41)) >= 0.05
    assert S.relevance(0.8, None, T0, t) is None and not S.is_live(0.8, None, T0, t, CFG)


def test_lifetime_cap_applies_even_with_high_relevance():
    cfg = lineage_test_config(**{"relevance.expiry_epsilon": 0.001})
    assert not S.is_live(1.0, 10, T0, T0 + timedelta(days=41), cfg)  # age > 4 * HL
    assert S.is_live(1.0, 10, T0, T0 + timedelta(days=39), cfg)


def test_reinforcement_deterministic_and_bounded_by_as_of():
    links = [(T0 + timedelta(days=10), 0.5), (T0 + timedelta(days=20), 0.5)]
    a1 = S.reinforced_anchor(T0, links, T0 + timedelta(days=30))
    a2 = S.reinforced_anchor(T0, list(reversed(links)), T0 + timedelta(days=30))
    assert a1 == a2 == T0 + timedelta(days=12.5)  # 0 -> 5 -> 5 + 0.5*(20-5)
    assert S.reinforced_anchor(T0, links, T0 + timedelta(days=15)) == T0 + timedelta(days=5)  # child after as_of ignored
    assert S.reinforced_anchor(T0, [], T0 + timedelta(days=99)) == T0


def test_path_strength_is_a_product_with_depth_and_strength_limits():
    edges = {"f": [("p1", 0.5), ("p2", 0.3)], "p1": [("g", 0.5)], "p2": [("g", 0.9)], "g": [("h", 0.9)]}
    best = S.strongest_paths("f", edges, min_strength=0.1, max_depth=6)
    assert best["g"].strength == pytest.approx(0.27) and best["g"].via == ["p2", "g"]  # 0.3*0.9 > 0.5*0.5
    assert best["h"].strength == pytest.approx(0.243) and best["h"].depth == 3
    assert "h" not in S.strongest_paths("f", edges, min_strength=0.1, max_depth=2)
    assert "h" not in S.strongest_paths("f", edges, min_strength=0.25, max_depth=6)
    assert S.strongest_paths("f", {"f": [("z", 0.0)]}, min_strength=0.0, max_depth=3) == {}


def test_config_hash_is_stable_and_sensitive():
    a, b = load_lineage_config(), load_lineage_config()
    assert a.config_hash == b.config_hash and len(a.config_hash) == 16
    assert lineage_test_config(**{"similarity.min_similarity": 0.3}).config_hash != lineage_test_config().config_hash
    with pytest.raises(ValueError):
        config_from_dict({**a.model_dump(), "similarity": {**a.similarity.model_dump(), "role_weights": {"trigger": 1}}})
