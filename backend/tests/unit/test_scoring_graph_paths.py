import pytest

from app.core.config import ScoringWeights, Settings
from app.domain import EdgeStatus, ImpactDirection
from app.services.graph.builder import ClaimRecord, EventInput, GraphBuilder, MentionRecord
from app.services.graph.paths import PathAnalyzer
from app.services.relationships.applicability import EventContext, evaluate_rule, evaluate_trigger
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.relationships.scoring import combine, score_article_claims

W = ScoringWeights(confidence=0.3, evidence=0.3, relevance=0.25, historical=0.15)


def claim(cid, src, tgt, sign, verified=True, conf=0.85, primary=True, domain="reuters.com", art="a1"):
    return ClaimRecord(cid, art, src, tgt, src, tgt, "INCREASES" if sign > 0 else "REDUCES", sign, "m",
                       f"passage for {tgt}", verified, conf, primary, domain, None)


def oil_event(eid="e1", claims=None, mentions=None, etype="COMMODITY_PRICE_CHANGE"):
    return EventInput(eid, etype, "Oil shock", mentions or [MentionRecord("commodity:crude_oil", "Brent", "COMMODITY")],
                      claims if claims is not None else [claim("c1", "EVENT", "variable:crude_oil_price", 1)])


# -------------------------------------------------------------------- scoring
class TestScoring:
    def test_formula(self):
        r = combine(confidence=1, evidence=0.5, relevance=0.8, historical=0.2, historical_status="AVAILABLE",
                    applicability=1.0, weights=W)
        assert r.score == pytest.approx(0.3 * 1 + 0.3 * 0.5 + 0.25 * 0.8 + 0.15 * 0.2)
        assert r.details["is_probability"] is False and r.details["weights_are_heuristic"] is True

    def test_missing_historical_is_renormalised_not_zero(self):
        with_h0 = combine(confidence=1, evidence=1, relevance=1, historical=0.0, historical_status="AVAILABLE",
                          applicability=1, weights=W)
        missing = combine(confidence=1, evidence=1, relevance=1, historical=None, historical_status="UNAVAILABLE",
                          applicability=1, weights=W)
        assert missing.score == pytest.approx(1.0)  # not penalised as if H were 0
        assert with_h0.score == pytest.approx(0.85)
        assert missing.historical_support is None and missing.details["missing_components"] == ["historical"]

    def test_applicability_scales_score(self):
        a = combine(confidence=1, evidence=1, relevance=1, historical=None, historical_status="U", applicability=0.7, weights=W)
        assert a.score == pytest.approx(0.7)

    def test_unverified_claim_scores_lower(self, kb):
        v = score_article_claims(confidences=[0.9], verified=[True], source_domains=["reuters.com"],
                                 is_primary_effect=True, kb=kb, weights=W)
        u = score_article_claims(confidences=[0.9], verified=[False], source_domains=["reuters.com"],
                                 is_primary_effect=True, kb=kb, weights=W)
        assert u.score < v.score and u.evidence_strength == pytest.approx(0.2)

    def test_more_independent_sources_more_evidence(self, kb):
        one = score_article_claims(confidences=[0.9], verified=[True], source_domains=["reuters.com"],
                                   is_primary_effect=True, kb=kb, weights=W)
        two = score_article_claims(confidences=[0.9, 0.9], verified=[True, True],
                                   source_domains=["reuters.com", "livemint.com"], is_primary_effect=True, kb=kb, weights=W)
        assert two.evidence_strength > one.evidence_strength


