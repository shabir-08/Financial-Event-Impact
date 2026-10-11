"""Black Swan simulator endpoints: scenario catalog, 3D knowledge graph, simulations, entity details.

Simulations are HYPOTHETICAL: user-supplied shock values are assumptions, kept apart from reported
events; the graph shows knowledge-base pathways and the predictions block is the only numerical output.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (get_kb, get_market_provider, get_optional_pattern_library, get_scenario_catalog,
                          get_simulation_models, get_visual_layers)
from app.core.config import Settings, get_settings
from app.core.errors import AppError, NotFoundError
from app.database.session import get_db
from app.domain import RelationshipType
from app.schemas.api import ErrorResponse
from app.schemas.simulation import (
    EntityResponse,
    Graph3DResponse,
    ScenarioListResponse,
    ScenarioOut,
    SimulationRequest,
    SimulationResponse,
)
from app.services.market_data.base import MarketDataProvider
from app.services.market_data.event_view import build_price_chart
from app.services.market_data.service import MarketDataService
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.simulation import inference
from app.services.simulation.graph3d import full_knowledge_graph, layer_for
from app.services.simulation.orchestrator import SimulationOrchestrator, scenario_listing
from app.services.simulation.scenarios import ScenarioCatalog

router = APIRouter(tags=["black swan simulator"])
ERRORS = {404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


def _orchestrator(db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
                  kb: KnowledgeBase = Depends(get_kb), catalog: ScenarioCatalog = Depends(get_scenario_catalog),
                  models: dict = Depends(get_simulation_models), layers: dict = Depends(get_visual_layers),
                  patterns=Depends(get_optional_pattern_library)) -> SimulationOrchestrator:
    return SimulationOrchestrator(db, settings, kb, catalog, models, layers, patterns)


@router.get("/api/scenarios", response_model=ScenarioListResponse)
def list_scenarios(settings: Settings = Depends(get_settings), catalog: ScenarioCatalog = Depends(get_scenario_catalog),
                   models: dict = Depends(get_simulation_models)) -> ScenarioListResponse:
    """Hypothetical scenario templates with parameter units, accepted input ranges (slider bounds) and,
    separately, the range the quantitative model was validated on."""
    return ScenarioListResponse(
        scenario_catalog_version=f"{catalog.version}+{catalog.content_hash}",
        scenarios=scenario_listing(catalog, models, settings.simulation_scenario_model_id),
        model_compatibility=inference.compatibility(models))


@router.get("/api/scenarios/{scenario_id}", response_model=ScenarioOut, responses=ERRORS)
def get_scenario(scenario_id: str, settings: Settings = Depends(get_settings),
                 catalog: ScenarioCatalog = Depends(get_scenario_catalog),
                 models: dict = Depends(get_simulation_models)) -> ScenarioOut:
    catalog.get(scenario_id)  # 404 for unknown ids
    return next(s for s in scenario_listing(catalog, models, settings.simulation_scenario_model_id) if s["id"] == scenario_id)


@router.get("/api/graph/3d", response_model=Graph3DResponse)
def graph_3d(kb: KnowledgeBase = Depends(get_kb), catalog: ScenarioCatalog = Depends(get_scenario_catalog),
             layers: dict = Depends(get_visual_layers)) -> Graph3DResponse:
    """The full knowledge graph with layer metadata (positions are computed by the frontend).
    Edge support scores are knowledge-base reliability/relevance ratings, not probabilities."""
    return Graph3DResponse.model_validate(full_knowledge_graph(kb, catalog, layers))


@router.post("/api/simulations", response_model=SimulationResponse, responses=ERRORS)
def create_simulation(req: SimulationRequest, orch: SimulationOrchestrator = Depends(_orchestrator)) -> SimulationResponse:
    """Run a hypothetical scenario. Identical requests under identical model / knowledge-base / catalog
    versions return the stored result (``cached: true``, same ``simulation_id``)."""
    result, _ = orch.run(req.scenario_id, req.shocks, req.horizon_days, req.max_depth)
    return SimulationResponse.model_validate(result)


@router.get("/api/simulations/{simulation_id}", response_model=SimulationResponse, responses=ERRORS)
def get_simulation(simulation_id: str, orch: SimulationOrchestrator = Depends(_orchestrator)) -> SimulationResponse:
    return SimulationResponse.model_validate(orch.get(simulation_id))


def _listed_assets(kb: KnowledgeBase, entity_id: str) -> list[str]:
    if kb.is_asset(entity_id):
        return [entity_id]
    return [a.id for a in kb.assets.values()
            if any(x.source == entity_id and x.relationship_type == RelationshipType.ASSOCIATED_WITH for x in a.exposures)]


def _require_node(kb: KnowledgeBase, entity_id: str) -> None:
    if not kb.node_exists(entity_id):
        raise NotFoundError(f"entity {entity_id} not found", details={"hint": "use node ids from GET /api/graph/3d"})


@router.get("/api/entities/{entity_id}", response_model=EntityResponse, responses=ERRORS)
def get_entity(entity_id: str, settings: Settings = Depends(get_settings), kb: KnowledgeBase = Depends(get_kb),
               layers: dict = Depends(get_visual_layers), models: dict = Depends(get_simulation_models)) -> EntityResponse:
    """Details for a node clicked in the 3D graph: knowledge-base identity, relationships with their
    mechanisms, listed instruments, and whether the simulator's model produces an estimate for it."""
    _require_node(kb, entity_id)
    ntype = kb.node_type(entity_id)

    def rel(r) -> dict:
        return {"id": r.id, "source": r.source, "source_label": kb.node_label(r.source), "target": r.target,
                "target_label": kb.node_label(r.target), "relationship_type": r.relationship_type.value,
                "sign": r.effect_sign, "mechanism": r.mechanism, "time_horizon": r.time_horizon,
                "evidence_basis": r.evidence_basis, "reliability": r.reliability,
                "economic_relevance": r.economic_relevance, "score_is_probability": False}

    m = models.get(settings.simulation_scenario_model_id)
    listed = _listed_assets(kb, entity_id)
    targets = [t for t in (m.targets if m else []) if t["kb_asset_id"] and t["kb_asset_id"] in listed]
    out: dict = {"id": entity_id, "label": kb.node_label(entity_id), "type": ntype,
                 "layer": layer_for(entity_id, ntype, layers), "is_asset": kb.is_asset(entity_id),
                 "is_model_target": bool(targets),
                 "model_targets": [{"symbol": t["symbol"], "kb_asset_id": t["kb_asset_id"], "model_id": m.model_id} for t in targets],
                 "listed_assets": [{"id": a, "name": kb.assets[a].name, "symbols": kb.assets[a].symbols,
                                    "exchange": kb.assets[a].exchange, "currency": kb.assets[a].currency} for a in listed],
                 "outgoing_relationships": [rel(r) for r in kb.outgoing(entity_id)],
                 "incoming_relationships": [rel(r) for r in kb.rules.values() if r.target == entity_id],
                 "historical_data_available_via": f"/api/entities/{entity_id}/historical" if listed else None}
    if entity_id in kb.entities:
        e = kb.entities[entity_id]
        out.update(aliases=e.aliases, country=e.country, effect_variable=e.effect_variable)
    else:
        a = kb.assets[entity_id]
        out.update(aliases=a.aliases, country=a.country, asset_type=a.asset_type.value, currency=a.currency,
                   exchange=a.exchange, quote_semantics=a.quote_semantics)
    return EntityResponse.model_validate(out)


