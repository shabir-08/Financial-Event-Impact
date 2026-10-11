"""Data-quality vocabulary for market data: limitation codes, window definitions, gaps, freshness.

Everything here is descriptive metadata so a frontend can explain *why* data is missing and
avoid presenting stale observations as current prices. No prices are produced here.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

#: A series whose latest bar is more than this many expected sessions old is flagged stale.
STALE_AFTER_SESSIONS = 2


class LimitationCode(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NO_PROVIDER_COVERAGE = "NO_PROVIDER_COVERAGE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    MISSING_OBSERVATIONS = "MISSING_OBSERVATIONS"
    NOT_YET_ELAPSED = "NOT_YET_ELAPSED"
    FUTURE_RANGE = "FUTURE_RANGE"
    NOT_REQUESTED = "NOT_REQUESTED"


_LIMITATIONS: dict[LimitationCode, tuple[str, str]] = {
    LimitationCode.NOT_CONFIGURED: (
        "integration", "No market-data provider is configured (MARKET_DATA_PROVIDER=none)."),
    LimitationCode.NO_PROVIDER_COVERAGE: (
        "provider_coverage", "The configured provider does not cover this asset (no symbol mapping or no data for the symbol)."),
    LimitationCode.PROVIDER_ERROR: (
        "provider_outage", "The market-data provider failed or rate-limited the request."),
    LimitationCode.MISSING_OBSERVATIONS: (
        "missing_observations", "The provider returned data, but observations needed for this calculation are missing."),
    LimitationCode.NOT_YET_ELAPSED: (
        "timing", "The event is too recent: the required trading sessions have not happened yet."),
    LimitationCode.FUTURE_RANGE: (
        "timing", "The requested date range is in the future."),
    LimitationCode.NOT_REQUESTED: (
        "analysis_scope", "Market data was not requested for this asset in this analysis run "
                          "(outside the top assets analysed)."),
}


def limitation(code: LimitationCode | str | None, detail: str | None = None) -> dict[str, Any] | None:
    if code is None:
        return None
    c = LimitationCode(code)
    source, message = _LIMITATIONS[c]
    return {"code": c.value, "source": source, "message": message, "detail": detail}


def limitation_legend() -> list[dict[str, str]]:
    return [{"code": c.value, "source": s, "message": m} for c, (s, m) in _LIMITATIONS.items()]


AVAILABILITY_LEGEND = {
    "AVAILABLE": "All requested values could be computed from provider data.",
    "PARTIALLY_AVAILABLE": "Some values are available; others are missing or not yet elapsed.",
    "UNAVAILABLE": "No values could be computed; see the limitation code for the reason.",
}

WINDOW_DEFINITIONS: dict[str, str] = {
    "anchor_date": "The event's information time (earliest source-article timestamp, else the event date), "
                   "converted to the asset's exchange time zone, taken as a calendar date.",
    "reference_close": "The last available close on a trading day strictly before the anchor date (pre-event "
                       "baseline). Intraday timing is unknown, so a window may include same-day moves that "
                       "happened before the news.",
    "window_k": "The close of the k-th trading session on or after the anchor date (session 1 = the anchor date "
                "if it is a trading day). Trading days are the dates present in the provider's series, so each "
                "market's weekends and holidays are skipped.",
    "return_pct": "(close at window k / reference close - 1) x 100, in the asset's quote currency; no FX "
                  "conversion. For yield instruments the value is the change in the yield level.",
    "window_status": "AVAILABLE = computed; NOT_YET_ELAPSED = the k-th session has not happened yet; "
                     "MISSING = the session should exist but the provider has no observation.",
    "historical_comparison": "For comparable past events: the 5-trading-day return using the same definitions, "
                             "compared with the direction implied by the impact path. Co-movement is context, "
                             "not proof of causation.",
}


def expected_sessions_between(a: date, b: date, weekend_trading: bool) -> int:
    """Number of calendar days strictly between a and b on which a session would normally occur."""
    n, d = 0, a + timedelta(days=1)
    while d < b:
        if weekend_trading or d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def find_gaps(dates: list[date], weekend_trading: bool = False, start: date | None = None,
              end: date | None = None) -> list[dict[str, Any]]:
    """Periods with no observations where sessions would normally be expected.

    A single missing weekday is flagged ``likely_holiday`` (exchange holidays are not modelled).
    Leading/trailing gaps relative to the requested range are reported separately.
    """
    gaps: list[dict[str, Any]] = []
    ds = sorted(dates)
    if not ds:
        return gaps
    if start is not None:
        lead = expected_sessions_between(start - timedelta(days=1), ds[0], weekend_trading)
        if lead >= 3:
            gaps.append({"kind": "LEADING", "from_date": start.isoformat(), "to_date": ds[0].isoformat(),
                         "missing_sessions": lead, "likely_holiday": False})
    for a, b in zip(ds, ds[1:]):
        missing = expected_sessions_between(a, b, weekend_trading)
        if missing >= 1:
            gaps.append({"kind": "INTERNAL", "from_date": a.isoformat(), "to_date": b.isoformat(),
                         "missing_sessions": missing, "likely_holiday": missing == 1})
    if end is not None:
        trail = expected_sessions_between(ds[-1], end, weekend_trading)
        if trail >= 3:
            gaps.append({"kind": "TRAILING", "from_date": ds[-1].isoformat(), "to_date": end.isoformat(),
                         "missing_sessions": trail, "likely_holiday": False})
    return gaps


def freshness(latest: date | None, today: date, weekend_trading: bool = False,
              retrieved_at: datetime | None = None) -> dict[str, Any]:
    if latest is None:
        return {"latest_observation_date": None, "retrieved_at": retrieved_at, "sessions_since_latest": None,
                "is_stale": None, "latest_may_be_incomplete": False, "usable_as_current_price": False,
                "rule": f"stale if more than {STALE_AFTER_SESSIONS} expected sessions have passed since the latest bar"}
    sessions = expected_sessions_between(latest, today, weekend_trading)
    incomplete = latest >= today  # today's bar may be an in-progress session
    stale = sessions > STALE_AFTER_SESSIONS
    return {
        "latest_observation_date": latest.isoformat(),
        "retrieved_at": retrieved_at,
        "calendar_days_since_latest": (today - latest).days,
        "sessions_since_latest": sessions,
        "is_stale": stale,
        "latest_may_be_incomplete": incomplete,
        "usable_as_current_price": not stale and not incomplete,
        "rule": f"stale if more than {STALE_AFTER_SESSIONS} expected sessions have passed since the latest bar; "
                "a bar dated today may be an incomplete session",
    }