# --------------------------------------------------------------- applicability
class TestApplicability:
    def test_hard_condition_excludes_rule(self, kb):
        rule = kb.rules["kb.geo.me_risk_to_israel_premium"]
        ctx = EventContext("WAR_CONFLICT", {"region:middle_east"})
        assert not evaluate_rule(rule, ctx).applicable
        assert evaluate_rule(rule, EventContext("WAR_CONFLICT", {"country:israel"})).applicable

    def test_soft_context_reduces_applicability(self, kb):
        rule = kb.rules["kb.energy.oil_to_india_import_bill"]
        assert evaluate_rule(rule, EventContext("X", set())).factor == pytest.approx(0.7)
        assert evaluate_rule(rule, EventContext("X", {"country:india"})).factor == 1.0

    def test_trigger_sign_from_primary_effect(self, kb):
        trig = next(t for t in kb.triggers if t.id == "kb.trigger.fed_decision")
        down = evaluate_trigger(trig, EventContext("INTEREST_RATE_CHANGE", {"institution:fed"},
                                                   {"variable:us_policy_rate": -1}))
        unknown = evaluate_trigger(trig, EventContext("INTEREST_RATE_CHANGE", {"institution:fed"}))
        assert down.applicable and down.sign == -1
        assert unknown.applicable and unknown.sign == 0


# ---------------------------------------------------------------------- graph
class TestGraphBuilder:
    def test_dynamic_graph_differs_per_event(self, kb):
        s = Settings(_env_file=None)
        oil = GraphBuilder(kb, s).build(oil_event())
        fed = GraphBuilder(kb, s).build(EventInput(
            "e2", "INTEREST_RATE_CHANGE", "Fed hike", [MentionRecord("institution:fed", "Fed", "INSTITUTION")],
            [claim("c9", "EVENT", "variable:us_policy_rate", 1)]))
        assert "asset:jets" in oil.nodes and "asset:jets" not in fed.nodes
        assert "asset:kbe" in fed.nodes and "asset:kbe" not in oil.nodes

    def test_statuses_and_unresolved_exclusion(self, kb):
        claims = [claim("c1", "EVENT", "variable:crude_oil_price", 1),
                  claim("c2", "EVENT", "variable:opec_production", -1, verified=False),
                  claim("c3", "EVENT", None, 1)]
        b = GraphBuilder(kb, Settings(_env_file=None)).build(oil_event(claims=claims))
        ev = b.event_node
        assert b.edges[(ev, "variable:crude_oil_price")].status == EdgeStatus.REPORTED
        assert b.edges[(ev, "variable:opec_production")].status == EdgeStatus.UNVERIFIED
        assert any(x["kind"] == "claim_unresolved_endpoint" for x in b.excluded)
        assert b.edges[("variable:crude_oil_price", "variable:jet_fuel_cost")].status == EdgeStatus.INFERRED

    def test_conflicting_directions_become_context_dependent(self, kb):
        claims = [claim("c1", "EVENT", "variable:crude_oil_price", 1, art="a1"),
                  claim("c2", "EVENT", "variable:crude_oil_price", -1, art="a2", domain="livemint.com")]
        b = GraphBuilder(kb, Settings(_env_file=None)).build(oil_event(claims=claims))
        e = b.edges[(b.event_node, "variable:crude_oil_price")]
        assert e.sign == 0 and e.conditions["conflicting_directions"] == [-1, 1]

    def test_involvement_edges_are_not_traversable(self, kb):
        mentions = [MentionRecord("company:interglobe_aviation", "IndiGo", "COMPANY")]
        b = GraphBuilder(kb, Settings(_env_file=None)).build(oil_event(claims=[], mentions=mentions))
        e = b.edges[(b.event_node, "company:interglobe_aviation")]
        assert not e.traversable
        assert PathAnalyzer(kb, Settings(_env_file=None)).analyze(b).paths == []  # mention alone != impact

    def test_rule_with_unmet_hard_condition_not_applied(self, kb):
        b = GraphBuilder(kb, Settings(_env_file=None)).build(EventInput(
            "e3", "WAR_CONFLICT", "Conflict", [MentionRecord("region:middle_east", "Middle East", "REGION")], []))
        assert "variable:middle_east_geopolitical_risk" in b.nodes  # via trigger
        assert "variable:israel_risk_premium" not in b.nodes
        assert any(x.get("rule_id") == "kb.geo.me_risk_to_israel_premium" for x in b.excluded)

    def test_node_limit_bounds_graph(self, kb):
        s = Settings(_env_file=None, graph_max_nodes=10)
        b = GraphBuilder(kb, s).build(oil_event())
        assert len(b.nodes) <= 10
        assert any(x["kind"] == "node_limit_reached" for x in b.excluded)


