"""Page-ready market analysis for an event: asset summaries, price charts with event markers and
gaps, backend-calculated window returns, historical comparisons and data-availability reasons.

Prices come only from the provider (or its local cache). Returns and comparisons are the values
persisted by the analysis run, so the page shows exactly what the analysis used.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain import DataAvailability
from app.models import AnalysisRun, Asset, AssetImpact, Event, HistoricalEvent, MarketData, MarketObservation
from app.services.market_data.base import MarketDataProvider
from app.services.market_data.quality import (
    AVAILABILITY_LEGEND,
    WINDOW_DEFINITIONS,
    LimitationCode,
    expected_sessions_between,
    find_gaps,
    freshness,
    limitation,
    limitation_legend,
)
from app.services.market_data.service import FLAT_MOVE_PCT, MarketDataService
from app.services.market_data.windows import anchor_date_for
from app.services.relationships.knowledge_base import KnowledgeBase


@dataclass
class CacheOnlyProvider:
    """Stand-in used when no provider is configured now but a run cached data earlier:
    serves the local cache only and never fetches."""

    name: str
    simulated: bool = False
    live: bool = False

    async def fetch_daily(self, symbol, start, end):  # pragma: no cover - never called (live=False)
        raise RuntimeError("cache-only provider cannot fetch")


def _num(v: Any, nd: int = 6) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else round(f, nd)


async def build_price_chart(service: MarketDataService, asset_id: str, start: date, end: date,
                            today: date | None = None) -> dict[str, Any]:
    """Bars, gaps, freshness and availability for one asset/date range (shared with /history)."""
    today = today or datetime.now(timezone.utc).date()
    sr = await service.get_series(asset_id, [(start, end)])
    weekend = service.trades_weekends(asset_id)
    bars: list[dict[str, Any]] = []
    if sr.series is not None and not sr.series.empty:
        f = sr.series.frame
        f = f[(f.index >= start) & (f.index <= end)]
        prev_date, prev_close = None, None
        for d, row in f.iterrows():
            close = _num(row["close"])
            spans_gap = bool(prev_date and expected_sessions_between(prev_date, d, weekend) > 0)
            bars.append({
                "date": d.isoformat(), "open": _num(row.get("open")), "high": _num(row.get("high")),
                "low": _num(row.get("low")), "close": close, "volume": _num(row.get("volume")),
                "daily_return_pct": _num((close / prev_close - 1) * 100, 4) if prev_close and close else None,
                "return_spans_gap": spans_gap,
            })
            prev_date, prev_close = d, close
    dates = [date.fromisoformat(b["date"]) for b in bars]
    gaps = find_gaps(dates, weekend, start=start, end=min(end, today - timedelta(days=1)))
    retrieved_at = None
    if service.provider is not None and dates:
        retrieved_at = service.session.scalar(
            select(func.max(MarketData.retrieved_at)).where(
                MarketData.asset_id == asset_id, MarketData.provider == service.provider.name,
                MarketData.trade_date >= start, MarketData.trade_date <= end))
    if not bars:
        status = DataAvailability.UNAVAILABLE
        lim = limitation(sr.reason_code or LimitationCode.MISSING_OBSERVATIONS, sr.status_reason)
    elif any(g["kind"] != "INTERNAL" or not g["likely_holiday"] for g in gaps):
        status = DataAvailability.PARTIALLY_AVAILABLE
        lim = limitation(LimitationCode.MISSING_OBSERVATIONS,
                         f"{sum(g['missing_sessions'] for g in gaps)} expected session(s) without observations")
    else:
        status, lim = DataAvailability.AVAILABLE, None
    return {
        "status": status.value, "limitation": lim, "provider": service.provider.name if service.provider else None,
        "symbol": sr.symbol, "range_start": start.isoformat(), "range_end": end.isoformat(),
        "price_field": sr.series.price_field if sr.series is not None else None,
        "currency": sr.series.currency if sr.series is not None else None,
        "simulated": bool(sr.series is not None and sr.series.simulated),
        "retrieved_from_cache": sr.from_cache, "provider_notes": sr.series.notes if sr.series is not None else [],
        "bars": bars, "gaps": gaps,
        "latest_observation": bars[-1] if bars else None,
        "freshness": freshness(dates[-1] if dates else None, today, weekend, retrieved_at),
    }


def _direction(pct: float | None) -> str | None:
    if pct is None:
        return None
    return "FLAT" if abs(pct) < FLAT_MOVE_PCT else ("UP" if pct > 0 else "DOWN")


def _returns(obs: MarketObservation | None, impact: AssetImpact | None, run: AnalysisRun) -> dict[str, Any]:
    if obs is None:
        code = (impact.market_data_reason_code if impact else None) or (
            LimitationCode.NOT_REQUESTED if run.market_data_provider else LimitationCode.NOT_CONFIGURED)
        return {"status": DataAvailability.UNAVAILABLE.value, "limitation": limitation(code),
                "computed_in_analysis": False, "anchor_date": None, "reference_date": None,
                "reference_close": None, "windows": [], "simulated": False, "notes": []}
    code = obs.reason_code
    if code is None and obs.status != DataAvailability.AVAILABLE.value:
        # Runs recorded before reason codes existed: derive from the stored window statuses.
        statuses = {w.get("status") for w in obs.windows}
        text = " ".join(obs.notes)
        code = (LimitationCode.NOT_CONFIGURED if "not configured" in text
                else LimitationCode.NO_PROVIDER_COVERAGE if "symbol mapping" in text or "not found" in text
                else LimitationCode.PROVIDER_ERROR if "provider error" in text
                else LimitationCode.MISSING_OBSERVATIONS if "MISSING" in statuses or not statuses
                else LimitationCode.NOT_YET_ELAPSED if "NOT_YET_ELAPSED" in statuses else None)
    return {
        "status": obs.status,
        "limitation": limitation(code, "; ".join(obs.notes) or None) if code else None,
        "computed_in_analysis": True, "provider": obs.provider, "symbol": obs.symbol,
        "anchor_date": obs.anchor_date.isoformat() if obs.anchor_date else None,
        "reference_date": obs.reference_date.isoformat() if obs.reference_date else None,
        "reference_close": obs.reference_close, "windows": obs.windows, "simulated": obs.is_simulated,
        "notes": obs.notes,
    }


def _historical_context(impact: AssetImpact | None, hist_rows: dict[str, HistoricalEvent],
                        asset_name: str) -> dict[str, Any]:
    hc = (impact.historical_comparison if impact else None) or {}
    comparisons = []
    for c in hc.get("comparisons", []):
        h = hist_rows.get(c["historical_event_id"])
        pct = c.get("return_pct")
        comparisons.append({
            "historical_event_id": c["historical_event_id"], "title": c["title"], "event_date": c["event_date"],
            "source_type": c.get("source_type"), "verification_note": h.verification_note if h else None,
            "relevant_asset": asset_name, "window_trading_days": hc.get("comparison_window_trading_days", 5),
            "reference_date": c.get("reference_date"), "observed_return_pct": pct,
            "observed_direction": _direction(pct),
            "path_implied_direction": {1: "UP", -1: "DOWN"}.get(c.get("predicted_sign")),
            "consistent_with_path": None if c.get("consistency") is None else c["consistency"] == 1.0,
            "consistency_score": c.get("consistency"), "status": c.get("status"),
            "limitation": limitation(c.get("reason_code")) if c.get("reason_code") else None,
            "notes": c.get("notes", []),
        })
    limits = [hc.get("caveat") or "Historical co-movement is context, not proof of causation.",
              "Comparisons use one 5-trading-day window and do not control for concurrent events, "
              "market regime or the size of the shock.",
              "Past events are matched on a shared driver variable with a known direction, not on headlines."]
    if any(c["source_type"] == "CURATED_REFERENCE" for c in comparisons):
        limits.append("Reference events are hand-curated; verify their dates and details.")
    limits += hc.get("notes", [])
    return {"status": hc.get("status", "NOT_REQUESTED"), "historical_support": hc.get("historical_support"),
            "seed_variable": hc.get("seed_variable"), "comparisons": comparisons, "limitations": limits,
            "flat_move_threshold_pct": hc.get("flat_move_threshold_pct", FLAT_MOVE_PCT)}


def _markers(returns: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    if returns.get("reference_date"):
        out.append({"kind": "REFERENCE", "date": returns["reference_date"], "label": "Pre-event reference close",
                    "window_trading_days": None})
    if returns.get("anchor_date"):
        out.append({"kind": "EVENT", "date": returns["anchor_date"],
                    "label": "Event information date (exchange time zone)", "window_trading_days": None})
    for w in returns.get("windows", []):
        if w.get("end_date"):
            out.append({"kind": "WINDOW_END", "date": w["end_date"],
                        "label": f"End of {w['window_trading_days']}-trading-day window",
                        "window_trading_days": w["window_trading_days"]})
    return out


LIMITATION_PRIORITY = [c.value for c in (
    LimitationCode.NOT_CONFIGURED, LimitationCode.NO_PROVIDER_COVERAGE, LimitationCode.PROVIDER_ERROR,
    LimitationCode.FUTURE_RANGE, LimitationCode.MISSING_OBSERVATIONS, LimitationCode.NOT_YET_ELAPSED,
    LimitationCode.NOT_REQUESTED)]


def _overall(chart: dict[str, Any], returns: dict[str, Any]) -> tuple[str, dict | None]:
    statuses = {chart["status"], returns["status"]}
    if statuses == {"AVAILABLE"}:
        return "AVAILABLE", None
    # Report the most fundamental cause: configuration > coverage > outage > data/timing.
    lims = [x for x in (chart.get("limitation"), returns.get("limitation")) if x]
    lim = min(lims, key=lambda x: LIMITATION_PRIORITY.index(x["code"])) if lims else None
    if statuses == {"UNAVAILABLE"}:
        return "UNAVAILABLE", lim
    return "PARTIALLY_AVAILABLE", lim


async def build_event_market_view(
    session: Session, event: Event, run: AnalysisRun, kb: KnowledgeBase, settings: Settings,
    provider: MarketDataProvider | None, *, asset_id: str | None = None, limit: int = 8,
    pre_days: int = 30, post_days: int = 45, include_bars: bool = True,
) -> dict[str, Any]:
    if provider is None and run.market_data_provider:
        provider = CacheOnlyProvider(run.market_data_provider)  # type: ignore[assignment]
    service = MarketDataService(session, provider, kb, settings)
    stmt = select(AssetImpact).where(AssetImpact.analysis_run_id == run.id).order_by(AssetImpact.best_path_score.desc())
    if asset_id:
        stmt = stmt.where(AssetImpact.asset_id == asset_id)
    impacts = session.scalars(stmt.limit(limit)).all()
    obs = session.scalars(select(MarketObservation).where(MarketObservation.analysis_run_id == run.id,
                                                          MarketObservation.observation_kind == "CURRENT_EVENT")).all()
    obs_by_asset = {o.asset_id: o for o in obs}
    hist_rows = {h.id: h for h in session.scalars(select(HistoricalEvent)).all()}
    info_time = event.first_reported_at or (
        datetime.combine(event.event_date, datetime.min.time(), tzinfo=timezone.utc) if event.event_date else None)

    assets_out = []
    for imp in impacts:
        asset = session.get(Asset, imp.asset_id)
        if asset is None:
            continue
        returns = _returns(obs_by_asset.get(imp.asset_id), imp, run)
        if returns.get("anchor_date"):
            anchor = date.fromisoformat(returns["anchor_date"])
        elif info_time is not None:
            anchor = anchor_date_for(info_time, asset.exchange_timezone)
        else:
            anchor = datetime.now(timezone.utc).date()
        chart = await build_price_chart(service, imp.asset_id, anchor - timedelta(days=pre_days),
                                        anchor + timedelta(days=post_days))
        chart["markers"] = _markers(returns) or [
            {"kind": "EVENT", "date": anchor.isoformat(), "label": "Event information date (exchange time zone)",
             "window_trading_days": None}]
        if not include_bars:
            chart["bars"] = []
        status, lim = _overall(chart, returns)
        name = kb.node_label(imp.asset_id)
        assets_out.append({
            "summary": {
                "asset_id": asset.id, "name": asset.name, "symbol": chart["symbol"] or returns.get("symbol"),
                "all_provider_symbols": {s.provider: s.symbol for s in asset.symbols},
                "asset_type": asset.asset_type, "exchange": asset.exchange, "exchange_timezone": asset.exchange_timezone,
                "country": asset.country, "currency": asset.currency, "quote_semantics": asset.quote_semantics,
                "provider": chart["provider"], "impact_direction": imp.impact_direction,
                "best_path_score": imp.best_path_score,
            },
            "availability": {"status": status, "limitation": lim},
            "latest_observation": chart["latest_observation"],
            "freshness": chart["freshness"],
            "chart": chart,
            "returns": returns,
            "historical_context": _historical_context(imp, hist_rows, name),
        })
    session.commit()  # persist any newly cached bars
    return {
        "event_id": event.id, "event_title": event.title, "analysis_id": run.id, "mode": run.mode,
        "event_date": event.event_date.isoformat() if event.event_date else None,
        "first_reported_at": event.first_reported_at.isoformat() if event.first_reported_at else None,
        "market_data_provider": provider.name if provider is not None and getattr(provider, "live", True) else None,
        "market_data_provider_at_analysis": run.market_data_provider,
        "event_windows_trading_days": (run.config or {}).get("market_event_windows", settings.market_event_windows),
        "window_definitions": WINDOW_DEFINITIONS,
        "availability_legend": AVAILABILITY_LEGEND,
        "limitation_codes": limitation_legend(),
        "notes": ["Prices come only from the market-data provider or its local cache; nothing is interpolated.",
                  "Returns are the values computed during the analysis run and are not price predictions."],
        "assets": assets_out,
    }
