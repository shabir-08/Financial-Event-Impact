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
