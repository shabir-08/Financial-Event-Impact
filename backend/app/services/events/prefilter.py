"""Stage 1 of event detection: cheap, transparent relevance heuristics (no LLM call)."""

from __future__ import annotations

from dataclasses import dataclass

from app.models import Article
from app.services.relationships.knowledge_base import KnowledgeBase

ACCEPTED_LANGUAGES = {None, "", "en", "english"}


@dataclass
class PrefilterResult:
    passed: bool
    score: float
    reason: str
    category_hints: list[str]


def prefilter_article(article: Article, kb: KnowledgeBase) -> PrefilterResult:
    lang = (article.language or "").strip().lower()
    if lang not in ACCEPTED_LANGUAGES:
        return PrefilterResult(False, 0.0, f"unsupported language: {article.language}", [])
    text = article.text_for_analysis.lower()
    head = article.headline.lower()
    if len(head) < 15:
        return PrefilterResult(False, 0.0, "headline too short to analyse", [])

    noise = [t for t in kb.categories["noise_terms"] if t in text]
    hits: dict[str, int] = {}
    for cat, meta in kb.categories["categories"].items():
        n = sum(1 for kw in meta["keywords"] if kw in text)
        if n:
            hits[cat] = n
    fin = sum(1 for t in kb.categories["financial_terms"] if t in text)
    score = sum(hits.values()) + 0.5 * fin - 2.0 * len(noise)
    hints = sorted(hits, key=lambda c: -hits[c])[:3]
    if noise and score < 3:
        return PrefilterResult(False, score, f"non-financial topic terms: {', '.join(noise)}", hints)
    if not hits and fin < 2:
        return PrefilterResult(False, score, "no financial event keywords and fewer than 2 financial terms", hints)
    return PrefilterResult(True, score, "passed keyword pre-filter", hints)
