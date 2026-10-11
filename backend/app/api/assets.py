from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_kb, get_market_provider
from app.core.config import Settings, get_settings
from app.core.errors import AppError, NotFoundError
from app.database.session import get_db
from app.models import Asset
from app.schemas.api import AssetHistoryResponse, AssetOut
from app.services.market_data.base import MarketDataProvider
from app.services.market_data.event_view import build_price_chart
from app.services.market_data.service import MarketDataService
from app.services.relationships.knowledge_base import KnowledgeBase

router = APIRouter(prefix="/api/assets", tags=["assets"])


def _asset_out(a: Asset) -> AssetOut:
    return AssetOut(id=a.id, name=a.name, asset_type=a.asset_type, currency=a.currency, country=a.country,
                    exchange=a.exchange, exchange_timezone=a.exchange_timezone, quote_semantics=a.quote_semantics,
                    symbols={s.provider: s.symbol for s in a.symbols})


@router.get("", response_model=list[AssetOut])
def list_assets(asset_type: str | None = None, db: Session = Depends(get_db)) -> list[AssetOut]:
    stmt = select(Asset).options(selectinload(Asset.symbols)).order_by(Asset.id)
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type.upper())
    return [_asset_out(a) for a in db.scalars(stmt).all()]


@router.get("/{asset_id}/history", response_model=AssetHistoryResponse)
async def asset_history(
    asset_id: str, start: date | None = None, end: date | None = None,
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings), kb: KnowledgeBase = Depends(get_kb),
    provider: MarketDataProvider | None = Depends(get_market_provider),
    include_bars: bool = Query(True),
) -> AssetHistoryResponse:
    """Daily history from the configured provider (cached in PostgreSQL). Never fabricated:
    unavailable data is reported with status UNAVAILABLE and a reason."""
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise NotFoundError(f"asset {asset_id} not found", details={"hint": "GET /api/assets"})
    end = end or date.today()
    start = start or end - timedelta(days=90)
    if start > end:
        raise AppError("start must be on or before end")
    chart = await build_price_chart(MarketDataService(db, provider, kb, settings), asset_id, start, end)
    db.commit()  # keep newly cached bars
    return AssetHistoryResponse(
        asset=_asset_out(asset), provider=chart["provider"], symbol=chart["symbol"], status=chart["status"],
        reason=(chart["limitation"] or {}).get("detail"), limitation=chart["limitation"], start=start, end=end,
        price_field=chart["price_field"], simulated=chart["simulated"],
        retrieved_from_cache=chart["retrieved_from_cache"], latest_observation=chart["latest_observation"],
        freshness=chart["freshness"], gaps=chart["gaps"],
        calculation={"daily_return_pct": "(close_t / previous available close - 1) x 100, quote currency; "
                                         "return_spans_gap=true when sessions are missing in between",
                     "currency": asset.currency, "exchange_timezone": asset.exchange_timezone,
                     "quote_semantics": asset.quote_semantics, "provider_notes": chart["provider_notes"]},
        bars=chart["bars"] if include_bars else [],
    )
