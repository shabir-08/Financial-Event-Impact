"""Response models for market-analysis endpoints (typed so the frontend contract is explicit)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

Availability = Literal["AVAILABLE", "PARTIALLY_AVAILABLE", "UNAVAILABLE"]


class Limitation(BaseModel):
    code: Literal["NOT_CONFIGURED", "NO_PROVIDER_COVERAGE", "PROVIDER_ERROR", "MISSING_OBSERVATIONS",
                  "NOT_YET_ELAPSED", "FUTURE_RANGE", "NOT_REQUESTED"]
    source: Literal["integration", "provider_coverage", "provider_outage", "missing_observations", "timing",
                    "analysis_scope"]
    message: str
    detail: str | None = None


class LimitationCodeInfo(BaseModel):
    code: str
    source: str
    message: str


class PriceBar(BaseModel):
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    daily_return_pct: float | None
    return_spans_gap: bool = False


class DataGap(BaseModel):
    kind: Literal["LEADING", "INTERNAL", "TRAILING"]
    from_date: date
    to_date: date
    missing_sessions: int
    likely_holiday: bool


class Freshness(BaseModel):
    latest_observation_date: date | None
    retrieved_at: datetime | None
    calendar_days_since_latest: int | None = None
    sessions_since_latest: int | None
    is_stale: bool | None
    latest_may_be_incomplete: bool
    usable_as_current_price: bool
    rule: str


class ChartMarker(BaseModel):
    kind: Literal["EVENT", "REFERENCE", "WINDOW_END"]
    date: date
    label: str
    window_trading_days: int | None


class PriceChart(BaseModel):
    status: Availability
    limitation: Limitation | None
    provider: str | None
    symbol: str | None
    range_start: date
    range_end: date
    price_field: str | None
    currency: str | None
    simulated: bool
    retrieved_from_cache: bool
    provider_notes: list[str]
    bars: list[PriceBar]
    gaps: list[DataGap]
    latest_observation: PriceBar | None
    freshness: Freshness
    markers: list[ChartMarker] = []


class WindowReturn(BaseModel):
    window_trading_days: int
    end_date: date | None
    end_close: float | None
    return_pct: float | None
    status: Literal["AVAILABLE", "NOT_YET_ELAPSED", "MISSING"]


class EventReturns(BaseModel):
    status: Availability
    limitation: Limitation | None
    computed_in_analysis: bool
    provider: str | None = None
    symbol: str | None = None
    anchor_date: date | None
    reference_date: date | None
    reference_close: float | None
    windows: list[WindowReturn]
    simulated: bool
    notes: list[str]


class HistoricalComparisonItem(BaseModel):
    historical_event_id: str
    title: str
    event_date: date
    source_type: str | None
    verification_note: str | None
    relevant_asset: str
    window_trading_days: int
    reference_date: date | None
    observed_return_pct: float | None
    observed_direction: Literal["UP", "DOWN", "FLAT"] | None
    path_implied_direction: Literal["UP", "DOWN"] | None
    consistent_with_path: bool | None
    consistency_score: float | None
    status: str | None
    limitation: Limitation | None
    notes: list[str]


class HistoricalContext(BaseModel):
    status: str
    historical_support: float | None
    seed_variable: str | None
    comparisons: list[HistoricalComparisonItem]
    limitations: list[str]
    flat_move_threshold_pct: float


class AssetSummary(BaseModel):
    asset_id: str
    name: str
    symbol: str | None
    all_provider_symbols: dict[str, str]
    asset_type: str
    exchange: str | None
    exchange_timezone: str
    country: str | None
    currency: str | None
    quote_semantics: str | None
    provider: str | None
    impact_direction: str
    best_path_score: float


class AssetAvailability(BaseModel):
    status: Availability
    limitation: Limitation | None


class AssetMarketView(BaseModel):
    summary: AssetSummary
    availability: AssetAvailability
    latest_observation: PriceBar | None
    freshness: Freshness
    chart: PriceChart
    returns: EventReturns
    historical_context: HistoricalContext


class EventMarketResponse(BaseModel):
    event_id: str
    event_title: str
    analysis_id: str
    mode: str
    event_date: date | None
    first_reported_at: datetime | None
    market_data_provider: str | None
    market_data_provider_at_analysis: str | None
    event_windows_trading_days: list[int]
    window_definitions: dict[str, str]
    availability_legend: dict[str, str]
    limitation_codes: list[LimitationCodeInfo]
    notes: list[str]
    assets: list[AssetMarketView]
