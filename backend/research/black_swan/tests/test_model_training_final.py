"""Validation tests for output/model_training_final.csv (run: pytest research/black_swan/tests)."""

from __future__ import annotations

import glob
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
RAW = ROOT / "data" / "raw"
sys.path.insert(0, str(ROOT / "pipeline"))


@pytest.fixture(scope="module")
def f():
    return pd.read_csv(OUT / "model_training_final.csv")


@pytest.fixture(scope="module")
def schema():
    return pd.read_csv(OUT / "model_training_final_schema.csv")


@pytest.fixture(scope="module")
def audit():
    return pd.read_csv(OUT / "model_training_final_audit.csv")


@pytest.fixture(scope="module")
def backup():
    files = sorted(glob.glob(str(OUT / "backups" / "model_training_final.pre_audit_*.csv")))
    assert files, "pre-audit backup missing"
    return pd.read_csv(files[0])


def raw(sym: str) -> pd.Series:
    df = pd.read_csv(RAW / f"{sym}.csv")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.set_index("date")["value"]


# ------------------------------------------------------------------ structure
def test_shape_and_schema(f, schema):
    assert len(f) == 493
    assert list(schema.column) == list(f.columns)
    feats = schema[schema.role == "feature"].column.tolist()
    tgts = schema[schema.role == "target"].column.tolist()
    assert len(feats) == 14 and len(tgts) == 18
    assert all(c.startswith("x_") for c in feats) and all(c.startswith("y_") for c in tgts)
    # every x_ column is a feature, and no id/date/label/target is a feature
    assert set(feats) == {c for c in f.columns if c.startswith("x_")}
    assert not {"week_start", "week_end", "split", "cv_group", "regime", "event_ids", "known_event_ids"} & set(feats)
    assert "x_is_black_swan" not in f.columns  # ex-post label removed from inputs


def test_rows_preserved_vs_backup(f, backup):
    assert (f[["week_start", "week_end", "split"]].values == backup[["week_start", "week_end", "split"]].values).all()
    for c in [c for c in backup.columns if c.startswith("y_")]:
        assert f[c].equals(backup[c]), c
    for c in ["x_vix_level_at_start", "x_nifty_prev_20d_ret_pct", "x_nifty_prev_20d_vol_ann_pct", "regime"]:
        assert f[c].equals(backup[c]), c


def test_no_duplicates_and_ordering(f):
    assert not f.week_start.duplicated().any() and not f.duplicated().any()
    assert f.week_start.is_monotonic_increasing
    assert (pd.to_datetime(f.week_end) > pd.to_datetime(f.week_start)).all()
    # consecutive blocks are adjacent and non-overlapping
    assert (f.week_start.iloc[1:].values == f.week_end.iloc[:-1].values).all()


# ------------------------------------------------------------------ targets
def test_targets_are_next_five_nse_sessions(f):
    nifty = raw("NIFTY50")
    days = list(nifty.index)
    pos = {d: i for i, d in enumerate(days)}
    for r in f.itertuples():
        d0, d1 = date.fromisoformat(r.week_start), date.fromisoformat(r.week_end)
        assert pos[d1] - pos[d0] == 5
        assert r.y_nifty50_5d_ret_pct == pytest.approx(round((nifty[d1] / nifty[d0] - 1) * 100, 4), abs=1e-4)


def test_missing_targets_not_imputed(f):
    pharma = raw("NIFTYPHARMA")
    na = f[f.y_niftypharma_5d_ret_pct.isna()]
    assert len(na) == 2
    for r in na.itertuples():  # missing because the provider has no bar on one endpoint
        assert date.fromisoformat(r.week_start) not in pharma.index or date.fromisoformat(r.week_end) not in pharma.index
    assert (f[[c for c in f.columns if c.startswith("x_")]].isna().sum() == 0).all()


# ------------------------------------------------------------------ feature timing (leakage)
SHOCKS = [("BRENT", "brent", "x_brent_5d_ret_pct"), ("SP500", "sp500", "x_sp500_5d_ret_pct"),
          ("USDINR", "usdinr", "x_usdinr_5d_ret_pct"), ("GOLD", "gold", "x_gold_5d_ret_pct"),
          ("UST10Y", "ust10y", "x_ust10y_5d_chg_bp")]


