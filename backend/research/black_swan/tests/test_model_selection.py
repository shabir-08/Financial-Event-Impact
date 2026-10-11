"""Tests for the dataset verification, candidate-training protocol and the exported forecast artifact."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / "pipeline"))
sys.path.insert(0, str(REPO))

import train_candidates as tc  # noqa: E402
import verify_training_dataset as vd  # noqa: E402

SEL = HERE / "output" / "model_selection"
ARTIFACT = REPO / "data" / "models" / "forecast_trailing_v2.json"


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return pd.read_csv(tc.CSV)


@pytest.fixture(scope="module")
def summary() -> dict:
    return json.loads((SEL / "model_selection_summary.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def verification() -> dict:
    return vd.main()


def test_primary_csv_unchanged_since_selection(summary):
    assert hashlib.sha256(tc.CSV.read_bytes()).hexdigest() == summary["dataset"]["sha256"]


def test_dataset_structure(df, verification):
    assert df.shape == (493, 39)
    assert verification["split_counts"] == {"train": 308, "test": 185}
    assert len(verification["features"]) == 14 and len(verification["targets"]) == 18
    assert verification["missing_values"] == {"y_niftypharma_5d_ret_pct": 2}
    assert verification["duplicates"] == {"full_rows": 0, "week_start": 0, "feature_vectors": 0}
    assert verification["regime_by_split"]["test"]["BLACK_SWAN"] == 0
    assert verification["regime_by_split"]["train"]["BLACK_SWAN"] == 7


def test_timing_and_alignment(verification):
    assert verification["windows"]["target_window_sessions"] == [5]
    assert verification["windows"]["consecutive_rows_contiguous_non_overlapping"]
    assert not verification["split_boundary"]["target_windows_overlap"]
    assert verification["feature_observations_dated_on_or_after_week_start"] == 0
    assert verification["event_flag_recompute"]["rows_mismatched"] == 0
    assert all(v["max_abs_diff"] < 1e-3 for v in verification["feature_recompute"].values())
    assert all(v["max_abs_diff"] < 1e-3 for v in verification["target_recompute"].values())
    # market features are trailing: they track the previous week's move, not the target week's
    for c in ("x_brent_5d_ret_pct", "x_sp500_5d_ret_pct", "x_usdinr_5d_ret_pct", "x_gold_5d_ret_pct", "x_ust10y_5d_chg_bp"):
        r = verification["feature_recompute"][c]
        assert r["corr_with_previous_row_target_window_move"] > 0.7 > abs(r["corr_with_same_week_move"])


def test_missing_targets_are_masked_not_zero_filled():
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(60, 3)), columns=["a", "b", "c"])
    Y = pd.DataFrame({"t1": X.a * 2 + rng.normal(scale=0.01, size=60), "t2": X.b})
    Y.loc[:9, "t1"] = np.nan  # if zero-filled, the fitted slope would be biased
    fm = tc.FittedModel("ridge", {"alpha": 1e-6}, ["t1", "t2"]).fit(X, Y)
    assert fm.models["t1"].named_steps["model"].coef_[0] == pytest.approx(2 * X.a[10:].std(ddof=0), rel=0.02)
    m = tc.metrics(np.array([1.0, np.nan, -2.0]), np.array([0.5, 9.0, -1.0]))
    assert m["n"] == 2 and m["mae"] == pytest.approx(0.75)


def test_selection_used_validation_only(summary):
    v = summary["validation"]
    cands = {k: v[k]["mae"] for k in ("ridge", "random_forest", "xgboost") if v[k]["beats_zero"]}
    assert summary["selected_model"] == min(cands, key=cands.get)
    assert v["zero_baseline"]["n"] == 18 * 198  # 198 train weeks ending 2019-2022 x 18 targets (no test rows)


def test_artifact_loads_in_backend_and_reproduces_metrics(df, summary):
    from app.services.simulation.inference import _load_artifact

    m = _load_artifact(ARTIFACT)
    assert m.model_id == "forecast_trailing_v2" and m.supports_hypothetical_shocks is False and m.horizon == 5
    assert m.feature_order == summary["dataset"]["features"]
    te = df[df.split == "test"]
    P = m.predict(te[m.feature_order].to_numpy())
    Y = te[[t["column"] for t in m.targets]].to_numpy()
    ok = np.isfinite(Y)
    assert float(np.abs(P - Y)[ok].mean()) == pytest.approx(summary["test"]["ridge"]["pooled"]["mae"], abs=1e-9)
    raw = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert raw["status"] == "no_demonstrated_skill"
    assert raw["provenance"]["source_dataset_sha256"] == summary["dataset"]["sha256"]
