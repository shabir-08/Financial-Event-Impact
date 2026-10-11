"""Per-event analysis views: entities, graph, ranked paths and evidence."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_kb
from app.database.session import get_db
from app.models import (
    Article,
    AssetImpact,
    EventArticle,
    EventEntity,
    ExtractedClaim,
    ImpactPath,
    MarketObservation,
    Relationship,
)
from app.repositories.queries import get_event_or_404, get_run_for_event
from app.schemas.api import (
    AssetImpactOut,
    EntitiesResponse,
    EntityMentionOut,
    EvidenceResponse,
    PathOut,
    PathsResponse,
)
from app.services.graph.serialization import graph_payload
from app.services.relationships.knowledge_base import KnowledgeBase

router = APIRouter(prefix="/api/events", tags=["analysis views"])


@router.get("/{event_id}/entities", response_model=EntitiesResponse)
def event_entities(event_id: str, db: Session = Depends(get_db)) -> EntitiesResponse:
    ev = get_event_or_404(db, event_id)
    rows = db.scalars(select(EventEntity).where(EventEntity.event_id == ev.id)).all()
    art = [EntityMentionOut.model_validate(r) for r in rows if r.origin == "ARTICLE"]
    inf = [EntityMentionOut.model_validate(r) for r in rows if r.origin == "INFERRED"]
    counts: dict[str, int] = {}
    for r in art:
        counts[r.normalization_status] = counts.get(r.normalization_status, 0) + 1
    run = get_run_for_event(db, ev, require=False)
    return EntitiesResponse(event_id=ev.id, analysis_id=run.id if run else None, article_entities=art,
                            inferred_entities=inf, counts={**counts, "INFERRED": len(inf)})


@router.get("/{event_id}/graph")
def event_graph(event_id: str, analysis_id: str | None = None, include_involvement: bool = True,
                min_score: float = Query(0.0, ge=0.0, le=1.0), db: Session = Depends(get_db)) -> dict:
    """Cytoscape.js-ready graph (``elements.nodes`` / ``elements.edges``) for the event's analysis."""
    ev = get_event_or_404(db, event_id)
    run = get_run_for_event(db, ev, analysis_id)
    return graph_payload(db, run, include_involvement=include_involvement, min_score=min_score)


