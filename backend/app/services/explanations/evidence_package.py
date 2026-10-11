"""Assemble the structured evidence package handed to the explanation model.

Everything in the package comes from persisted records of one analysis run; the LLM sees no
other facts. Short reference ids (A*, P*, R*, PATH*, M*) let the explanation cite evidence and
let ``validation.validate_explanation`` check every citation.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AnalysisRun,
    Article,
    AssetImpact,
    Event,
    EventArticle,
    EventEntity,
    ImpactPath,
    MarketObservation,
    Relationship,
)
from app.schemas.llm import EXPLANATION_VERSION
from app.services.relationships.knowledge_base import KnowledgeBase

MAX_PATHS = 10
MAX_ASSETS = 12


def build_evidence_package(session: Session, run: AnalysisRun, kb: KnowledgeBase) -> dict[str, Any]:
    event = session.get(Event, run.event_id)
    articles = session.scalars(
        select(Article).join(EventArticle, EventArticle.article_id == Article.id)
        .where(EventArticle.event_id == event.id).order_by(Article.published_at)
    ).all()
    a_ref = {a.id: f"A{i}" for i, a in enumerate(articles, start=1)}

    paths = session.scalars(select(ImpactPath).where(ImpactPath.analysis_run_id == run.id)
                            .order_by(ImpactPath.rank).limit(MAX_PATHS)).all()
    path_rel_ids = {rid for p in paths for rid in p.relationship_ids}
    rels = session.scalars(
        select(Relationship).where(Relationship.analysis_run_id == run.id)
        .options(selectinload(Relationship.evidence))
    ).all()
    rels = [r for r in rels if r.id in path_rel_ids or (r.status in ("REPORTED", "UNVERIFIED")
                                                        and r.conditions.get("traversable", True))]
    passages: list[dict] = []
    p_index: dict[tuple[str | None, str], str] = {}
    r_ref: dict[str, str] = {}
    rel_items = []
    for i, r in enumerate(sorted(rels, key=lambda r: -r.score), start=1):
        r_ref[r.id] = f"R{i}"
        ev_refs = []
        for ev in r.evidence:
            if ev.evidence_type == "ARTICLE_PASSAGE" and ev.passage:
                key = (ev.article_id, ev.passage)
                if key not in p_index:
                    p_index[key] = f"P{len(p_index) + 1}"
                    passages.append({"ref": p_index[key], "article_ref": a_ref.get(ev.article_id),
                                     "text": ev.passage, "verified_verbatim": ev.verified})
                ev_refs.append(p_index[key])
            elif ev.reference:
                ev_refs.append(f"kb:{ev.reference}")
        rel_items.append({
            "ref": r_ref[r.id], "source": r.source_node_id, "source_label": kb.node_label(r.source_node_id),
            "target": r.target_node_id, "target_label": kb.node_label(r.target_node_id),
            "relationship_type": r.relationship_type, "direction": r.direction, "status": r.status,
            "origin": r.origin, "mechanism": r.mechanism, "score": r.score,
            "score_components": {"confidence": r.confidence, "evidence_strength": r.evidence_strength,
                                 "economic_relevance": r.economic_relevance,
                                 "historical_support": r.historical_support,
                                 "historical_support_status": r.historical_support_status,
                                 "applicability": r.applicability},
            "conditions_note": (r.conditions or {}).get("note"),
            "evidence": ev_refs,
        })

    for link in session.scalars(select(EventArticle).where(EventArticle.event_id == event.id)).all():
        for text in link.supporting_passages:
            key = (link.article_id, text)
            if key not in p_index:
                p_index[key] = f"P{len(p_index) + 1}"
                passages.append({"ref": p_index[key], "article_ref": a_ref.get(link.article_id),
                                 "text": text, "verified_verbatim": True})

    path_items = []
    for i, p in enumerate(paths, start=1):
        path_items.append({
            "ref": f"PATH{i}", "rank": p.rank, "target_asset": p.target_asset_id, "node_ids": p.node_ids,
            "node_labels": [event.title if n.startswith("event:") else kb.node_label(n) for n in p.node_ids],
            "relationship_refs": [r_ref[rid] for rid in p.relationship_ids if rid in r_ref],
            "edge_statuses": [next((x["status"] for x in rel_items if x["ref"] == r_ref.get(rid)), "?")
                              for rid in p.relationship_ids],
            "path_score": p.path_score, "impact_direction": p.impact_direction,
            "uncertainties": p.uncertainties,
        })
    path_ref_by_id = {p.id: f"PATH{i}" for i, p in enumerate(paths, start=1)}

    impacts = session.scalars(select(AssetImpact).where(AssetImpact.analysis_run_id == run.id)
                              .order_by(AssetImpact.best_path_score.desc()).limit(MAX_ASSETS)).all()
    obs = session.scalars(select(MarketObservation).where(MarketObservation.analysis_run_id == run.id)).all()
    obs_items = []
    for i, o in enumerate(obs, start=1):
        obs_items.append({"ref": f"M{i}", "asset_id": o.asset_id, "kind": o.observation_kind,
                          "historical_event_id": o.historical_event_id, "status": o.status,
                          "provider": o.provider, "anchor_date": str(o.anchor_date) if o.anchor_date else None,
                          "reference_date": str(o.reference_date) if o.reference_date else None,
                          "windows": o.windows, "simulated_data": o.is_simulated, "notes": o.notes})
    asset_items = [{
        "asset_id": a.asset_id, "name": kb.node_label(a.asset_id),
        "quote_semantics": kb.assets[a.asset_id].quote_semantics if a.asset_id in kb.assets else None,
        "impact_direction": a.impact_direction, "best_path_score": a.best_path_score,
        "path_refs": [path_ref_by_id[p] for p in a.path_ids if p in path_ref_by_id],
        "market_data_status": a.market_data_status,
        "historical_support": (a.historical_comparison or {}).get("historical_support"),
        "historical_status": (a.historical_comparison or {}).get("status"),
    } for a in impacts]

    mentions = session.scalars(select(EventEntity).where(EventEntity.event_id == event.id)).all()
    entities = [{"node_id": m.entity_id, "name": kb.node_label(m.entity_id) if m.entity_id else m.mention_text,
                 "mention": m.mention_text, "type": m.entity_type, "origin": m.origin,
                 "normalization_status": m.normalization_status} for m in mentions]

    conflicting = [f"{kb.node_label(r.source_node_id)} -> {kb.node_label(r.target_node_id)}: sources disagree on direction"
                   for r in rels if (r.conditions or {}).get("conflicting_directions")]
    missing = []
    if not run.market_data_provider:
        missing.append("No market-data provider configured: no price observations or historical comparisons.")
    missing += [f"{a['name']}: market data {a['market_data_status']}" for a in asset_items
                if a["market_data_status"] not in ("AVAILABLE",)]
    unresolved = [m.mention_text for m in mentions if m.normalization_status != "RESOLVED"]
    if unresolved:
        missing.append(f"Entities that could not be normalised: {unresolved[:10]}")
    if all(not a.content for a in articles):
        missing.append("Source provider supplied headlines/summaries only, not full article text.")

    limitations = [
        "Relationship and path scores are heuristic ranking scores, not probabilities of price moves.",
        "INFERRED edges come from a generic economic knowledge base and may not hold in current conditions.",
        "Historical co-movement does not establish causation.",
    ]
    if run.mode == "SIMULATED":
        limitations.insert(0, "SIMULATED analysis: mock LLM and/or simulated articles were used.")

    return {
        "package_version": EXPLANATION_VERSION,
        "analysis_id": run.id,
        "mode": run.mode,
        "event": {"id": event.id, "title": event.title, "event_type": event.event_type, "summary": event.summary,
                  "event_date": str(event.event_date) if event.event_date else None, "countries": event.countries,
                  "reported_figures": [f for f in event.reported_figures if f.get("passage_verified")],
                  "primary_effects": event.primary_effects, "relevance_rationale": event.relevance_rationale,
                  "verification_status": event.verification_status, "is_simulated": event.is_simulated},
        "articles": [{"ref": a_ref[a.id], "article_id": a.id, "headline": a.headline, "source_name": a.source_name,
                      "url": a.url, "published_at": a.published_at.isoformat() if a.published_at else None,
                      "is_simulated": a.is_simulated, "input_origin": a.input_origin} for a in articles],
        "passages": passages,
        "entities": entities,
        "relationships": rel_items,
        "candidate_paths": path_items,
        "candidate_assets": asset_items,
        "market_observations": obs_items,
        "data_availability": {"market_data_provider": run.market_data_provider or None},
        "conflicting_evidence": conflicting,
        "missing_data": missing,
        "known_limitations": limitations,
    }
