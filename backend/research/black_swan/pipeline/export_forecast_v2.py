"""Export the model selected by train_candidates.py as a JSON artifact for the backend.

Reads output/model_selection/model_selection_summary.json, refits the selected Ridge on the TRAIN
partition only (the exact model whose test metrics are reported) and writes
data/models/forecast_trailing_v2.json in the schema loaded by app.services.simulation.inference
(no pickle: plain coefficients, standardisation and metadata).

    python pipeline/export_forecast_v2.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from export_models import MODELS, _targets  # noqa: E402
from train_candidates import CSV, DEST, VAL_YEARS, FittedModel  # noqa: E402

MODEL_ID = "forecast_trailing_v2"


def linear_params(fm: FittedModel, targets: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(mean, sd, intercept[T], W[F,T]) from per-target sklearn Ridge pipelines that share one scaler fit."""
    scalers = [fm.models[t].named_steps["scale"] for t in targets]
    mu, sd = scalers[0].mean_, scalers[0].scale_
    for s in scalers[1:]:  # all train rows have every target, so each per-target scaler saw the same rows
        if not (np.allclose(s.mean_, mu) and np.allclose(s.scale_, sd)):
            raise ValueError("per-target scalers differ; cannot export a single standardisation")
    W = np.column_stack([fm.models[t].named_steps["model"].coef_ for t in targets])
    b = np.array([fm.models[t].named_steps["model"].intercept_ for t in targets])
    return mu, sd, b, W


def main() -> Path:
    summ = json.loads((DEST / "model_selection_summary.json").read_text(encoding="utf-8"))
    if summ["selected_model"] != "ridge":
        raise SystemExit(f"selected model is {summ['selected_model']}; this exporter handles ridge only")
    df = pd.read_csv(CSV)
    sha = hashlib.sha256(CSV.read_bytes()).hexdigest()
    if sha != summ["dataset"]["sha256"]:
        raise SystemExit("training CSV changed since model selection; re-run train_candidates.py")
    X, Y = summ["dataset"]["features"], summ["dataset"]["targets"]
    params = summ["validation"]["ridge"]["best_params"]
    train = df[df.split == "train"]
    if train[X].isna().any().any():
        raise SystemExit("train features contain NaN; the JSON artifact has no imputer")
    fm = FittedModel("ridge", params, Y).fit(train[X], train[Y])
    mu, sd, b, W = linear_params(fm, Y)
    # the exported linear form must reproduce the sklearn model exactly
    assert np.allclose(b + ((train[X].to_numpy() - mu) / sd) @ W, fm.predict(train[X]))

    # empirical intervals from the train-only validation folds (no test data)
    yr = pd.to_datetime(train.week_end).dt.year.to_numpy()
    res = np.vstack([train.loc[yr == v, Y].to_numpy()
                     - FittedModel("ridge", params, Y).fit(train.loc[yr < v, X], train.loc[yr < v, Y]).predict(train.loc[yr == v, X])
                     for v in VAL_YEARS])
    q = {t: {f"q{int(p * 100):02d}": float(np.nanquantile(res[:, k], p)) for p in (0.05, 0.10, 0.50, 0.90, 0.95)}
         for k, t in enumerate(Y)}

    pa = pd.read_csv(DEST / "test_per_asset.csv")
    pa = pa[pa.model == "ridge"].set_index("target")
    test = summ["test"]
    art = {
        "model_id": MODEL_ID, "kind": "forecast_trailing", "supports_hypothetical_shocks": False,
        "status": "no_demonstrated_skill",
        "interpretation": ("Forecast of the next 5 NSE sessions from information known at the prediction time. With the "
                           f"selected penalty (alpha={params['alpha']}) the coefficients are ~0, so it effectively predicts "
                           "each asset's 2016-2022 average weekly return."),
        "unsupported_reason": ("Inputs are trailing 5-session moves; a hypothetical shock can only be read as 'the shock "
                               "already happened last week', which excludes the immediate reaction. The model also shows no "
                               "skill: its test MAE is not distinguishable from the zero-return baseline."),
        "horizon_trading_days": 5,
        "features": [{"column": c} for c in X], "feature_order": X, "targets": _targets(Y),
        "estimator": {"library": "scikit-learn", "class": "Ridge (one per target, shared alpha)", "alpha": params["alpha"],
                      "preprocessing": "StandardScaler fitted on train rows (population SD)"},
        "standardization": {"mean": mu.tolist(), "sd": sd.tolist(), "fitted_on": "train partition only (308 rows)"},
        "coefficients": {"intercept": b.tolist(), "weights_per_standardized_feature": W.tolist()},
        "feature_domain": {c: {"min": float(train[c].min()), "p01": float(train[c].quantile(0.01)),
                               "p99": float(train[c].quantile(0.99)), "max": float(train[c].max())} for c in X},
        "n_rows_used_per_target": [int(train[t].notna().sum()) for t in Y],
        "training": {"rows": int(len(train)), "period": f"{train.week_start.min()}..{train.week_end.max()}",
                     "selection": "expanding-window validation on 2019-2022 (train partition only)",
                     "validation": summ["validation"]},
        "evaluation": {
            "test_partition": {"rows": int((df.split == "test").sum()), "period": f"{df[df.split == 'test'].week_start.min()}.."
                                                                         f"{df[df.split == 'test'].week_end.max()}",
                               "evaluated_once": True, "contains_black_swan_rows": False},
            "test": test,
            "per_target": {t: {"n_oos": int(pa.loc[t, "n"]), "mae_model": round(float(pa.loc[t, "mae"]), 4),
                               "mae_zero_baseline": round(float(pa.loc[t, "zero_mae"]), 4),
                               "directional_accuracy": round(float(pa.loc[t, "directional_accuracy"]), 4),
                               "beats_zero_baseline": bool(pa.loc[t, "beats_zero"]), "oos_r2": None} for t in Y},
            "episode_holdout": summ["episode_holdout"],
        },
        "prediction_intervals": {"method": "empirical residual quantiles from train-only validation folds",
                                 "residual_quantiles": q},
        "limitations": [
            "No skill demonstrated: test MAE difference vs zero baseline has a 95% block-bootstrap CI that includes 0.",
            "Test partition (2023-2026) contains no BLACK_SWAN weeks; crisis generalisation is not demonstrated.",
            "Leave-one-event-group-out: worse than the zero baseline on both Black Swan groups (only 2 independent groups).",
            "Features must all be present (no imputation in the artifact).",
        ],
        "provenance": {"exported_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "source_dataset": "research/black_swan/output/model_training_final.csv", "source_dataset_sha256": sha,
                       "selection_summary": "research/black_swan/output/model_selection/model_selection_summary.json",
                       "exporter": "research/black_swan/pipeline/export_forecast_v2.py", "environment": summ["environment"]},
        "model_version": f"{MODEL_ID}+{sha[:12]}",
    }
    path = MODELS / f"{MODEL_ID}.json"
    path.write_text(json.dumps(art, indent=1), encoding="utf-8")
    return path


if __name__ == "__main__":
    print("wrote", main())
