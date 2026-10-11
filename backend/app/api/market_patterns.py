"""Historical market-pattern endpoints: analogue search, market regimes, event-conditioned responses.

Everything returned is historical observation or descriptive statistics of it. User shock values are
labelled as assumptions; nothing here is a forecast, probability or causal estimate.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_pattern_library, get_scenario_catalog
from app.core.errors import NotFoundError
from app.schemas.api import ErrorResponse
from app.schemas.patterns import EventResponseGroups, PatternSearchRequest, PatternSearchResponse
from app.services.patterns import events as event_analysis
from app.services.patterns import service
from app.services.patterns.library import PatternLibrary
from app.services.simulation.scenarios import ScenarioCatalog

router = APIRouter(prefix="/api/market-patterns", tags=["historical market patterns"])
ERRORS = {404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


@router.get("/conditions/latest")
def latest_conditions(lib: PatternLibrary = Depends(get_pattern_library)) -> dict:
    """Most recent observed market conditions in the library (trailing features as of an NSE close) and their regimes."""
    return {**lib.latest, "feature_meta": {f: lib.feature_meta[f] for f in lib.latest["values"]},
            "library_version": lib.version}


@router.post("/search", response_model=PatternSearchResponse, responses=ERRORS)
def search_patterns(req: PatternSearchRequest, lib: PatternLibrary = Depends(get_pattern_library),
                    catalog: ScenarioCatalog = Depends(get_scenario_catalog)) -> PatternSearchResponse:
    """Find the historical weeks most similar to a scenario or to market conditions and report what happened."""
    out = service.search(lib, catalog, req.mode, req.shocks, req.conditions, req.condition_features, req.assets,
                         req.k, req.horizon_days)
    return PatternSearchResponse.model_validate(out)


@router.get("/regimes", responses=ERRORS)
def regimes(asset: str | None = Query(None, description="Target symbol or asset id (default NIFTY50)"),
            lib: PatternLibrary = Depends(get_pattern_library)) -> dict:
    """Rule-based market regimes (start-of-week information only) with the historical outcomes that followed."""
    return service.regime_summary(lib, asset)


@router.get("/event-responses", response_model=EventResponseGroups)
def event_responses(group_by: Literal["event_class", "event_category_normalized"] = "event_class",
                    lib: PatternLibrary = Depends(get_pattern_library)) -> EventResponseGroups:
    """Observed market responses after past events, grouped by class or category, one event per episode in statistics."""
    return EventResponseGroups(group_by=group_by, groups=event_analysis.summarize(lib.events, group_by),
                               n_events=len(lib.events), n_independent_episodes=len({e["episode_id"] for e in lib.events}),
                               library_version=lib.version)


@router.get("/event-responses/{event_id}", responses=ERRORS)
def event_response(event_id: str, lib: PatternLibrary = Depends(get_pattern_library)) -> dict:
    """One research event's measured responses, pre-event conditions, overlap and sources."""
    e = next((x for x in lib.events if x["event_id"] == event_id), None)
    if e is None:
        raise NotFoundError(f"historical event {event_id} not found", details={"hint": "GET /api/market-patterns/event-responses"})
    return {"event": e, "library_version": lib.version,
            "note": "Movements in windows that contain other events cannot be attributed to this event alone."}
