"""Market-data access (with DB caching), observed event reactions and historical comparisons.

Two deliberately separate outputs:
* CURRENT_EVENT observations: how an asset moved after THIS event (observed reaction). Context
  only; never used as historical support and never presented as causal attribution.
* HISTORICAL_EVENT comparisons: how the asset moved after comparable past events whose reported
  direction on the same seed variable is known. Their directional consistency with the path's
  implied sign becomes the historical-support component H of the asset's final edge.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.domain import DataAvailability
from app.models import AssetSymbol, HistoricalEvent, MarketData
from app.services.graph.paths import RankedPath
from app.services.market_data.base import MarketDataProvider, PriceSeries, empty_frame
from app.services.market_data.quality import LimitationCode
from app.services.market_data.windows import EventWindowResult, anchor_date_for, event_window_returns
from app.services.relationships.knowledge_base import KnowledgeBase

log = logging.getLogger(__name__)

FLAT_MOVE_PCT = 0.25  # |return| below this is treated as no clear move
COMPARISON_WINDOW = 5  # trading days used for historical consistency
SAME_EVENT_EXCLUSION_DAYS = 30
#: Exchanges whose calendars have historically included weekend sessions (e.g. TASE's Sunday trading).
WEEKEND_TRADING_TIMEZONES = {"Asia/Jerusalem", "Asia/Riyadh", "Asia/Tehran"}


def build_market_provider(settings: Settings) -> MarketDataProvider | None:
    if settings.market_data_provider == "none":
        return None
    if settings.market_data_provider == "yahoo_chart":
        from app.services.market_data.yahoo_chart import YahooChartProvider

        return YahooChartProvider(settings)
    if settings.market_data_provider == "alphavantage":
        from app.services.market_data.alphavantage import AlphaVantageProvider

        return AlphaVantageProvider(settings)
    raise ValueError(f"Unknown market data provider {settings.market_data_provider}")


@dataclass
class SeriesResult:
    series: PriceSeries | None
    status_reason: str | None
    symbol: str | None = None
    from_cache: bool = False
    reason_code: LimitationCode | None = None


@dataclass
class HistoricalComparison:
    asset_id: str
    status: str  # AVAILABLE | INSUFFICIENT_DATA | NO_COMPARABLE_EVENTS | UNAVAILABLE
    support: float | None
    path_rank: int | None = None
    seed_variable: str | None = None
    comparisons: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"status": self.status, "historical_support": self.support, "path_rank": self.path_rank,
                "seed_variable": self.seed_variable, "comparison_window_trading_days": COMPARISON_WINDOW,
                "flat_move_threshold_pct": FLAT_MOVE_PCT, "comparisons": self.comparisons, "notes": self.notes,
                "caveat": "Historical co-movement is context, not proof that the events caused the moves."}


class MarketDataService:
    def __init__(self, session: Session, provider: MarketDataProvider | None, kb: KnowledgeBase,
                 settings: Settings) -> None:
        self.session = session
        self.provider = provider
        self.kb = kb
        self.settings = settings

    # ------------------------------------------------------------------ series
    def symbol_for(self, asset_id: str) -> str | None:
        if self.provider is None:
            return None
        row = self.session.scalar(select(AssetSymbol).where(AssetSymbol.asset_id == asset_id,
                                                            AssetSymbol.provider == self.provider.name))
        if row:
            return row.symbol
        spec = self.kb.assets.get(asset_id)
        return spec.symbols.get(self.provider.name) if spec else None

    async def get_series(self, asset_id: str, ranges: list[tuple[date, date]]) -> SeriesResult:
        if self.provider is None:
            return SeriesResult(None, "no market-data provider configured (MARKET_DATA_PROVIDER=none)",
                                reason_code=LimitationCode.NOT_CONFIGURED)
        symbol = self.symbol_for(asset_id)
        if not symbol:
            return SeriesResult(None, f"no {self.provider.name} symbol mapping for this asset",
                                reason_code=LimitationCode.NO_PROVIDER_COVERAGE)
        today = datetime.now(timezone.utc).date()
        ranges = [(s, min(e, today)) for s, e in ranges if s <= today]
        if not ranges:
            return SeriesResult(None, "requested window is in the future", symbol,
                                reason_code=LimitationCode.FUTURE_RANGE)
        start, end = min(r[0] for r in ranges), max(r[1] for r in ranges)
        if self._cache_covers(asset_id, ranges, today):
            return SeriesResult(self._load_cache(asset_id, symbol, start, end), None, symbol, True)
        if not getattr(self.provider, "live", True):
            return SeriesResult(None, f"no market-data provider configured; cached {self.provider.name} data does "
                                      "not cover the requested range", symbol,
                                reason_code=LimitationCode.NOT_CONFIGURED)
        try:
            series = await self.provider.fetch_daily(symbol, start, end)
        except AppError as exc:
            return SeriesResult(None, f"provider error: {exc.message}", symbol,
                                reason_code=LimitationCode.PROVIDER_ERROR)
        if series.empty:
            text = "; ".join(series.notes) or "provider returned no data"
            coverage = any(k in text for k in ("not found", "not recognised", "provider error", "no result"))
            return SeriesResult(series, text, symbol, reason_code=LimitationCode.NO_PROVIDER_COVERAGE
                                if coverage else LimitationCode.MISSING_OBSERVATIONS)
        series = self._drop_weekend_artifacts(asset_id, series)
        self._store(asset_id, series)
        return SeriesResult(series, None, symbol)

    def trades_weekends(self, asset_id: str) -> bool:
        return self.asset_timezone(asset_id) in WEEKEND_TRADING_TIMEZONES

    def _drop_weekend_artifacts(self, asset_id: str, series: PriceSeries) -> PriceSeries:
        """Some providers emit a bar dated Saturday/Sunday (e.g. a live last-quote for FX). Markets that
        do not trade at weekends cannot have a session then, so such bars are dropped, not used."""
        if self.trades_weekends(asset_id):
            return series
        mask = [d.weekday() < 5 for d in series.frame.index]
        dropped = len(mask) - sum(mask)
        if dropped:
            series.frame = series.frame[mask]
            series.notes.append(f"dropped {dropped} weekend-dated bar(s) as provider artifacts")
        return series

    def _cache_covers(self, asset_id: str, ranges: list[tuple[date, date]], today: date) -> bool:
        for s, e in ranges:
            e_eff = min(e, today - timedelta(days=1))
            for lo, hi in ((s, s + timedelta(days=10)), (e_eff - timedelta(days=10), e_eff)):
                hit = self.session.scalar(
                    select(MarketData.id).where(MarketData.asset_id == asset_id,
                                                MarketData.provider == self.provider.name,
                                                MarketData.trade_date >= lo, MarketData.trade_date <= hi).limit(1))
                if hit is None:
                    return False
        return True

    def _load_cache(self, asset_id: str, symbol: str, start: date, end: date) -> PriceSeries:
        rows = self.session.scalars(
            select(MarketData).where(MarketData.asset_id == asset_id, MarketData.provider == self.provider.name,
                                     MarketData.trade_date >= start, MarketData.trade_date <= end)
            .order_by(MarketData.trade_date)).all()
        if not rows:
            return PriceSeries(self.provider.name, symbol, empty_frame())
        frame = pd.DataFrame({"open": [r.open for r in rows], "high": [r.high for r in rows],
                              "low": [r.low for r in rows], "close": [r.close for r in rows],
                              "volume": [r.volume for r in rows]}, index=[r.trade_date for r in rows])
        return PriceSeries(self.provider.name, symbol, frame, rows[0].currency,
                           simulated=any(r.is_simulated for r in rows), notes=["loaded from local cache"])

    def _store(self, asset_id: str, series: PriceSeries) -> None:
        dates = list(series.frame.index)
        existing = set(self.session.scalars(
            select(MarketData.trade_date).where(MarketData.asset_id == asset_id,
                                                MarketData.provider == series.provider,
                                                MarketData.trade_date >= min(dates),
                                                MarketData.trade_date <= max(dates))).all())
        for d, row in series.frame.iterrows():
            if d in existing:
                continue
            self.session.add(MarketData(
                asset_id=asset_id, provider=series.provider, symbol=series.symbol, trade_date=d,
                open=_f(row.get("open")), high=_f(row.get("high")), low=_f(row.get("low")),
                close=float(row["close"]), volume=_f(row.get("volume")), currency=series.currency,
                is_simulated=series.simulated))
        self.session.flush()

    def asset_timezone(self, asset_id: str) -> str:
        spec = self.kb.assets.get(asset_id)
        return spec.exchange_timezone if spec else "UTC"

    # ---------------------------------------------------------------- analysis
    async def analyze_asset(
        self, asset_id: str, info_time: datetime | date, paths: list[RankedPath],
        hist_events: list[HistoricalEvent], current_event_id: str,
    ) -> tuple[EventWindowResult, SeriesResult, HistoricalComparison]:
        windows = self.settings.market_event_windows
        current_anchor = anchor_date_for(info_time, self.asset_timezone(asset_id))
        candidates = self._comparable(paths, hist_events, current_anchor, current_event_id)
        ranges = [(current_anchor - timedelta(days=15), current_anchor + timedelta(days=max(windows) * 2 + 10))]
        for h, _, _ in candidates:
            ranges.append((h.event_date - timedelta(days=15), h.event_date + timedelta(days=COMPARISON_WINDOW * 2 + 10)))
        sr = await self.get_series(asset_id, ranges)
        if sr.series is None or sr.series.empty:
            current = EventWindowResult(DataAvailability.UNAVAILABLE, current_anchor, None, None, [],
                                        [sr.status_reason or "no data"],
                                        sr.reason_code or LimitationCode.MISSING_OBSERVATIONS)
        else:
            current = event_window_returns(sr.series, current_anchor, windows)
        comparison = self._compare(asset_id, sr, candidates)
        return current, sr, comparison

    def _comparable(self, paths: list[RankedPath], hist: list[HistoricalEvent], current_anchor: date,
                    current_event_id: str) -> list[tuple[HistoricalEvent, RankedPath, int]]:
        """(historical event, path, predicted sign) for past events with a known direction on the path's seed."""
        out: list[tuple[HistoricalEvent, RankedPath, int]] = []
        for path in sorted(paths, key=lambda p: -p.score):
            if len(path.edges) < 2:
                continue
            rest_sign = 1
            for e in path.edges[1:]:
                rest_sign *= e.sign
            if rest_sign == 0:
                continue
            seed = path.nodes[1]
            for h in hist:
                if h.event_id == current_event_id or abs((h.event_date - current_anchor).days) <= SAME_EVENT_EXCLUSION_DAYS:
                    continue
                d = next((p.get("direction") for p in h.primary_effects if p.get("variable") == seed), None)
                if d not in ("UP", "DOWN"):
                    continue
                out.append((h, path, (1 if d == "UP" else -1) * rest_sign))
            if out:
                break  # use the highest-ranked path that has comparable history
        out.sort(key=lambda x: x[0].event_date, reverse=True)
        return out[: self.settings.historical_max_comparisons]

    def _compare(self, asset_id: str, sr: SeriesResult,
                 candidates: list[tuple[HistoricalEvent, RankedPath, int]]) -> HistoricalComparison:
        if not candidates:
            return HistoricalComparison(asset_id, "NO_COMPARABLE_EVENTS", None,
                                        notes=["no reference event shares this path's seed variable with a known direction"])
        path = candidates[0][1]
        if sr.series is None or sr.series.empty:
            return HistoricalComparison(asset_id, "UNAVAILABLE", None, path.rank, path.nodes[1],
                                        notes=[sr.status_reason or "no data"])
        rows, scores = [], []
        for h, _, predicted in candidates:
            res = event_window_returns(sr.series, anchor_date_for(h.event_date, None), [COMPARISON_WINDOW])
            w = res.window(COMPARISON_WINDOW)
            row = {"historical_event_id": h.id, "title": h.title, "event_date": h.event_date.isoformat(),
                   "source_type": h.source_type, "predicted_sign": predicted, "status": res.status.value,
                   "reference_date": res.reference_date.isoformat() if res.reference_date else None,
                   "return_pct": w.return_pct if w else None, "notes": res.notes,
                   "reason_code": res.reason_code.value if res.reason_code else None}
            if w and w.return_pct is not None:
                if abs(w.return_pct) < FLAT_MOVE_PCT:
                    consistency = 0.5
                else:
                    consistency = 1.0 if (w.return_pct > 0) == (predicted > 0) else 0.0
                row["consistency"] = consistency
                scores.append(consistency)
            rows.append(row)
        n = len(scores)
        if n >= self.settings.historical_min_comparisons:
            support, status = round(sum(scores) / n, 4), "AVAILABLE"
        else:
            support, status = None, "INSUFFICIENT_DATA"
        notes = [f"{n} comparable event(s) with price data; minimum required {self.settings.historical_min_comparisons}"]
        return HistoricalComparison(asset_id, status, support, path.rank, path.nodes[1], rows, notes)


def _f(v) -> float | None:
    try:
        return None if v is None or pd.isna(v) else float(v)
    except (TypeError, ValueError):
        return None
