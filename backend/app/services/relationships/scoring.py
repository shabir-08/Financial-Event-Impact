"""Transparent hybrid relationship scoring.

    base  = (w_c*C + w_e*E + w_r*R + w_h*H) / (w_c + w_e + w_r + w_h)
    score = A * base

C relationship confidence, E evidence strength, R economic relevance, H historical support,
A applicability to the current event - all on [0, 1].

* Missing historical support (H unavailable) is NOT scored as zero: H and its weight are dropped
  and the remaining weights are renormalised. ``historical_support_status`` records why.
* Weights are heuristic defaults (configurable via SCORE_WEIGHT_*), not empirically calibrated.
* The score ranks how well-supported a relationship is for this event. It is NOT a probability
  that any asset will rise or fall.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from app.core.config import ScoringWeights
from app.services.relationships.knowledge_base import KBRule, KnowledgeBase

FORMULA = "score = A * (w_c*C + w_e*E + w_r*R + w_h*H) / sum(w over available components)"

# Evidence strength for knowledge-base mechanisms, by evidence basis (no article evidence involved).
KB_EVIDENCE_BY_BASIS = {
    "INSTRUMENT_DEFINITION": 0.9,  # e.g. a USD/INR quote mechanically reflects the rupee's value
    "ESTABLISHED_MECHANISM": 0.6,
    "EMPIRICAL_ASSOCIATION": 0.5,
    "CONTESTED": 0.3,
}
TRIGGER_EVIDENCE = 0.5
UNVERIFIED_PASSAGE_CONFIDENCE_FACTOR = 0.5
UNVERIFIED_EVIDENCE = 0.2


def source_count_factor(n_sources: int) -> float:
    return 0.6 if n_sources <= 1 else 0.8 if n_sources == 2 else 0.9


@dataclass
class ScoreResult:
    confidence: float
    evidence_strength: float
    economic_relevance: float
    historical_support: float | None
    historical_support_status: str
    applicability: float
    score: float
    details: dict


def combine(
    *, confidence: float, evidence: float, relevance: float, historical: float | None,
    historical_status: str, applicability: float, weights: ScoringWeights, notes: dict | None = None,
) -> ScoreResult:
    comps = {"confidence": (weights.confidence, confidence), "evidence": (weights.evidence, evidence),
             "relevance": (weights.relevance, relevance)}
    if historical is not None:
        comps["historical"] = (weights.historical, historical)
    total_w = sum(w for w, _ in comps.values())
    base = sum(w * v for w, v in comps.values()) / total_w if total_w else 0.0
    score = round(applicability * base, 4)
    details = {
        "formula": FORMULA,
        "weights_configured": weights.model_dump(),
        "weights_effective": {k: round(w / total_w, 4) for k, (w, _) in comps.items()} if total_w else {},
        "missing_components": [] if historical is not None else ["historical"],
        "base_before_applicability": round(base, 4),
        "is_probability": False,
        "weights_are_heuristic": True,
        **(notes or {}),
    }
    return ScoreResult(round(confidence, 4), round(evidence, 4), round(relevance, 4),
                       None if historical is None else round(historical, 4), historical_status,
                       round(applicability, 4), score, details)


def score_kb_rule(rule: KBRule, applicability: float, weights: ScoringWeights,
                  historical: float | None = None, historical_status: str = "UNAVAILABLE") -> ScoreResult:
    return combine(
        confidence=rule.reliability, evidence=KB_EVIDENCE_BY_BASIS[rule.evidence_basis],
        relevance=rule.economic_relevance, historical=historical, historical_status=historical_status,
        applicability=applicability, weights=weights,
        notes={"evidence_source": "knowledge_base_rationale", "evidence_basis": rule.evidence_basis},
    )


def score_article_claims(
    *, confidences: list[float], verified: list[bool], source_domains: list[str | None],
    is_primary_effect: bool, kb: KnowledgeBase, weights: ScoringWeights,
) -> ScoreResult:
    """Score a REPORTED/UNVERIFIED edge supported by one or more article claims."""
    any_verified = any(verified)
    conf = max(c * (1.0 if v else UNVERIFIED_PASSAGE_CONFIDENCE_FACTOR) for c, v in zip(confidences, verified))
    verified_domains = {d or "(unknown)" for d, v in zip(source_domains, verified) if v}
    qualities, assessed = [], []
    for d in verified_domains:
        q, ok = kb.source_quality_for(None if d == "(unknown)" else d)
        qualities.append(q)
        assessed.append(ok)
    if any_verified:
        evidence = source_count_factor(len(verified_domains)) * (0.5 + 0.5 * mean(qualities))
    else:
        evidence = UNVERIFIED_EVIDENCE
    relevance = 1.0 if is_primary_effect else 0.8
    return combine(
        confidence=conf, evidence=evidence, relevance=relevance, historical=None,
        historical_status="NOT_APPLICABLE_REPORTED_EDGE", applicability=1.0, weights=weights,
        notes={"evidence_source": "article_passages", "n_supporting_sources": len(verified_domains),
               "source_quality_assessed": all(assessed) if assessed else False,
               "source_quality_values": [round(q, 2) for q in qualities]},
    )


def score_trigger(reliability: float, relevance: float, weights: ScoringWeights) -> ScoreResult:
    return combine(confidence=reliability, evidence=TRIGGER_EVIDENCE, relevance=relevance, historical=None,
                   historical_status="UNAVAILABLE", applicability=1.0, weights=weights,
                   notes={"evidence_source": "event_trigger_rule"})
