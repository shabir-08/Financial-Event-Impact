from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_kb
from app.core.errors import NotFoundError
from app.database.session import get_db
from app.models import AnalysisRun, AssetImpact
from app.schemas.api import AnalysisOut
from app.services.relationships.knowledge_base import KnowledgeBase

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: str, include_evidence_package: bool = False, db: Session = Depends(get_db),
                 kb: KnowledgeBase = Depends(get_kb)) -> AnalysisOut:
    run = db.get(AnalysisRun, analysis_id)
    if run is None:
        raise NotFoundError(f"analysis {analysis_id} not found")
    impacts = db.scalars(select(AssetImpact).where(AssetImpact.analysis_run_id == run.id)
                         .order_by(AssetImpact.best_path_score.desc()).limit(10)).all()
    explanation = run.explanation
    if explanation and not include_evidence_package:
        explanation = {k: v for k, v in explanation.items() if k != "evidence_package"}
    return AnalysisOut(
        id=run.id, event_id=run.event_id, article_id=run.article_id, status=run.status, mode=run.mode,
        trigger=run.trigger, analysis_version=run.analysis_version, knowledge_base_version=run.knowledge_base_version,
        llm_provider=run.llm_provider, llm_model=run.llm_model, market_data_provider=run.market_data_provider,
        config=run.config, steps=run.steps, warnings=run.warnings, error=run.error, started_at=run.started_at,
        finished_at=run.finished_at, graph_generated_at=run.graph_generated_at, graph_stats=run.graph_stats,
        explanation_status=run.explanation_status, explanation=explanation,
        top_assets=[{"asset_id": a.asset_id, "name": kb.node_label(a.asset_id), "impact_direction": a.impact_direction,
                     "best_path_score": a.best_path_score, "market_data_status": a.market_data_status}
                    for a in impacts],
    )