def test_shock_observations_precede_prediction(audit):
    for _, col, _ in SHOCKS:
        end = pd.to_datetime(audit[f"obs_{col}_end_date"])
        start = pd.to_datetime(audit[f"obs_{col}_start_date"])
        assert (end < pd.to_datetime(audit.week_start_close)).all(), col
        assert (start < pd.to_datetime(audit.feature_window_start_session)).all(), col
    assert (pd.to_datetime(audit.obs_vix_date) < pd.to_datetime(audit.week_start_close)).all()


def test_shock_values_recomputed_from_raw(f, audit):
    for sym, col, xcol in SHOCKS:
        s = raw(sym)
        a = s.loc[pd.to_datetime(audit[f"obs_{col}_start_date"]).dt.date].values
        b = s.loc[pd.to_datetime(audit[f"obs_{col}_end_date"]).dt.date].values
        exp = (b - a) * 100 if col == "ust10y" else (b / a - 1) * 100
        assert np.allclose(f[xcol].values, np.round(exp, 4), atol=1e-3), xcol


def test_shocks_no_longer_contemporaneous_with_target(f, backup):
    # The pre-audit S&P feature was measured over the target week (corr ~0.5 with the Nifty target).
    assert backup.x_sp500_5d_ret_pct.corr(backup.y_nifty50_5d_ret_pct) > 0.4
    assert abs(f.x_sp500_5d_ret_pct.corr(f.y_nifty50_5d_ret_pct)) < 0.2


def test_event_flags_only_use_public_events(f, audit):
    em = pd.read_csv(OUT / "events_master.csv").set_index("event_id")
    for r, a in zip(f.itertuples(), audit.itertuples()):
        ids = [] if pd.isna(r.known_event_ids) else r.known_event_ids.split(";")
        assert r.x_is_event == int(bool(ids))
        pred = datetime.fromisoformat(a.prediction_timestamp_utc)
        for eid, ts in zip(ids, a.known_event_public_at_utc.split(";") if ids else []):
            public = datetime.fromisoformat(ts)
            assert public <= pred, (eid, r.week_start)
            raw_t = datetime.fromisoformat(em.loc[eid, "info_time_utc"].replace("Z", "+00:00"))
            assert public >= raw_t  # never earlier than the recorded information time
        flags = [c for c in f.columns if c.startswith("x_event_")]
        if r.x_is_event == 0:
            assert sum(getattr(r, c) for c in flags) == 0


def test_each_event_mapped_once(f):
    ids = [x for s in f.known_event_ids.dropna() for x in s.split(";")]
    assert len(ids) == len(set(ids))
    em = pd.read_csv(OUT / "events_master.csv")
    assert set(em.event_id) - set(ids) == {"EV051"}  # public after the last complete row (2026-10-07)


# ------------------------------------------------------------------ split / validation
def test_chronological_split(f):
    tr, te = f[f.split == "train"], f[f.split == "test"]
    assert pd.to_datetime(tr.week_end).max() <= pd.to_datetime(te.week_start).min()
    assert (pd.to_datetime(tr.week_end).dt.year <= 2022).all()
    assert (f.regime[f.split == "test"] == "BLACK_SWAN").sum() == 0  # documented limitation


def test_scenario_file_preserves_pre_audit_values(backup):
    sc = pd.read_csv(OUT / "model_training_final_scenario_inputs.csv")
    for old, new in [("x_brent_5d_ret_pct", "s_brent_5d_ret_pct_in_target_window"),
                     ("x_sp500_5d_ret_pct", "s_sp500_5d_ret_pct_in_target_window"),
                     ("x_usdinr_5d_ret_pct", "s_usdinr_5d_ret_pct_in_target_window"),
                     ("x_gold_5d_ret_pct", "s_gold_5d_ret_pct_in_target_window"),
                     ("x_ust10y_5d_chg_bp", "s_ust10y_5d_chg_bp_in_target_window")]:
        assert np.allclose(backup[old], sc[new], equal_nan=True)


def test_preprocessing_fitted_on_training_rows_only():
    from train_model import MaskedRidge

    X = np.arange(20, dtype=float).reshape(10, 2)
    Y = np.column_stack([np.arange(10.0), [np.nan] + list(range(9))])
    m = MaskedRidge().fit(X[:6], Y[:6], 1.0)
    assert np.allclose(m.mu, X[:6].mean(0))          # scaler uses only the rows passed to fit
    assert m.n_used == [6, 5]                         # NaN target masked, not imputed


def test_training_pipeline_loads(f):
    from train_model import load

    df, X, Y = load()
    assert len(df) == len(f) and len(X) == 14 and len(Y) == 18
