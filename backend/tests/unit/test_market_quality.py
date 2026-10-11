from datetime import date

import pandas as pd

from app.services.market_data.base import PriceSeries
from app.services.market_data.quality import LimitationCode, find_gaps, freshness, limitation
from app.services.market_data.windows import event_window_returns


def test_single_missing_weekday_is_likely_holiday_multi_day_is_not():
    # Mon 5, Tue 6, (Wed 7 missing), Thu 8, then nothing until Wed 14 (Fri 9, Mon 12, Tue 13 missing)
    ds = [date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 8), date(2026, 10, 14)]
    gaps = find_gaps(ds)
    assert [(g["from_date"], g["missing_sessions"], g["likely_holiday"]) for g in gaps] == [
        ("2026-10-06", 1, True), ("2026-10-08", 3, False)]


def test_weekends_are_not_gaps_unless_market_trades_weekends():
    ds = [date(2026, 10, 9), date(2026, 10, 12)]  # Fri -> Mon
    assert find_gaps(ds) == []
    assert find_gaps(ds, weekend_trading=True)[0]["missing_sessions"] == 2


def test_leading_and_trailing_gaps():
    ds = [date(2026, 10, 12), date(2026, 10, 13)]
    gaps = find_gaps(ds, start=date(2026, 10, 1), end=date(2026, 10, 30))
    assert {g["kind"] for g in gaps} == {"LEADING", "TRAILING"}


def test_freshness_flags_stale_and_incomplete():
    fresh = freshness(date(2026, 10, 9), date(2026, 10, 12))  # Fri bar, Monday today
    assert fresh["is_stale"] is False and fresh["usable_as_current_price"] is True
    stale = freshness(date(2026, 9, 30), date(2026, 10, 12))
    assert stale["is_stale"] is True and stale["usable_as_current_price"] is False
    today_bar = freshness(date(2026, 10, 12), date(2026, 10, 12))
    assert today_bar["latest_may_be_incomplete"] is True and today_bar["usable_as_current_price"] is False
    none = freshness(None, date(2026, 10, 12))
    assert none["usable_as_current_price"] is False and none["is_stale"] is None


def test_limitation_has_source_and_message():
    lim = limitation(LimitationCode.NOT_CONFIGURED, "x")
    assert lim["source"] == "integration" and "configured" in lim["message"] and lim["detail"] == "x"
    assert limitation(None) is None


def test_window_reason_codes():
    s = PriceSeries("t", "X", pd.DataFrame({"close": [1.0, 1.1, 1.2]},
                                           index=[date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 5)]))
    recent = event_window_returns(s, date(2026, 10, 5), [1, 3], today=date(2026, 10, 6))
    assert recent.reason_code == LimitationCode.NOT_YET_ELAPSED
    no_ref = event_window_returns(s, date(2026, 9, 1), [1], today=date(2026, 10, 6))
    assert no_ref.reason_code == LimitationCode.MISSING_OBSERVATIONS
    full = event_window_returns(s, date(2026, 10, 2), [1], today=date(2026, 10, 6))
    assert full.reason_code is None
