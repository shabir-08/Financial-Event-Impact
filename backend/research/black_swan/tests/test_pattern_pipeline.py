"""Tests for the pattern-tracking data pipeline: baseline integrity, feature timing, event responses,
training dataset v2 and the exported pattern library."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
OUT = HERE / "output"
sys.path.insert(0, str(HERE / "pipeline"))
sys.path.insert(0, str(REPO))

import market_features as mf  # noqa: E402
from compute import load_series  # noqa: E402

BASELINE_SHA = "4cc595053b894f8d655ad224978310c06069d53cb527bb32a58bc06642208b7e"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def series():
    return load_series()


def test_baseline_unchanged():
    assert sha(OUT / "model_training_final.csv") == BASELINE_SHA
    inv = json.loads((OUT / "data_inventory.json").read_text(encoding="utf-8"))
    assert inv["baseline"]["sha256"] == BASELINE_SHA and inv["baseline"]["shape"] == [493, 39]


def test_source_hashes_recorded():
    prov = json.loads((OUT / "market_features_provenance.json").read_text(encoding="utf-8"))
    for name, h in prov["raw_hashes"].items():
        assert sha(HERE / "data" / "raw" / name) == h
    assert prov["baseline_sha256"] == BASELINE_SHA


def test_baseline_equivalent_features_match_baseline():
    b = pd.read_csv(OUT / "model_training_final.csv")
    w = pd.read_csv(OUT / "market_features_weekly.csv")
    assert (b.week_start == w.week_start).all() and (b.week_end == w.week_end).all()
    for c in mf.BASELINE_EQUIVALENT:
        assert float(np.nanmax(np.abs(b[c] - w[c]))) < 1e-3, c


def test_features_do_not_use_future_data(series):
    """Changing every observation after the cut-off must leave the features unchanged."""
    sessions = list(series["NIFTY50"].dropna().index)
    for d0 in (date(2018, 9, 24), date(2020, 3, 23), date(2022, 2, 24), date(2025, 4, 7)):
        d0 = max(d for d in sessions if d <= d0)
        clean = mf.compute_features(series, sessions, [d0]).iloc[0]
        tampered = {}
        for sym, s in series.items():
            s = s.copy()
            future = (s.index > d0) if sym in mf.NSE_SYMS else (s.index >= d0)  # foreign d0 prints are after 15:30 IST
            s[future] = s[future] * 3 + 7
            tampered[sym] = s
        dirty = mf.compute_features(tampered, sessions, [d0]).iloc[0]
        for c in [c for c in clean.index if c.startswith("x_")]:
            assert clean[c] == pytest.approx(dirty[c], nan_ok=True), (d0, c)


def test_source_observation_dates_precede_cutoff():
    d = pd.read_csv(OUT / "market_features_daily.csv")
    for sym in mf.NSE_SYMS:
        assert (d[f"src_{sym.lower()}_date"] <= d.date).all()
    for sym in mf.FOREIGN_SYMS:
        assert (d[f"src_{sym.lower()}_date"] < d.date).all()


def test_insufficient_history_is_nan_not_zero(series):
    s = pd.read_csv(OUT / "market_features_schema.csv")
    assert set(s.role) == {"baseline_equivalent", "feature", "outcome_descriptor"}
    sessions = list(series["NIFTY50"].dropna().index)
    early = mf.compute_features(series, sessions, [sessions[10]]).iloc[0]  # only 10 sessions of history
    for c in ("x_nifty_prev_20d_ret_pct", "x_nifty_prev_60d_ret_pct", "x_nifty_prev_60d_vol_ann_pct",
              "x_nifty_max_drawdown_60d_pct", "x_brent_20d_ret_pct", "x_ust10y_20d_chg_bp"):
        assert np.isnan(early[c]), c


def test_training_v2_preserves_baseline_and_has_no_leaky_columns():
    b = pd.read_csv(OUT / "model_training_final.csv")
    v2 = pd.read_csv(OUT / "model_training_v2.csv")
    pd.testing.assert_frame_equal(v2[b.columns], b)
    assert not [c for c in v2.columns if c.startswith(("o_", "s_"))]
    assert "x_is_black_swan" not in v2.columns
    assert v2.y_niftypharma_5d_ret_pct.isna().sum() == 2  # missing targets stay missing


def test_event_responses_match_source_and_timing():
    er = pd.read_csv(OUT / "historical_event_responses.csv")
    em = pd.read_csv(OUT / "events_master.csv")
    emr = pd.read_csv(OUT / "event_market_returns.csv")
    assert len(er) == len(em) == 51 and (er.event_id == em.event_id).all()
    prov = json.loads((OUT / "historical_event_responses_provenance.json").read_text(encoding="utf-8"))
    assert prov["events_master_sha256"] == sha(OUT / "events_master.csv") and prov["events_added"] == 0
    for e in er.itertuples():
        src = emr[(emr.event_id == e.event_id) & (emr.asset_symbol == "NIFTY50") & (emr.window_trading_days == 5)].iloc[0]
        if src.window_status == "AVAILABLE":
            assert e.nifty_5d_return_pct == pytest.approx(src.percentage_return)
        else:
            assert np.isnan(e.nifty_5d_return_pct)
        # pre-event conditions are read at the baseline close, which is at or before the information time
        assert pd.Timestamp(e.nifty_baseline_date).date() <= pd.Timestamp(e.info_time_utc).date()


def test_pattern_library_contents():
    lib = json.loads((REPO / "data" / "patterns" / "pattern_library_v1.json").read_text(encoding="utf-8"))
    cols = lib["weekly"]["columns"]
    assert len(lib["weekly"]["rows"]) == 493 and len(lib["event_responses"]["rows"]) == 51
    assert "x_is_black_swan" not in cols and "event_regime_ex_post" in cols
    groups = {m["group"] for m in lib["feature_meta"].values()}
    assert groups == {"condition", "shock", "target", "outcome_descriptor"}
    assert lib["latest_conditions"]["as_of_session"] == pd.read_csv(OUT / "market_features_daily.csv").date.iloc[-1]
    for name, h in lib["provenance"]["sources"].items():
        assert sha(OUT / name) == h, name


def test_regime_labels_use_start_of_week_information_only():
    from app.services.patterns.regimes import REQUIRED, classify

    lib = json.loads((REPO / "data" / "patterns" / "pattern_library_v1.json").read_text(encoding="utf-8"))
    cols = lib["weekly"]["columns"]
    for row in lib["weekly"]["rows"][:60]:
        r = dict(zip(cols, row))
        cond = {k: r[k] for k in REQUIRED}  # condition features only; targets/outcomes withheld
        lab = classify(cond)
        assert (lab["volatility_regime"], lab["trend_regime"]) == (r["volatility_regime"], r["trend_regime"])
    assert all(lib["feature_meta"][f]["group"] == "condition" for f in REQUIRED)
