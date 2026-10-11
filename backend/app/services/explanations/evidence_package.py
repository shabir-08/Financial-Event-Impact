"""Assemble the structured evidence package handed to the explanation model.

Everything in the package comes from persisted records of one analysis run; the LLM sees no
other facts. Short reference ids (A*, P*, R*, PATH*, M*) let the explanation cite evidence and
let ``validation.validate_explanation`` check every citation.
"""

from __future__ import annotations

import json
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


# --------------------------------------------------------------------------------------- LLM-sized package
LLM_MAX_PASSAGE_CHARS = 400
LLM_MAX_TEXT_CHARS = 240


def _r(v: Any, d: int = 4) -> Any:
    return round(v, d) if isinstance(v, float) else v


def _cut(text: Any, n: int) -> Any:
    return text if not isinstance(text, str) or len(text) <= n else text[: n - 1] + "…"


def _compact(pkg: dict[str, Any]) -> dict[str, Any]:
    """The evidence package as sent to the explanation model: the same reference ids, labels, statuses,
    scores and observed returns, without verbose internals (score components, raw price fields, duplicate
    entity mentions). Keeps prompts within free-tier request limits (e.g. Groq 8k tokens/minute).
    The explanation is validated against this compact package, i.e. exactly what the model saw."""
    seen: set[str] = set()
    entities = []
    for e in pkg.get("entities", []):
        key = e.get("node_id") or e.get("mention")
        if key in seen:
            continue
        seen.add(key)
        entities.append({"name": e.get("name"), "type": e.get("type"), "origin": e.get("origin"),
                         **({} if e.get("normalization_status") == "RESOLVED" else {"unresolved": True})})
    return {
        **{k: pkg[k] for k in ("package_version", "analysis_id", "mode") if k in pkg},
        "event": {**{k: v for k, v in pkg["event"].items() if k not in ("id", "reported_figures")},
                  "summary": _cut(pkg["event"].get("summary"), 800),
                  "relevance_rationale": _cut(pkg["event"].get("relevance_rationale"), LLM_MAX_TEXT_CHARS),
                  # verified figures only (as in the full package); value + the sentence it came from
                  "reported_figures": [{"value": f.get("value"), "passage": _cut(f.get("passage"), 180)}
                                       for f in pkg["event"].get("reported_figures", [])]},
        "articles": [{k: a.get(k) for k in ("ref", "headline", "source_name", "published_at", "is_simulated")} for a in pkg.get("articles", [])],
        "passages": [{**p, "text": _cut(p.get("text"), LLM_MAX_PASSAGE_CHARS)} for p in pkg.get("passages", [])],
        "entities": entities,
        "relationships": [{"ref": r["ref"], "source": r["source_label"], "target": r["target_label"],
                           "type": r["relationship_type"], "direction": r["direction"], "status": r["status"],
                           "mechanism": _cut(r.get("mechanism"), 160), "score": _r(r.get("score"), 2),
                           "evidence": r.get("evidence", [])} for r in pkg.get("relationships", [])],
        "candidate_paths": [{"ref": p["ref"], "target_asset": p["target_asset"],
                             "node_labels": ["EVENT" if i == 0 else lab for i, lab in enumerate(p["node_labels"])],
                             "relationship_refs": p["relationship_refs"], "edge_statuses": p["edge_statuses"],
                             "path_score": _r(p.get("path_score"), 2), "impact_direction": p["impact_direction"],
                             "uncertainties": [_cut(u, LLM_MAX_TEXT_CHARS) for u in (p.get("uncertainties") or [])[:2]]}
                            for p in pkg.get("candidate_paths", [])],
        "candidate_assets": [{k: (_r(a.get(k), 2) if k == "best_path_score" else a.get(k)) for k in
                              ("asset_id", "name", "impact_direction", "best_path_score", "path_refs", "market_data_status",
                               "historical_status")} for a in pkg.get("candidate_assets", [])],
        "market_observations": [{"ref": o["ref"], "asset_id": o["asset_id"], "kind": o["kind"],
                                 "historical_event_id": o.get("historical_event_id"), "status": o["status"],
                                 "anchor_date": o.get("anchor_date"), "simulated_data": o.get("simulated_data"),
                                 "returns_pct_by_trading_days": {str(w.get("window_trading_days")): (_r(w.get("return_pct"), 2)
                                                                     if w.get("status") == "AVAILABLE" else w.get("status"))
                                                                 for w in (o.get("windows") or [])}}
                                for o in pkg.get("market_observations", [])],
        **{k: pkg[k] for k in ("data_availability", "conflicting_evidence", "missing_data", "known_limitations") if k in pkg},
    }


def _tokens(obj: Any) -> int:
    return len(json.dumps(obj, ensure_ascii=False, default=str)) // 3  # conservative: JSON is ~3 chars/token


def _keep_paths(c: dict[str, Any], n: int) -> int:
    dropped = max(0, len(c["candidate_paths"]) - n)
    if dropped:
        c["candidate_paths"] = c["candidate_paths"][:n]
        used = {r for p in c["candidate_paths"] for r in p["relationship_refs"]}
        c["relationships"] = [r for r in c["relationships"] if r["ref"] in used or r["status"] in ("REPORTED", "UNVERIFIED")]
        left = {p["ref"] for p in c["candidate_paths"]}
        for a in c["candidate_assets"]:
            a["path_refs"] = [r for r in a["path_refs"] if r in left]
    return dropped


def compact_for_llm(pkg: dict[str, Any], token_budget: int = 6000) -> dict[str, Any]:
    """Compact package; if still over the token budget (~Groq free-tier 8k tokens/min minus prompt overhead),
    trim the least essential parts first and say so in ``trimmed_for_size``."""
    c = _compact(pkg)
    trimmed: list[str] = []
    obs = c["market_observations"]
    if _tokens(c) > token_budget:  # 1. one historical comparison per asset
        per: dict[str, int] = {}
        keep = [o for o in obs if o["kind"] != "HISTORICAL_EVENT"
                or per.__setitem__(o["asset_id"], per.get(o["asset_id"], 0) + 1) or per[o["asset_id"]] <= 1]
        if len(keep) < len(obs):
            trimmed.append(f"{len(obs) - len(keep)} historical-comparison observation(s)")
            c["market_observations"] = obs = keep
    if _tokens(c) > token_budget:  # 2. market observations only for the top 6 assets
        top = {a["asset_id"] for a in c["candidate_assets"][:6]}
        keep = [o for o in obs if o["asset_id"] in top]
        if len(keep) < len(obs):
            trimmed.append(f"market observations for {len({o['asset_id'] for o in obs} - top)} lower-ranked asset(s)")
            c["market_observations"] = keep
    if _tokens(c) > token_budget and c["entities"]:  # 3. entity list
        trimmed.append(f"{len(c['entities'])} entity name(s)")
        c["entities"] = []
    if _tokens(c) > token_budget and len(c["candidate_assets"]) > 8:  # 4. top 8 candidate assets
        trimmed.append(f"{len(c['candidate_assets']) - 8} lower-ranked candidate asset(s)")
        c["candidate_assets"] = c["candidate_assets"][:8]
    for n in (6, 4, 3):  # 5. last resort: fewer paths
        if _tokens(c) > token_budget and (d := _keep_paths(c, n)):
            trimmed.append(f"{d} further lower-ranked path(s)")
    if trimmed:
        c["trimmed_for_size"] = {"omitted": trimmed,
                                 "note": "Omitted to fit the model's request-size limit; say that the evidence shown is partial."}
    return c