@router.get("/api/entities/{entity_id}/historical", responses=ERRORS)
async def entity_historical(
    entity_id: str, start: date | None = None, end: date | None = None,
    days: int = Query(365, ge=5, le=3650, description="Calendar days before `end` when `start` is omitted"),
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings), kb: KnowledgeBase = Depends(get_kb),
    provider: MarketDataProvider | None = Depends(get_market_provider),
) -> dict:
    """Observed daily market data for an asset, or for a company's listed instrument, from the configured
    provider (cached in PostgreSQL). Non-tradable entities return UNAVAILABLE; nothing is generated."""
    _require_node(kb, entity_id)
    end = end or date.today()
    start = start or end - timedelta(days=days)
    if start > end:
        raise AppError("start must be on or before end")
    listed = _listed_assets(kb, entity_id)
    base = {"entity_id": entity_id, "label": kb.node_label(entity_id), "type": kb.node_type(entity_id),
            "range_start": start.isoformat(), "range_end": end.isoformat(), "is_simulated_scenario_data": False}
    if not listed:
        return {**base, "status": "UNAVAILABLE", "asset_id": None, "bars": [],
                "limitation": {"code": "NOT_TRADABLE", "source": "entity_type",
                               "message": "This entity has no listed instrument in the asset catalog, so no price history exists for it.",
                               "detail": None}}
    asset_id = listed[0]
    chart = await build_price_chart(MarketDataService(db, provider, kb, settings), asset_id, start, end)
    db.commit()  # keep newly cached bars
    relation = ("self" if asset_id == entity_id else
                "listed_equity" if kb.node_type(entity_id) == "COMPANY" else "tracking_instrument")
    return {**base, "asset_id": asset_id, "asset_name": kb.assets[asset_id].name, "instrument_relation": relation,
            "instrument_note": ("Prices are for an instrument that tracks this variable, not the variable itself."
                                if relation == "tracking_instrument" else None),
            "other_listed_assets": listed[1:], **chart}
