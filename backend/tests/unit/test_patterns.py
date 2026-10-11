"""Historical pattern logic on synthetic data: analogue search, standardisation, regimes, event grouping."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.patterns import analogues
from app.services.patterns.events import summarize
from app.services.patterns.regimes import classify, spells


def week(i: int, **vals) -> dict:
    ws = date(2018, 1, 1) + timedelta(weeks=i)
    return {"week_start": ws.isoformat(), "week_end": (ws + timedelta(days=7)).isoformat(),
            "cv_group": f"NORMAL_{ws.year}", **vals}


ROWS = [week(i, a=float(i), b=float(i % 7) * 100, y=float(i) / 10) for i in range(60)]


class TestAnalogues:
    def test_pool_excludes_outcomes_after_as_of(self):
        as_of = date.fromisoformat(ROWS[20]["week_end"])
        r = analogues.search(ROWS, {"a": 59.0, "b": 0.0}, ["a", "b"], ["y"], 5, as_of)
        assert r.pool_size == 21
        assert all(date.fromisoformat(x["week_end"]) <= as_of for x in r.analogues)

    def test_standardisation_makes_scale_irrelevant(self):
        as_of = date(2030, 1, 1)
        r1 = analogues.search(ROWS, {"a": 30.0, "b": 300.0}, ["a", "b"], ["y"], 8, as_of)
        scaled = [{**x, "b": x["b"] * 1000} for x in ROWS]
        r2 = analogues.search(scaled, {"a": 30.0, "b": 300000.0}, ["a", "b"], ["y"], 8, as_of)
        assert [x["week_start"] for x in r1.analogues] == [x["week_start"] for x in r2.analogues]
        assert [x["distance"] for x in r1.analogues] == pytest.approx([x["distance"] for x in r2.analogues])

    def test_exact_match_ranks_first_with_zero_distance(self):
        r = analogues.search(ROWS, {"a": 12.0, "b": ROWS[12]["b"]}, ["a", "b"], ["y"], 3, date(2030, 1, 1))
        assert r.analogues[0]["week_start"] == ROWS[12]["week_start"] and r.analogues[0]["distance"] == 0
        assert r.analogues[0]["outcomes"]["y"] == pytest.approx(1.2)

    def test_out_of_range_and_weak_warnings(self):
        r = analogues.search(ROWS, {"a": 500.0, "b": 0.0}, ["a", "b"], ["y"], 5, date(2030, 1, 1))
        codes = {w["code"] for w in r.warnings}
        assert {"outside_historical_range", "weak_analogues"} <= codes
        assert r.feature_ranges["a"]["within_historical_range"] is False

    def test_missing_indicators_excluded_and_counted(self):
        rows = [*ROWS[:10], week(70, a=None, b=1.0, y=0.0), week(71, a=float("nan"), b=1.0, y=0.0)]
        r = analogues.search(rows, {"a": 1.0, "b": 1.0}, ["a", "b"], ["y"], 5, date(2030, 1, 1))
        assert r.excluded_missing == 2 and r.pool_size == 12

    def test_adjacent_weeks_are_one_cluster_and_small_samples_withhold_statistics(self):
        r = analogues.search(ROWS[:8], {"a": 3.0, "b": 0.0}, ["a", "b"], ["y"], 8, date(2030, 1, 1))
        assert r.n_clusters == 1  # consecutive weeks: one episode
        assert r.statistics is None and "insufficient_sample" in {w["code"] for w in r.warnings}

    def test_statistics_when_sample_sufficient(self):
        spread = ROWS[::6]  # weeks six apart -> separate clusters
        r = analogues.search(spread, {"a": 30.0, "b": 0.0}, ["a", "b"], ["y"], 10, date(2030, 1, 1))
        assert r.n_clusters == 10 and r.statistics is not None
        s = r.statistics["y"]
        assert s["n"] == 10 and s["share_positive"] + s["share_negative"] <= 1

    def test_describe_ignores_missing(self):
        assert analogues.describe([1.0, None, float("nan"), 3.0])["n"] == 2


class TestRegimes:
    @pytest.mark.parametrize("vol,label", [(8, "low_volatility"), (12, "elevated_volatility"), (19.9, "elevated_volatility"),
                                           (20, "high_volatility")])
    def test_volatility(self, vol, label):
        f = {"x_nifty_prev_20d_vol_ann_pct": vol, "x_nifty_prev_60d_ret_pct": 0, "x_nifty_max_drawdown_60d_pct": -2,
             "x_nifty_rebound_from_60d_trough_pct": 1}
        assert classify(f)["volatility_regime"] == label

    def test_trend_and_recovery(self):
        base = {"x_nifty_prev_20d_vol_ann_pct": 15, "x_nifty_max_drawdown_60d_pct": -3, "x_nifty_rebound_from_60d_trough_pct": 2}
        assert classify({**base, "x_nifty_prev_60d_ret_pct": 9})["trend_regime"] == "strong_uptrend"
        assert classify({**base, "x_nifty_prev_60d_ret_pct": -9})["trend_regime"] == "strong_downtrend"
        assert classify({**base, "x_nifty_prev_60d_ret_pct": 1})["trend_regime"] == "no_strong_trend"
        rec = {**base, "x_nifty_prev_60d_ret_pct": -9, "x_nifty_max_drawdown_60d_pct": -15, "x_nifty_rebound_from_60d_trough_pct": 6}
        assert classify(rec)["trend_regime"] == "recovery_after_drawdown"

    def test_missing_inputs_give_none_and_labels_are_reproducible(self):
        assert classify({}) == {"volatility_regime": None, "trend_regime": None}
        f = {"x_nifty_prev_20d_vol_ann_pct": 25, "x_nifty_prev_60d_ret_pct": -10, "x_nifty_max_drawdown_60d_pct": -12,
             "x_nifty_rebound_from_60d_trough_pct": 1}
        assert classify(f) == classify(dict(f))
        assert classify({**f, "y_nifty50_5d_ret_pct": -50, "o_nifty_window_max_drawdown_pct": -40}) == classify(f)

    def test_spells(self):
        assert spells(["a", "a", "b", "a", None, "a"]) == 4


def test_event_summary_uses_one_event_per_episode():
    evs = [{"event_id": "E1", "event_name": "x", "episode_id": "EP1", "event_class": "B", "info_time_utc": "2020-01-01",
            "nifty_5d_return_pct": -10.0, "overlaps_other_events": True},
           {"event_id": "E2", "event_name": "y", "episode_id": "EP1", "event_class": "B", "info_time_utc": "2020-01-05",
            "nifty_5d_return_pct": 99.0, "overlaps_other_events": False},
           *[{"event_id": f"E{i}", "event_name": "z", "episode_id": f"EP{i}", "event_class": "B", "info_time_utc": f"202{i}-01-01",
              "nifty_5d_return_pct": float(i)} for i in (2, 3)]]
    g = summarize(evs, "event_class")[0]
    assert g["n_events"] == 4 and g["n_independent_episodes"] == 3 and g["sample_sufficient"]
    st = g["episode_statistics"]["nifty_5d_return_pct"]
    assert st["n"] == 3 and st["max"] == 3.0  # E2 (same episode, later) excluded from statistics
    assert g["n_events_with_overlapping_windows"] == 1
    small = summarize(evs[:2], "event_class")[0]
    assert not small["sample_sufficient"] and small["episode_statistics"] is None
