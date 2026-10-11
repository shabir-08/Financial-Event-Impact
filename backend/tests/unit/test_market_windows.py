from datetime import date, datetime, timezone

import pandas as pd
import pytest

from app.domain import DataAvailability
from app.services.market_data.base import PriceSeries, empty_frame
from app.services.market_data.windows import anchor_date_for, event_window_returns


def series(closes: dict[date, float]) -> PriceSeries:
    return PriceSeries("test", "X", pd.DataFrame({"close": list(closes.values())}, index=list(closes.keys())))


# Mon 2026-10-05 anchor; trading days skip the weekend and a holiday on Wed 10-07.
S = series({date(2026, 10, 1): 100.0, date(2026, 10, 2): 100.0, date(2026, 10, 5): 102.0,
            date(2026, 10, 6): 104.0, date(2026, 10, 8): 99.0, date(2026, 10, 9): 101.0})


def test_reference_is_last_close_before_anchor_and_windows_count_sessions():
    r = event_window_returns(S, date(2026, 10, 5), [1, 3, 4], today=date(2026, 10, 11))
    assert r.reference_date == date(2026, 10, 2) and r.reference_close == 100.0
    assert r.window(1).return_pct == pytest.approx(2.0)
    assert r.window(3).end_date == date(2026, 10, 8)  # holiday 10-07 skipped
    assert r.window(3).return_pct == pytest.approx(-1.0)
    assert r.status == DataAvailability.AVAILABLE


def test_weekend_anchor_starts_on_next_session():
    r = event_window_returns(S, date(2026, 10, 3), [1], today=date(2026, 10, 11))  # Saturday
    assert r.reference_date == date(2026, 10, 2) and r.window(1).end_date == date(2026, 10, 5)


def test_partial_when_window_not_elapsed():
    r = event_window_returns(S, date(2026, 10, 5), [1, 20], today=date(2026, 10, 11))
    assert r.status == DataAvailability.PARTIALLY_AVAILABLE
    assert r.window(20).status == "NOT_YET_ELAPSED" and r.window(20).return_pct is None


def test_no_reference_is_unavailable_not_fabricated():
    r = event_window_returns(S, date(2026, 9, 1), [1], today=date(2026, 10, 11))
    assert r.status == DataAvailability.UNAVAILABLE and r.reference_close is None


def test_empty_series_unavailable():
    r = event_window_returns(PriceSeries("t", "X", empty_frame()), date(2026, 10, 5), [1, 5])
    assert r.status == DataAvailability.UNAVAILABLE and all(w.return_pct is None for w in r.windows)


def test_anchor_respects_exchange_timezone():
    t = datetime(2026, 10, 4, 22, 0, tzinfo=timezone.utc)  # Sunday 22:00 UTC = Monday morning in India
    assert anchor_date_for(t, "Asia/Kolkata") == date(2026, 10, 5)
    assert anchor_date_for(t, "America/New_York") == date(2026, 10, 4)


def test_not_yet_elapsed_note_when_no_session_after_anchor():
    r = event_window_returns(S, date(2026, 10, 10), [1, 3], today=date(2026, 10, 11))  # Saturday after last bar
    assert r.status == DataAvailability.UNAVAILABLE
    assert all(w.status == "NOT_YET_ELAPSED" for w in r.windows)
    assert any("not elapsed" in n for n in r.notes)
