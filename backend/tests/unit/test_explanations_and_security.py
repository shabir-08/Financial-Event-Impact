import logging

from app.core.logging import RedactingFilter
from app.schemas.llm import AssetExplanation, Explanation, MechanismExplanation
from app.services.explanations.validation import sanitize, validate_explanation

PACKAGE = {
    "articles": [{"ref": "A1"}], "passages": [{"ref": "P1", "text": "Brent crude jumped 8%"}],
    "relationships": [{"ref": "R1"}, {"ref": "R2"}],
    "candidate_paths": [{"ref": "PATH1"}],
    "candidate_assets": [{"asset_id": "asset:usdinr"}],
    "market_observations": [{"ref": "M1", "windows": [{"return_pct": 1.2345}]}],
}


def expl(**kw) -> Explanation:
    base = dict(
        event_summary="Brent crude jumped 8% (P1).", financial_relevance="High.", direct_entities=["OPEC+"],
        mechanisms=[MechanismExplanation(path_ref="PATH1", explanation="Oil -> rupee", evidence_refs=["R1", "P1"],
                                         status_note="R1 reported, rest inferred")],
        affected_assets=[AssetExplanation(asset_ref="asset:usdinr", explanation="x", direction_statement="potential upward pressure",
                                          evidence_refs=["PATH1", "M1"])],
        historical_context="USD/INR moved 1.23% in the window (M1); not causal.",
        reported_vs_inferred="r", uncertainties=["u"], missing_data=[], limitations="l")
    base.update(kw)
    return Explanation(**base)


def test_valid_explanation_passes():
    r = validate_explanation(expl(), PACKAGE)
    assert r.valid, r.issues


def test_invented_reference_rejected_and_sanitised():
    bad = expl(mechanisms=[MechanismExplanation(path_ref="PATH9", explanation="x", evidence_refs=["R1"], status_note="")],
               affected_assets=[AssetExplanation(asset_ref="asset:aapl", explanation="x", direction_statement="d",
                                                 evidence_refs=["R77"])])
    r = validate_explanation(bad, PACKAGE)
    assert not r.valid and {"PATH9", "asset:aapl", "R77"} <= r.invalid_refs
    cleaned = sanitize(bad, r)
    assert cleaned.mechanisms == [] and cleaned.affected_assets == []
    assert validate_explanation(cleaned, PACKAGE).valid


def test_fabricated_percentage_rejected():
    r = validate_explanation(expl(historical_context="Airline stocks historically fall 14.7% after such shocks."), PACKAGE)
    assert not r.valid and r.unsupported_numbers == ["14.7%"]


def test_overconfident_language_rejected():
    r = validate_explanation(expl(limitations="The rupee will definitely weaken."), PACKAGE)
    assert not r.valid


def test_log_redaction():
    f = RedactingFilter(["sk-ant-supersecret", "finnhubkey123"])
    rec = logging.LogRecord("x", logging.INFO, "f", 1, "calling %s with token=%s apikey=abc",
                            ("https://x?token=finnhubkey123", "sk-ant-supersecret"), None)
    f.filter(rec)
    msg = rec.getMessage()
    assert "supersecret" not in msg and "finnhubkey123" not in msg and "abc" not in msg


def test_compact_package_respects_budget_and_declares_trims():
    import json

    from app.services.explanations.evidence_package import compact_for_llm
    from app.services.explanations.validation import package_refs

    path = lambda i: {"ref": f"PATH{i}", "rank": i, "target_asset": f"asset:a{i % 10}", "node_ids": ["event:x", "v", f"asset:a{i % 10}"],  # noqa: E731
                      "node_labels": ["A very long event title " * 3, "Crude oil price", f"Asset {i}"], "relationship_refs": [f"R{i}"],
                      "edge_statuses": ["INFERRED"], "path_score": 0.5, "impact_direction": "POTENTIAL_UPWARD_PRESSURE", "uncertainties": []}
    big = {
        "package_version": 12, "analysis_id": "a", "mode": "LIVE",
        "event": {"id": "e", "title": "t", "summary": "s" * 2000, "reported_figures": [], "relevance_rationale": "r"},
        "articles": [{"ref": "A1", "headline": "h", "source_name": "s", "published_at": None, "is_simulated": False}],
        "passages": [{"ref": "P1", "article_ref": "A1", "text": "p" * 900, "verified_verbatim": True}],
        "entities": [{"node_id": f"n{i}", "name": f"Entity {i}", "type": "COMPANY", "origin": "INFERRED",
                      "normalization_status": "RESOLVED", "mention": f"m{i}"} for i in range(300)],
        "relationships": [{"ref": f"R{i}", "source_label": "a", "target_label": "b", "relationship_type": "INCREASES", "direction": "POSITIVE",
                           "status": "INFERRED", "mechanism": "m" * 400, "score": 0.5, "evidence": []} for i in range(40)],
        "candidate_paths": [path(i) for i in range(40)],
        "candidate_assets": [{"asset_id": f"asset:a{i}", "name": f"A{i}", "impact_direction": "X", "best_path_score": 0.5,
                              "path_refs": ["PATH1"], "market_data_status": "AVAILABLE", "historical_status": None} for i in range(12)],
        "market_observations": [{"ref": f"M{i}", "asset_id": f"asset:a{i % 12}", "kind": "HISTORICAL_EVENT", "status": "AVAILABLE",
                                 "windows": [{"window_trading_days": 5, "return_pct": 1.234, "status": "AVAILABLE"}]} for i in range(60)],
        "missing_data": [], "known_limitations": [],
    }
    c = compact_for_llm(big, token_budget=3000)
    assert len(json.dumps(c, default=str)) // 3 <= 3000
    assert c["trimmed_for_size"]["omitted"]  # the model is told what was left out
    assert package_refs(c) <= package_refs(big)  # no new reference ids appear
    small = compact_for_llm({**big, "entities": [], "candidate_paths": big["candidate_paths"][:2], "relationships": big["relationships"][:2],
                             "market_observations": [], "candidate_assets": big["candidate_assets"][:2]}, token_budget=3000)
    assert "trimmed_for_size" not in small
