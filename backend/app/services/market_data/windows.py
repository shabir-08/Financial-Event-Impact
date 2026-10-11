"""Event-window return calculations (pure functions over a PriceSeries).

Definitions
-----------
* anchor date: the event's information time (earliest article timestamp, else the event date)
  converted to the asset's exchange time zone, taken as a calendar date.
* reference close: the last available close on a trading day STRICTLY BEFORE the anchor date.
  Because intraday timing is unknown, this is a pre-event baseline; it means the window may
  include price moves that occurred on the anchor date before the news broke.
* window k: the close on the k-th trading session on or after the anchor date (session 1 is the
  anchor date itself if it is a trading day). Trading days are the dates present in the provider's
  series, so exchange holidays/weekends are skipped automatically per market.
* return = close_k / reference_close - 1, in the asset's quote currency (no FX conversion).
Missing data is reported, never interpolated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.domain import DataAvailability
from app.services.market_data.base import PriceSeries
from app.services.market_data.quality import LimitationCode

STALE_REFERENCE_DAYS = 7


@dataclass
class WindowReturn:
    window: int
    end_date: date | None
    end_close: float | None
    return_pct: float | None
    status: str  # AVAILABLE | NOT_YET_ELAPSED | MISSING


@dataclass
class EventWindowResult:
    status: DataAvailability
    anchor_date: date | None
    reference_date: date | None
    reference_close: float | None
    windows: list[WindowReturn]
    notes: list[str] = field(default_factory=list)
    reason_code: LimitationCode | None = None

    def window(self, k: int) -> WindowReturn | None:
        return next((w for w in self.windows if w.window == k), None)

    def to_json(self) -> list[dict]:
        return [
            {"window_trading_days": w.window, "end_date": w.end_date.isoformat() if w.end_date else None,
             "end_close": w.end_close, "return_pct": w.return_pct, "status": w.status}
            for w in self.windows
        ]


def anchor_date_for(info_time: datetime | date, exchange_tz: str | None) -> date:
    if isinstance(info_time, datetime):
        aware = info_time if info_time.tzinfo else info_time.replace(tzinfo=timezone.utc)
        try:
            tz = ZoneInfo(exchange_tz or "UTC")
        except Exception:  # noqa: BLE001
            tz = ZoneInfo("UTC")
        return aware.astimezone(tz).date()
    return info_time


def event_window_returns(series: PriceSeries, anchor: date, windows: list[int],
                         today: date | None = None) -> EventWindowResult:
    today = today or datetime.now(timezone.utc).date()
    if series.empty:
        return EventWindowResult(DataAvailability.UNAVAILABLE, anchor, None, None,
                                 [WindowReturn(k, None, None, None, "MISSING") for k in windows],
                                 ["no price observations available"] + series.notes,
                                 LimitationCode.MISSING_OBSERVATIONS)
    closes = series.frame["close"].dropna()
    dates = list(closes.index)
    before = [d for d in dates if d < anchor]
    after = [d for d in dates if d >= anchor]
    notes = list(series.notes)
    if not before:
        return EventWindowResult(DataAvailability.UNAVAILABLE, anchor, None, None,
                                 [WindowReturn(k, None, None, None, "MISSING") for k in windows],
                                 notes + ["no observation before the anchor date to use as reference"],
                                 LimitationCode.MISSING_OBSERVATIONS)
    ref_date = before[-1]
    ref_close = float(closes.loc[ref_date])
    if (anchor - ref_date).days > STALE_REFERENCE_DAYS:
        notes.append(f"reference close is {(anchor - ref_date).days} days before the anchor date (gap in data)")
    out = []
    for k in windows:
        if len(after) >= k:
            d = after[k - 1]
            c = float(closes.loc[d])
            out.append(WindowReturn(k, d, c, round((c / ref_close - 1) * 100, 4), "AVAILABLE"))
        else:
            # Series runs up to (about) today -> the window simply has not elapsed yet.
            status = "NOT_YET_ELAPSED" if dates[-1] >= today - timedelta(days=5) else "MISSING"
            out.append(WindowReturn(k, None, None, None, status))
    n_ok = sum(1 for w in out if w.status == "AVAILABLE")
    if not after and all(w.status == "NOT_YET_ELAPSED" for w in out):
        notes.append("no trading session has occurred on or after the anchor date yet; windows have not elapsed")
    status = (DataAvailability.AVAILABLE if n_ok == len(out)
              else DataAvailability.PARTIALLY_AVAILABLE if n_ok else DataAvailability.UNAVAILABLE)
    statuses = {w.status for w in out}
    code = (LimitationCode.MISSING_OBSERVATIONS if "MISSING" in statuses
            else LimitationCode.NOT_YET_ELAPSED if "NOT_YET_ELAPSED" in statuses else None)
    return EventWindowResult(status, anchor, ref_date, ref_close, out, notes, code)
