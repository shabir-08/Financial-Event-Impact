"""Phase F: evaluate the v2 features and the scenario-conditional feature sets under the baseline protocol.

Same partitions, folds, grids, metrics and bootstrap as train_candidates.py. Experiments:
  forecast_v2          model_training_v2.csv (39 trailing features): ridge, RF, XGBoost, kNN analogue
  forecast_v1_knn      baseline 14 features: kNN analogue only (the other baseline models already exist)
  scenario_s5          5 same-week shocks (scenario_conditional_v1's inputs): ridge, RF, kNN
  scenario_s5_cond     5 shocks + 5 trailing conditions: ridge, RF, kNN

DECISION RULES (fixed before any of these experiments was run):
  R1 forecast: v2 counts as an improvement only if (a) its validation-selected model has a lower validation
     MAE than the baseline's selected model (ridge, 3.1747), (b) on test its MAE vs the zero baseline has a
     95% week-block bootstrap CI entirely below 0, and (c) the paired test difference vs the baseline ridge
     predictions has a 95% CI entirely below 0. Otherwise forecast_trailing_v2 stays the forecasting model.
  R2 scenario: scenario_s5_cond replaces the s5 feature set only if its validation-selected model beats the
     s5 validation-selected model on validation AND the paired test difference has a 95% CI entirely below 0.
     Otherwise scenario_conditional_v1 stays.
  Test results are computed once per experiment and never used to change features, grids or models.

    python pipeline/run_v2_experiments.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import train_candidates as tc  # noqa: E402

OUT = tc.HERE / "output"
DEST = OUT / "model_selection_v2"
CONDITIONS = ["x_nifty_prev_20d_vol_ann_pct", "x_nifty_prev_60d_ret_pct", "x_nifty_drawdown_from_60d_peak_pct",
              "x_vix_level_at_start", "x_nifty_prev_20d_ret_pct"]
SHOCKS = ["s_brent_5d_ret_pct_in_target_window", "s_sp500_5d_ret_pct_in_target_window", "s_usdinr_5d_ret_pct_in_target_window",
          "s_gold_5d_ret_pct_in_target_window", "s_ust10y_5d_chg_bp_in_target_window"]


def paired_bootstrap(Y: np.ndarray, A: np.ndarray, B: np.ndarray, seed: int) -> dict:
    """95% CI of MAE(A) - MAE(B) on the same test weeks, resampling whole weeks."""
    rng = np.random.default_rng(seed)
    m = np.isfinite(Y)
    ea, eb = np.abs(A - Y), np.abs(B - Y)
    n = len(Y)
    d = []
    for _ in range(tc.N_BOOT):
        i = rng.integers(0, n, n)
        mm = m[i]
        d.append(ea[i][mm].mean() - eb[i][mm].mean())
    lo, hi = np.percentile(d, [2.5, 97.5])
    return {"mae_diff": float(ea[m].mean() - eb[m].mean()), "ci95": [float(lo), float(hi)], "n_weeks": n}


def preds(path: Path, model: str, targs: list[str]) -> np.ndarray:
    tp = pd.read_csv(path)
    return tp[[f"{model}__{t}" for t in targs]].to_numpy()


def main() -> dict:
    DEST.mkdir(parents=True, exist_ok=True)
    base = pd.read_csv(tc.CSV)
    v2 = pd.read_csv(OUT / "model_training_v2.csv")
    scen = pd.read_csv(OUT / "model_training_final_scenario_inputs.csv")
    v2_feats = [c for c in v2.columns if c.startswith("x_")]
    sframe = v2.merge(scen[["week_start", "week_end", *SHOCKS]], on=["week_start", "week_end"], validate="one_to_one")
    ridge_rf_knn = {"ridge": tc.GRIDS["ridge"], "random_forest": tc.GRIDS["random_forest"], **tc.EXTRA_GRIDS}
    runs = {
        "forecast_v2": (v2, v2_feats, {**tc.GRIDS, **tc.EXTRA_GRIDS}, [OUT / "model_training_v2.csv"]),
        "forecast_v1_knn": (base, [c for c in base.columns if c.startswith("x_")], tc.EXTRA_GRIDS, [tc.CSV]),
        "scenario_s5": (sframe, SHOCKS, ridge_rf_knn, [tc.CSV, OUT / "model_training_final_scenario_inputs.csv"]),
        "scenario_s5_cond": (sframe, SHOCKS + CONDITIONS, ridge_rf_knn,
                             [OUT / "model_training_v2.csv", OUT / "model_training_final_scenario_inputs.csv"]),
    }
    results = {}
    for name, (frame, feats, grids, src) in runs.items():
        print(f"== {name}: {len(feats)} features, models {list(grids)}", flush=True)
        results[name] = tc.main(frame=frame, feats=feats, dest=DEST / name, grids=grids, label=name, source_files=src)

    test = base[base.split == "test"]
    targs = [c for c in base.columns if c.startswith("y_")]
    Y = test[targs].to_numpy()
    base_sel = json.loads((OUT / "model_selection" / "model_selection_summary.json").read_text())
    # baseline ridge refitted deterministically with its selected params (the baseline run predates test_predictions.csv)
    bx = [c for c in base.columns if c.startswith("x_")]
    train = base[base.split == "train"]
    base_ridge = tc.FittedModel("ridge", base_sel["validation"]["ridge"]["best_params"], targs).fit(
        train[bx], train[targs]).predict(test[bx])
    assert abs(float(np.nanmean(np.abs(base_ridge - Y))) - base_sel["test"]["ridge"]["pooled"]["mae"]) < 1e-9

    f = results["forecast_v2"]
    sel = f["selected_model"]
    r1 = {"baseline_selected_validation_mae": base_sel["validation"]["ridge"]["mae"], "v2_selected": sel}
    if sel != "zero_baseline":
        P = preds(DEST / "forecast_v2" / "test_predictions.csv", sel, targs)
        r1.update(v2_selected_validation_mae=f["validation"][sel]["mae"],
                  a_validation_better=f["validation"][sel]["mae"] < base_sel["validation"]["ridge"]["mae"],
                  b_vs_zero=f["test"][sel]["vs_zero_bootstrap"],
                  c_vs_baseline_ridge=paired_bootstrap(Y, P, base_ridge, tc.SEED + 1))
        r1["improvement"] = bool(r1["a_validation_better"] and r1["b_vs_zero"]["ci95"][1] < 0
                                 and r1["c_vs_baseline_ridge"]["ci95"][1] < 0)
    else:
        r1["improvement"] = False
    s5, s5c = results["scenario_s5"], results["scenario_s5_cond"]
    a, b = s5["selected_model"], s5c["selected_model"]
    r2 = {"s5_selected": a, "s5_cond_selected": b}
    if a != "zero_baseline" and b != "zero_baseline":
        r2.update(s5_validation_mae=s5["validation"][a]["mae"], s5_cond_validation_mae=s5c["validation"][b]["mae"],
                  paired_test_s5cond_minus_s5=paired_bootstrap(Y, preds(DEST / "scenario_s5_cond" / "test_predictions.csv", b, targs),
                                                               preds(DEST / "scenario_s5" / "test_predictions.csv", a, targs), tc.SEED + 2))
        r2["replace_scenario_feature_set"] = bool(s5c["validation"][b]["mae"] < s5["validation"][a]["mae"]
                                                  and r2["paired_test_s5cond_minus_s5"]["ci95"][1] < 0)
    else:
        r2["replace_scenario_feature_set"] = False
    out = {"decision_rules": __doc__.split("DECISION RULES")[1].split("python pipeline")[0].strip(),
           "R1_forecast": r1, "R2_scenario": r2,
           "summary": {k: {"selected": v["selected_model"],
                           "validation_mae": {m: (v["validation"][m]["mae"] if isinstance(v["validation"][m], dict) and "mae" in v["validation"][m] else None)
                                              for m in v["validation"] if v["validation"][m] is not None},
                           "test_mae": {m: round(x["pooled"]["mae"], 4) for m, x in v["test"].items()}} for k, v in results.items()}}
    (DEST / "v2_comparison.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = main()
    print(json.dumps({k: r[k] for k in ("R1_forecast", "R2_scenario", "summary")}, indent=1))