# ---------------------------------------------------------------------- paths
class TestPaths:
    def test_expected_chains_and_directions(self, kb):
        s = Settings(_env_file=None)
        pa = PathAnalyzer(kb, s).analyze(GraphBuilder(kb, s).build(oil_event()))
        by_asset = {a.asset_id: a for a in pa.assets}
        assert by_asset["asset:jets"].impact_direction == ImpactDirection.POTENTIAL_DOWNWARD_PRESSURE
        assert by_asset["asset:usdinr"].impact_direction == ImpactDirection.POTENTIAL_UPWARD_PRESSURE
        assert by_asset["asset:xom"].impact_direction == ImpactDirection.POTENTIAL_UPWARD_PRESSURE
        assert by_asset["asset:tlt"].impact_direction == ImpactDirection.POTENTIAL_DOWNWARD_PRESSURE
        chain = next(p for p in pa.paths if p.target == "asset:usdinr").nodes
        assert chain[1:] == ["variable:crude_oil_price", "variable:india_oil_import_bill",
                             "variable:india_current_account_deficit", "variable:inr_value", "asset:usdinr"]

    def test_ranking_sorted_and_bounded(self, kb):
        s = Settings(_env_file=None, path_max_total=5, path_max_per_asset=1)
        pa = PathAnalyzer(kb, s).analyze(GraphBuilder(kb, s).build(oil_event()))
        assert len(pa.paths) == 5
        scores = [p.score for p in pa.paths]
        assert scores == sorted(scores, reverse=True) and [p.rank for p in pa.paths] == [1, 2, 3, 4, 5]
        assert all(p.breakdown["is_probability"] is False for p in pa.paths)

    def test_depth_limit(self, kb):
        s = Settings(_env_file=None, path_max_depth=2)
        pa = PathAnalyzer(kb, s).analyze(GraphBuilder(kb, s).build(oil_event()))
        assert pa.paths and all(len(p.nodes) - 1 <= 2 for p in pa.paths)

    def test_cycle_avoidance(self, kb):
        # Add a cycle crude_oil_price -> opec_production -> global_oil_supply -> crude_oil_price
        from app.services.relationships.knowledge_base import KBRule

        rules = list(kb.rules.values()) + [KBRule(
            id="kb.test.cycle", source="variable:crude_oil_price", target="variable:opec_production",
            relationship_type="MAY_INCREASE", effect_sign=1, mechanism="test cycle", reliability=0.5,
            economic_relevance=0.5)]
        kb2 = KnowledgeBase([r for r in rules if r.kind == "RELATIONSHIP"], kb.triggers, list(kb.entities.values()),
                            list(kb.assets.values()), kb.historical_events, kb.categories, kb.source_quality, "t")
        s = Settings(_env_file=None)
        pa = PathAnalyzer(kb2, s).analyze(GraphBuilder(kb2, s).build(oil_event()))
        for p in pa.paths:
            assert len(p.nodes) == len(set(p.nodes))  # simple paths only

    def test_context_dependent_link_gives_uncertain_direction(self, kb):
        s = Settings(_env_file=None)
        pa = PathAnalyzer(kb, s).analyze(GraphBuilder(kb, s).build(oil_event()))
        rel = next(p for p in pa.paths if p.target == "asset:reliance_ns" and "variable:refining_margins" in p.nodes)
        assert rel.net_sign == 0 and rel.impact_direction == ImpactDirection.DIRECTION_UNCERTAIN
        assert rel.breakdown["direction_factor"] < 1

    def test_mixed_signals_detected(self, kb):
        s = Settings(_env_file=None)
        an = PathAnalyzer(kb, s)
        pa = an.analyze(GraphBuilder(kb, s).build(oil_event()))
        up = next(p for p in pa.paths if p.net_sign == 1)
        down = next(p for p in pa.paths if p.net_sign == -1)
        down.nodes = [*down.nodes[:-1], up.target]
        assets = an.aggregate_assets([up, down])
        assert assets[0].impact_direction == ImpactDirection.MIXED_SIGNALS
