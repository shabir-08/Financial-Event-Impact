from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_kb, get_market_provider
from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.repositories.queries import get_event_or_404, get_run_for_event
from app.schemas.market import EventMarketResponse
from app.services.market_data.base import MarketDataProvider
from app.services.market_data.event_view import build_event_market_view
from app.services.relationships.knowledge_base import KnowledgeBase

router = APIRouter(prefix="/api/events", tags=["market analysis"])


@router.get("/{event_id}/market", response_model=EventMarketResponse)
async def event_market(
    event_id: str,
    analysis_id: str | None = None,
    asset_id: str | None = Query(None, description="Only this asset"),
    limit: int = Query(8, ge=1, le=50, description="Top-N assets by path score"),
    pre_days: int = Query(30, ge=1, le=730, description="Chart calendar days before the event"),
    post_days: int = Query(45, ge=1, le=730, description="Chart calendar days after the event"),
    include_bars: bool = True,
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings), kb: KnowledgeBase = Depends(get_kb),
    provider: MarketDataProvider | None = Depends(get_market_provider),
) -> EventMarketResponse:
    """Everything the market-analysis page needs for an event's candidate assets.

    * **summary**: asset identity, symbol, exchange, currency, provider
    * **chart**: provider bars (or local cache) around the event, gaps, freshness and event/window markers
    * **returns**: the 1/3/5/20-trading-day returns computed by the analysis run, with definitions
    * **historical_context**: comparable past events and their observed moves (not causal evidence)
    * **availability**: AVAILABLE / PARTIALLY_AVAILABLE / UNAVAILABLE with a limitation code and source

    No prices are generated: unavailable data is returned as empty bars plus a limitation.
    """
    event = get_event_or_404(db, event_id)
    run = get_run_for_event(db, event, analysis_id)
    data = await build_event_market_view(db, event, run, kb, settings, provider, asset_id=asset_id, limit=limit,
                                         pre_days=pre_days, post_days=post_days, include_bars=include_bars)
    return EventMarketResponse.model_validate(data)