@router.get("/{event_id}/paths", response_model=PathsResponse)
def event_paths(event_id: str, analysis_id: str | None = None, limit: int = Query(25, ge=1, le=200),
                asset_id: str | None = None, db: Session = Depends(get_db),
                kb: KnowledgeBase = Depends(get_kb)) -> PathsResponse:
    ev = get_event_or_404(db, event_id)
    run = get_run_for_event(db, ev, analysis_id)
    stmt = select(ImpactPath).where(ImpactPath.analysis_run_id == run.id).order_by(ImpactPath.rank)
    if asset_id:
        stmt = stmt.where(ImpactPath.target_asset_id == asset_id)
    paths = db.scalars(stmt.limit(limit)).all()
    rel_ids = {rid for p in paths for rid in p.relationship_ids}
    rels = {r.id: r for r in db.scalars(select(Relationship).where(Relationship.id.in_(rel_ids))).all()} if rel_ids else {}
    out_paths = []
    for p in paths:
        out_paths.append(PathOut(
            id=p.id, rank=p.rank, target_asset_id=p.target_asset_id, target_asset_name=kb.node_label(p.target_asset_id),
            node_ids=p.node_ids, node_labels=[ev.title if n.startswith("event:") else kb.node_label(n) for n in p.node_ids],
            relationships=[{"id": rid, "source": rels[rid].source_node_id, "target": rels[rid].target_node_id,
                            "relationship_type": rels[rid].relationship_type, "direction": rels[rid].direction,
                            "status": rels[rid].status, "origin": rels[rid].origin, "score": rels[rid].score,
                            "mechanism": rels[rid].mechanism, "kb_rule_id": rels[rid].kb_rule_id}
                           for rid in p.relationship_ids if rid in rels],
            path_score=p.path_score, score_breakdown=p.score_breakdown, impact_direction=p.impact_direction,
            explanation=p.explanation, uncertainties=p.uncertainties))
    obs = db.scalars(select(MarketObservation).where(MarketObservation.analysis_run_id == run.id)).all()
    impacts = db.scalars(select(AssetImpact).where(AssetImpact.analysis_run_id == run.id)
                         .order_by(AssetImpact.best_path_score.desc())).all()
    assets = [AssetImpactOut(
        asset_id=a.asset_id, asset_name=kb.node_label(a.asset_id),
        asset_type=kb.assets[a.asset_id].asset_type.value if a.asset_id in kb.assets else None,
        impact_direction=a.impact_direction, best_path_score=a.best_path_score, path_ids=a.path_ids,
        mechanism=a.mechanism, uncertainty=a.uncertainty, market_data_status=a.market_data_status,
        historical_comparison=a.historical_comparison,
        observations=[{"kind": o.observation_kind, "status": o.status, "provider": o.provider, "symbol": o.symbol,
                       "historical_event_id": o.historical_event_id, "anchor_date": o.anchor_date,
                       "reference_date": o.reference_date, "reference_close": o.reference_close,
                       "windows": o.windows, "simulated_data": o.is_simulated, "notes": o.notes}
                      for o in obs if o.asset_id == a.asset_id],
    ) for a in impacts]
    expl = None
    if run.explanation:
        expl = {k: v for k, v in run.explanation.items() if k != "evidence_package"}
    return PathsResponse(event_id=ev.id, analysis_id=run.id, mode=run.mode, paths=out_paths, assets=assets,
                         explanation=expl)


@router.get("/{event_id}/evidence", response_model=EvidenceResponse)
def event_evidence(event_id: str, analysis_id: str | None = None, db: Session = Depends(get_db)) -> EvidenceResponse:
    ev = get_event_or_404(db, event_id)
    links = db.scalars(select(EventArticle).where(EventArticle.event_id == ev.id)).all()
    articles = []
    for l in links:
        a = db.get(Article, l.article_id)
        articles.append({"article_id": a.id, "headline": a.headline, "source_name": a.source_name, "url": a.url,
                         "published_at": a.published_at, "provider": a.provider, "is_simulated": a.is_simulated,
                         "input_origin": a.input_origin, "role": l.role,
                         "supporting_passages": l.supporting_passages, "association_reason": l.association_reason})
    claims = [{"id": c.id, "article_id": c.article_id, "source_mention": c.source_mention,
               "target_mention": c.target_mention, "source_entity_id": c.source_entity_id,
               "target_entity_id": c.target_entity_id, "relationship_type": c.relationship_type,
               "effect_sign": c.effect_sign, "passage": c.passage, "passage_verified": c.passage_verified,
               "extraction_confidence": c.extraction_confidence, "is_primary_effect": c.is_primary_effect,
               "used_in_graph": bool(c.source_entity_id and c.target_entity_id)}
              for c in db.scalars(select(ExtractedClaim).where(ExtractedClaim.event_id == ev.id)).all()]
    run = get_run_for_event(db, ev, analysis_id, require=False)
    rel_ev = []
    if run:
        for r in db.scalars(select(Relationship).where(Relationship.analysis_run_id == run.id)
                            .options(selectinload(Relationship.evidence))).all():
            for e in r.evidence:
                rel_ev.append({"relationship_id": r.id, "source": r.source_node_id, "target": r.target_node_id,
                               "status": r.status, "evidence_type": e.evidence_type, "article_id": e.article_id,
                               "passage": e.passage, "reference": e.reference, "verified": e.verified})
    return EvidenceResponse(event_id=ev.id, analysis_id=run.id if run else None, articles=articles, claims=claims,
                            relationship_evidence=rel_ev)
